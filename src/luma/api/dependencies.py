from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from luma.db.models.case_management import OperationsAccount
from luma.db.session import Database
from luma.services.auth import authenticate_session

bearer_scheme = HTTPBearer(auto_error=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    database = cast(Database, request.app.state.database)
    async with database.session() as session:
        yield session


SessionDependency = Annotated[AsyncSession, Depends(get_session)]


async def require_operations_account(
    session: SessionDependency,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> OperationsAccount:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required"
        )
    account = await authenticate_session(session, credentials.credentials)
    if account is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid session")
    await session.commit()
    return account


OperationsAccountDependency = Annotated[OperationsAccount, Depends(require_operations_account)]
BearerDependency = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]
