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
    "catalog_fact",
    "derived_fact",
    "absence",
    "explicit_assumption",
    "recommendation",
]

DerivedOperation = Literal["comparison", "sum", "difference", "product"]
"""The operations the runtime can restate from the inputs a derivation names.

Deliberately short. A derivation the runtime cannot recompute is not verified
by listing its inputs, it is only decorated with them, so anything outside this
set stays withheld.
"""

_DERIVED_OPERATIONS = frozenset({"comparison", "sum", "difference", "product"})

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
        normalized = {
            normalize_field_path(path): value for path, value in self.fields.items()
        }
        # The row *is* this SKU, so naming it is the one claim that needs no
        # column. The 2026-08-05 replay found the model claiming
        # `field_path=sku, value=CH-A` and the contract withholding it, because
        # the identifier was never flattened into the fields the model is shown.
        normalized.setdefault("sku", self.sku)
        return normalized


@dataclass(frozen=True, slots=True)
class ClaimInput:
    """One value a derivation rests on.

    A derivation has no field path of its own, so it is verified through the
    inputs it names rather than through its output. An input the customer
    supplied — their headcount, the quantity they asked for — is theirs, not the
    catalog's, and is taken at face value; `customer_stated` records that
    difference instead of hiding it.
    """

    sku: str = ""
    field_path: str = ""
    value: str = ""
    customer_stated: bool = False


@dataclass(frozen=True, slots=True)
class AttributeClaim:
    """One atomic thing the reply asserts about one SKU."""

    claim_type: ClaimType
    sku: str
    field_path: str = ""
    value: str = ""
    marker_present: bool = False
    confirming_question: bool = False
    source_value: str = ""
    """The English catalog value a non-Latin surface form rests on.

    No active SKU carries Arabic text, so an Arabic reply is grounded in an
    English row and its wording is translation. Carrying the English value
    alongside the Arabic one lets the row be checked without a translation
    call.
    """
    operation: str = ""
    inputs: tuple[ClaimInput, ...] = ()


@dataclass(frozen=True, slots=True)
class ClaimCheck:
    status: AttributeStatus
    supported: bool
    reason: str
    may_reach_customer: bool


