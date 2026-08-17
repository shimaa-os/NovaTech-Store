from __future__ import annotations

import argparse
import asyncio
import getpass

import pyotp
from sqlalchemy import or_, select

from .db import SessionLocal
from .models import User
from .security import encrypt_mfa_secret, hash_password


async def create_admin(args: argparse.Namespace) -> None:
    email = args.email.strip().lower()
    username = args.username.strip().lower()
    password = getpass.getpass("Admin password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        raise SystemExit("Passwords do not match")
    password_hash = hash_password(password, admin=True)
    secret = pyotp.random_base32()
    encrypted_secret = encrypt_mfa_secret(secret)
    async with SessionLocal() as db:
        exists = await db.scalar(select(User.id).where(or_(User.email == email, User.username == username)))
        if exists:
            raise SystemExit("Admin email or username already exists")
        user = User(
            email=email,
            username=username,
            password_hash=password_hash,
            role="admin",
            mfa_secret=encrypted_secret,
            mfa_confirmed=True,
        )
        db.add(user)
        await db.commit()
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name="NovaTech Store")
    print("Admin created.")
    print("Add this TOTP URI to an authenticator app before first login:")
    print(uri)


def main() -> None:
    parser = argparse.ArgumentParser(prog="novatech")
    subparsers = parser.add_subparsers(dest="command", required=True)
    admin_parser = subparsers.add_parser("create-admin")
    admin_parser.add_argument("--email", required=True)
    admin_parser.add_argument("--username", required=True)
    admin_parser.set_defaults(func=create_admin)
    args = parser.parse_args()
    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()
