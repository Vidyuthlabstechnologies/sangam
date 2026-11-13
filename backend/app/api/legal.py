"""Public legal pages: privacy policy, terms of use, account deletion.

No sign-in is needed. Google Play, Play Console reviewers and people who have
lost access to the app must be able to open these from a browser.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.core import legal_content

router = APIRouter(prefix="/legal", tags=["legal"])

_PAGE_HEADERS = {
    # One hour: edits go live quickly, and Play's crawler is not hammering us.
    "Cache-Control": "public, max-age=3600",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}

# URL checkers and uptime monitors often probe with HEAD before GET.
_METHODS = ["GET", "HEAD"]


def _html(content: str) -> HTMLResponse:
    return HTMLResponse(content, headers=_PAGE_HEADERS)


@router.api_route("/privacy", methods=_METHODS, response_class=HTMLResponse, include_in_schema=False)
async def privacy_policy() -> HTMLResponse:
    return _html(legal_content.privacy_policy_html())


@router.api_route("/terms", methods=_METHODS, response_class=HTMLResponse, include_in_schema=False)
async def terms_of_use() -> HTMLResponse:
    return _html(legal_content.terms_html())


@router.api_route("/delete-account", methods=_METHODS, response_class=HTMLResponse, include_in_schema=False)
async def delete_account_instructions() -> HTMLResponse:
    return _html(legal_content.delete_account_html())
