from __future__ import annotations

from typing import Any, Protocol


class CRMProvider(Protocol):
    """Abstract CRM provider interface.

    Implement this protocol to add new CRM integrations
    (Zoho CRM, Salesforce, HubSpot, etc.)
    """

    async def find_contact_by_phone(self, phone: str) -> dict[str, Any] | None:
        """Find a contact by phone number."""
        ...

    async def create_contact(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new contact."""
        ...

    async def create_deal(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new deal/opportunity."""
        ...

    async def update_deal(self, deal_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update an existing deal."""
        ...
