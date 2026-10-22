"""Public Treejar product page links for catalog rows (`tj-asty.3`).

Kept out of ``src/models/product.py`` on purpose: that file is bound whole into
the corpus-bridge retrieval-contract digest, and a link helper changes nothing
retrieval returns, so it must not strand the stored evidence.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

TREEJAR_PRODUCT_URL_PREFIX = "https://treejartrading.ae/product/"
_TREEJAR_HOST_RE = re.compile(
    r"^https?://(?:www\.|new\.)?treejartrading\.ae(?P<path>/product/[^\s?#]+)",
    re.IGNORECASE,
)
_SLUG_SAFE_RE = re.compile(r"^[a-z0-9][a-z0-9\-_.]*$", re.IGNORECASE)
_SLUGIFY_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    return _SLUGIFY_RE.sub("-", text.casefold()).strip("-")


def product_canonical_url(product: Any) -> str | None:
    """The public Treejar product page for a catalog row, or ``None``.

    Every row the Treejar sync writes carries ``treejar_url`` and
    ``treejar_slug`` (``src/integrations/inventory/sync.py``). The staging host
    ``new.treejartrading.ae`` is folded onto the public one. A row whose
    attributes are a mapping without a slug gets no link: a guessed URL that
    404s is worse than none. Only a row with no attributes at all -- the pinned
    snapshot the scenario replay uses -- falls back to a slug of its name.
    """

    attributes = getattr(product, "attributes", None)
    if isinstance(attributes, Mapping):
        url = attributes.get("treejar_url")
        if isinstance(url, str) and (match := _TREEJAR_HOST_RE.match(url.strip())):
            return f"https://treejartrading.ae{match.group('path')}"
        slug = attributes.get("treejar_slug")
        if isinstance(slug, str) and _SLUG_SAFE_RE.match(slug.strip()):
            return f"{TREEJAR_PRODUCT_URL_PREFIX}{slug.strip()}"
        return None
    if attributes is not None:
        return None
    name = getattr(product, "name_en", None)
    slug = _slugify(name) if isinstance(name, str) else ""
    return f"{TREEJAR_PRODUCT_URL_PREFIX}{slug}" if slug else None
