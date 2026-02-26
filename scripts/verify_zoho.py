import asyncio
import os
import sys

# Add project root to path so we can import src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.integrations.crm.zoho_crm import ZohoCRMClient
from src.integrations.inventory.zoho_inventory import ZohoInventoryClient
import redis.asyncio as aioredis
from src.core.config import settings

async def main():
    print("--- Verifying Zoho Integrations ---")
    
    # Initialize redis for token caching
    redis = aioredis.from_url(settings.redis_url)

    print("\n--- 1. Zoho Inventory ---")
    inventory_client = ZohoInventoryClient(redis_client=redis)
    try:
        print("Fetching items...")
        items_data = await inventory_client.get_items(page=1, per_page=5)
        
        items = items_data.get("items", [])
        print(f"✅ Found {len(items)} items.")
        
        if items:
            sku = items[0].get("sku")
            print(f"\nFetching stock for SKU: {sku}...")
            if sku:
                stock_data = await inventory_client.get_stock(sku)
                print(f"✅ Stock data: {stock_data}")
            else:
                print("Item has no SKU.")
    except Exception as e:
        print(f"❌ Zoho Inventory test failed: {e}")

    print("\n--- 2. Zoho CRM ---")
    test_phone = os.getenv("TEST_PHONE", "+971500000000")
    crm_client = ZohoCRMClient(redis_client=redis)
    try:
        print(f"Searching for contact by phone: {test_phone}...")
        contact = await crm_client.find_contact_by_phone(test_phone)
        
        contact_id = None
        if contact:
            contact_id = contact.get("id")
            print(f"✅ Contact found: {contact_id}")
        else:
            print("Contact not found. Creating a test contact...")
            deal_contact_data = {
                "Phone": test_phone,
                "Last_Name": "Verification Test Contact",
                "Lead_Source": "Chatbot"
            }
            # Note: create_contact is actually defined in the CRM router or using _request directly
            # For simplicity, we'll try to use the raw request
            create_resp = await crm_client._request(
                method="POST",
                path="/Contacts",
                json={"data": [deal_contact_data]}
            )
            data = create_resp.json()
            if data and "data" in data and len(data["data"]) > 0:
                contact_id = data["data"][0]["details"]["id"]
                print(f"✅ Contact created with ID: {contact_id}")
            else:
                 print(f"❌ Failed to create contact: {data}")

        if contact_id:
             print("\nCreating a test deal...")
             deal_data = {
                 "Deal_Name": "Integration Test Deal",
                 "Contact_Name": {"id": contact_id},
                 "Stage": "New Lead",
                 "Pipeline": "Standard (Standard)",
                 "Amount": 100.0,
             }
             deal_resp = await crm_client._request(
                 method="POST",
                 path="/Deals",
                 json={"data": [deal_data]}
             )
             deal_resp_json = deal_resp.json()
             if deal_resp_json and "data" in deal_resp_json and len(deal_resp_json["data"]) > 0:
                  deal_id = deal_resp_json["data"][0]["details"]["id"]
                  print(f"✅ Deal created with ID: {deal_id}")
             else:
                  print(f"❌ Failed to create deal: {deal_resp_json}")
                  
    except Exception as e:
         print(f"❌ Zoho CRM test failed: {e}")
         
    finally:
         await redis.close()

if __name__ == "__main__":
    asyncio.run(main())
