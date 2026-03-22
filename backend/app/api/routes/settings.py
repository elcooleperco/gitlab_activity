"""API настроек подключения к GitLab и UI-предпочтений."""

import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.db.models import AppSetting
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


UI_PREFS_KEY = "ui_preferences"


@router.get("/preferences")
async def get_preferences(db: AsyncSession = Depends(get_db)):
    """Получить сохранённые UI-предпочтения (периоды и т.д.)."""
    result = await db.execute(
        select(AppSetting.value).where(AppSetting.key == UI_PREFS_KEY)
    )
    row = result.scalar_one_or_none()
    if row:
        try:
            return json.loads(row)
        except json.JSONDecodeError:
            pass
    return {}


@router.put("/preferences")
async def save_preferences(data: dict, db: AsyncSession = Depends(get_db)):
    """Сохранить UI-предпочтения."""
    value = json.dumps(data, ensure_ascii=False)
    stmt = pg_insert(AppSetting).values(
        key=UI_PREFS_KEY, value=value
    ).on_conflict_do_update(
        index_elements=["key"], set_={"value": value}
    )
    await db.execute(stmt)
    await db.commit()
    return {"status": "ok"}
