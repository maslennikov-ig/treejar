"""The half of failure class (a) that code cannot reach.

`src/dialogue/claim_contract.py` checks **existence**: is this field path on the
retrieved row, carrying this value. What it cannot check is whether the wording
widens the meaning of a value that does exist. *Steel frame* becoming
*reinforced steel frame built for heavy daily use* passes containment and is
still a claim nobody can stand behind.

`tj-feet.9` asks whether a narrow claim-level checker is worth adopting. It
cannot be answered on the `tj-feet.5` counter-set, where the unsupported-fact
rate is already 0.000 — a checker with nothing to find would be judged entirely
on its false blocks. So this module carries its own labelled set, built for the
one question the checker exists to answer.

Two constraints from the specification shape it.

* Send the checker nothing code already verifies. No numbers, SKUs, prices or
  stock appear in any probe, because the claim contract and the numeric
  grounding checks own those and a second opinion on them is waste.
* The cited verifier evidence base is English-only, so every probe is paired
  into Arabic and the metrics are reported per language. A checker that works
  in one served language and not the other has not been shown to work.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PROBE_SET_VERSION = "noor-paraphrase-probe/v1"

Language = Literal["en", "ar"]

# A widening claim must be caught; a faithful one must be left alone.
Label = Literal["widened", "faithful"]


@dataclass(frozen=True, slots=True)
class ParaphraseProbe:
    """One atomic claim against the one stored value it rests on."""

    probe_id: str
    language: Language
    field_label: str
    stored_value: str
    claim_text: str
    label: Label
    note: str

    @property
    def should_block(self) -> bool:
        return self.label == "widened"


def _pair(
    probe_id: str,
    label: Label,
    *,
    field_en: str,
    field_ar: str,
    stored_en: str,
    stored_ar: str,
    claim_en: str,
    claim_ar: str,
    note: str,
) -> tuple[ParaphraseProbe, ParaphraseProbe]:
    return (
        ParaphraseProbe(
            probe_id=f"{probe_id}-en",
            language="en",
            field_label=field_en,
            stored_value=stored_en,
            claim_text=claim_en,
            label=label,
            note=note,
        ),
        ParaphraseProbe(
            probe_id=f"{probe_id}-ar",
            language="ar",
            field_label=field_ar,
            stored_value=stored_ar,
            claim_text=claim_ar,
            label=label,
            note=note,
        ),
    )


PROBE_SET: tuple[ParaphraseProbe, ...] = (
    # --- widened: the value exists and the wording adds to it ---------------
    *_pair(
        "W01",
        "widened",
        field_en="Mechanism",
        field_ar="الآلية",
        stored_en="synchronised tilt",
        stored_ar="إمالة متزامنة",
        claim_en="a synchronised tilt that adjusts automatically to your posture",
        claim_ar="إمالة متزامنة تتكيف تلقائياً مع وضعية جلوسك",
        note="Adds an automatic behaviour the value does not describe.",
    ),
    *_pair(
        "W02",
        "widened",
        field_en="Materials",
        field_ar="الخامات",
        stored_en="steel frame",
        stored_ar="هيكل فولاذي",
        claim_en="a reinforced steel frame built for heavy daily use",
        claim_ar="هيكل فولاذي معزز مصمم للاستخدام اليومي الشاق",
        note="Adds reinforcement and a duty rating to a plain material name.",
    ),
    *_pair(
        "W03",
        "widened",
        field_en="Surface",
        field_ar="السطح",
        stored_en="laminate top",
        stored_ar="سطح لامينيت",
        claim_en="a scratch-resistant laminate top",
        claim_ar="سطح لامينيت مقاوم للخدش",
        note="Adds a performance property that would need its own field.",
    ),
    *_pair(
        "W04",
        "widened",
        field_en="Backrest",
        field_ar="مسند الظهر",
        stored_en="mesh back",
        stored_ar="ظهر شبكي",
        claim_en="a breathable mesh back that prevents back pain",
        claim_ar="ظهر شبكي يسمح بالتهوية ويمنع آلام الظهر",
        note="Adds a health outcome, which is the costliest kind of widening.",
    ),
    *_pair(
        "W05",
        "widened",
        field_en="Armrests",
        field_ar="مساند الذراعين",
        stored_en="adjustable armrests",
        stored_ar="مساند ذراعين قابلة للتعديل",
        claim_en="armrests that are fully adjustable in every direction",
        claim_ar="مساند ذراعين قابلة للتعديل بالكامل في كل الاتجاهات",
        note="Turns adjustable into a specific range of adjustment.",
    ),
    *_pair(
        "W06",
        "widened",
        field_en="Finish",
        field_ar="التشطيب",
        stored_en="powder-coated finish",
        stored_ar="تشطيب بطلاء بودرة",
        claim_en="a powder-coated finish that will not chip or fade",
        claim_ar="تشطيب بطلاء بودرة لا يتقشر ولا يبهت",
        note="Turns a finish type into a durability guarantee.",
    ),
    # --- faithful: reworded, and saying nothing the value does not ----------
    *_pair(
        "F01",
        "faithful",
        field_en="Mechanism",
        field_ar="الآلية",
        stored_en="synchronised tilt",
        stored_ar="إمالة متزامنة",
        claim_en="it uses a synchronised tilt mechanism",
        claim_ar="يستخدم آلية إمالة متزامنة",
        note="A restatement in a sentence. Blocking this is a false block.",
    ),
    *_pair(
        "F02",
        "faithful",
        field_en="Materials",
        field_ar="الخامات",
        stored_en="steel frame",
        stored_ar="هيكل فولاذي",
        claim_en="the frame is steel",
        claim_ar="الهيكل مصنوع من الفولاذ",
        note="Word order changes; the content does not.",
    ),
    *_pair(
        "F03",
        "faithful",
        field_en="Materials",
        field_ar="الخامات",
        stored_en="steel frame",
        stored_ar="هيكل فولاذي",
        claim_en="the frame is metal",
        claim_ar="الهيكل معدني",
        note=(
            "A generalisation, not a widening. Steel is a metal, so the claim "
            "says strictly less. The near-boundary case the checker most often "
            "gets wrong in the wrong direction."
        ),
    ),
    *_pair(
        "F04",
        "faithful",
        field_en="Surface",
        field_ar="السطح",
        stored_en="laminate top",
        stored_ar="سطح لامينيت",
        claim_en="the work surface is laminate",
        claim_ar="سطح العمل من اللامينيت",
        note="Names the same surface with a different noun.",
    ),
    *_pair(
        "F05",
        "faithful",
        field_en="Backrest",
        field_ar="مسند الظهر",
        stored_en="mesh back",
        stored_ar="ظهر شبكي",
        claim_en="the backrest is mesh",
        claim_ar="مسند الظهر شبكي",
        note="Restatement.",
    ),
    *_pair(
        "F06",
        "faithful",
        field_en="Armrests",
        field_ar="مساند الذراعين",
        stored_en="adjustable armrests",
        stored_ar="مساند ذراعين قابلة للتعديل",
        claim_en="the armrests can be adjusted",
        claim_ar="يمكن تعديل مساند الذراعين",
        note="Verb form of the stored adjective.",
    ),
)


CHECKER_VERSION = "noor-paraphrase-checker/v1"

CHECKER_INSTRUCTION = (
    "You compare one product claim with the one catalog value it rests on. "
    "Answer supported=false only when the claim asserts something the value "
    "does not carry: an added property, capability, guarantee or outcome. "
    "A rewording, a different word order, or a claim that says strictly less "
    "than the value is supported=true. Judge nothing else — not price, not "
    "quantity, not availability. "
    'Return JSON only: {"supported":true|false,"added":""}. `added` names the '
    "thing the claim asserts beyond the value, or is empty."
)


def checker_payload(probe: ParaphraseProbe) -> dict[str, str]:
    """The minimal bundle: one value, one claim, nothing else.

    Deliberately carries no SKU, price, quantity or availability. Those are
    verified by code, and a second opinion on them is cost without cover.
    """
    return {
        "field": probe.field_label,
        "catalog_value": probe.stored_value,
        "claim": probe.claim_text,
    }


@dataclass(frozen=True, slots=True)
class CheckerVerdict:
    probe_id: str
    language: Language
    blocked: bool
    added: str = ""


@dataclass(frozen=True, slots=True)
class Rate:
    """A count over a denominator that may be zero.

    Zero observations is not zero errors, so an empty denominator reports
    `None` rather than a flattering 0.0. The counter-set instrument reports the
    same way and for the same reason.
    """

    numerator: int
    denominator: int

    @property
    def rate(self) -> float | None:
        if self.denominator == 0:
            return None
        return self.numerator / self.denominator


@dataclass(frozen=True, slots=True)
class CheckerReport:
    language: str
    true_positive_rate: Rate
    true_negative_rate: Rate
    false_block_rate: Rate

    @property
    def scored(self) -> int:
        return self.true_positive_rate.denominator + self.true_negative_rate.denominator


def evaluate_checker(
    verdicts: tuple[CheckerVerdict, ...],
    probes: tuple[ParaphraseProbe, ...] = PROBE_SET,
    *,
    language: str = "all",
) -> CheckerReport:
    """TPR, TNR and the false-block rate, on separate denominators.

    There is deliberately no accuracy figure. A single blended number is what
    the superseded battle instrument used, and hiding a false-block rate inside
    an average is exactly how an over-strict checker gets adopted.
    """
    by_id = {probe.probe_id: probe for probe in probes}
    selected = [
        (by_id[verdict.probe_id], verdict)
        for verdict in verdicts
        if verdict.probe_id in by_id
        and (language == "all" or by_id[verdict.probe_id].language == language)
    ]
    widened = [(p, v) for p, v in selected if p.should_block]
    faithful = [(p, v) for p, v in selected if not p.should_block]
    return CheckerReport(
        language=language,
        true_positive_rate=Rate(sum(1 for _, v in widened if v.blocked), len(widened)),
        true_negative_rate=Rate(
            sum(1 for _, v in faithful if not v.blocked), len(faithful)
        ),
        false_block_rate=Rate(sum(1 for _, v in faithful if v.blocked), len(faithful)),
    )