def _unverified(status: AttributeStatus, reason: str) -> ClaimCheck:
    """Cannot be proven, and therefore not blocked.

    Owner decision of 2026-08-06, and the reason `supported` and
    `may_reach_customer` are separate fields rather than one. A claim the
    contract cannot verify is not a claim the contract has caught. Blocking it
    trades a rare invented attribute for a common spoiled answer, and a spoiled
    answer is the worse of the two: the customer sees it immediately, and it
    tells them the catalog is silent about something the catalog states.

    The evidence behind the decision: across the counter-set built specifically
    to bait fabrication, the measured unsupported-fact rate was 0.000, so the
    strict rule had caught nothing while rewriting 30 of 37 replies. It is
    recorded as unverified so it stays visible in the logs.
    """
    return ClaimCheck(
        status=status, supported=False, reason=reason, may_reach_customer=True
    )


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

    if claim.claim_type == "absence":
        return _check_absence(claim, rows)

    if claim.claim_type == "derived_fact":
        return _check_derivation(claim, rows)

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
            verdict = _claimed_value_is_grounded(claim, stored)
            if not verdict.ok:
                return ClaimCheck(
                    status=status,
                    supported=False,
                    reason=f"assumption contradicts the row: {verdict.reason}",
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
        return _unverified(status, f"field path is {status.value} on the retrieved row")

    row = _row_for(claim.sku, rows)
    stored = (row.normalized_fields() if row else {}).get(
        normalize_field_path(claim.field_path), ""
    )
    verdict = _claimed_value_is_grounded(claim, stored)
    return ClaimCheck(
        status=status,
        supported=verdict.ok,
        reason=verdict.reason,
        may_reach_customer=verdict.ok,
    )


def _check_absence(
    claim: AttributeClaim,
    rows: Mapping[str, RetrievedRow],
) -> ClaimCheck:
    """Verify the sentence that says the catalog is silent about something.

    `tj-feet.14`. Routing this through the attribute check withheld it: the path
    is absent, so the claim was unsupported — which withheld the assistant
    saying the catalog does not state something, the exact sentence the partial
    answer exists to produce. An absence statement is not an attribute claim, so
    it is checked against the row's *status* rather than against a value.

    It is checked, not waved through: denying an attribute the row does state is
    a false statement about the catalog and stays withheld.
    """
    status = attribute_status(claim.sku, claim.field_path, rows)
    if status is AttributeStatus.KNOWN_VALUE:
        return ClaimCheck(
            status=status,
            supported=False,
            reason="the retrieved row does state this attribute",
            may_reach_customer=False,
        )
    return ClaimCheck(
        status=status,
        supported=True,
        reason=f"the row reports this attribute as {status.value}, which is what the reply says",
        may_reach_customer=True,
    )


def _check_derivation(
    claim: AttributeClaim,
    rows: Mapping[str, RetrievedRow],
) -> ClaimCheck:
    """Verify the inputs of a derivation and the arithmetic over them.

    `tj-feet.12`. A comparison, a total or a calculation has no field path by
    definition, so routing it through the existence check made it permanently
    unsupported. What can be verified is the other end: every input value is
    checked against the row it names, and the figure the reply states must be
    one the runtime can recompute from those inputs.

    Listing inputs without recomputing would only decorate the claim, so an
    operation outside `_DERIVED_OPERATIONS` stays withheld even when every input
    is sound.
    """
    unknown = AttributeStatus.UNKNOWN
    operation = normalize_field_path(claim.operation)
    if operation not in _DERIVED_OPERATIONS:
        return _unverified(
            unknown, "the derivation names no operation the runtime can restate"
        )
    if not claim.inputs:
        return _unverified(unknown, "the derivation names no input to verify")
    if operation == "comparison" and len(claim.inputs) < 2:
        return _unverified(unknown, "a comparison rests on at least two inputs")
    if operation == "difference" and len(claim.inputs) != 2:
        return _unverified(
            unknown, "a difference is restatable over exactly two inputs"
        )

    unverifiable: str | None = None
    for derived_input in claim.inputs:
        outcome, reason = _derivation_input_outcome(derived_input, rows)
        if outcome == "blocked":
            return ClaimCheck(
                status=unknown,
                supported=False,
                reason=f"a derivation input is refused: {reason}",
                may_reach_customer=False,
            )
        if outcome == "unverified":
            unverifiable = reason
    if unverifiable is not None:
        return _unverified(unknown, f"a derivation input is unverified: {unverifiable}")

    # Only the computed operations can prove a stated figure wrong. A comparison
    # restates rather than calculates, so a stray number in it is unverified,
    # not false.
    if operation != "comparison" and not _numbers_are_covered(
        _numbers_in(claim.value), _restatable_numbers(operation, claim.inputs)
    ):
        return ClaimCheck(
            status=unknown,
            supported=False,
            reason=(
                f"the {operation} of the inputs it names does not produce the "
                "figure the reply states"
            ),
            may_reach_customer=False,
        )
    return ClaimCheck(
        status=unknown,
        supported=True,
        reason=f"every input is supported and the {operation} restates from them",
        may_reach_customer=True,
    )


def _derivation_input_outcome(
    derived_input: ClaimInput,
    rows: Mapping[str, RetrievedRow],
) -> tuple[str, str]:
    """One input of a derivation: `ok`, `unverified`, or `blocked`.

    Only two things block. A per-product seating capacity, whatever route it
    takes — the owner decision of 2026-08-05 is that capacity is not a catalog
    fact, and multiplying it by a quantity does not make it one, which is what
    `two desks x ten people = twenty` was doing. And a value the row positively
    contradicts. A figure carrying no SKU is about the customer's own team, not
    about a product, so the capacity rule does not reach it.
    """
    is_capacity = normalize_field_path(derived_input.field_path) in CAPACITY_FIELD_PATHS
    if is_capacity and derived_input.sku.strip():
        return "blocked", (
            "seating capacity is not a catalog fact and may not be derived from; "
            "it belongs in a marked assumption with a confirming question"
        )
    stored = _stored_value(derived_input.sku, derived_input.field_path, rows)
    if not stored:
        # Nothing to compare against. The customer's own quantity looks exactly
        # like this, and so does a path the catalog simply does not carry.
        return "unverified", "the row carries no value for this input"
    if not _value_is_covered(derived_input.value, stored):
        return "blocked", "an input contradicts the value stored on the row"
    return "ok", "the row carries this value"


def _restatable_numbers(
    operation: str,
    inputs: tuple[ClaimInput, ...],
) -> set[float]:
    """Every figure the reply may state, given these inputs and this operation.

    The input figures themselves are always restatable — a comparison that
    quotes both prices is restating, not computing. Beyond them only the single
    result of the named operation is allowed, so a derivation cannot smuggle in
    a number of its own.
    """
    per_input = [_numbers_in(item.value) for item in inputs]
    allowed: set[float] = set().union(*per_input) if per_input else set()
    if operation == "comparison":
        return allowed
    if any(len(numbers) != 1 for numbers in per_input):
        # Arithmetic over an input that carries no number, or several, is not
        # something the runtime can restate.
        return allowed
    operands = [next(iter(numbers)) for numbers in per_input]
    if operation == "sum":
        allowed.add(round(sum(operands), 6))
    elif operation == "difference":
        allowed.add(round(abs(operands[0] - operands[1]), 6))
    elif operation == "product":
        product = 1.0
        for operand in operands:
            product *= operand
        allowed.add(round(product, 6))
    return allowed


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


_ARABIC_LETTER_RE = re.compile(r"[؀-ۿݐ-ݿ]")


@dataclass(frozen=True, slots=True)
class _ValueVerdict:
    ok: bool
    reason: str


def _stored_value(
    sku: str,
    field_path: str,
    rows: Mapping[str, RetrievedRow],
) -> str:
    row = _row_for(sku, rows)
    return (row.normalized_fields() if row else {}).get(
        normalize_field_path(field_path), ""
    )


def _numbers_are_covered(claimed: set[float], allowed: set[float]) -> bool:
    """Every figure the claim states is one the row or the arithmetic produces.

    Compared with a tolerance rather than by set membership, because these
    numbers come from parsing decimal strings and `800.00 + 900.00` is not
    reliably `1700.0` on the nose.
    """
    return all(
        any(abs(number - candidate) <= 1e-6 for candidate in allowed)
        for number in claimed
    )


def _is_translated_surface(value: str, source_value: str) -> bool:
    """Is this wording a translation of the stored English value?

    Only a non-Latin surface form opens the translation branch. Without that
    restriction `source_value` would be an escape hatch: a model could name the
    stored value there and write anything it liked in `value`, which is the one
    thing the contract exists to prevent. No active SKU carries Arabic text, so
    Arabic is exactly the case that needs it and English is exactly the case
    that must not have it.
    """
    return bool(
        _ARABIC_LETTER_RE.search(str(value))
        and not _ARABIC_LETTER_RE.search(str(source_value))
    )


def _claimed_value_is_grounded(claim: AttributeClaim, stored: str) -> _ValueVerdict:
    """Does the value this claim states rest on the value the row carries?

    `tj-feet.13`. The module has always said that an Arabic reply is verified
    against the English row and its wording treated as translation; literal
    containment did not implement that, so every translated value was withheld —
    `هيكل فولاذي` against a stored `steel frame`, `دبي` against `Dubai`. The
    claim now carries the English value it rests on, which costs no call.

    Words are translation. A *figure* is a fact in any script, so a translated
    surface may not state a number the row does not carry.
    """
    if claim.source_value and _is_translated_surface(claim.value, claim.source_value):
        if not _value_is_covered(claim.source_value, stored):
            return _ValueVerdict(
                False,
                "the source value the translation rests on is not the value "
                "stored on the row",
            )
        allowed = _numbers_in(claim.source_value) | _numbers_in(stored)
        if not _numbers_are_covered(_numbers_in(claim.value), allowed):
            return _ValueVerdict(
                False, "the translated wording states a number the row does not carry"
            )
        return _ValueVerdict(
            True, "verified against the English row; the surface form is translation"
        )
    if _value_is_covered(claim.value, stored):
        return _ValueVerdict(
            True, "exact SKU, field path and value present on the retrieved row"
        )
    return _ValueVerdict(False, "claimed value is not the value stored on the row")


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
    unverified: tuple[tuple[AttributeClaim, ClaimCheck], ...] = ()
    """Claims that reached the customer without the row being able to confirm them.

    Kept as its own bucket rather than folded into `approved`, because giving up
    the block is not a reason to give up the visibility. This is what tells us,
    on live traffic, whether the strict rule was protecting anything.
    """

    @property
    def withheld_field_paths(self) -> tuple[str, ...]:
        return tuple(
            sorted({claim.field_path for claim, _ in self.withheld if claim.field_path})
        )

    @property
    def unverified_field_paths(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {claim.field_path for claim, _ in self.unverified if claim.field_path}
            )
        )


