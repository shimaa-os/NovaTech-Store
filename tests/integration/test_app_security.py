from __future__ import annotations

import asyncio
from decimal import Decimal

from conftest import create_cart_item, create_product, create_user, csrf_headers, fetch_product, fetch_user
from fastapi.testclient import TestClient


def login(client: TestClient) -> None:
    asyncio.run(create_user(balance=Decimal("100.00")))
    response = client.post(
        "/api/auth/login",
        headers=csrf_headers(client),
        json={"email": "user@example.com", "password": "correct horse battery"},
    )
    assert response.status_code == 200


def test_static_internal_paths_are_not_served(client: TestClient) -> None:
    for path in ["/users.json", "/admins.json", "/config.py", "/backend/app/main.py", "/%2e%2e/users.json"]:
        assert client.get(path).status_code == 404
        assert client.head(path).status_code == 404


def test_csrf_and_origin_required_for_mutating_api(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"email": "x@example.com", "password": "wrong"})
    assert response.status_code == 403
    response = client.post(
        "/api/auth/login",
        headers={"Origin": "http://evil.test", "X-CSRF-Token": "bad"},
        json={"email": "x@example.com", "password": "wrong"},
    )
    assert response.status_code == 403


def test_login_sets_http_only_cookie(client: TestClient) -> None:
    asyncio.run(create_user())
    response = client.post(
        "/api/auth/login",
        headers=csrf_headers(client),
        json={"email": "user@example.com", "password": "correct horse battery"},
    )
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "nova_session=" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie


def test_checkout_idempotency_prevents_double_charge(client: TestClient) -> None:
    asyncio.run(create_user(balance=Decimal("100.00")))
    user = asyncio.run(fetch_user())
    asyncio.run(create_product(price=Decimal("25.00"), quantity=2))
    asyncio.run(create_cart_item(user.id, 1, 1))
    response = client.post(
        "/api/auth/login",
        headers=csrf_headers(client),
        json={"email": "user@example.com", "password": "correct horse battery"},
    )
    assert response.status_code == 200

    headers = csrf_headers(client) | {"Idempotency-Key": "checkout-key-1"}
    first = client.post("/api/checkout", headers=headers, json={})
    second = client.post("/api/checkout", headers=headers, json={})
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["order_id"] == second.json()["order_id"]
    assert asyncio.run(fetch_user()).balance == Decimal("75.00")
    assert asyncio.run(fetch_product()).quantity == 1


def test_password_change_revokes_session(client: TestClient) -> None:
    login(client)
    response = client.patch(
        "/api/profile/password",
        headers=csrf_headers(client),
        json={"old_password": "correct horse battery", "new_password": "new correct horse battery"},
    )
    assert response.status_code == 200
    assert client.get("/api/me").status_code == 401
