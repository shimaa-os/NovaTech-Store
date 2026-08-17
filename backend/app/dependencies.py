from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_db
from .models import User
from .redis_client import get_redis
from .services.sessions import SessionIdentity, read_session


@dataclass(frozen=True)
class AuthenticatedUser:
    user: User
    session: SessionIdentity


async def current_identity(request: Request) -> SessionIdentity | None:
    return await read_session(get_redis(), request)


async def require_user(
    identity: SessionIdentity | None = Depends(current_identity),
    db: AsyncSession = Depends(get_db),
) -> AuthenticatedUser:
    if identity is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user = await db.scalar(select(User).where(User.id == identity.user_id, User.is_active.is_(True)))
    if user is None or user.role != identity.role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return AuthenticatedUser(user, identity)


async def require_admin(auth: AuthenticatedUser = Depends(require_user)) -> AuthenticatedUser:
    if auth.user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator access required")
    return auth

