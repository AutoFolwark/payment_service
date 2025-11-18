from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, AsyncSession, async_sessionmaker
from config import settings
from core.utils import BASE_DIR

if settings.DEBUG:
    SQLALCHEMY_ASYNC_DATABASE_URL = f"sqlite+aiosqlite:///{BASE_DIR}/db.sqlite"
else:
    SQLALCHEMY_ASYNC_DATABASE_URL = f'postgresql+asyncpg://{settings.DB_USER}:{settings.DB_PASS}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}'


engine_async: AsyncEngine = create_async_engine(SQLALCHEMY_ASYNC_DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(
    bind=engine_async,
    expire_on_commit=False,
    class_=AsyncSession,
)

async def get_db()-> AsyncGenerator[AsyncSession | Any, Any]:
    async with AsyncSessionLocal() as session:
        yield session


@asynccontextmanager
async def get_db_context():
    async with AsyncSessionLocal() as session:
        yield session