def apply_contract(
    claims: tuple[AttributeClaim, ...],
    rows: Mapping[str, RetrievedRow],
) -> ContractResult:
    approved: list[AttributeClaim] = []
    withheld: list[tuple[AttributeClaim, ClaimCheck]] = []
    unverified: list[tuple[AttributeClaim, ClaimCheck]] = []
    for claim in claims:
        check = check_claim(claim, rows)
        if not check.may_reach_customer:
            withheld.append((claim, check))
            continue
        approved.append(claim)
        if not check.supported:
            unverified.append((claim, check))
    return ContractResult(
        approved=tuple(approved),
        withheld=tuple(withheld),
        unverified=tuple(unverified),
    )


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


_COMPARISON_MARKER_RE = re.compile(
    r"(?:\bcompare\b|\bcomparison\b|\bversus\b|\bvs\.?\b|"
    r"\bdifference\s+between\b|\bwhich\s+(?:one\s+)?(?:is|would\s+be)\s+better\b|"
    r"\bwhich\s+(?:one|of\s+(?:these|them))\b|"
    r"قارن|مقارنة|الفرق\s+بين)",
    re.IGNORECASE,
)
_COMPARISON_STAND_DOWN_RE = re.compile(
    r"(?:\bno\s+(?:other\s+)?alternatives?\b|\bno\s+upsell\b|"
    r"\bonly\s+(?:these|those|that|this)\b|\bnothing\s+else\b|"
    r"\bjust\s+(?:these|those|the)\s+two\b|"
    r"بدون\s+بدائل)",
    re.IGNORECASE,
)


