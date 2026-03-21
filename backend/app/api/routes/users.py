"""API для работы с пользователями GitLab."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db.models import GitlabUser
from app.services.analytics import AnalyticsService

router = APIRouter(prefix="/users", tags=["Пользователи"])


class UserResponse(BaseModel):
    """Данные пользователя."""
    id: int
    username: str
    name: str
    email: str | None = None
    state: str
    is_admin: bool
    avatar_url: str | None = None
    created_at: str | None = None
    last_activity_at: str | None = None


@router.get("", response_model=list[UserResponse])
async def get_users(
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Получить список пользователей с поиском."""
    query = select(GitlabUser).order_by(GitlabUser.username)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            GitlabUser.username.ilike(pattern) | GitlabUser.name.ilike(pattern)
        )
    result = await db.execute(query)
    users = result.scalars().all()
    return [
        UserResponse(
            id=u.id,
            username=u.username,
            name=u.name,
            email=u.email,
            state=u.state,
            is_admin=u.is_admin,
            avatar_url=u.avatar_url,
            created_at=u.created_at.isoformat() if u.created_at else None,
            last_activity_at=u.last_activity_at.isoformat() if u.last_activity_at else None,
        )
        for u in users
    ]


@router.get("/{user_id}")
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    """Получить данные конкретного пользователя."""
    result = await db.execute(select(GitlabUser).where(GitlabUser.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return {"error": "Пользователь не найден"}
    return UserResponse(
        id=user.id,
        username=user.username,
        name=user.name,
        email=user.email,
        state=user.state,
        is_admin=user.is_admin,
        avatar_url=user.avatar_url,
        created_at=user.created_at.isoformat() if user.created_at else None,
        last_activity_at=user.last_activity_at.isoformat() if user.last_activity_at else None,
    )


@router.get("/{user_id}/activity")
async def get_user_activity(
    user_id: int,
    date_from: date = Query(..., description="Начало периода"),
    date_to: date = Query(..., description="Конец периода"),
    db: AsyncSession = Depends(get_db),
):
    """Получить метрики активности пользователя за период."""
    analytics = AnalyticsService(db)
    summary = await analytics.get_summary(date_from, date_to, user_id=user_id)
    if not summary:
        return {"error": "Данные не найдены"}
    return summary[0]
