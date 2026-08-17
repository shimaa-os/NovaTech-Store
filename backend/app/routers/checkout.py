from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..dependencies import AuthenticatedUser, require_user
from ..services.checkout import checkout

router = APIRouter(prefix="/api", tags=["checkout"])


@router.post("/checkout")
async def run_checkout(
    auth: AuthenticatedUser = Depends(require_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db, use_cache=False),
) -> dict:
    if not idempotency_key or len(idempotency_key) > 128:
        raise HTTPException(status_code=400, detail="Idempotency-Key is required")
    return await checkout(db, auth.user.id, idempotency_key)
