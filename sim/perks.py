"""Perk triggers: the sim events an affix can hook, and what happens when it does.

The event names are fixed and small on purpose - `kill`, `hit_taken`,
`hit_dealt`, `step`, `equip`. Anything an affix wants to react to has to be one
of these, which keeps the dispatch honest: there is one place to look for what
a trigger can possibly do, and adding a new hook is a deliberate act rather
than a call sprinkled somewhere in the tick.

`step` and `equip` carry no affixes yet. They are here because the loadout
recalc and the movement path are the two obvious places a future affix will
want to reach, and leaving the seam visible is cheaper than retrofitting it.

Triggers read their totals from `Derived.triggers`, which is the only place
item contributions are folded (see agent/loadout.py). A trigger that is not in
that dict simply does not fire.
"""

KILL = "kill"
HIT_TAKEN = "hit_taken"
HIT_DEALT = "hit_dealt"
STEP = "step"
EQUIP = "equip"

EVENTS: tuple[str, ...] = (KILL, HIT_TAKEN, HIT_DEALT, STEP, EQUIP)


def on_kill(derived, stats, config) -> dict:
    """Fired when the agent kills something. Returns what the perks did.

    Healing is capped at the effective maximum: a vampiric weapon keeps the
    agent alive during a long fight, it does not inflate it past its ceiling.
    """
    result = {"healed": 0, "bonus_xp": 0}
    heal = int(derived.triggers.get("on_kill_heal", 0))
    if heal > 0 and stats.hp < derived.max_hp:
        before = stats.hp
        stats.hp = min(derived.max_hp, stats.hp + heal)
        result["healed"] = stats.hp - before
    bonus = int(derived.triggers.get("on_kill_xp", 0))
    if bonus > 0:
        stats.gain_xp(bonus, config, ceiling=derived.max_hp)
        result["bonus_xp"] = bonus
    return result


def on_hit_taken(derived, attacker, damage: int) -> dict:
    """Fired when something wounds the agent. Returns what the perks did.

    Reflected damage can kill: a thorned set means a rat that keeps biting
    eventually kills itself, which is the behaviour that makes the affix worth
    wearing rather than a rounding error.
    """
    result = {"reflected": 0}
    reflect = int(derived.triggers.get("on_hit_taken_reflect", 0))
    if reflect > 0 and attacker is not None and damage > 0:
        attacker.hp -= reflect
        result["reflected"] = reflect
    return result
