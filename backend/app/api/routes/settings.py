"""API настроек подключения к GitLab."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings
from app.services.gitlab_client import GitLabClient

router = APIRouter(prefix="/settings", tags=["Настройки"])


class SettingsResponse(BaseModel):
    """Ответ с текущими настройками."""
    gitlab_url: str
    has_token: bool


class SettingsUpdate(BaseModel):
    """Запрос на обновление настроек."""
    gitlab_url: str | None = None
    gitlab_token: str | None = None


class ConnectionTestResponse(BaseModel):
    """Результат проверки подключения."""
    success: bool
    message: str
    username: str | None = None


@router.get("", response_model=SettingsResponse)
async def get_settings():
    """Получить текущие настройки."""
    return SettingsResponse(
        gitlab_url=settings.gitlab_url,
        has_token=bool(settings.gitlab_token),
    )


@router.put("")
async def update_settings(data: SettingsUpdate):
    """Обновить настройки подключения к GitLab и сохранить в БД."""
    if data.gitlab_url is not None:
        settings.gitlab_url = data.gitlab_url
        await settings.save_to_db("gitlab_url", data.gitlab_url)
    if data.gitlab_token is not None:
        settings.gitlab_token = data.gitlab_token
        await settings.save_to_db("gitlab_token", data.gitlab_token)
    return {"status": "ok"}


@router.get("/test", response_model=ConnectionTestResponse)
async def test_connection():
    """Проверить подключение к GitLab."""
    try:
        client = GitLabClient()
        user = await client.test_connection()
        return ConnectionTestResponse(
            success=True,
            message="Подключение успешно",
            username=user.get("username"),
        )
    except Exception as e:
        return ConnectionTestResponse(
            success=False,
            message=f"Ошибка подключения: {str(e)}",
        )
