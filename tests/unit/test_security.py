from decimal import Decimal

import pytest
from app.schemas import finite_decimal
from app.security import hash_password, verify_password
from app.services.csrf import create_csrf_token, verify_csrf_token
from fastapi import Response


def test_argon2_password_policy_and_verification() -> None:
    with pytest.raises(ValueError):
        hash_password("short")
    encoded = hash_password("correct horse battery")
    assert encoded.startswith("$argon2")
    assert verify_password("correct horse battery", encoded)
    assert not verify_password("wrong password", encoded)


def test_admin_password_minimum_is_stronger() -> None:
    with pytest.raises(ValueError):
        hash_password("fifteen-chars!!", admin=True)
    assert verify_password("sixteen-chars!!!", hash_password("sixteen-chars!!!", admin=True))


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_decimal_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        finite_decimal(value)


def test_decimal_quantization_uses_exact_decimal() -> None:
    assert finite_decimal("10.999") == Decimal("11.00")


def test_csrf_token_is_signed() -> None:
    response = Response()
    token = create_csrf_token(response)
    assert verify_csrf_token(token)
    assert not verify_csrf_token(token + "x")