def requests_product_comparison(customer_text: str) -> bool:
    """Did the customer ask for two or more options to be weighed?

    Read over the **customer request**, never over the reply, like the sizing
    detector above it.

    The stand-down half matters as much as the trigger. S06 asked for one exact
    SKU with no alternatives and no quotation, and the checklist marked it down
    for not consulting. Consulting anyway would be answering the checklist
    instead of the customer.
    """

    text = str(customer_text)
    if not text.strip():
        return False
    if _COMPARISON_STAND_DOWN_RE.search(text):
        return False
    return bool(_COMPARISON_MARKER_RE.search(text))


def comparison_consultation_directive() -> str:
    """The per-turn directive for a comparison the model answers and leaves.

    S04 on 2026-08-07: correct on every fact, recommended one of the two, and
    stopped. The evaluator's reading was no acknowledgement, no clarifying
    question, and no complete solution beyond the two items compared.

    It lives here rather than in the product system prompt, which the stage
    contract freezes.
    """

    return (
        "The customer has asked you to weigh options. Answer the comparison "
        "they asked for and recommend one, with the reason in their own terms. "
        "Then do the three things a salesperson would: acknowledge the team or "
        "project they described, name what the workspace still needs to be "
        "complete beyond the items compared, and ask one short question that "
        "moves this forward or state the next concrete step. Look up any "
        "complementary item with search_products before naming it, and give "
        "its confirmed price and stock; never name a product, price or "
        "availability you have not verified this turn. Never offer a discount "
        "or a bonus. If a detail is unconfirmed, say so rather than filling "
        "the gap."
    )


_OPENING_STAGES = frozenset({"greeting", "qualifying", "needs_analysis"})

_TRANSACTIONAL_NARROWING_RE = re.compile(
    r"(?:\b(?:do\s+not|don'?t)\s+(?:suggest|offer|recommend|include|add|propose)\b"
    r"|\bno\s+(?:other\s+)?alternatives?\b|\bno\s+upsell\b"
    r"|\bonly\s+(?:these|those|that|this)\b|\bnothing\s+else\b"
    rf"|\bexactly\s+{_COUNT_WORD}\b"
    r"|\bexact\s+(?:live\s+)?(?:sku|price|item|model|quantity)\b"
    r"|بدون\s+بدائل|لا\s+تقترح)",
    re.IGNORECASE,
)


def earns_consultative_opening(customer_text: str, *, sales_stage: str) -> bool:
    """Is this a turn where a salesperson would still be building the sale?

    Read over the **customer request** and the typed stage, never over the
    reply, like the two detectors above it.

    Coarse on purpose. Rules 6, 7 and 13 of the checklist are not shaped like a
    request -- nobody asks to be thanked or to hear what Treejar is -- so there
    is no phrase to trigger on, only a phase of the conversation. The precision
    lives in the directive, where each of the three moves carries its own
    condition. The stand-down is the same principle as the comparison
    detector's: a customer who has narrowed to one exact item is not asking to
    be sold to, and consulting anyway answers the checklist instead of them.
    """

    text = str(customer_text)
    if not text.strip():
        return False
    if sales_stage.strip().casefold() not in _OPENING_STAGES:
        return False
    return not _TRANSACTIONAL_NARROWING_RE.search(text)


