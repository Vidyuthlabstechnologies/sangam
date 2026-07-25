from uuid import UUID
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.actor import Actor, ActorType, Role, Permission
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_access_token,
)
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    type: str = "human"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    actor_id: str
    name: str
    roles: list[str]


class RefreshRequest(BaseModel):
    token: str


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(req: RegisterRequest, session: AsyncSession = Depends(get_session)):
    existing = await session.execute(select(Actor).where(Actor.email == req.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    actor = Actor(
        name=req.name,
        email=req.email,
        type=ActorType(req.type) if req.type in {"human", "agent", "system"} else ActorType.HUMAN,
        password_hash=get_password_hash(req.password),
        roles=[Role.INITIATOR],
        permissions=[Permission.CREATE_WORKFLOW, Permission.READ_WORKFLOW],
    )
    session.add(actor)
    await session.commit()
    await session.refresh(actor)

    token = create_access_token(str(actor.id))
    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
        actor_id=str(actor.id),
        name=actor.name,
        roles=[r.value if hasattr(r, "value") else r for r in actor.roles],
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Actor).where(Actor.email == req.email))
    actor = result.scalar_one_or_none()
    if not actor or not actor.password_hash:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not verify_password(req.password, actor.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not actor.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive")

    token = create_access_token(str(actor.id))
    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
        actor_id=str(actor.id),
        name=actor.name,
        roles=[r.value if hasattr(r, "value") else r for r in actor.roles],
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(req: RefreshRequest):
    payload = decode_access_token(req.token)
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    token = create_access_token(payload["sub"])
    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
        actor_id=payload["sub"],
        name="",
        roles=[],
    )
