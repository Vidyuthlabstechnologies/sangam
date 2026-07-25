"""MCP Server: SAP ERP Integration

Connects Sangam workflows to SAP for procurement, finance, and vendor management.
Stateless HTTP MCP server following 2026 spec.
"""

from typing import Optional, Dict, Any
import httpx
import os
import base64

from app.mcp_servers.base import MCPServer, MCPTool


def create_sap_server(
    base_url: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> MCPServer:
    server = MCPServer(name="sap", version="1.0.0")
    sap_url = base_url or os.environ.get("SAP_BASE_URL", "")
    sap_user = username or os.environ.get("SAP_USERNAME", "")
    sap_pass = password or os.environ.get("SAP_PASSWORD", "")

    auth_header = "Basic " + base64.b64encode(
        f"{sap_user}:{sap_pass}".encode()
    ).decode()

    headers = {
        "Authorization": auth_header,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    async def create_purchase_order(
        vendor_id: str,
        material: str,
        quantity: int,
        unit_price: float,
        currency: str = "INR",
        delivery_date: Optional[str] = None,
    ):
        async with httpx.AsyncClient(headers=headers, timeout=30) as client:
            payload = {
                "VENDOR_ID": vendor_id,
                "MATERIAL": material,
                "QUANTITY": quantity,
                "UNIT_PRICE": unit_price,
                "CURRENCY": currency,
            }
            if delivery_date:
                payload["DELIVERY_DATE"] = delivery_date

            resp = await client.post(
                f"{sap_url}/api/purchase-orders",
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    async def get_vendor_details(vendor_id: str):
        async with httpx.AsyncClient(headers=headers, timeout=15) as client:
            resp = await client.get(
                f"{sap_url}/api/vendors/{vendor_id}"
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "vendor_id": data.get("VENDOR_ID"),
                "name": data.get("NAME"),
                "status": data.get("STATUS"),
                "payment_terms": data.get("PAYMENT_TERMS"),
                "gst_number": data.get("GST_NUMBER"),
            }

    async def check_material_stock(material_code: str, plant: str = "PLANT01"):
        async with httpx.AsyncClient(headers=headers, timeout=15) as client:
            resp = await client.get(
                f"{sap_url}/api/materials/{material_code}/stock",
                params={"plant": plant},
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "material": material_code,
                "plant": plant,
                "available_qty": data.get("AVAILABLE_QTY", 0),
                "reserved_qty": data.get("RESERVED_QTY", 0),
                "unit": data.get("UNIT", "EA"),
            }

    async def create_invoice(
        purchase_order_id: str,
        amount: float,
        tax_amount: float,
        currency: str = "INR",
    ):
        async with httpx.AsyncClient(headers=headers, timeout=30) as client:
            payload = {
                "PO_NUMBER": purchase_order_id,
                "AMOUNT": amount,
                "TAX_AMOUNT": tax_amount,
                "CURRENCY": currency,
            }
            resp = await client.post(
                f"{sap_url}/api/invoices", json=payload
            )
            resp.raise_for_status()
            return resp.json()

    server.register(MCPTool(
        name="create_purchase_order",
        description="Create a purchase order in SAP",
        input_schema={
            "type": "object",
            "properties": {
                "vendor_id": {"type": "string"},
                "material": {"type": "string"},
                "quantity": {"type": "integer"},
                "unit_price": {"type": "number"},
                "currency": {"type": "string", "default": "INR"},
                "delivery_date": {"type": "string"},
            },
            "required": ["vendor_id", "material", "quantity", "unit_price"],
        },
        handler=create_purchase_order,
    ))

    server.register(MCPTool(
        name="get_vendor_details",
        description="Get vendor master details from SAP",
        input_schema={
            "type": "object",
            "properties": {
                "vendor_id": {"type": "string"},
            },
            "required": ["vendor_id"],
        },
        handler=get_vendor_details,
    ))

    server.register(MCPTool(
        name="check_material_stock",
        description="Check material stock availability in SAP",
        input_schema={
            "type": "object",
            "properties": {
                "material_code": {"type": "string"},
                "plant": {"type": "string", "default": "PLANT01"},
            },
            "required": ["material_code"],
        },
        handler=check_material_stock,
    ))

    server.register(MCPTool(
        name="create_invoice",
        description="Create an invoice in SAP against a purchase order",
        input_schema={
            "type": "object",
            "properties": {
                "purchase_order_id": {"type": "string"},
                "amount": {"type": "number"},
                "tax_amount": {"type": "number"},
                "currency": {"type": "string", "default": "INR"},
            },
            "required": ["purchase_order_id", "amount", "tax_amount"],
        },
        handler=create_invoice,
    ))

    return server
