"""End-to-end vendor onboarding through the HTTP surface.

This is the flow the Android app drives, so these tests double as the
contract the phone codes against.
"""
import pytest


@pytest.mark.asyncio
async def test_create_and_list_vendor(client, auth_headers):
    resp = await client.post(
        "/vendors",
        json={
            "name": "Meridian Life Sciences",
            "gstin": "29AABCM1234K1Z5",
            "contact_email": "qa@meridian.example",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "Meridian Life Sciences"
    assert body["status"] == "draft"
    assert body["licences"] == []
    assert body["is_qualifiable"] is False

    listing = await client.get("/vendors", headers=auth_headers)
    assert listing.status_code == 200
    assert any(v["id"] == body["id"] for v in listing.json())


@pytest.mark.asyncio
async def test_get_vendor_404_for_unknown_id(client, auth_headers):
    resp = await client.get(
        "/vendors/00000000-0000-0000-0000-000000000000", headers=auth_headers
    )
    assert resp.status_code == 404


async def _create_vendor(client, auth_headers, name="Meridian Life Sciences"):
    resp = await client.post("/vendors", json={"name": name}, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_upload_document_extracts_and_creates_licence(client, auth_headers):
    vendor_id = await _create_vendor(client, auth_headers)

    resp = await client.post(
        f"/vendors/{vendor_id}/documents",
        files={"file": ("licence.pdf", b"%PDF-1.4 fake", "application/pdf")},
        data={"document_type": "licence"},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    doc = resp.json()
    assert doc["structured_data"]["licence_number"] == "MFG/25/2024/KA/00847"
    assert doc["status"] in ("completed", "needs_review")

    # The extraction should have been promoted onto the vendor.
    vendor = (await client.get(f"/vendors/{vendor_id}", headers=auth_headers)).json()
    assert len(vendor["licences"]) == 1
    licence = vendor["licences"][0]
    assert licence["licence_number"] == "MFG/25/2024/KA/00847"
    assert licence["licence_type"] == "cdsco"
    assert licence["expiry_date"] == "2029-03-13"
    assert licence["verified"] is False, "Extracted licences await human verification"
    assert vendor["legal_name"] == "Meridian Life Sciences Private Limited"


@pytest.mark.asyncio
async def test_empty_upload_rejected(client, auth_headers):
    vendor_id = await _create_vendor(client, auth_headers)
    resp = await client.post(
        f"/vendors/{vendor_id}/documents",
        files={"file": ("licence.pdf", b"", "application/pdf")},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_submit_for_qualification_creates_approval_workflow(client, auth_headers):
    vendor_id = await _create_vendor(client, auth_headers)
    await client.post(
        f"/vendors/{vendor_id}/documents",
        files={"file": ("licence.pdf", b"%PDF-1.4 fake", "application/pdf")},
        data={"document_type": "licence"},
        headers=auth_headers,
    )

    resp = await client.post(
        f"/vendors/{vendor_id}/submit-for-qualification", headers=auth_headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "pending_qualification"
    assert body["workflow_id"]

    vendor = (await client.get(f"/vendors/{vendor_id}", headers=auth_headers)).json()
    assert vendor["status"] == "pending_qualification"
    assert vendor["qualification_workflow_id"] == body["workflow_id"]


@pytest.mark.asyncio
async def test_cannot_qualify_vendor_without_licences(client, auth_headers):
    vendor_id = await _create_vendor(client, auth_headers, name="No Docs Ltd")
    resp = await client.post(
        f"/vendors/{vendor_id}/submit-for-qualification", headers=auth_headers
    )
    assert resp.status_code == 400
    assert "licence" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_cannot_submit_twice(client, auth_headers):
    vendor_id = await _create_vendor(client, auth_headers, name="Double Submit Ltd")
    await client.post(
        f"/vendors/{vendor_id}/documents",
        files={"file": ("licence.pdf", b"%PDF-1.4 fake", "application/pdf")},
        data={"document_type": "licence"},
        headers=auth_headers,
    )
    first = await client.post(
        f"/vendors/{vendor_id}/submit-for-qualification", headers=auth_headers
    )
    assert first.status_code == 200

    second = await client.post(
        f"/vendors/{vendor_id}/submit-for-qualification", headers=auth_headers
    )
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_requires_authentication(client):
    """No auth override in this test — the endpoint must refuse."""
    resp = await client.get("/vendors")
    assert resp.status_code in (401, 403)