def consultative_opening_directive(*, opening_states_the_offer: bool = False) -> str:
    """The three sentences Noor never says.

    Measured on 2026-08-07 over all ten stored acceptance transcripts, scored
    criterion by criterion. Rule 7, Treejar's value proposition, is zero in ten
    of ten. Rule 11, an incentive, is zero in ten of ten. Rule 13, asking what
    the customer's company does, is zero in five of five where it applies. Rule
    6, a compliment or thanks, is four of a possible twenty. Meanwhile rules 1
    and 2 are a perfect twenty of twenty. Nothing here is a catalog, tool or
    rewrite failure: these are sentences the model does not say.

    Rules 9 and 10 joined it on 2026-08-08, on the owner's decision that Noor
    may widen past the literal request from the catalog. They cost 4.48 points
    between them and share this trigger exactly: both are the work a salesperson
    does once the job is understood, and both must stand down for the customer
    who has already narrowed. One directive rather than three keeps the "at most
    one question" bound shared, which is what stops the reply becoming an
    interrogation.

    Rule 11 arrives here in its honest form only. A discount is a commercial
    commitment nobody has authorised and the sibling directive forbids one
    outright; a package of verified rows quoted at their combined total commits
    nothing, and is what the source guideline asks for on a comprehensive order.

    **Two escape clauses removed on 2026-08-08, after the first live run.** The
    `a830001` measurement found the value proposition and the company question
    in **0 of 26** transcripts -- not partial compliance, total absence -- while
    rules 11 and 15 moved on the same run. The difference was in the wording, and
    both faults were mine:

    - "If you have not already said it in this conversation, say what Treejar
      is" was self-cancelling. `src/llm/opening_guard.py` prepends
      "Hello, I'm Noor from Treejar." to every first turn, so the model has
      already named Treejar in the same reply the directive is asking it to. The
      condition is satisfied before it is read. Naming the company and saying
      what it offers are now stated as different acts.
    - "Keep the whole reply to at most one question ... or leave it for the next
      turn" permanently starved rule 13. There is always a more urgent product
      question, so the company question was always the one deferred, every turn.
      It now rides in the same sentence, counted as one question, which is how a
      salesperson asks it anyway.

    The bound itself stays: the transcripts are not interrogations, and that is
    the bound working.

    **`opening_states_the_offer`, added 2026-08-12 after `tj-fcv8`.** The
    escape clause above was removed because the anchor was
    "Hello, I'm Noor from Treejar." and nothing more, so naming the company and
    saying what it does really were different acts. `_EN_CAPABILITY` was later
    added to that anchor and this sentence was never told. The measured round
    of 2026-08-12 shows the cost: 18 of 20 replies say the line of business
    twice, and three of them say it as a lower-case fragment copied from the
    example clause below.

    The caller decides, because the caller knows whether the deterministic
    opening will be prepended to this reply. That is the difference from the
    self-cancelling condition of 2026-08-08: this is not the model judging what
    it has already said, it is code stating what the reply will begin with.

    **The product menu, `tj-fcfn`, added 2026-08-13.** Rule 5 fell three
    readings running on the frozen twenty, 1.85 to 1.70 to 1.45 of 2, and the
    losing replies all had one shape: the single question offered a list of
    what we sell. "Find out what the furniture is for" was already here and was
    not enough, because it described the target without forbidding the miss --
    the same failure mode as the value proposition before it and the name ask
    before that.

    The reading separates the two cleanly. Every reply scoring 2 offered
    choices that were kinds of work or kinds of space: individual workstations
    against a meeting room, files in a staff area against a client-facing one,
    collaboration against privacy. Every reply scoring 1 offered choices that
    were catalog categories. So the instruction is stated on the options
    themselves, which is the part the model actually writes.

    It is stated positively, with no prohibition, under the owner's observation
    of 2026-08-10 that this model follows a positive instruction and loses a
    ban -- the observation that took rule 11 out of two prohibitions wrapped
    around a permission, and that
    `test_the_widening_is_a_package_at_the_catalog_price` guards by asserting
    this directive contains no "never" at all. Saying "a list of products is
    wrong" is the wording that has already been measured at 0.00.

    It lives here rather than in the product system prompt, which the stage
    contract freezes.
    """

    offer_clause = (
        "This reply already opens with a sentence saying that Treejar supplies "
        "office furniture in the UAE and quotes from its own catalog with "
        "confirmed prices and stock. That discharges what Treejar offers. Do "
        "not say it again in any words, and do not begin with a fragment of "
        "it: spend the reply on what the opening does not cover."
        if opening_states_the_offer
        else "In this reply, in one short clause, say what Treejar offers: an "
        "office furniture supplier in the UAE quoting from its own catalog "
        "with confirmed prices and stock. The greeting names Treejar but does "
        "not say what Treejar does, so it does not discharge this."
    )
    return (
        "You are still building this sale, so do the things a salesperson does "
        f"besides answering. {offer_clause} If they have described a team or a "
        "workplace, ask what their company does -- in the same sentence as "
        "whatever else you need to know. Knowing the company's name is not "
        "knowing its line of work, so a name they gave you does not answer "
        "this. A question folded that way counts as one question, so it rides "
        "in this reply. Find out what the "
        "furniture is for -- the work done in the space, who uses it, what "
        "would make the result right -- and recommend against that job rather "
        "than against the words of the request. Where you offer them options "
        "inside that question, make the options kinds of work or kinds of "
        "space -- one person's desk, a room people meet in, a reception "
        "visitors wait in. Someone who has not yet said what they need can "
        "answer that, and their answer is what tells you which products to "
        "bring. Keep the whole reply to at most "
        "one question, counting a folded pair as one. None of this comes before "
        "answering what they asked. State a service, term or capability where a "
        "tool in this run has confirmed it, and quote every figure at the "
        "catalog price."
    )


