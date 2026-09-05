from __future__ import annotations

from sqlalchemy import select

from luma.config import get_settings
from luma.db.models.case_management import OperationsAccount
from luma.db.session import Database
from luma.runtime import run_async
from luma.services.auth import hash_password


async def bootstrap_operations_account() -> bool:
    settings = get_settings()
    if (
        settings.environment == "production"
        and settings.operations_password == "change-me-before-production"
    ):
        raise RuntimeError("refusing to bootstrap production with the default password")
    database = Database(settings.database_url, echo=settings.database_echo)
    try:
        async with database.transaction() as session:
            existing = await session.scalar(
                select(OperationsAccount).where(
                    OperationsAccount.username == settings.operations_username
                )
            )
            if existing is not None:
                return False
            session.add(
                OperationsAccount(
                    username=settings.operations_username,
                    password_hash=hash_password(settings.operations_password),
                    display_name=settings.operations_display_name,
                    active=True,
                )
            )
        return True
    finally:
        await database.dispose()


def main() -> None:
    created = run_async(bootstrap_operations_account())
    print("operations account created" if created else "operations account already exists")


if __name__ == "__main__":
    main()
