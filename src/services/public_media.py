from __future__ import annotations

from urllib.parse import quote, urlencode

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from src.core.config import settings

_CANONICAL_BASE_URL = "https://noor.starec.ai"
_PRODUCT_MEDIA_SIGNING_SALT = "product-media-v1"


def _public_base_url() -> str:
    domain = settings.domain.strip()
    if not domain:
        return _CANONICAL_BASE_URL
    if domain.startswith(("http://", "https://")):
        return domain.rstrip("/")
    return f"https://{domain}".rstrip("/")


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        secret_key=settings.app_secret_key,
        salt=_PRODUCT_MEDIA_SIGNING_SALT,
    )


def sign_product_image_token(zoho_item_id: str) -> str:
    payload = {"item_id": zoho_item_id}
    return str(_serializer().dumps(payload))


def verify_signed_product_image_token(
    token: str,
    zoho_item_id: str,
    ttl_seconds: int,
) -> bool:
    if ttl_seconds <= 0:
        return False

    try:
        payload = _serializer().loads(token, max_age=ttl_seconds)
    except (BadSignature, SignatureExpired):
        return False

    if not isinstance(payload, dict):
        return False

    signed_item_id = payload.get("item_id")
    return isinstance(signed_item_id, str) and signed_item_id == zoho_item_id


def build_signed_product_image_url(zoho_item_id: str) -> str:
    safe_item_id = quote(zoho_item_id, safe="")
    query = urlencode({"token": sign_product_image_token(zoho_item_id)})
    return f"{_public_base_url()}/api/v1/public-media/products/{safe_item_id}?{query}"
