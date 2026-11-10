from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings

DATABASE_URL = get_settings().database_url
engine_options: dict = {"pool_pre_ping": True}
if DATABASE_URL.startswith("postgresql"):
    # Fail fast instead of hanging when the managed database cannot be reached.
    engine_options.update(
        pool_timeout=5, pool_recycle=1800, connect_args={"connect_timeout": 5}
    )
engine = create_async_engine(DATABASE_URL, **engine_options)

if engine.dialect.name == "sqlite":

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")


Session = async_sessionmaker(engine, expire_on_commit=False)


async def get_session():
    async with Session() as session:
        yield session