_SOLUTION_STAGES = frozenset({"solution"})


def earns_solution_consultation(customer_text: str, *, sales_stage: str) -> bool:
    """Is this the turn where the products are presented?

    Same shape and the same stand-down as `earns_consultative_opening`, one
    stage later. The opening directive stops at `needs_analysis`, and the
    presentation is where the six judge readings in `tj-2m5m.4` all land: "the
    conversation is entirely product-centric", "only restates the product
    details. No delivery, installation, complementary products", and a customer
    who asked for workstations and chairs being answered about chairs.

    A customer who has narrowed to one exact item is still left alone, exactly
    as they are at the opening. Widening a request that was deliberately
    narrowed is friction, not expertise, wherever in the conversation it
    happens.
    """

    text = str(customer_text)
    if not text.strip():
        return False
    if sales_stage.strip().casefold() not in _SOLUTION_STAGES:
        return False
    return not _TRANSACTIONAL_NARROWING_RE.search(text)


def solution_consultation_directive() -> str:
    """Present a solution to the job, not a list of what was named.

    Rules 9 and 10 cost 5.10 points between them and are the largest genuinely
    open loss in the acceptance set. The opening directive already carries them
    for the early stages; nothing carried them here, which is why S08 could run
    four assistant turns that were each a bulleted echo of the requirement just
    stated.

    Two bounds keep it from becoming an interrogation or a sales pitch. It adds
    no second question, because the reply that already asks one is doing its
    job. And a complementary item is named only where a tool confirmed it this
    turn: the loss this repairs is silence, and inventing a service to fill it
    would be a worse answer than the silence was.

    It lives here rather than in the product system prompt, which the stage
    contract freezes.
    """

    return (
        "You are presenting a solution, which is more than listing back what "
        "they named. Cover everything they asked for, not only the first item. "
        "If you still do not know what the space is for -- the work done "
        "there, who uses it, what would make the result right -- ask that, in "
        "one short question, and recommend against that job rather than "
        "against the words of the request. If you do know it, name one "
        "complementary item or service that belongs with this job and say why "
        "it belongs. Look it up with search_products first and give its "
        "confirmed price and stock; if nothing this turn has confirmed it, "
        "leave it out rather than describing it. Never invent a service, a "
        "term or a figure, and never offer a discount. If this reply already "
        "asks a question, do not add a second one."
    )


_PROJECT_SCALE_RE = re.compile(
    r"(?:\bnew\s+office\b|\bnew\s+floor\b|\bfit[\s-]?out\b|\brelocat\w*\b"
    r"|\bmoving\s+(?:to|into)\b|\bmove[\s-]?in\b|\bwhole\s+office\b"
    r"|\bfull\s+office\b|\bentire\s+(?:office|floor)\b|\boffice\s+setup\b"
    r"|\btender\b|\bboq\b|\bbill\s+of\s+quantities\b|\bfloor\s+plan\b"
    r"|\bturnkey\b|\bhandover\b|\bfurnish(?:ing)?\s+(?:a|an|our|the)\b"
    r"|مكتب\s+جديد|تجهيز\s+مكتب|مناقصة)",
    re.IGNORECASE,
)

