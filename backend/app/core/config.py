"""Конфигурация приложения. Загрузка настроек из переменных окружения."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Основные настройки приложения."""

    # GitLab
    gitlab_url: str = "http://localhost"
    gitlab_token: str = ""

    # База данных
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/gitlab_analyzer"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Приложение
    backend_port: int = 8000
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
