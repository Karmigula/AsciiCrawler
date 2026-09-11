"""Pricing a set of gear, and finding the best set the agent could wear.

Three things live here:

- `derive` folds equipped items into one bundle of effective numbers: body
  stats, cognition parameters, and summed trigger amounts. Nothing else in the
  codebase is allowed to guess at an item's contribution; if it is not folded
  here it does not exist.
- `score` prices that bundle. The weights are the agent's *taste*, and a
  synergy table means the whole can be worth more than the sum of its parts:
  an axe and a vampiric charm are worth more together than apart, because
  killing quickly and healing on kills feed each other.
- `best_assignment` brute-forces the slot assignment over the items the agent
  owns. Slots would be independent if not for synergies, which is exactly why
  a greedy per-slot pick is not good enough and the search has to consider
  combinations.

The synergy table is also what lets a cursed item win: an item that costs 3
defense can still be the right choice if it completes a pairing worth more.
That is the decision the whole loot system exists to produce.
"""

from dataclasses import dataclass, field, replace
from itertools import product

from config import Config
from sim import effects as effects_module
from sim.affixes import COGNITION_FIELDS

Slot = str

EQUIP_SLOTS: tuple[Slot, ...] = ("weapon", "armor", "ring", "amulet")


@dataclass(frozen=True)
class Derived:
    """Everything an equipped set adds up to."""

    attack: int
    defense: int
    max_hp: int
    fov_radius: int
    memory_ttl: int
    flee_threat: float
    w_explore: float
    threat_radius: int
    triggers: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Synergy:
    """A pairing worth more than its parts.

    `requires` is a list of (derived field or trigger name, threshold); when
    every one is met the bonus applies. Kept as data so the table can be read,
    tested and tuned without touching the evaluator.
    """

    key: str
    label: str
    requires: tuple[tuple[str, float], ...]
    bonus: float


SYNERGIES: tuple[Synergy, ...] = (
    # Kill fast and heal on kills: each makes the other better.
    Synergy("bloodletter", "bloodletter", (("attack", 9), ("on_kill_heal", 1)), 4.0),
    # Standing and punishing blows only pays if you can take them.
    Synergy("bulwark", "bulwark", (("defense", 6), ("on_hit_taken_reflect", 1)), 4.0),
    # Seeing far is worth more to something that wants to see new things.
    Synergy("scout", "scout", (("fov_radius", 11), ("w_explore", 1.4)), 3.5),
    Synergy("stalker", "stalker", (("threat_radius", 13), ("attack", 8)), 2.5),
)


def derive(stats, equipped: dict, config: Config, effects=()) -> Derived:
    """Fold base stats, equipment and any running effects into real numbers.

    Effects land last and can push a number below what the gear gave, because
    that is what a curse is. They go through the same funnel as everything
    else so the brain plans on them: a dimmed creature searches with the sight
    it has, and a dreadful one flees sooner, without either of them knowing
    why.
    """
    attack = stats.attack
    defense = stats.defense
    max_hp = stats.max_hp
    cognition = {
        "fov_radius": float(config.fov_radius),
        "memory_ttl": float(config.memory_ttl),
        "flee_threat": float(config.flee_threat),
        "w_explore": float(config.w_explore),
        "threat_radius": float(config.threat_radius),
    }
    triggers: dict = {}
    for item in equipped.values():
        if item is None:
            continue
        for affix in item.affixes:
            if affix.category == "trigger":
                triggers[affix.field] = triggers.get(affix.field, 0.0) + affix.amount
            elif affix.field in COGNITION_FIELDS:
                cognition[affix.field] += affix.amount
            elif affix.field == "attack":
                attack += int(affix.amount)
            elif affix.field == "defense":
                defense += int(affix.amount)
            elif affix.field == "max_hp":
                max_hp += int(affix.amount)
        attack += item.kind.attack
        defense += item.kind.defense

    if effects:
        running = effects_module.modifiers(effects)
        attack += running["attack"]
        defense += running["defense"]
        max_hp += running["max_hp"]
        cognition["fov_radius"] += running["fov_radius"]
        cognition["flee_threat"] += running["flee_threat"]
        cognition["w_explore"] += running["w_explore"]

    return Derived(
        attack=attack,
        defense=defense,
        max_hp=max(1, max_hp),
        fov_radius=max(1, int(round(cognition["fov_radius"]))),
        memory_ttl=max(1, int(round(cognition["memory_ttl"]))),
        flee_threat=max(0.0, cognition["flee_threat"]),
        w_explore=max(0.0, cognition["w_explore"]),
        threat_radius=max(1, int(round(cognition["threat_radius"]))),
        triggers=triggers,
    )


