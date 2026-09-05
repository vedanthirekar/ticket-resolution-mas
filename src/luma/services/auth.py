from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from luma.db.models.case_management import OperationsAccount, OperationsSession

SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("operations password must contain at least 12 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32
    )
    encoded_salt = base64.b64encode(salt).decode()
    encoded_digest = base64.b64encode(digest).decode()
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${encoded_salt}${encoded_digest}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt_value, expected_value = encoded.split("$", 5)
        if algorithm != "scrypt":
            return False
        salt = base64.b64decode(salt_value)
        expected = base64.b64decode(expected_value)
        actual = hashlib.scrypt(
            password.encode(), salt=salt, n=int(n), r=int(r), p=int(p), dklen=len(expected)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def create_session(
    session: AsyncSession,
    *,
    username: str,
    password: str,
    ttl: timedelta = timedelta(hours=8),
    now: datetime | None = None,
) -> str | None:
    account = await session.scalar(
        select(OperationsAccount).where(OperationsAccount.username == username)
    )
    if (
        account is None
        or not account.active
        or not verify_password(password, account.password_hash)
    ):
        return None
    token = secrets.token_urlsafe(32)
    issued_at = now or datetime.now(UTC)
    session.add(
        OperationsSession(
            account_id=account.id,
            token_hash=hash_session_token(token),
            expires_at=issued_at + ttl,
            last_used_at=issued_at,
        )
    )
    await session.flush()
    return token


async def authenticate_session(
    session: AsyncSession, token: str, *, now: datetime | None = None
) -> OperationsAccount | None:
    checked_at = now or datetime.now(UTC)
    row = (
        await session.execute(
            select(OperationsSession, OperationsAccount)
            .join(OperationsAccount, OperationsAccount.id == OperationsSession.account_id)
            .where(
                OperationsSession.token_hash == hash_session_token(token),
                OperationsSession.revoked_at.is_(None),
                OperationsSession.expires_at > checked_at,
                OperationsAccount.active.is_(True),
            )
        )
    ).one_or_none()
    if row is None:
        return None
    operation_session: OperationsSession = row[0]
    account: OperationsAccount = row[1]
    operation_session.last_used_at = checked_at
    return account


async def revoke_session(session: AsyncSession, token: str, *, now: datetime | None = None) -> bool:
    operation_session = await session.scalar(
        select(OperationsSession).where(
            OperationsSession.token_hash == hash_session_token(token),
            OperationsSession.revoked_at.is_(None),
        )
    )
    if operation_session is None:
        return False
    operation_session.revoked_at = now or datetime.now(UTC)
    await session.flush()
    return True