_PROJECT_QUANTITY_RE = re.compile(
    r"\b(\d{2,4})\s*(?:x\s*)?"
    r"(?:pcs|pieces|units|seats?|people|persons?|staff|employees?|desks?|"
    r"chairs?|workstations?|كرسي|كراسي|موظف|شخص)\b",
    re.IGNORECASE,
)

PROJECT_QUANTITY_THRESHOLD = 20


def signals_a_project(customer_text: str) -> bool:
    """Is this a fit-out rather than a shopping trip?

    Both research reports of 2026-08-09 reached the same conclusion
    independently: one opening for everyone, then a fork, because a 7-unit
    order and a 100-unit project want opposite handling. Widening the request
    is expertise on one and friction on the other.

    Deliberately "quantity **or** complexity", never a magic number alone --
    report B is explicit that seven executive desks for a new room can need
    more consultation than thirty replacement chairs. The threshold of 20 is a
    starting hypothesis against a measured median of 7, to be moved once enough
    conversations have outcomes attached, not a discovered constant.
    """

    text = str(customer_text)
    if not text.strip():
        return False
    if _PROJECT_SCALE_RE.search(text):
        return True
    return any(
        int(match.group(1)) >= PROJECT_QUANTITY_THRESHOLD
        for match in _PROJECT_QUANTITY_RE.finditer(text)
    )


def project_consultation_directive() -> str:
    """Widen the sale -- but only where widening is wanted.

    This used to live inside `consultative_opening_directive` and fire on every
    early turn, including the seven-chair orders where both reports call it
    friction rather than expertise. It now needs a project signal.
    """

    return (
        "This is a fit-out, not a single purchase, so the job is to get the "
        "whole space working rather than to answer one line of it. Say one "
        "short line acknowledging what they are building, in their own terms "
        "and without flattery -- a new office is worth a sentence, an order of "
        "chairs is not. Do not stop "
        "at the item they named: name the one piece the setup is missing that "
        "matters most, look it up with search_products first, and give its "
        "confirmed price and stock. One piece, not a list. Where their project "
        "spans several kinds of furniture, put the pieces together as one "
        "package and state their combined total from those same verified rows. "
        "Quote every figure at the catalog price. On a quantity this size, "
        "availability for "
        "the whole order matters more than the lowest unit price: say plainly "
        "if stock covers it, and if it does not, say what does."
    )


_QUOTATION_WORD = r"(?:quotation|quote|proforma|offer)"

_RESUME_VERB = (
    r"(?:pick\s+(?:this|it)\s+up|revisit|reconnect|touch\s+base|speak|talk"
    r"|circle\s+back|follow\s+up|decide|order|buy)"
)

_DECISION_DEFERRED_RE = re.compile(
    r"(?:\bnot\s+ready\b|\bnot\s+(?:buying|purchasing|ordering)\b"
    r"|\bnot\s+yet\s+(?:ready|buying|ordering|deciding)\b"
    r"|\bno\s+rush\b|\bin\s+no\s+hurry\b"
    r"|\bhold\s+off\b|\bput\s+(?:this|it)\s+on\s+hold\b"
    r"|\b(?:need\s+to\s+)?think\s+(?:it\s+over|about\s+it)\b"
    r"|\b(?:discuss|review|check)\s+(?:it\s+)?(?:internally|with\s+(?:my|the)\s+"
    r"(?:team|manager|management|board|partner|partners))\b"
    r"|\b(?:get|come)\s+back\s+to\s+you\b"
    r"|\bwaiting\s+for\s+(?:budget\s+)?approval\b|\bbudget\s+is\s+not\s+approved\b"
    # A decision placed in the future is a deferral however calmly it is put.
    r"|\bdecision\s+(?:is\s+)?expected\b|\bwe\s+(?:will\s+)?decide\s+(?:with)?in\b"
    r"|\bdecision\s+(?:with)?in\s+\w+\s+(?:days?|weeks?|months?)\b"
    # A date alone says nothing: "we need 20 chairs next week" is a deadline,
    # not a deferral. Only a date the customer attaches to talking again counts.
    rf"|\b{_RESUME_VERB}(?:\s+\w+){{0,3}}\s+(?:next|later\s+this)\s+"
    r"(?:week|month|quarter)\b"
    r"|لسنا\s+مستعدين|سنعود\s+إليك)",
    re.IGNORECASE,
)

