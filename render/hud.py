"""The HUD: turning handed state into lines of text. No pygame, no game logic.

Kept pygame-free and pure so the thing that decides *what the watcher is told*
can be tested headlessly, which is most of the value: a HUD that says the wrong
number is worse than no HUD, and that is a content bug rather than a drawing
one.

Everything here reads state it is handed. It never reaches into the world -
the numbers it shows about the agent are the agent's own, including the ones
the agent is wrong about.
"""

Line = tuple[str, tuple[int, int, int]]


def _bar(value: int, maximum: int, width: int = 12) -> str:
    """A crude text meter: [####----]."""
    if maximum <= 0:
        return "[" + "-" * width + "]"
    filled = max(0, min(width, round(width * value / maximum)))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def health_color(value: int, maximum: int, config) -> tuple[int, int, int]:
    """Green when healthy, amber when hurt, red when in trouble."""
    if maximum <= 0:
        return config.hud_bad_color
    fraction = value / maximum
    if fraction > 0.6:
        return config.hud_good_color
    if fraction > 0.3:
        return config.hud_warn_color
    return config.hud_bad_color


def hud_lines(agent, world_size: int, config, speed: int = 1, paused: bool = False) -> list[Line]:
    """Build the HUD as (text, colour) lines, top to bottom."""
    stats = agent.stats
    derived = agent.derived
    if stats is None or derived is None:
        return [("booting", config.hud_color)]

    from agent.loadout import archetype

    lines: list[Line] = []
    lines.append(
        (
            f"hp {stats.hp:3}/{derived.max_hp:<3} {_bar(stats.hp, derived.max_hp)}",
            health_color(stats.hp, derived.max_hp, config),
        )
    )
    lines.append(
        (
            f"lvl {stats.level:<2} xp {stats.xp:<4} atk {derived.attack:<3} def {derived.defense:<3}",
            config.hud_color,
        )
    )
    lines.append((f"build  {archetype(derived, config)}", config.hud_accent_color))
    lines.append((f"goal   {agent.goal_name}", _goal_color(agent.goal_name, config)))
    lines.append(("", config.hud_color))
    lines.append(
        (
            f"kills {agent.kills:<4} deaths {agent.deaths:<3}",
            config.hud_color,
        )
    )
    lines.append(
        (
            f"gold  {agent.gold:<4} potions {agent.potions:<3}",
            config.hud_color,
        )
    )
    lines.append(
        (
            f"traps {agent.traps_found:<4} sprung {agent.traps_sprung:<3}",
            config.hud_color,
        )
    )
    lines.append(("", config.hud_color))
    lines.append((f"sight  {derived.fov_radius}   recall {derived.memory_ttl}", config.hud_color))
    lines.append((f"nerve  {derived.flee_threat:.2f}  wander {derived.w_explore:.2f}", config.hud_color))
    lines.append(("", config.hud_color))
    lines.append((f"tick   {agent.tick_count}", config.hud_color))
    lines.append((f"known  {len(agent.memory)} tiles", config.hud_color))
    lines.append((f"chunks {world_size}", config.hud_color))
    lines.append((f"near   {len(agent.active_entities)} awake", config.hud_color))
    speed_text = "PAUSED" if paused else f"{speed}x"
    lines.append((f"speed  {speed_text}", config.hud_accent_color))
    return lines


def _goal_color(goal: str, config) -> tuple[int, int, int]:
    return {
        "FLEE": config.hud_bad_color,
        "LOOT": config.hud_accent_color,
    }.get(goal, config.hud_good_color)


def equipment_lines(agent, config) -> list[Line]:
    """What the agent is wearing, one line per slot."""
    from agent.loadout import EQUIP_SLOTS

    lines: list[Line] = [("worn", config.hud_accent_color)]
    for slot in EQUIP_SLOTS:
        item = agent.equipped.get(slot)
        if item is None:
            lines.append((f" {slot:<7} -", config.hud_dim_color))
        else:
            colour = config.hud_bad_color if item.cursed else config.hud_color
            lines.append((f" {slot:<7} {item.name}", colour))
    if agent.backpack:
        lines.append((f" bag     {len(agent.backpack)} spare", config.hud_dim_color))
    return lines


def help_lines(config) -> list[Line]:
    """The key map, shown when nothing else is competing for the corner."""
    return [
        ("space pause   1/2/3 speed", config.hud_dim_color),
        ("F1 fov  F2 age  F3 threat", config.hud_dim_color),
        ("F4 plan F5 frontier", config.hud_dim_color),
        ("n new world   p screenshot", config.hud_dim_color),
    ]
