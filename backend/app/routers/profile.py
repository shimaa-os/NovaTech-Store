from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..dependencies import AuthenticatedUser, require_user
from ..models import User
from ..redis_client import get_redis
from ..schemas import DeleteAccountRequest, PasswordChangeRequest, UsernameUpdateRequest
from ..security import hash_password, verify_password
from ..services.sessions import delete_current_session, revoke_user_sessions
from .auth import user_view

router = APIRouter(prefix="/api", tags=["profile"])


@router.get("/me")
async def me(auth: AuthenticatedUser = Depends(require_user)) -> dict:
    return {"status": "success", "user": user_view(auth.user), "role": auth.user.role}


@router.get("/wallet")
async def wallet(auth: AuthenticatedUser = Depends(require_user)) -> dict:
    return {"status": "success", "balance": float(auth.user.balance)}


@router.patch("/profile/username")
async def update_username(
    payload: UsernameUpdateRequest,
    auth: AuthenticatedUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    auth.user.username = payload.new_name
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Username is unavailable") from exc
    await db.refresh(auth.user)
    return {"status": "success", "message": "Username Updated", "user": user_view(auth.user)}


@router.patch("/profile/password")
async def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    response: Response,
    auth: AuthenticatedUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not verify_password(payload.old_password, auth.user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    auth.user.password_hash = hash_password(payload.new_password, admin=auth.user.role == "admin")
    auth.user.password_changed_at = datetime.now(UTC)
    await db.commit()
    await revoke_user_sessions(get_redis(), auth.user.id)
    await delete_current_session(get_redis(), request, response)
    return {"status": "success", "message": "Password changed. Please sign in again."}


@router.delete("/profile")
async def delete_profile(
    payload: DeleteAccountRequest,
    request: Request,
    response: Response,
    auth: AuthenticatedUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not verify_password(payload.password, auth.user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    user = await db.scalar(select(User).where(User.id == auth.user.id).with_for_update())
    if user:
        user.is_active = False
    await db.commit()
    await revoke_user_sessions(get_redis(), auth.user.id)
    await delete_current_session(get_redis(), request, response)
    return {"status": "success", "message": "Account disabled"}
