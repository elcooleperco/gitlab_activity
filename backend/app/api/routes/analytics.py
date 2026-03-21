"""API аналитики — сводки, рейтинги, сравнения."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.services.analytics import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Аналитика"])


@router.get("/summary")
async def get_summary(
    date_from: date = Query(..., description="Начало периода"),
    date_to: date = Query(..., description="Конец периода"),
    db: AsyncSession = Depends(get_db),
):
    """Получить сводку активности всех пользователей за период."""
    analytics = AnalyticsService(db)
    return await analytics.get_summary(date_from, date_to)


@router.get("/daily")
async def get_daily_activity(
    date_from: date = Query(..., description="Начало периода"),
    date_to: date = Query(..., description="Конец периода"),
    user_id: int | None = Query(None, description="ID пользователя (опционально)"),
    db: AsyncSession = Depends(get_db),
):
    """Получить дневную разбивку активности за период."""
    analytics = AnalyticsService(db)
    return await analytics.get_daily_activity(date_from, date_to, user_id)


@router.get("/ranking")
async def get_ranking(
    date_from: date = Query(..., description="Начало периода"),
    date_to: date = Query(..., description="Конец периода"),
    db: AsyncSession = Depends(get_db),
):
    """Получить рейтинг пользователей по активности за период."""
    analytics = AnalyticsService(db)
    summary = await analytics.get_summary(date_from, date_to)
    # Добавляем позицию в рейтинге
    for i, user in enumerate(summary, 1):
        user["rank"] = i
    return summary


@router.get("/inactive")
async def get_inactive_users(
    date_from: date = Query(..., description="Начало периода"),
    date_to: date = Query(..., description="Конец периода"),
    db: AsyncSession = Depends(get_db),
):
    """Получить список неактивных пользователей за период."""
    analytics = AnalyticsService(db)
    return await analytics.get_inactive_users(date_from, date_to)
