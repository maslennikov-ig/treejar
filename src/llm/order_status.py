"""Order status mapping: Zoho CRM stages and Inventory statuses → customer-friendly labels."""

from __future__ import annotations

from typing import Any

# CRM Deal Stage → (EN, AR) labels
DEAL_STAGE_MAP: dict[str, tuple[str, str]] = {
    "New Lead": ("Order received", "تم استلام الطلب"),
    "Qualification": ("Processing your order", "يتم معالجة طلبك"),
    "Order Confirmed": ("Confirmed, preparing", "تم التأكيد، جاري التحضير"),
    "Consignment": ("In transit", "في الطريق"),
    "Order Collected": ("Delivered", "تم التسليم"),
    "Closed Won": ("Delivered", "تم التسليم"),
    "Closed Lost": ("Order cancelled", "تم إلغاء الطلب"),
}

# Inventory Sale Order Status → (EN, AR) labels
INVENTORY_STATUS_MAP: dict[str, tuple[str, str]] = {
    "draft": ("Quotation stage", "مرحلة عرض الأسعار"),
    "confirmed": ("Confirmed, preparing", "تم التأكيد، جاري التحضير"),
    "fulfilled": ("Shipped / Delivered", "تم الشحن / التسليم"),
    "void": ("Cancelled", "ملغي"),
}


def _lang_index(language: str) -> int:
    """Return 0 for EN, 1 for AR."""
    return 1 if language.lower().startswith("ar") else 0


def get_deal_stage_label(stage: str, language: str) -> str:
    """Map a Zoho CRM deal stage to a customer-friendly label."""
    idx = _lang_index(language)
    if stage in DEAL_STAGE_MAP:
        return DEAL_STAGE_MAP[stage][idx]
    # Fallback for unknown/custom stages
    if idx == 1:
        return f"حالة الطلب: {stage}"
    return f"Order status: {stage}"


def get_inventory_status_label(status: str, language: str) -> str:
    """Map a Zoho Inventory sale order status to a customer-friendly label."""
    idx = _lang_index(language)
    if status in INVENTORY_STATUS_MAP:
        return INVENTORY_STATUS_MAP[status][idx]
    if idx == 1:
        return f"حالة الطلب: {status}"
    return f"Order status: {status}"


def format_order_status(
    deal_data: dict[str, Any] | None,
    order_data: dict[str, Any] | None,
    language: str,
) -> str:
    """Combine CRM deal and Inventory order data into a human-readable status message."""
    is_ar = _lang_index(language) == 1

    if not deal_data and not order_data:
        if is_ar:
            return "لم يتم العثور على طلب مرتبط بهذه المحادثة."
        return "No order found linked to this conversation."

    # Localized label templates
    labels = (
        {
            "order": "الطلب",
            "deal_status": "حالة الصفقة",
            "so_number": "رقم الطلب",
            "ship_status": "حالة الشحن",
            "ship_date": "تاريخ الشحن",
            "delivery": "طريقة التوصيل",
        }
        if is_ar
        else {
            "order": "Order",
            "deal_status": "Deal status",
            "so_number": "Sale Order",
            "ship_status": "Shipment status",
            "ship_date": "Shipment date",
            "delivery": "Delivery method",
        }
    )

    parts: list[str] = []

    # CRM Deal info
    if deal_data:
        stage = deal_data.get("Stage", "")
        label = get_deal_stage_label(stage, language) if stage else ""
        deal_name = deal_data.get("Deal_Name", "")

        if deal_name:
            parts.append(f"{labels['order']}: {deal_name}")
        if label:
            parts.append(f"{labels['deal_status']}: {label}")

    # Inventory Sale Order info
    if order_data:
        so_number = order_data.get("salesorder_number", "")
        status = order_data.get("status", "")
        label = get_inventory_status_label(status, language) if status else ""
        shipment_date = order_data.get("shipment_date", "")
        delivery_method = order_data.get("delivery_method", "")

        if so_number:
            parts.append(f"{labels['so_number']}: {so_number}")
        if label:
            parts.append(f"{labels['ship_status']}: {label}")
        if shipment_date:
            parts.append(f"{labels['ship_date']}: {shipment_date}")
        if delivery_method:
            parts.append(f"{labels['delivery']}: {delivery_method}")

    return "\n".join(parts)
