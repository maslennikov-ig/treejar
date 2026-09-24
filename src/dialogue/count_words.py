"""One shared vocabulary for spelled-out counts, in English and Arabic.

Head counts and quantities used to be read by several private word lists that
stopped at ten or twelve, so "a team of fifteen" or "twenty people" slipped
through as ordinary words. Every reader of a spelled-out count goes through
this module instead:

- `parse_count_word` turns a word or phrase ("twenty-five", "a dozen",
  "خمسة وعشرون") into an int;
- `COUNT_WORD_PATTERN` is a regex alternation (longest forms first) for
  embedding in a caller's own pattern; it carries no groups or boundaries;
- `head_count` reads a head count ("12 people", "a team of six",
  "لخمسة موظفين", "فريق من عشرة أشخاص"), and `strip_head_counts` removes
  such phrases from a text.

Callers keep their own caps and semantics (an option ordinal still stops at
ten); this module only knows what the words mean.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable

__all__ = [
    "AR_COUNT_WORD_PATTERN",
    "COUNT_PATTERN",
    "COUNT_WORD_PATTERN",
    "EN_COUNT_WORD_PATTERN",
    "count_value",
    "head_count",
    "normalize_arabic_letters",
    "parse_count_word",
    "strip_head_counts",
]

# --- English -----------------------------------------------------------------

_EN_UNITS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
}
_EN_TEENS = {
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}
_EN_TENS = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}

# --- Arabic ------------------------------------------------------------------
# Written in a normalized spelling: hamza forms of alef as "ا", ta marbuta as
# "ه", alef maqsura as "ي". `_arabic_regex` widens each back to every spelling.

_AR_UNITS: dict[str, int] = {
    "واحد": 1,
    "واحده": 1,
    "احد": 1,
    "احدي": 1,
    "اثنان": 2,
    "اثنين": 2,
    "اثنتان": 2,
    "اثنتين": 2,
    "ثلاث": 3,
    "ثلاثه": 3,
    "اربع": 4,
    "اربعه": 4,
    "خمس": 5,
    "خمسه": 5,
    "ست": 6,
    "سته": 6,
    "سبع": 7,
    "سبعه": 7,
    "ثمان": 8,
    "ثماني": 8,
    "ثمانيه": 8,
    "تسع": 9,
    "تسعه": 9,
}
# Units that stand alone as a count. "احد"/"احدي" only appear inside teens and
# compounds; alone they mean "someone"/"one of".
_AR_STANDALONE_UNITS = {
    word: value for word, value in _AR_UNITS.items() if word not in {"احد", "احدي"}
}
_AR_TEN = {"عشر": 10, "عشره": 10}
_AR_TEENS: dict[str, int] = {}
for _unit, _value in _AR_UNITS.items():
    if _value == 1 and _unit.startswith("واحد"):
        continue
    if _value == 2:
        continue
    for _ten in _AR_TEN:
        _AR_TEENS[f"{_unit} {_ten}"] = 10 + _value
for _two in ("اثنا", "اثني", "اثنتا", "اثنتي"):
    for _ten in _AR_TEN:
        _AR_TEENS[f"{_two} {_ten}"] = 12
_AR_TENS: dict[str, int] = {}
for _stem, _value in (
    ("عشر", 20),
    ("ثلاث", 30),
    ("اربع", 40),
    ("خمس", 50),
    ("ست", 60),
    ("سبع", 70),
    ("ثمان", 80),
    ("تسع", 90),
):
    _AR_TENS[f"{_stem}ون"] = _value
    _AR_TENS[f"{_stem}ين"] = _value

_ARABIC_LETTER_FOLD = str.maketrans(
    {"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ة": "ه", "ى": "ي"}
)
_ARABIC_DIACRITICS_RE = re.compile(r"[\u064b-\u065f\u0670\u0640]")
_ARABIC_CHAR_CLASSES = {"ا": "[اأإآٱ]", "ه": "[هة]", "ي": "[يى]"}


def normalize_arabic_letters(text: str) -> str:
    """Drop Arabic diacritics and tatweel, and fold alef/ta marbuta/ya forms."""
    return _ARABIC_DIACRITICS_RE.sub("", text).translate(_ARABIC_LETTER_FOLD)


def _arabic_regex(word: str) -> str:
    return "".join(
        _ARABIC_CHAR_CLASSES.get(char, r"\s+" if char == " " else re.escape(char))
        for char in word
    )


def _alternation(
    words: Iterable[str], to_regex: Callable[[str], str] = re.escape
) -> str:
    ordered = sorted(set(words), key=lambda word: (-len(word), word))
    return "|".join(to_regex(word) for word in ordered)


# --- Value table used by the parser -------------------------------------------

_COUNT_VALUES: dict[str, int] = {}
_COUNT_VALUES.update(_EN_UNITS)
_COUNT_VALUES.update(_EN_TEENS)
_COUNT_VALUES.update(_EN_TENS)
for _tens_word, _tens_value in _EN_TENS.items():
    for _unit_word, _unit_value in _EN_UNITS.items():
        _COUNT_VALUES[f"{_tens_word} {_unit_word}"] = _tens_value + _unit_value
_COUNT_VALUES["dozen"] = 12
_COUNT_VALUES["a dozen"] = 12
_COUNT_VALUES.update(_AR_STANDALONE_UNITS)
_COUNT_VALUES.update(_AR_TEN)
_COUNT_VALUES.update(_AR_TEENS)
_COUNT_VALUES.update(_AR_TENS)
for _tens_word, _tens_value in _AR_TENS.items():
    for _unit_word, _unit_value in _AR_UNITS.items():
        _COUNT_VALUES[f"{_unit_word} و{_tens_word}"] = _tens_value + _unit_value

# --- Patterns -----------------------------------------------------------------

_EN_SIMPLE = _alternation([*_EN_UNITS, *_EN_TEENS, *_EN_TENS])
EN_COUNT_WORD_PATTERN = (
    r"(?:a[\s-]+dozen|dozen|"
    rf"(?:{_alternation(_EN_TENS)})[\s-]+(?:{_alternation(_EN_UNITS)})|"
    rf"{_EN_SIMPLE})"
)
AR_COUNT_WORD_PATTERN = (
    rf"(?:(?:{_alternation(_AR_UNITS, _arabic_regex)})\s+و\s*"
    rf"(?:{_alternation(_AR_TENS, _arabic_regex)})|"
    rf"{_alternation(_AR_TEENS, _arabic_regex)}|"
    rf"{_alternation(_AR_TENS, _arabic_regex)}|"
    rf"{_alternation([*_AR_STANDALONE_UNITS, *_AR_TEN], _arabic_regex)})"
)
# Longest forms first: compounds and teens precede the plain words they start
# with, so "twenty five" is never read as "twenty" and "seventeen" never as
# "seven".
COUNT_WORD_PATTERN = rf"(?:{EN_COUNT_WORD_PATTERN}|{AR_COUNT_WORD_PATTERN})"
# A count as digits (ASCII or Arabic-Indic) or words.
COUNT_PATTERN = rf"(?:\d{{1,3}}|{COUNT_WORD_PATTERN})"

_SEPARATOR_RE = re.compile(r"[\s\-\u2010-\u2015]+")
_AR_CONJUNCTION_RE = re.compile(r" و ")


def _normalize_phrase(text: str) -> str:
    folded = normalize_arabic_letters(text.casefold())
    joined = " ".join(_SEPARATOR_RE.sub(" ", folded).split())
    return _AR_CONJUNCTION_RE.sub(" و", joined)


def parse_count_word(text: str) -> int | None:
    """Value of a spelled-out count ("fifteen", "twenty-five", "ستة"), else None.

    Digits are not words; use `count_value` to accept either.
    """
    return _COUNT_VALUES.get(_normalize_phrase(text))


def count_value(text: str) -> int | None:
    """Value of a count written as digits or as words, else None."""
    stripped = text.strip()
    if stripped.isdigit():
        return int(stripped)
    return parse_count_word(stripped)


# --- Head counts --------------------------------------------------------------

_EN_PEOPLE_NOUNS = (
    r"(?:persons?|people|staff|employees?|users?|seats?|members?|colleagues?|"
    r"designers?|workers?|individuals?)"
)
_EN_GROUP_NOUNS = r"(?:team|group|office|staff|crew|department)"
_AR_PEOPLE_NOUNS = (
    r"(?:[اأ]شخاص|شخص(?:ا|ين)?|[اأ]فراد|فرد(?:ا|ين)?|"
    r"موظف(?:ين|ون|ا)?|مستخدم(?:ين|ون|ا)?|مصمم(?:ين|ون|ا)?|"
    r"زملاء|زميل(?:ا)?|[اأ]عضاء|عضو(?:ا)?|عمال|عامل(?:ين|ا)?|مقاعد|مقعد(?:ا)?)"
)
_AR_GROUP_NOUNS = r"(?:فريق|مجموعة|مجموعه|مكتب|طاقم|قسم)"

_EN_HEAD_COUNT_RE = re.compile(
    rf"\b(?P<count>\d{{1,3}}|{EN_COUNT_WORD_PATTERN})[\s-]+{_EN_PEOPLE_NOUNS}\b",
    re.IGNORECASE,
)
_EN_HEAD_COUNT_WITH_MODIFIERS_RE = re.compile(
    rf"\b(?P<count>\d{{1,3}}|{EN_COUNT_WORD_PATTERN})[\s-]+"
    rf"(?:[a-z][\w-]*\s+){{0,2}}{_EN_PEOPLE_NOUNS}\b",
    re.IGNORECASE,
)
_EN_GROUP_OF_RE = re.compile(
    rf"\b{_EN_GROUP_NOUNS}\s+of\s+(?P<count>\d{{1,3}}|{EN_COUNT_WORD_PATTERN})"
    rf"(?:[\s-]+{_EN_PEOPLE_NOUNS})?\b",
    re.IGNORECASE,
)
_AR_HEAD_COUNT_RE = re.compile(
    # "لست" is "I am not", never "for six".
    rf"(?<!\w)(?:ل(?!ست(?!\S))|و)?(?P<count>\d{{1,3}}|{AR_COUNT_WORD_PATTERN})\s+"
    rf"{_AR_PEOPLE_NOUNS}(?!\w)",
)
_AR_GROUP_OF_RE = re.compile(
    rf"(?<!\w)[لو]?{_AR_GROUP_NOUNS}\s+(?:من|مكون\s+من|مكونة\s+من)\s+"
    rf"(?P<count>\d{{1,3}}|{AR_COUNT_WORD_PATTERN})"
    rf"(?:\s+{_AR_PEOPLE_NOUNS})?(?!\w)",
)


def _head_count_patterns(*, allow_modifiers: bool) -> tuple[re.Pattern[str], ...]:
    english = _EN_HEAD_COUNT_WITH_MODIFIERS_RE if allow_modifiers else _EN_HEAD_COUNT_RE
    return (_EN_GROUP_OF_RE, english, _AR_GROUP_OF_RE, _AR_HEAD_COUNT_RE)


def _prepare(text: str) -> str:
    return _ARABIC_DIACRITICS_RE.sub("", text)


def head_count(text: str, *, allow_modifiers: bool = False) -> int | None:
    """The head count a text states, from digits or words, else None.

    Reads "12 people", "fifteen staff", "a team of six (people)",
    "5 أشخاص", "لخمسة موظفين" and "فريق من عشرة أشخاص". With
    `allow_modifiers`, up to two words may sit between the count and the noun
    ("6 senior designers").
    """
    prepared = _prepare(text)
    best: tuple[int, int] | None = None
    for pattern in _head_count_patterns(allow_modifiers=allow_modifiers):
        match = pattern.search(prepared)
        if match is None:
            continue
        value = count_value(match.group("count"))
        if value is None:
            continue
        if best is None or match.start() < best[0]:
            best = (match.start(), value)
    return best[1] if best else None


def strip_head_counts(text: str, replacement: str = " ") -> str:
    """Remove every head-count phrase ("team of six", "20 people") from a text."""
    stripped = _prepare(text)
    for pattern in _head_count_patterns(allow_modifiers=False):
        stripped = pattern.sub(replacement, stripped)
    return stripped
