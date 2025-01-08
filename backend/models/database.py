from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os

from utils.logging import get_logger

logger = get_logger(__name__)
logger.disabled = True


class Base(DeclarativeBase):
    pass


db_url = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://graphy:graphydocs@postgres:5432/graphydb"
)


def get_session_maker(db_url: str = db_url):
    # Convert standard PostgreSQL URL to async format if needed
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(
        db_url,
        echo=False,
        future=True,
        pool_pre_ping=True,  # Add connection health check
    )

    return sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


async def init_db(db_url: str = db_url):
    """Initialize database tables"""
    logger.info("Creating database tables...")
    engine = create_async_engine(db_url)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables created successfully")


SessionLocal = get_session_maker(db_url)


async def get_db():
    async_session = SessionLocal()
    try:
        yield async_session
    finally:
        await async_session.close()


__all__ = ["get_db", "init_db"]
