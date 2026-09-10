"""Names for the things that live and die down there.

Built from syllable parts rather than a list of finished names, because a list
runs out and starts repeating. An onset, a vowel and a coda make a syllable;
two or three syllables make a name; a surname or a byname is bolted on after.

The parts come in *styles*, and that is the whole trick. One pile of syllables
produces one flavour of name however many you draw, so each style carries its
own consonants, vowels, endings and surname vocabulary: the sylvan set is soft
and vowel-heavy, the hold set is blunt and Norse-ish, the wretched set is all
back-of-the-throat. Thalinel Moonweaver and Brokk Ironfoot cannot come out of
the same bag.

Pronounceable is a rule, not luck. Segments that are individually fine still
meet badly - an early draft of this offered Feashshandziosheth - so a name has
to get past `_sayable` before it is handed out: no three consonants in a row,
no three vowels, no repeated block, and a length someone would actually read.
Anything that fails is redrawn rather than patched up, which is easier to get
right than making every seam rule airtight.

Nothing here touches the world or the agent. It takes a `Random` and returns a
string, so a test can hand it a seeded one and get the same name forever.
"""

import random
from dataclasses import dataclass

VOWEL_LETTERS = frozenset("aeiouy")
CONSONANTS = frozenset("bcdfghjklmnpqrstvwxz")

MIN_LENGTH = 4
MAX_LENGTH = 12


@dataclass(frozen=True)
class Style:
    """One people's worth of name parts.

    `onsets` may contain clusters and the empty string; `simple` is the subset
    safe to use straight after a consonant, so a coda and the next onset never
    pile into something unsayable. `titles` are used as "the Scarred"; `heads`
    and `tails` compound into a surname.
    """

    key: str
    onsets: tuple[str, ...]
    simple: tuple[str, ...]
    vowels: tuple[str, ...]
    codas: tuple[str, ...]
    endings: tuple[str, ...]
    heads: tuple[str, ...]
    tails: tuple[str, ...]
    titles: tuple[str, ...]
    surname_chance: float = 0.45
    title_chance: float = 0.3


SYLVAN = Style(
    key="sylvan",
    # Soft and liquid: l, r, th, v, n, s and no hard stops to speak of.
    onsets=("l", "ll", "n", "r", "s", "sh", "th", "v", "f", "m", "el", "il",
            "ae", "y", "", "", ""),
    simple=("l", "n", "r", "s", "th", "v", "m", "f"),
    vowels=("a", "e", "i", "o", "ae", "ai", "ia", "ie", "io", "y", "ea", "ei"),
    codas=("", "", "", "", "l", "n", "r", "s", "th"),
    endings=("iel", "ael", "wyn", "aril", "ith", "ien", "las", "riel", "eth",
             "ian", "yr", "ell", "anor", "amir", "essa", "ora"),
    heads=("Moon", "Star", "Silver", "Dawn", "Dusk", "Leaf", "Rain", "Mist",
           "Willow", "Amber", "Thistle", "Ivy", "Song", "Feather"),
    tails=("whisper", "weaver", "leaf", "song", "wind", "shade", "bloom",
           "brook", "light", "fall", "glade", "wing"),
    titles=("Fair", "Quiet", "Wandering", "Sleepless", "Patient", "Green-Eyed",
            "Far-Walking"),
    surname_chance=0.55,
)

