from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from decimal import Decimal

import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test-novatech.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("APP_ORIGIN", "http://testserver")
os.environ.setdefault("ALLOWED_HOSTS", '["testserver","127.0.0.1","localhost"]')
os.environ.setdefault("SESSION_SECRET", "test-session-secret-with-at-least-32-bytes")
os.environ.setdefault("CSRF_SECRET", "test-csrf-secret-with-at-least-32-bytes")
os.environ.setdefault("OTP_SECRET", "test-otp-secret-with-at-least-32-bytes")
os.environ.setdefault("ENVIRONMENT", "test")

from app import dependencies  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Base, Cart, CartItem, Product, User  # noqa: E402
from app.routers import auth, profile  # noqa: E402
from app.security import hash_password  # noqa: E402


@pytest.fixture()
def fake_redis(monkeypatch: pytest.MonkeyPatch):
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(dependencies, "get_redis", lambda: redis)
    monkeypatch.setattr(auth, "get_redis", lambda: redis)
    monkeypatch.setattr(profile, "get_redis", lambda: redis)
    yield redis


@pytest.fixture()
def client(fake_redis) -> Iterator[TestClient]:
    async def reset_db() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(reset_db())
    with TestClient(create_app(), base_url="http://testserver") as test_client:
        yield test_client
    asyncio.run(reset_db())


def csrf_headers(client: TestClient) -> dict[str, str]:
    response = client.get("/api/auth/csrf")
    assert response.status_code == 200
    return {"Origin": "http://testserver", "X-CSRF-Token": response.json()["csrfToken"]}


async def create_user(
    *,
    email: str = "user@example.com",
    username: str = "user",
    password: str = "correct horse battery",
    balance: Decimal = Decimal("0.00"),
) -> User:
    async with SessionLocal() as db:
        user = User(email=email, username=username, password_hash=hash_password(password), balance=balance)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def create_product(
    *,
    product_id: int = 1,
    price: Decimal = Decimal("10.00"),
    quantity: int = 5,
) -> Product:
    async with SessionLocal() as db:
        product = Product(
            id=product_id,
            name="Nova Test Product",
            category="Testing",
            price=price,
            quantity=quantity,
            brand="Nova",
            description="Test product",
            rating=Decimal("4.5"),
            badge="Test",
            images=[{"path": "images/products/product-placeholder.svg"}],
        )
        db.add(product)
        await db.commit()
        await db.refresh(product)
        return product


async def create_cart_item(user_id, product_id: int, quantity: int) -> None:
    async with SessionLocal() as db:
        cart = Cart(user_id=user_id)
        db.add(cart)
        await db.flush()
        db.add(CartItem(cart_id=cart.id, product_id=product_id, quantity=quantity))
        await db.commit()


async def fetch_product(product_id: int = 1) -> Product:
    async with SessionLocal() as db:
        product = await db.get(Product, product_id)
        assert product is not None
        return product


async def fetch_user(email: str = "user@example.com") -> User:
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == email))
        assert user is not None
        return user