_QUOTE_DOCUMENT_DECLINED_RE = re.compile(
    rf"\bdo\s+not\s+create\s+a\s+{_QUOTATION_WORD}\b"
    # "the no-quotation instruction" is the same refusal, restated.
    rf"|\bno[\s-]+{_QUOTATION_WORD}\b|\bwithout\s+a\s+{_QUOTATION_WORD}\b"
    r"|لا\s+نريد\s+عرض\s+سعر|بدون\s+عرض\s+سعر",
    re.IGNORECASE,
)


def defers_the_decision(customer_text: str) -> bool:
    """Has the customer said, in some form, "not now"?

    Deliberately narrower than `defers_the_purchase`: refusing the paperwork is
    not the same as refusing to buy. S05, S06 and S08 all say some form of "no
    quotation" while actively pricing an order, and the source guideline
    conditions rule 15 on the customer not being *ready for the deal* -- "если
    клиент не готов к сделке" -- not on whether they wanted a document. Charging
    the rule on a paperwork refusal marked three scenarios down for obeying.
    """

    text = str(customer_text)
    if not text.strip():
        return False
    return bool(_DECISION_DEFERRED_RE.search(text))


def declines_a_quotation_document(customer_text: str) -> bool:
    """Has the customer refused the paperwork, whatever they think of the deal?"""

    text = str(customer_text)
    if not text.strip():
        return False
    return bool(_QUOTE_DOCUMENT_DECLINED_RE.search(text))


def defers_the_purchase(customer_text: str) -> bool:
    """Either signal, for the dialogue side.

    The directive is allowed the looser reading. A customer who declines the
    document today is worth a proposed next contact even if they are still
    pricing, because the conversation otherwise ends on nothing. The rubric is
    not allowed the looser reading, which is what `defers_the_decision` is for.
    """

    return defers_the_decision(customer_text) or declines_a_quotation_document(
        customer_text
    )


def next_contact_directive() -> str:
    """Close the turn on a date, not on an open ending.

    Deliberately narrow: it proposes a time and asks the customer to confirm
    it. Writing anything into a calendar is a tool call the runtime owns, and
    a promise about a follow-up nobody scheduled is exactly the unverified
    commitment the contract exists to stop.
    """

    return (
        "The customer has told you they are not buying today. Do not leave the "
        "conversation open-ended: propose one specific time to speak again -- a "
        "named day, and a morning or afternoon -- and ask them to confirm it "
        "or name a better one. Say in one clause what you will bring to it, "
        "and keep it to something you can actually deliver from the catalog. "
        "Do not claim anything has been scheduled, booked or entered anywhere "
        "unless a tool call in this conversation did it."
    )


def substantive_reply_directive() -> str:
    """Never send a turn that only says what the customer already said.

    The defect this answers is visible without a judge. In S08 the customer
    opens with a restriction -- "do not create a quotation" -- and three of the
    four assistant turns that follow are a bulleted restatement of the
    customer's own requirement, with no product, no price and no question. The
    closing turn proposes as the customer's next step ("verify whether three
    units fit within AED 6,000") an action Noor holds the tools to perform. The
    behaviour is identical in both stored builds, so it is a standing defect
    rather than sampling noise.

    Two failures, one cause: obedience generalised past what was asked. A ban on
    a quotation became a ban on selling. This directive applies to every turn,
    including the narrowed ones the consultative directive stands down on --
    a customer who wants one exact price still deserves that price rather than a
    summary of their own message.

    **"Whole content" was the escape clause, removed 2026-08-08.** S08 survived
    this directive on the `a830001` run, and the audit found why: its turns are a
    restatement *plus* a sentence of intent ("I'll keep these details in mind"),
    so the restatement was never the *whole* content and the prohibition never
    bound. The test is now what the reply adds, not what it consists of --
    padding a summary with a promise does not make it a reply.
    """

    return (
        "Obey the restriction the customer actually stated and nothing wider. A "
        "customer who rules out a quotation has not ruled out prices, stock, "
        "products or advice; a customer who narrows you to certain categories "
        "still wants the items inside them named. Every reply must add at least "
        "one thing the customer did not already have: a verified product, a "
        "confirmed price or stock figure, a fact about delivery or terms, or a "
        "question. Restating what they told you and promising what you intend "
        "to do are not additions, and adding one to the other does not make "
        "one: a reply built only from those two must not be sent. "
        "If the next step is something your tools can do now -- look a product "
        "up, confirm a price or stock, check a total against their budget -- do "
        "it in this reply instead of handing it back to them as their next "
        "step. Every figure you give still comes from a row you verified this "
        "turn."
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
