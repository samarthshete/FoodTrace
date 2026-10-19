import asyncio

from alembic import context
from sqlalchemy import Connection

from app.db.models import Base
from app.db.session import make_engine
from app.settings import get_settings

target_metadata = Base.metadata


def _url() -> str:
    # Tests pass an explicit URL via config attributes; otherwise use settings/env.
    return context.config.attributes.get("database_url") or get_settings().database_url


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _run_async() -> None:
    engine = make_engine(_url())
    async with engine.connect() as connection:
        await connection.run_sync(_run)
    await engine.dispose()


if context.is_offline_mode():
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(_run_async())
