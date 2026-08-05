"""Verification for product attributes the assistant asserts to a customer.

Failure class (a) of the 2026-08-05 sealed round, supply side. The existing
guard is demand-side: it fires only when the customer asked about one of two
hardcoded gap types and the catalog text is silent. The observed failure is the
opposite — nobody asked and the model volunteered a mesh back, a synchronised
tilt, a desk that seats ten.

This module decides whether an asserted attribute has a source. It checks
**existence**: does the field path exist on the row that was actually retrieved,
for that SKU, carrying that value. Whether wording widens the meaning of a value
that does exist is paraphrase, and is deliberately out of scope here.

Three findings from the 2026-08-05 catalog audit shape it.

* The specification key namespace is not canonical. `Recommended load` and
  `Recommended Load` are separate keys on the live catalog, so a contract that
  compared raw paths would report supported claims as unsupported.
* No active SKU carries Arabic text. Every Arabic reply is already grounded in
  an English row, so a claim is verified against the English field and the
  Arabic surface form is treated as translation, never as a separate source.
* Seating capacity is not a catalog field at all. It is parsed out of free text,
  and where that text names a number at all it names two different ones in 25 of
  28 cases. Owner decision of 2026-08-05: the assistant may state a capacity only
  as a visible assumption carrying a confirming question, never as a fact.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

ClaimType = Literal[
    "catalog_fact", "derived_fact", "explicit_assumption", "recommendation"
]

CAPACITY_FIELD_PATHS = frozenset(
    {
        "capacity",
        "seats",
        "seatcount",
        "seatingcapacity",
        "numberofseats",
        "persons",
        "people",
        "pax",
        "seatsperunit",
    }
)
"""Paths that name a seat count. None of them exists on the live catalog."""


class AttributeStatus(StrEnum):
    """What is known about one attribute of one SKU.

    A missing attribute is a status, not an empty string, so the reply can say
    something useful about it instead of falling silent or refusing.
    """

    KNOWN_VALUE = "known_value"
    CONFIRMED_ABSENT = "confirmed_absent"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class RetrievedRow:
    """One catalog row as it actually reached the model this turn."""

    sku: str
    fields: Mapping[str, str] = field(default_factory=dict)
    absent_fields: frozenset[str] = frozenset()
    not_applicable_fields: frozenset[str] = frozenset()

    def normalized_fields(self) -> dict[str, str]:
        return {
            normalize_field_path(path): value for path, value in self.fields.items()
        }


@dataclass(frozen=True, slots=True)
class AttributeClaim:
    """One atomic thing the reply asserts about one SKU."""

    claim_type: ClaimType
    sku: str
    field_path: str = ""
    value: str = ""
    marker_present: bool = False
    confirming_question: bool = False


@dataclass(frozen=True, slots=True)
class ClaimCheck:
    status: AttributeStatus
    supported: bool
    reason: str
    may_reach_customer: bool


_NON_WORD_RE = re.compile(r"[^0-9a-z؀-ۿ]+")


def normalize_field_path(path: str) -> str:
    """Fold a field path to its comparable form.

    `attributes.specifications.Recommended load` and `Recommended Load` are the
    same field on a catalog whose key namespace was never normalized. The
    container prefix is dropped so a claim can name the leaf it means.
    """
    leaf = str(path).strip().rsplit(".", 1)[-1]
    return _NON_WORD_RE.sub("", leaf.casefold())


def _row_for(sku: str, rows: Mapping[str, RetrievedRow]) -> RetrievedRow | None:
    normalized = str(sku).strip().casefold()
    for candidate_sku, row in rows.items():
        if str(candidate_sku).strip().casefold() == normalized:
            return row
    return None


def attribute_status(
    sku: str,
    field_path: str,
    rows: Mapping[str, RetrievedRow],
) -> AttributeStatus:
    row = _row_for(sku, rows)
    if row is None:
        return AttributeStatus.UNKNOWN
    normalized = normalize_field_path(field_path)
    if normalized in {normalize_field_path(p) for p in row.not_applicable_fields}:
        return AttributeStatus.NOT_APPLICABLE
    value = row.normalized_fields().get(normalized)
    if value is not None and value.strip():
        return AttributeStatus.KNOWN_VALUE
    if normalized in {normalize_field_path(p) for p in row.absent_fields}:
        return AttributeStatus.CONFIRMED_ABSENT
    return AttributeStatus.UNKNOWN


def check_claim(
    claim: AttributeClaim,
    rows: Mapping[str, RetrievedRow],
) -> ClaimCheck:
    """Decide whether one claim may reach the customer as written."""
    if claim.claim_type == "recommendation":
        return ClaimCheck(
            status=AttributeStatus.NOT_APPLICABLE,
            supported=True,
            reason="a recommendation is an opinion, not a catalog attribute",
            may_reach_customer=True,
        )

    is_capacity = normalize_field_path(claim.field_path) in CAPACITY_FIELD_PATHS

    if claim.claim_type == "explicit_assumption":
        if not (claim.marker_present and claim.confirming_question):
            return ClaimCheck(
                status=AttributeStatus.UNKNOWN,
                supported=False,
                reason=(
                    "an assumption without a visible marker and a confirming "
                    "question reads as a stated fact"
                ),
                may_reach_customer=False,
            )
        status = attribute_status(claim.sku, claim.field_path, rows)
        if status is AttributeStatus.KNOWN_VALUE:
            row = _row_for(claim.sku, rows)
            stored = (row.normalized_fields() if row else {}).get(
                normalize_field_path(claim.field_path), ""
            )
            if not _value_is_covered(claim.value, stored):
                return ClaimCheck(
                    status=status,
                    supported=False,
                    reason="assumption contradicts the value already on the row",
                    may_reach_customer=False,
                )
        return ClaimCheck(
            status=status,
            supported=True,
            reason="marked assumption with a confirming question, contradicting nothing",
            may_reach_customer=True,
        )

    if is_capacity:
        # Owner decision, 2026-08-05. Capacity is derived from free text that
        # states two different numbers on 25 of the 28 SKUs naming one at all.
        # Nothing may present it as a catalog fact.
        return ClaimCheck(
            status=attribute_status(claim.sku, claim.field_path, rows),
            supported=False,
            reason=(
                "seating capacity is not a catalog field; it may be offered only "
                "as a marked assumption with a confirming question"
            ),
            may_reach_customer=False,
        )

    status = attribute_status(claim.sku, claim.field_path, rows)
    if status is not AttributeStatus.KNOWN_VALUE:
        return ClaimCheck(
            status=status,
            supported=False,
            reason=f"field path is {status.value} on the retrieved row",
            may_reach_customer=False,
        )

    row = _row_for(claim.sku, rows)
    stored = (row.normalized_fields() if row else {}).get(
        normalize_field_path(claim.field_path), ""
    )
    if not _value_is_covered(claim.value, stored):
        return ClaimCheck(
            status=status,
            supported=False,
            reason="claimed value is not the value stored on the row",
            may_reach_customer=False,
        )
    return ClaimCheck(
        status=status,
        supported=True,
        reason="exact SKU, field path and value present on the retrieved row",
        may_reach_customer=True,
    )


_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")
_ARABIC_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def _numbers_in(text: str) -> set[float]:
    """Every number a value carries, free of separators and digit script."""
    found: set[float] = set()
    for token in _NUMBER_RE.findall(str(text).translate(_ARABIC_INDIC_DIGITS)):
        try:
            found.add(float(token.replace(",", "")))
        except ValueError:
            continue
    return found


def _value_is_covered(claimed: str, stored: str) -> bool:
    """Containment, not paraphrase.

    Whether wording widens the meaning of a value that does exist belongs to
    tj-feet.9. Here a claim passes when its value is the stored one.

    Literal containment alone was too strict, and the `tj-feet.10` measurement
    of 2026-08-05 put a number on it: withholding `AED 800` against a stored
    `800.00` was the largest single class of withholding, ahead of every real
    one. A price the catalog does state being reported to the customer as not
    stated is the worst thing this function can cause, so a value whose numbers
    are all stored numbers is covered. Currency, thousands separators, Arabic
    digits and word order are presentation; a *different* number is not.
    """
    claimed_normalized = " ".join(str(claimed).casefold().split())
    stored_normalized = " ".join(str(stored).casefold().split())
    if not claimed_normalized:
        return bool(stored_normalized)
    if claimed_normalized in stored_normalized:
        return True
    claimed_numbers = _numbers_in(claimed_normalized)
    stored_numbers = _numbers_in(stored_normalized)
    return bool(claimed_numbers) and claimed_numbers <= stored_numbers


@dataclass(frozen=True, slots=True)
class ContractResult:
    approved: tuple[AttributeClaim, ...]
    withheld: tuple[tuple[AttributeClaim, ClaimCheck], ...]

    @property
    def withheld_field_paths(self) -> tuple[str, ...]:
        return tuple(
            sorted({claim.field_path for claim, _ in self.withheld if claim.field_path})
        )


def apply_contract(
    claims: tuple[AttributeClaim, ...],
    rows: Mapping[str, RetrievedRow],
) -> ContractResult:
    approved: list[AttributeClaim] = []
    withheld: list[tuple[AttributeClaim, ClaimCheck]] = []
    for claim in claims:
        check = check_claim(claim, rows)
        if check.may_reach_customer:
            approved.append(claim)
        else:
            withheld.append((claim, check))
    return ContractResult(approved=tuple(approved), withheld=tuple(withheld))


def row_from_catalog_product(
    *,
    sku: str,
    attributes: Mapping[str, object] | None,
    extras: Mapping[str, object] | None = None,
) -> RetrievedRow:
    """Flatten a catalog row into the field paths a claim can name.

    `specifications` is the substantive carrier on the live catalog; a key that
    exists there with an empty value is `confirmed_absent`, while a key that was
    never synced is `unknown`. The distinction is the whole point of the typed
    status, so it is preserved rather than collapsed.
    """
    fields: dict[str, str] = {}
    absent: set[str] = set()
    for name, value in (extras or {}).items():
        text = "" if value is None else str(value).strip()
        if text:
            fields[str(name)] = text

    specifications = (attributes or {}).get("specifications")
    if isinstance(specifications, Mapping):
        for name, value in specifications.items():
            path = f"attributes.specifications.{name}"
            text = "" if value is None else str(value).strip()
            if text:
                fields[path] = text
            else:
                absent.add(path)

    features = (attributes or {}).get("features")
    if isinstance(features, list):
        joined = "; ".join(str(item).strip() for item in features if str(item).strip())
        if joined:
            fields["attributes.features"] = joined
        else:
            absent.add("attributes.features")

    for name in ("brand", "manufacturer", "availability"):
        value = (attributes or {}).get(name)
        text = "" if value is None else str(value).strip()
        if text:
            fields[f"attributes.{name}"] = text
        else:
            absent.add(f"attributes.{name}")

    return RetrievedRow(sku=str(sku), fields=fields, absent_fields=frozenset(absent))


_SIZING_PEOPLE_RE = re.compile(
    r"(?:\b(?:people|persons?|staff|employees?|colleagues?|team|headcount)\b"
    r"|أشخاص|اشخاص|شخص|موظف|فريق|أفراد|افراد)",
    re.IGNORECASE,
)

_COUNT_WORD = (
    r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"fifteen|twenty|thirty|forty|fifty|hundred)"
)

_SIZING_FIT_RE = re.compile(
    r"(?:\b(?:enough|sufficient|suffice|fits?|accommodates?|"
    rf"seats?\s+(?:our|your|the|my|all|a\b|up\s+to|{_COUNT_WORD}))\b"
    r"|يكفي|تكفي|كافي|يتسع|تتسع|يسع|يستوعب|تستوعب)",
    re.IGNORECASE,
)


def requests_sizing_judgement(customer_text: str) -> bool:
    """Did the customer ask whether a product suits a headcount they stated?

    Read over the **customer request**, never over the reply. A lexical
    backstop over generated text is on the specification's rejected list; this
    is the same demand-side shape the existing evidence-gap detection uses.

    English and Arabic only, per the owner decision of 2026-08-05 on the served
    languages. A request in any other language simply does not fire the
    directive, which leaves behaviour exactly as it was.
    """
    text = str(customer_text)
    if not text.strip():
        return False
    return bool(_SIZING_PEOPLE_RE.search(text) and _SIZING_FIT_RE.search(text))


def sizing_assumption_directive() -> str:
    """The per-turn directive that unlocks the answer without unlocking a fact.

    Measured need: the `tj-feet.5` counter-set of 2026-08-05 put the
    false-refusal rate at 0.200, and all six were this one shape. The contract
    already approved the answer — a capacity carrying a visible marker and a
    confirming question — so the gap was instruction, not permission.

    It lives here rather than in the product system prompt, which the stage
    contract freezes.
    """
    return (
        "The customer has asked whether a product suits a headcount they "
        "stated. Answer it. Do the arithmetic in the open on their number and "
        "give the sizing as an explicit assumption: name it as an assumption, "
        "state the per-unit figure you are assuming, and ask one short "
        "question that confirms it. Seating or desk capacity is not a catalog "
        "fact and must never be presented as one, so never state it without "
        "that marker and that question. Give every confirmed detail alongside "
        "it, and close with one concrete next step. Declining to answer is not "
        "an acceptable outcome here."
    )


def assumption_eligible_paths(
    withheld_field_paths: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split withheld paths into the ones a marked assumption may re-offer.

    Only capacity. A headcount is the customer's own number and the assistant
    can do the arithmetic in the open; a back material is a property of the
    product, and no amount of labelling invents one.
    """
    eligible = tuple(
        path
        for path in withheld_field_paths
        if normalize_field_path(path) in CAPACITY_FIELD_PATHS
    )
    remaining = tuple(path for path in withheld_field_paths if path not in eligible)
    return eligible, remaining


