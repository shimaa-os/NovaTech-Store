import base64
import hashlib
import hmac
import secrets

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

from .config import get_settings

PASSWORD_HASHER = PasswordHasher(time_cost=3, memory_cost=65_536, parallelism=4, hash_len=32, salt_len=16)


def hash_password(password: str, *, admin: bool = False) -> str:
    minimum = 16 if admin else 15
    if len(password) < minimum or len(password) > 128:
        raise ValueError(f"Password must be between {minimum} and 128 characters")
    return PASSWORD_HASHER.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    try:
        return PASSWORD_HASHER.verify(encoded, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(encoded: str) -> bool:
    try:
        return PASSWORD_HASHER.check_needs_rehash(encoded)
    except InvalidHashError:
        return True


def random_token(bytes_count: int = 32) -> str:
    return secrets.token_urlsafe(bytes_count)


def keyed_digest(secret: str, value: str) -> str:
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def _fernet() -> Fernet:
    settings = get_settings()
    if settings.mfa_encryption_key:
        key = settings.mfa_encryption_key.encode()
    else:
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.session_secret.encode()).digest())
    return Fernet(key)


def encrypt_mfa_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_mfa_secret(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt MFA secret") from exc


def new_totp_secret() -> str:
    return pyotp.random_base32()


def verify_totp(encrypted_secret: str, code: str) -> bool:
    if not code:
        return False
    secret = decrypt_mfa_secret(encrypted_secret)
    return bool(pyotp.TOTP(secret).verify(code, valid_window=1))


def totp_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name="NovaTech Store")

