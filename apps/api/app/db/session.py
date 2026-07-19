from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

class DummyResult:
    def scalars(self):
        return self
    def all(self):
        return []
    def first(self):
        return None
    def __iter__(self):
        return iter([])

class DummyAsyncSession:
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    async def execute(self, *args, **kwargs):
        return DummyResult()
    def add(self, instance):
        pass
    async def flush(self):
        pass
    async def commit(self):
        pass
    async def rollback(self):
        pass
    async def close(self):
        pass

class DummySessionFactory:
    def __call__(self):
        return DummyAsyncSession()

engine = None
AsyncSessionFactory = None

try:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.APP_DEBUG,
        pool_pre_ping=True,
    )
    AsyncSessionFactory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False,
        class_=AsyncSession,
    )
except Exception:
    try:
        engine = create_async_engine(
            "sqlite+aiosqlite:///./hireai_dev.db",
            echo=settings.APP_DEBUG,
        )
        AsyncSessionFactory = async_sessionmaker(
            bind=engine,
            expire_on_commit=False,
            autoflush=False,
            class_=AsyncSession,
        )
    except Exception:
        AsyncSessionFactory = DummySessionFactory()


async def get_db():
    """FastAPI dependency — yields a session, closes it after the request."""
    if callable(AsyncSessionFactory):
        session = AsyncSessionFactory()
        if hasattr(session, "__aenter__"):
            async with session as s:
                try:
                    yield s
                except Exception:
                    await s.rollback()
                    raise
        else:
            yield session
    else:
        yield DummyAsyncSession()