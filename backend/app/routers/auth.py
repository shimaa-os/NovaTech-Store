
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..dependencies import AuthenticatedUser, require_user
from ..models import User
from ..redis_client import get_redis
from ..schemas import EmailRequest, LoginRequest, RegistrationRequest, VerifyOtpRequest
from ..security import hash_password, password_needs_rehash, verify_password, verify_totp
from ..services.otp import (
    create_pending_registration,
    resend_pending_registration,
    verify_pending_registration,
)
from ..services.rate_limit import enforce_rate_limit
from ..services.sessions import create_session, delete_current_session

router = APIRouter(prefix="/api/auth", tags=["authentication"])
GENERIC_AUTH_ERROR = "Invalid email or password"
GENERIC_REGISTRATION = "If the address can be registered, a verification code will be sent."


@router.post("/login")
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict:
    redis = get_redis()
    email = str(payload.email).lower()
    await enforce_rate_limit(redis, request, "login", email, limit=5, window_seconds=300)
    user = await db.scalar(select(User).where(User.email == email, User.role == "user"))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_AUTH_ERROR)
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
        await db.commit()
    await create_session(redis, response, user.id, user.role)
    return {"status": "success", "message": "Welcome Back", "role": user.role, "user": user_view(user)}


@router.post("/admin-login")
async def admin_login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict:
    redis = get_redis()
    email = str(payload.email).lower()
    await enforce_rate_limit(redis, request, "admin-login", email, limit=5, window_seconds=600)
    user = await db.scalar(select(User).where(User.email == email, User.role == "admin"))
    valid = bool(
        user
        and user.is_active
        and user.mfa_confirmed
        and user.mfa_secret
        and verify_password(payload.password, user.password_hash)
        and verify_totp(user.mfa_secret, payload.totp or "")
    )
    if not valid or user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_AUTH_ERROR)
    await create_session(redis, response, user.id, user.role)
    return {"status": "success", "message": "Welcome Admin", "role": user.role, "admin": user_view(user)}


@router.post("/register", status_code=202)
async def register(
    payload: RegistrationRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    redis = get_redis()
    email = str(payload.email).lower()
    await enforce_rate_limit(redis, request, "register", email, limit=3, window_seconds=3600)
    exists = await db.scalar(select(User.id).where(or_(User.email == email, User.username == payload.user_name)))
    if not exists:
        password_hash = hash_password(payload.password)
        await create_pending_registration(
            redis, email=email, username=payload.user_name, password_hash=password_hash
        )
    return {"status": "pending", "message": GENERIC_REGISTRATION, "delivery": "email"}


@router.post("/resend-otp", status_code=202)
async def resend_otp(payload: EmailRequest, request: Request) -> dict:
    redis = get_redis()
    email = str(payload.email).lower()
    await enforce_rate_limit(redis, request, "resend-otp", email, limit=3, window_seconds=3600)
    result = await resend_pending_registration(redis, email)
    if result == "cooldown":
        raise HTTPException(status_code=429, detail="Please wait before requesting another code")
    return {"status": "pending", "message": GENERIC_REGISTRATION, "delivery": "email"}


@router.post("/verify-otp")
async def verify_otp(
    payload: VerifyOtpRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict:
    redis = get_redis()
    email = str(payload.email).lower()
    await enforce_rate_limit(redis, request, "verify-otp", email, limit=6, window_seconds=600)
    pending = await verify_pending_registration(redis, email, payload.otp)
    if pending is None:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")
    existing = await db.scalar(
        select(User.id).where(or_(User.email == pending["email"], User.username == pending["username"]))
    )
    if existing:
        raise HTTPException(status_code=409, detail="Account cannot be created")
    user = User(
        username=pending["username"],
        email=pending["email"],
        password_hash=pending["password_hash"],
        role="user",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    await create_session(redis, response, user.id, user.role)
    return {"status": "success", "message": "Account Created Successfully", "role": "user", "user": user_view(user)}


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict:
    await delete_current_session(get_redis(), request, response)
    return {"status": "success", "message": "Logged Out"}


@router.get("/session")
async def session(auth: AuthenticatedUser = Depends(require_user)) -> dict:
    return {"status": "success", "role": auth.user.role, "user": user_view(auth.user)}


def user_view(user: User) -> dict:
    return {
        "user_name": user.username,
        "email": user.email,
        "balance": float(user.balance),
    }

