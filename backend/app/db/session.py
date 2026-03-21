"""Настройка подключения к базе данных и фабрика сессий."""

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession

from app.core.config import settings

# Асинхронный движок подключения к PostgreSQL
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=20,
    max_overflow=10,
)

# Фабрика асинхронных сессий
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncSession:
    """Получить сессию БД для использования в зависимостях FastAPI."""
    async with async_session_factory() as session:
        yield session
