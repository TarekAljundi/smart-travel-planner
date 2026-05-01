# backend/tests/conftest.py
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import get_settings

settings = get_settings()

# Use an in‑memory SQLite database for testing (no PostgreSQL needed)
TEST_DATABASE_URL = "sqlite+aiosqlite:///test.db"

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.fixture
async def async_session():
    """Async SQLAlchemy session connected to a test database."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session_factory() as session:
        yield session
    await engine.dispose()