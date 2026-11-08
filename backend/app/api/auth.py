from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.api.dependencies import get_current_actor
from app.models.actor import Actor

router = APIRouter(prefix="/auth", tags=["auth"])

_LOGIN_GONE = (
    "Password login is disabled. Sign in through your Zitadel organization. "
    "Sangam does not accept a password or mint an access token."
)
_REGISTER_GONE = (
    "Registration is disabled. Create the user in your Zitadel organization. "
    "Sangam does not store a password."
)
_REFRESH_GONE = (
    "Sangam does not mint or refresh sessions. The Zitadel client refreshes its own tokens."
)


class MeResponse(BaseModel):
    actor_id: str
    name: str
    email: str | None = None
    organization_id: str | None = None
    roles: list[str]


async def _discard_body(request: Request) -> None:
    # Touch the body so a posted password is not treated as credentials.
    await request.body()


@router.post("/register", status_code=410)
async def register(request: Request):
    await _discard_body(request)
    raise HTTPException(status_code=410, detail=_REGISTER_GONE)


@router.post("/login", status_code=410)
async def login(request: Request):
    await _discard_body(request)
    raise HTTPException(status_code=410, detail=_LOGIN_GONE)


@router.post("/refresh", status_code=410)
async def refresh(request: Request):
    await _discard_body(request)
    raise HTTPException(status_code=410, detail=_REFRESH_GONE)


@router.get("/me", response_model=MeResponse)
async def me(current_actor: Actor = Depends(get_current_actor)):
    roles = [role.value if hasattr(role, "value") else role for role in (current_actor.roles or [])]
    return MeResponse(
        actor_id=str(current_actor.id),
        name=current_actor.name,
        email=current_actor.email,
        organization_id=current_actor.zitadel_org_id,
        roles=roles,
    )