def _reading(derived: Derived, name: str) -> float:
    """Look a synergy requirement up in either the stats or the triggers."""
    if hasattr(derived, name):
        return float(getattr(derived, name))
    return float(derived.triggers.get(name, 0.0))


def active_synergies(derived: Derived) -> tuple[Synergy, ...]:
    """Every synergy whose requirements the loadout currently meets."""
    return tuple(
        synergy
        for synergy in SYNERGIES
        if all(
            _reading(derived, name) >= threshold for name, threshold in synergy.requires
        )
    )


def score(derived: Derived, config: Config) -> float:
    """What this loadout is worth to the agent, taste and synergies included."""
    total = (
        config.v_attack * derived.attack
        + config.v_defense * derived.defense
        + config.v_max_hp * derived.max_hp
        + config.v_fov * derived.fov_radius
        + config.v_memory * derived.memory_ttl
        + config.v_explore * derived.w_explore
        + config.v_trigger * sum(derived.triggers.values())
    )
    # Recklessness is priced rather than free: a lower flee threshold buys a
    # longer life, so an item that makes the agent bold has to earn it.
    total -= config.v_flee_penalty * derived.flee_threat
    total += sum(synergy.bonus for synergy in active_synergies(derived))
    return total


def best_assignment(stats, items, config: Config, cap: int = 4) -> dict:
    """Brute-force the best slot assignment over `items`.

    Candidates per slot are capped by solo score before the combinations are
    built, so the search stays small (cap ** 4) while still being a genuine
    joint search, which greedy per-slot picking is not: synergies couple the
    slots, so the best ring depends on what is in the other three.
    """
    by_slot: dict = {slot: [None] for slot in EQUIP_SLOTS}
    for item in items:
        slot = item.kind.slot
        if slot in by_slot:
            by_slot[slot].append(item)

    def solo(slot, item):
        if item is None:
            return float("inf")  # keep the empty option, sort it last
        return -score(derive(stats, {slot: item}, config), config)

    for slot, options in by_slot.items():
        options.sort(key=lambda item: solo(slot, item))
        del options[cap + 1 :]
        if None not in options:
            options.append(None)
    best: dict = {}
    best_score = float("-inf")
    for combination in product(*(by_slot[slot] for slot in EQUIP_SLOTS)):
        equipped = {
            slot: item for slot, item in zip(EQUIP_SLOTS, combination) if item is not None
        }
        value = score(derive(stats, equipped, config), config)
        if value > best_score:
            best, best_score = equipped, value
    return best


def effective_config(config: Config, derived: Derived) -> Config:
    """A Config the brain can use directly, with cognition affixes folded in.

    Returning a Config rather than a bag of overrides means every consumer -
    FOV, memory decay, EXPLORE scoring, FLEE - keeps reading exactly one thing,
    so gear that changes the mind cannot be forgotten at some call site.
    """
    return replace(
        config,
        fov_radius=derived.fov_radius,
        memory_ttl=derived.memory_ttl,
        flee_threat=derived.flee_threat,
        w_explore=derived.w_explore,
        threat_radius=derived.threat_radius,
    )


def archetype(derived: Derived, config: Config) -> str:
    """A cosmetic label for what this build has become.

    Synergies name themselves; failing that, the biggest weighted contribution
    does. Purely for the HUD - nothing reads this back.
    """
    active = active_synergies(derived)
    if active:
        return "/".join(synergy.label for synergy in active)
    leanings = {
        "brute": config.v_attack * derived.attack,
        "turtle": config.v_defense * derived.defense,
        "scout": config.v_fov * derived.fov_radius,
        "wanderer": config.v_explore * derived.w_explore,
    }
    return max(leanings, key=leanings.get)
