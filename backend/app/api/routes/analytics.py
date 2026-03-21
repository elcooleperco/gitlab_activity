"""API аналитики — сводки, рейтинги, сравнения, тепловые карты."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.services.analytics import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Аналитика"])


@router.get("/summary")
async def get_summary(
    date_from: date = Query(..., description="Начало периода"),
    date_to: date = Query(..., description="Конец периода"),
    user_ids: Optional[str] = Query(None, description="ID пользователей через запятую"),
    db: AsyncSession = Depends(get_db),
):
    """Получить сводку активности пользователей за период. Можно фильтровать по user_ids."""
    analytics = AnalyticsService(db)
    ids = [int(x) for x in user_ids.split(",") if x.strip()] if user_ids else None
    return await analytics.get_summary(date_from, date_to, user_ids=ids)


@router.get("/daily")
async def get_daily_activity(
    date_from: date = Query(..., description="Начало периода"),
    date_to: date = Query(..., description="Конец периода"),
    user_id: int | None = Query(None, description="ID одного пользователя"),
    user_ids: Optional[str] = Query(None, description="ID пользователей через запятую"),
    db: AsyncSession = Depends(get_db),
):
    """Получить дневную разбивку активности за период."""
    analytics = AnalyticsService(db)
    ids = [int(x) for x in user_ids.split(",") if x.strip()] if user_ids else None
    return await analytics.get_daily_activity(date_from, date_to, user_id=user_id, user_ids=ids)


@router.get("/ranking")
async def get_ranking(
    date_from: date = Query(..., description="Начало периода"),
    date_to: date = Query(..., description="Конец периода"),
    db: AsyncSession = Depends(get_db),
):
    """Рейтинг пользователей — только активные (total_score > 0)."""
    analytics = AnalyticsService(db)
    summary = await analytics.get_summary(date_from, date_to)
    active = [u for u in summary if u["total_score"] > 0]
    for i, user in enumerate(active, 1):
        user["rank"] = i
    return active


@router.get("/inactive")
async def get_inactive_users(
    date_from: date = Query(..., description="Начало периода"),
    date_to: date = Query(..., description="Конец периода"),
    db: AsyncSession = Depends(get_db),
):
    """Список неактивных пользователей за период с датой последней активности."""
    analytics = AnalyticsService(db)
    return await analytics.get_inactive_users(date_from, date_to)


@router.get("/contribution/{user_id}")
async def get_contribution_map(
    user_id: int,
    date_from: date = Query(..., description="Начало периода"),
    date_to: date = Query(..., description="Конец периода"),
    db: AsyncSession = Depends(get_db),
):
    """Тепловая карта активности пользователя (как в GitLab contributions)."""
    analytics = AnalyticsService(db)
    return await analytics.get_contribution_map(user_id, date_from, date_to)


@router.get("/user-day/{user_id}")
async def get_user_day_details(
    user_id: int,
    target_date: date = Query(..., description="Дата для детализации"),
    db: AsyncSession = Depends(get_db),
):
    """Детальный список действий пользователя за конкретный день."""
    analytics = AnalyticsService(db)
    return await analytics.get_user_day_details(user_id, target_date)
