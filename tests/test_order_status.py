"""Unit tests for the order status mapping module."""

from __future__ import annotations

import pytest

from src.llm.order_status import (
    format_order_status,
    get_deal_stage_label,
    get_inventory_status_label,
)


class TestDealStageMapping:
    """Tests for CRM deal stage → customer-friendly label mapping."""

    @pytest.mark.unit
    def test_qualification_en(self) -> None:
        assert get_deal_stage_label("Qualification", "en") == "Processing your order"

    @pytest.mark.unit
    def test_qualification_ar(self) -> None:
        assert get_deal_stage_label("Qualification", "ar") == "يتم معالجة طلبك"

    @pytest.mark.unit
    def test_new_lead_en(self) -> None:
        assert get_deal_stage_label("New Lead", "en") == "Order received"

    @pytest.mark.unit
    def test_order_confirmed_en(self) -> None:
        assert get_deal_stage_label("Order Confirmed", "en") == "Confirmed, preparing"

    @pytest.mark.unit
    def test_order_confirmed_ar(self) -> None:
        assert get_deal_stage_label("Order Confirmed", "ar") == "تم التأكيد، جاري التحضير"

    @pytest.mark.unit
    def test_consignment_en(self) -> None:
        assert get_deal_stage_label("Consignment", "en") == "In transit"

    @pytest.mark.unit
    def test_consignment_ar(self) -> None:
        assert get_deal_stage_label("Consignment", "ar") == "في الطريق"

    @pytest.mark.unit
    def test_closed_won_en(self) -> None:
        assert get_deal_stage_label("Closed Won", "en") == "Delivered"

    @pytest.mark.unit
    def test_closed_lost_en(self) -> None:
        assert get_deal_stage_label("Closed Lost", "en") == "Order cancelled"

    @pytest.mark.unit
    def test_unknown_stage_en(self) -> None:
        """Unknown stages should return a generic message with the stage name."""
        result = get_deal_stage_label("Some Custom Stage", "en")
        assert "Some Custom Stage" in result


class TestInventoryStatusMapping:
    """Tests for Zoho Inventory status → customer-friendly label mapping."""

    @pytest.mark.unit
    def test_draft_en(self) -> None:
        assert get_inventory_status_label("draft", "en") == "Quotation stage"

    @pytest.mark.unit
    def test_confirmed_en(self) -> None:
        assert get_inventory_status_label("confirmed", "en") == "Confirmed, preparing"

    @pytest.mark.unit
    def test_fulfilled_en(self) -> None:
        assert get_inventory_status_label("fulfilled", "en") == "Shipped / Delivered"

    @pytest.mark.unit
    def test_void_en(self) -> None:
        assert get_inventory_status_label("void", "en") == "Cancelled"

    @pytest.mark.unit
    def test_draft_ar(self) -> None:
        assert get_inventory_status_label("draft", "ar") == "مرحلة عرض الأسعار"

    @pytest.mark.unit
    def test_fulfilled_ar(self) -> None:
        assert get_inventory_status_label("fulfilled", "ar") == "تم الشحن / التسليم"


class TestFormatOrderStatus:
    """Tests for the combined format_order_status function."""

    @pytest.mark.unit
    def test_combined_deal_and_order(self) -> None:
        """Both CRM deal data and inventory order data available."""
        deal_data = {
            "id": "DEAL001",
            "Deal_Name": "Office Chairs",
            "Stage": "Order Confirmed",
        }
        order_data = {
            "salesorder_number": "SO-00003",
            "status": "confirmed",
            "shipment_date": "2026-04-01",
            "delivery_method": "Standard",
        }
        result = format_order_status(deal_data, order_data, "en")

        assert "Confirmed, preparing" in result
        assert "SO-00003" in result
        assert "2026-04-01" in result

    @pytest.mark.unit
    def test_deal_only(self) -> None:
        """Only CRM deal data available, no inventory order."""
        deal_data = {
            "id": "DEAL001",
            "Deal_Name": "Office Chairs",
            "Stage": "Consignment",
        }
        result = format_order_status(deal_data, None, "en")

        assert "In transit" in result

    @pytest.mark.unit
    def test_order_only(self) -> None:
        """Only inventory order data available, no CRM deal."""
        order_data = {
            "salesorder_number": "SO-00005",
            "status": "fulfilled",
        }
        result = format_order_status(None, order_data, "en")

        assert "Shipped / Delivered" in result
        assert "SO-00005" in result

    @pytest.mark.unit
    def test_arabic_combined(self) -> None:
        """Combined output in Arabic."""
        deal_data = {"Stage": "Consignment"}
        order_data = {"salesorder_number": "SO-001", "status": "confirmed"}

        result = format_order_status(deal_data, order_data, "ar")
        assert "في الطريق" in result

    @pytest.mark.unit
    def test_no_data(self) -> None:
        """Both None returns an appropriate error message."""
        result = format_order_status(None, None, "en")
        assert "not found" in result.lower() or "no order" in result.lower()
