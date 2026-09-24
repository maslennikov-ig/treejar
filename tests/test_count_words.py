"""The shared spelled-out count vocabulary (tj-aq4t)."""

from __future__ import annotations

import re

import pytest

from src.dialogue import count_words
from src.dialogue.count_words import (
    COUNT_PATTERN,
    COUNT_WORD_PATTERN,
    count_value,
    head_count,
    parse_count_word,
    strip_head_counts,
)


@pytest.mark.parametrize(
    ("phrase", "value"),
    [
        ("one", 1),
        ("Seven", 7),
        ("eleven", 11),
        ("fifteen", 15),
        ("nineteen", 19),
        ("twenty", 20),
        ("twenty five", 25),
        ("twenty-five", 25),
        ("Ninety–Nine", 99),
        ("dozen", 12),
        ("a dozen", 12),
        ("واحد", 1),
        ("اثنين", 2),
        ("ثلاثة", 3),
        ("ثلاثه", 3),
        ("أربعة", 4),
        ("اربعة", 4),
        ("ستة", 6),
        ("عشرة", 10),
        ("أحد عشر", 11),
        ("إحدى عشرة", 11),
        ("اثنا عشر", 12),
        ("اثني عشر", 12),
        ("خمسة عشر", 15),
        ("عشرون", 20),
        ("عشرين", 20),
        ("خمسة وعشرون", 25),
        ("خمسة و عشرين", 25),
        ("تسعين", 90),
    ],
)
def test_parse_count_word_reads_english_and_arabic(phrase: str, value: int) -> None:
    assert parse_count_word(phrase) == value


@pytest.mark.parametrize("phrase", ["", "a", "an", "12", "team", "احد", "chairs"])
def test_parse_count_word_rejects_non_counts(phrase: str) -> None:
    assert parse_count_word(phrase) is None


def test_count_value_accepts_digits_and_words() -> None:
    assert count_value("15") == 15
    assert count_value("١٢") == 12
    assert count_value("fifteen") == 15
    assert count_value("chairs") is None


def test_every_parsed_phrase_is_matched_whole_by_the_pattern() -> None:
    pattern = re.compile(COUNT_WORD_PATTERN, re.IGNORECASE)
    unmatched = [
        phrase
        for phrase in count_words._COUNT_VALUES
        if pattern.fullmatch(phrase) is None
    ]
    assert unmatched == []


@pytest.mark.parametrize(
    ("text", "count"),
    [
        ("seventeen people", "seventeen"),
        ("twenty five users", "twenty five"),
        ("eighty staff", "eighty"),
        ("12 seats", "12"),
    ],
)
def test_pattern_prefers_the_longest_form(text: str, count: str) -> None:
    match = re.match(rf"(?P<count>{COUNT_PATTERN})\s+\w+$", text)
    assert match is not None
    assert match.group("count") == count


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("for twenty people", 20),
        ("desks for 15 employees", 15),
        ("fifteen staff", 15),
        ("a dozen users", 12),
        ("twenty-five seats", 25),
        ("comfortable chairs for a team of fifteen", 15),
        ("a team of six", 6),
        ("a team of six people", 6),
        ("an office of 40", 40),
        ("group of eight colleagues", 8),
        ("مكاتب لخمسة موظفين", 5),
        ("كراسي لـ ١٢ شخص", 12),
        ("فريق من عشرة أشخاص", 10),
        ("نحتاج مكاتب لفريق من ستة", 6),
        ("خمسة وعشرين موظفاً", 25),
    ],
)
def test_head_count_reads_digits_words_and_group_phrasing(
    text: str, value: int
) -> None:
    assert head_count(text) == value


@pytest.mark.parametrize(
    "text",
    [
        "one chair please",
        "twenty chairs",
        "لست موظفا هنا",
        "I need a desk",
    ],
)
def test_head_count_ignores_non_head_counts(text: str) -> None:
    assert head_count(text) is None


def test_modifiers_are_only_read_when_allowed() -> None:
    assert head_count("6 senior designers") is None
    assert head_count("6 senior designers", allow_modifiers=True) == 6


def test_strip_head_counts_removes_the_whole_phrase() -> None:
    stripped = strip_head_counts("comfortable chairs for a team of fifteen people")
    assert stripped.split() == ["comfortable", "chairs", "for", "a"]
    assert strip_head_counts("desks for twenty people").split() == ["desks", "for"]
