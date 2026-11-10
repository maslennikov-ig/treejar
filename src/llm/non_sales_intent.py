"""Recognise customer messages that are not furniture sales enquiries.

A job seeker or a supplier writing to the sales line is not a lead, but a
person should still see the message: the pilot dialogue of 2026-11-05 with a
furniture technician's CV ended with no human ever learning of it. The runtime
alerts a manager without pausing Noor (``message_processor``).
"""

from __future__ import annotations

import re
from typing import Literal

NonSalesIntent = Literal["recruitment", "supplier_pitch"]

# Attachment notes ("[The customer sent a document ... It contains: a CV ...]")
# are part of the text on purpose: a CV sent as a PDF is the common case.
_RECRUITMENT_RE = re.compile(
    r"\bcv\b|\bresum(?:e|es|é)\b|curriculum\s+vitae|\bvacanc(?:y|ies)\b"
    r"|\bjob\s+(?:application|vacanc(?:y|ies)|opening|opportunit(?:y|ies))\b"
    r"|\b(?:looking|searching|seeking|apply(?:ing)?)\s+for\s+(?:a\s+|any\s+)?"
    r"(?:job|work|position|employment)\b"
    r"|\bseeking\s+(?:[a-z]+\s+){0,3}(?:job|work|tasks|position|role|employment)\b"
    r"|\b\d{1,2}\s*\+?\s*years?\s+(?:of\s+)?experience\b"
    r"|\bapply\s+for\s+(?:a|the|this|any)\s+(?:position|role|vacancy|job)\b"
    r"|\binternship\b|\bjob\s+seeker\b"
    r"|سيرة\s*ذاتية|وظيفة|وظائف|توظيف|أبحث\s+عن\s+عمل",
    re.IGNORECASE | re.UNICODE,
)
_SUPPLIER_PITCH_RE = re.compile(
    r"\bwe\s+are\s+(?:a\s+|an\s+|the\s+)?(?:leading\s+)?"
    r"(?:manufacturer|supplier|distributor|factory|vendor|exporter)s?\b"
    r"|\bour\s+(?:factory|company)\s+(?:manufactures|produces|supplies)\b"
    r"|\bbecome\s+(?:your|a)\s+(?:supplier|vendor|partner)\b"
    r"|\bregister\s+(?:us|our\s+company)\s+as\s+(?:a\s+)?(?:supplier|vendor)\b"
    r"|\bvendor\s+registration\b"
    r"|\bfurniture\s+supply\s+from\b"
    r"|\bsupply(?:ing)?\s+(?:office\s+)?furniture\s+(?:from|to\s+your)\b",
    re.IGNORECASE | re.UNICODE,
)


def non_sales_intent(customer_text: str | None) -> NonSalesIntent | None:
    """Return the non-sales purpose stated in *customer_text*, if any."""
    text = str(customer_text or "")
    if not text.strip():
        return None
    if _RECRUITMENT_RE.search(text):
        return "recruitment"
    if _SUPPLIER_PITCH_RE.search(text):
        return "supplier_pitch"
    return None
