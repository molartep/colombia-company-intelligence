from collections.abc import AsyncIterator

from asyncpg import PostgresError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.errors import DatabaseUnavailable

engine = create_async_engine(
    get_settings().database_url,
    pool_pre_ping=True,
    connect_args={"timeout": 5, "command_timeout": 30},
)
Session = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    try:
        async with Session() as session:
            yield session
    except (OSError, PostgresError) as exc:
        raise DatabaseUnavailable() from exc
