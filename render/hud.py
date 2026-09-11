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


def fit(text: str, limit: int) -> str:
    """Clip a line to the panel, marking that something was cut.

    Gear names are the reason: "sickly farsighted vampiric ring" is longer than
    the panel is wide, and an item name that runs off the screen tells the
    watcher less than one that admits it was trimmed.
    """
    if limit <= 1 or len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


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


def hud_lines(
    agent,
    world_size: int,
    config,
    speed: int = 1,
    paused: bool = False,
    biome: tuple[str, str] | None = None,
    boss: tuple | None = None,
) -> list[Line]:
    """Build the HUD as (text, colour) lines, top to bottom, clipped to fit.

    `biome` is the (key, label) of the ground under the agent, handed in
    rather than looked up: this module is given state and does not go asking
    the world for any.
    """
    stats = agent.stats
    derived = agent.derived
    if stats is None or derived is None:
        return [("booting", config.hud_color)]

    from agent.loadout import archetype

    lines: list[Line] = []
    if boss is not None:
        lines.extend(boss_lines(boss, config))
        lines.append(("", config.hud_color))
    if agent.name:
        lines.append((agent.name, config.hud_accent_color))
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
    if biome is not None:
        key, label = biome
        lines.append((f"biome  {label}", _biome_color(key, config)))
    lines.extend(effect_lines(agent, config))
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
    # Clip at the end rather than per line: a build label can name four
    # synergies and run off the panel just as easily as an item name can.
    return [(fit(text, config.hud_max_chars), colour) for text, colour in lines]


_BIOME_LABEL_FLOOR = 190  # dimmest a label's strongest channel may be


def boss_lines(boss: tuple, config) -> list[Line]:
    """Name and health for whatever named thing is on screen.

    Given its own bar rather than a line of numbers because the point of a
    boss is that the watcher can see how the fight is going from across the
    room, the same way they can see the creature's own health.
    """
    name, hp, full = boss
    share = hp / max(1, full)
    colour = (
        config.hud_bad_color
        if share <= 0.34
        else config.hud_warn_color
        if share <= 0.67
        else config.hud_accent_color
    )
    return [
        (fit(name, config.hud_max_chars), config.hud_accent_color),
        (f"{_bar(hp, full)} {hp}/{full}", colour),
    ]


def effect_lines(agent, config) -> list[Line]:
    """What is currently true of the creature that will not be true for long.

    Blessings read good and curses read bad, because the whole point of a
    totem is that you can tell from across the room which one it gave you.
    The countdown is there so a watcher can see it running out.
    """
    from sim.effects import describe

    running = describe(getattr(agent, "effects", {}) or {})
    if not running:
        return []
    lines: list[Line] = []
    for label, blessing, left in running:
        colour = config.hud_good_color if blessing else config.hud_bad_color
        lines.append((f" {label:<11} {left // 10:>4}", colour))
    return lines


def _biome_color(key: str, config) -> tuple[int, int, int]:
    """The biome's own hue, lifted until it reads as text.

    Wall colour is the most characteristic thing a biome has - it is what the
    place looks like from across the room. Straight off the palette it is far
    too dark for a panel, though, since it was chosen to sit behind lit
    glyphs. So the hue is kept and the brightness is not: scale until the
    strongest channel is bright enough to read, which lifts a dim biome a long
    way and leaves an already-bright one alone.
    """
    table = config.biome_colors.get(key) or config.biome_colors.get("halls", {})
    colour = table.get("#", config.hud_accent_color)
    brightest = max(colour) or 1
    if brightest >= _BIOME_LABEL_FLOOR:
        return colour
    lift = _BIOME_LABEL_FLOOR / brightest
    return tuple(min(255, round(channel * lift)) for channel in colour)


def _goal_color(goal: str, config) -> tuple[int, int, int]:
    return {
        "FLEE": config.hud_bad_color,
        "LOOT": config.hud_accent_color,
    }.get(goal, config.hud_good_color)