HOLD = Style(
    key="hold",
    # Blunt, Norse-ish, front-loaded consonants and short vowels.
    onsets=("b", "br", "d", "dr", "g", "gr", "h", "k", "kr", "n", "r", "t",
            "th", "v", "f", "m", "sk", "st"),
    simple=("b", "d", "g", "k", "n", "r", "t", "th", "m", "f", "v"),
    vowels=("a", "a", "o", "o", "u", "u", "i", "e", "ei", "au"),
    codas=("", "", "l", "n", "r", "m", "rn", "rk", "ld", "lm", "st", "gg",
           "kk", "nn", "rr"),
    endings=("in", "ur", "ar", "i", "orn", "ok", "grim", "din", "rik", "vald",
             "mund", "gar", "nar", "bek", "dur"),
    heads=("Iron", "Stone", "Axe", "Anvil", "Coal", "Deep", "Forge", "Granite",
           "Hammer", "Ore", "Oath", "Copper", "Flint", "Brass"),
    tails=("forge", "hammer", "bearer", "foot", "beard", "hand", "hewer",
           "delver", "shield", "breaker", "mantle", "helm"),
    titles=("Unmoved", "Stubborn", "Twice-Buried", "Grim", "Stout", "Sour",
            "Deep-Delved"),
    surname_chance=0.6,
)

COMMON = Style(
    key="common",
    # Plain medieval, the sort of name a person writes on a ledger.
    onsets=("b", "br", "c", "cr", "d", "g", "h", "j", "l", "m", "n", "p", "r",
            "s", "t", "th", "w", "f", "gr", "st", "", ""),
    simple=("b", "c", "d", "g", "h", "l", "m", "n", "p", "r", "s", "t", "w"),
    vowels=("a", "e", "e", "i", "o", "u", "ai", "ea", "ou"),
    codas=("", "", "", "l", "n", "r", "s", "d", "m", "ld", "rd", "st", "lm"),
    endings=("ric", "eth", "an", "en", "win", "mund", "ard", "bert", "ric",
             "wold", "iel", "is", "on", "a", "wen", "gar"),
    heads=("Stone", "Raven", "Oak", "Ash", "Mill", "Hart", "Marsh", "Bridge",
           "Wold", "Fletch", "Crow", "Tanner", "Barrow", "Holt"),
    tails=("bridge", "field", "ford", "wood", "hill", "gate", "moor", "well",
           "brook", "mark", "row", "combe"),
    titles=("Bold", "Unlucky", "Careful", "Late", "Curious", "Restless",
            "Nameless", "Small"),
)

WRETCHED = Style(
    key="wretched",
    # Back of the throat, and it does not get a surname so much as a reputation.
    onsets=("g", "gr", "k", "kr", "z", "zg", "n", "sn", "th", "dr", "b", "br",
            "m", "v", "gh", "kh"),
    simple=("g", "k", "z", "n", "b", "m", "r", "th", "d"),
    vowels=("a", "a", "u", "u", "o", "i", "au", "ou"),
    codas=("", "", "g", "k", "z", "sh", "rg", "rk", "gh", "zh", "nk", "mp"),
    endings=("ak", "uk", "og", "nak", "gash", "rok", "zul", "muk", "dug",
             "grish", "nak", "azh", "urk"),
    heads=("Bone", "Skull", "Gut", "Blood", "Rot", "Scar", "Iron", "Mud",
           "Ash", "Grave", "Tooth", "Sinew"),
    tails=("crusher", "gnawer", "render", "splitter", "eater", "breaker",
           "hauler", "biter", "dragger"),
    titles=("Scarred", "Fierce", "Unkilled", "Hungry", "Twice-Hanged",
            "Loud", "Left-Handed", "Rotten"),
    surname_chance=0.3,
    title_chance=0.5,
)

ARCANE = Style(
    key="arcane",
    # Sibilant and strange: the names things down there give themselves.
    onsets=("v", "vh", "z", "zh", "x", "s", "sv", "th", "thr", "kh", "qu", "y",
            "n", "l", "ph", "", ""),
    simple=("v", "z", "s", "th", "n", "l", "k", "r", "m"),
    vowels=("a", "e", "i", "o", "u", "y", "ae", "ei", "oa", "ua", "yi"),
    codas=("", "", "", "l", "n", "r", "s", "x", "th", "ss", "nx", "rz"),
    endings=("ith", "yx", "ael", "oth", "ys", "ax", "uun", "iel", "eth", "ora",
             "yr", "ish", "aal", "een"),
    heads=("Cinder", "Ember", "Hollow", "Lantern", "Salt", "Sorrow", "Tallow",
           "Vault", "Wick", "Gloom", "Frost", "Thorn"),
    tails=("bane", "mantle", "wander", "keep", "watch", "rest", "shadow",
           "wake", "march", "hollow"),
    titles=("Unfinished", "Forgetful", "Hollow", "Pale", "Doomed", "Thrice-Buried",
            "Undeterred", "Quiet"),
)

