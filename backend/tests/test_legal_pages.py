"""Public legal pages that Google Play and the DPDP Act 2023 require.

The privacy policy, terms and account-deletion pages must open without
signing in, say what the app really does, and never echo unescaped settings.
"""
import pytest
from httpx import AsyncClient

from app.config import settings


@pytest.mark.asyncio
async def test_privacy_policy_is_public_and_names_every_processor(client: AsyncClient):
    resp = await client.get("/legal/privacy")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    text = resp.text
    for needle in (
        "DPDP",
        "Firebase",
        "RevenueCat",
        "Google Play",
        "Sarvam",
        "microphone",
        "Aadhaar",
        "6 years",
        settings.legal_contact_email,
    ):
        assert needle in text, f"privacy policy is missing {needle!r}"


@pytest.mark.asyncio
async def test_terms_page_is_public(client: AsyncClient):
    resp = await client.get("/legal/terms")
    assert resp.status_code == 200
    assert "Terms of use" in resp.text
    assert "Google Play" in resp.text
    assert settings.legal_contact_email in resp.text


@pytest.mark.asyncio
async def test_account_deletion_page_explains_both_paths_and_retention(client: AsyncClient):
    resp = await client.get("/legal/delete-account")
    assert resp.status_code == 200
    text = resp.text
    # The labels must match the Android screen (OnboardingWizardScreen.kt).
    for label in ("Voice Agent", "Delete Account", "Delete Permanently"):
        assert label in text, f"delete page is missing the in-app label {label!r}"
    assert "mailto:" + settings.legal_contact_email in text
    assert "GST" in text
    assert "30 days" in text


@pytest.mark.asyncio
async def test_old_privacy_url_still_serves_the_same_policy(client: AsyncClient):
    old = await client.get("/onboarding/privacy-policy")
    new = await client.get("/legal/privacy")
    assert old.status_code == 200
    assert old.text == new.text


@pytest.mark.asyncio
async def test_configured_values_are_html_escaped(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "legal_operator_name", "<script>alert(1)</script>")
    monkeypatch.setattr(settings, "legal_postal_address", "1 <b>Road</b> & Co")
    for path in ("/legal/privacy", "/legal/terms", "/legal/delete-account"):
        text = (await client.get(path)).text
        assert "<script>alert(1)</script>" not in text
        assert "&lt;script&gt;" in text
    assert "1 &lt;b&gt;Road&lt;/b&gt; &amp; Co" in (await client.get("/legal/privacy")).text


PAGES = ("/legal/privacy", "/legal/terms", "/legal/delete-account")


@pytest.mark.asyncio
async def test_contact_email_cannot_break_out_of_the_mailto_attribute(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "legal_contact_email", 'a"><script>x</script>@e.com')
    for path in PAGES:
        text = (await client.get(path)).text
        assert "<script>x" not in text, path
        assert "&quot;&gt;&lt;script&gt;x" in text, path


@pytest.mark.asyncio
async def test_multiline_postal_address_keeps_its_line_breaks(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "legal_postal_address", "12 MG Road\n  Bengaluru 560001 \n\n")
    text = (await client.get("/legal/privacy")).text
    assert "12 MG Road<br>Bengaluru 560001" in text


@pytest.mark.asyncio
async def test_empty_postal_address_adds_no_blank_line(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "legal_postal_address", "")
    text = (await client.get("/legal/privacy")).text
    assert "<br></p>" not in text


@pytest.mark.asyncio
@pytest.mark.parametrize("path", PAGES)
async def test_pages_send_cache_and_hardening_headers(client: AsyncClient, path: str):
    resp = await client.get(path)
    assert resp.headers["content-type"] == "text/html; charset=utf-8"
    assert resp.headers["cache-control"] == "public, max-age=3600"
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["referrer-policy"] == "strict-origin-when-cross-origin"


@pytest.mark.asyncio
@pytest.mark.parametrize("path", PAGES)
async def test_head_requests_succeed_for_url_checkers(client: AsyncClient, path: str):
    resp = await client.head(path)
    assert resp.status_code == 200
    assert resp.content == b""
