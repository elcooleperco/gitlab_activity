"""Конфигурация приложения. Загрузка настроек из переменных окружения."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Основные настройки приложения (из переменных окружения)."""

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


# Настройки из env (неизменяемые)
_env_settings = Settings()


class RuntimeSettings:
    """Настройки, изменяемые в runtime через API. Приоритет: runtime > env."""

    def __init__(self):
        self._overrides: dict[str, str] = {}

    @property
    def gitlab_url(self) -> str:
        return self._overrides.get("gitlab_url", _env_settings.gitlab_url)

    @gitlab_url.setter
    def gitlab_url(self, value: str):
        self._overrides["gitlab_url"] = value

    @property
    def gitlab_token(self) -> str:
        return self._overrides.get("gitlab_token", _env_settings.gitlab_token)

    @gitlab_token.setter
    def gitlab_token(self, value: str):
        self._overrides["gitlab_token"] = value

    @property
    def database_url(self) -> str:
        return _env_settings.database_url

    @property
    def redis_url(self) -> str:
        return _env_settings.redis_url

    @property
    def backend_port(self) -> int:
        return _env_settings.backend_port

    @property
    def log_level(self) -> str:
        return _env_settings.log_level

    @property
    def cors_origins(self) -> list[str]:
        return _env_settings.cors_origins


settings = RuntimeSettings()