STYLES = (SYLVAN, HOLD, COMMON, WRETCHED, ARCANE)
BY_KEY = {style.key: style for style in STYLES}


def _syllable(rng: random.Random, style: Style, after: str) -> str:
    """One syllable that can be said after whatever `after` ended with."""
    closed = bool(after) and after[-1] in CONSONANTS
    onset = rng.choice(style.simple if closed else style.onsets)
    if not onset and after and after[-1] in VOWEL_LETTERS:
        # Two vowels meeting across a seam turn into a puddle, so give this
        # syllable something to open with.
        onset = rng.choice(style.simple)
    return onset + rng.choice(style.vowels) + rng.choice(style.codas)


def _ending(rng: random.Random, style: Style, after: str) -> str:
    """The last piece, chosen so it sounds like the end of a word."""
    ending = rng.choice(style.endings)
    if after and after[-1] in VOWEL_LETTERS and ending[0] in VOWEL_LETTERS:
        return rng.choice(style.simple) + ending
    return ending


def _runs_of(word: str, letters: frozenset, length: int) -> bool:
    """Whether `word` has that many of those letters in a row, anywhere."""
    run = 0
    for letter in word:
        run = run + 1 if letter in letters else 0
        if run >= length:
            return True
    return False


def _sayable(word: str) -> bool:
    """Whether a generated word is a name or a noise."""
    if not MIN_LENGTH <= len(word) <= MAX_LENGTH:
        return False
    if _runs_of(word, CONSONANTS, 3) or _runs_of(word, VOWEL_LETTERS, 3):
        return False
    for size in (2, 3):
        # "shsh", "arar": a repeated block reads as a stutter, not a name.
        for at in range(len(word) - size * 2 + 1):
            if word[at : at + size] == word[at + size : at + size * 2]:
                return False
    return True


def _compose(rng: random.Random, style: Style) -> str:
    """Syllables and then an ending; two or three pieces in total."""
    word = ""
    for _ in range(rng.choice((1, 1, 2))):
        word += _syllable(rng, style, word)
    return word + _ending(rng, style, word)


def given_name(rng: random.Random, style: Style | None = None) -> str:
    """A first name in that style, capitalised."""
    style = style or rng.choice(STYLES)
    word = ""
    for _ in range(30):
        word = _compose(rng, style)
        if _sayable(word):
            break
    return word.capitalize()


def epithet(rng: random.Random, style: Style) -> str:
    """A compound surname, a byname, or nothing at all."""
    roll = rng.random()
    if roll < style.surname_chance:
        head = rng.choice(style.heads)
        tail = rng.choice(style.tails)
        if tail == head.lower():
            # Hammerhammer, Ironiron: the two columns overlap in places.
            tail = rng.choice([other for other in style.tails if other != tail])
        return f"{head}{tail}"
    if roll < style.surname_chance + style.title_chance:
        return f"the {rng.choice(style.titles)}"
    return ""


def full_name(rng: random.Random, style: Style | None = None) -> str:
    """A whole name: "Thalinel Moonweaver", "Brokk the Stubborn", "Grazuk"."""
    style = style or rng.choice(STYLES)
    name = given_name(rng, style)
    extra = epithet(rng, style)
    return f"{name} {extra}" if extra else name


def name_for(seed: int, life: int = 0) -> str:
    """The name the creature of `life` on world `seed` was born with.

    Deterministic and drawn from its own stream, so naming a creature cannot
    shift a single tile of terrain or a single loot roll - the same rule every
    other generator in here follows.
    """
    return full_name(random.Random((seed * 1_000_003) ^ (life * 97 + 17)))