def wrap(text: str, limit: int, max_lines: int = 2) -> list[str]:
    """Break text on word boundaries into at most `max_lines` lines.

    Gear names are why: a legendary can be "sickly farsighted vampiric ring",
    which is longer than the panel is wide. Clipping it hides the very affixes
    that make the item interesting, so the name gets a second line instead. Any
    overflow past `max_lines` is still clipped - a name is worth two lines, not
    the whole panel.

    Wraps the text alone and leaves indenting to the caller, so a label column
    stays a column instead of being swallowed by the word splitting.
    """
    words = text.split()
    if not words or limit <= 0:
        return [text]
    lines: list[str] = []
    current = ""
    dropped = False
    for index, word in enumerate(words):
        candidate = f"{current} {word}" if current else word
        if len(candidate) <= limit or not current:
            current = candidate
            continue
        if len(lines) + 1 == max_lines:
            dropped = index < len(words)
            break
        lines.append(current)
        current = word
    if len(lines) < max_lines and current:
        lines.append(current)
    out = [fit(line, limit) for line in lines[:max_lines]]
    if dropped and out:
        # Ran out of lines with words still to place. Mark it, so a name that
        # was cut short does not read as the whole name.
        out[-1] = fit(out[-1] + " …", limit)
    return out


def equipment_lines(agent, config) -> list[Line]:
    """What the agent is wearing, wrapped onto a second line when it will not fit."""
    from agent.loadout import EQUIP_SLOTS

    lines: list[Line] = [("worn", config.hud_accent_color)]
    for slot in EQUIP_SLOTS:
        item = agent.equipped.get(slot)
        if item is None:
            lines.append((f" {slot:<7} -", config.hud_dim_color))
            continue
        colour = config.hud_bad_color if item.cursed else config.hud_color
        label = f" {slot:<7} "
        wrapped = wrap(item.name, config.hud_max_chars - len(label))
        lines.append((label + wrapped[0], colour))
        # Continuations line up under the name, so the slot column survives.
        lines.extend((" " * len(label) + line, colour) for line in wrapped[1:])
    if agent.backpack:
        lines.append((f" bag     {len(agent.backpack)} spare", config.hud_dim_color))
    return lines


RARITY_TINT = {
    "common": "hud_dim_color",
    "uncommon": "hud_good_color",
    "rare": "hud_color",
    "epic": "hud_accent_color",
    "legendary": "menu_pick_color",
}


def rarity_color(rarity: str, config):
    """Better loot reads brighter, so a legendary is obvious in a list."""
    return getattr(config, RARITY_TINT.get(rarity, "hud_color"), config.hud_color)


def bag_lines(agent, config) -> list[Line]:
    """What the agent is carrying but not wearing.

    The HUD only ever said "6 spare", which is the least interesting true thing
    that could be said about a bag full of cursed rings. Each spare is shown
    with what it would add or take away if it were worn, because that is the
    question a watcher actually has: why is it carrying that and not using it?
    """
    if not agent.backpack:
        return [("bag  empty", config.hud_dim_color)]

    lines: list[Line] = [(f"bag  {len(agent.backpack)} spare", config.hud_accent_color)]
    for item in agent.backpack:
        worn = agent.equipped.get(item.kind.slot)
        delta = ""
        if worn is not None:
            attack = item.attack - worn.attack
            defense = item.defense - worn.defense
            parts = []
            if attack:
                parts.append(f"{attack:+d} atk")
            if defense:
                parts.append(f"{defense:+d} def")
            delta = "  " + " ".join(parts) if parts else "  sidegrade"
        else:
            delta = "  slot empty"
        for index, text in enumerate(
            wrap(f"{item.kind.glyph} {item.name}{delta}", config.hud_max_chars - 1)
        ):
            lines.append((" " + text if index == 0 else "   " + text, rarity_color(item.rarity, config)))
    return lines


def help_lines(config) -> list[Line]:
    """The key map, shown when nothing else is competing for the corner."""
    return [
        ("space pause   1/2/3 speed", config.hud_dim_color),
        ("F1 fov  F2 age  F3 threat", config.hud_dim_color),
        ("F4 plan F5 frontier", config.hud_dim_color),
        ("n new world   p screenshot", config.hud_dim_color),
        ("b bag   j symbols", config.hud_dim_color),
        ("F10/F11 window   esc menu", config.hud_dim_color),
    ]


def chronicle_lines(agent, config) -> list[Line]:
    """The recent past, oldest first, as the watcher should read it."""
    entries = agent.log.recent(config.chronicle_length)
    if not entries:
        return []
    lines: list[Line] = [("recently", config.hud_accent_color)]
    for tick_at, text in entries:
        lines.append(
            (fit(f" {tick_at:>6}  {text}", config.hud_max_chars), config.hud_dim_color)
        )
    return lines