def partial_answer(
    *,
    sku: str,
    unknown_field_paths: tuple[str, ...],
    confirmed: Mapping[str, str],
    arabic: bool = False,
) -> str:
    """The useful answer for an attribute the catalog does not state.

    Never a refusal. It names what is not stated, offers to confirm it, and
    still hands over everything that is confirmed, because a customer who asked
    about a back material still wants the price.
    """
    unknown = ", ".join(
        normalize_field_path(path).replace("_", " ") or path
        for path in unknown_field_paths
    )
    confirmed_pairs = "; ".join(f"{name}: {value}" for name, value in confirmed.items())
    if arabic:
        lines = [
            f"الكتالوج لا يذكر {unknown} لـ {sku}، وسأؤكدها مع المسؤول."
            if unknown
            else f"سأؤكد التفاصيل الناقصة لـ {sku} مع المسؤول."
        ]
        if confirmed_pairs:
            lines.append(f"المؤكد الآن — {confirmed_pairs}.")
        return " ".join(lines)
    lines = [
        f"The catalog does not state the {unknown} for {sku}, and I will confirm "
        "that with a manager."
        if unknown
        else f"I will confirm the missing details for {sku} with a manager."
    ]
    if confirmed_pairs:
        lines.append(f"What is confirmed — {confirmed_pairs}.")
    return " ".join(lines)
