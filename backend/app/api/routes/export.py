"""API экспорта данных в CSV."""

import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.services.analytics import AnalyticsService

router = APIRouter(prefix="/export", tags=["Экспорт"])


def _make_csv_response(rows: list[dict], filename: str) -> StreamingResponse:
    """Создать HTTP-ответ с CSV-файлом."""
    if not rows:
        output = io.StringIO()
        output.write("Нет данных за указанный период\n")
        output.seek(0)
    else:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/csv/summary")
async def export_summary_csv(
    date_from: date = Query(..., description="Начало периода"),
    date_to: date = Query(..., description="Конец периода"),
    db: AsyncSession = Depends(get_db),
):
    """Экспорт сводки активности в CSV."""
    analytics = AnalyticsService(db)
    summary = await analytics.get_summary(date_from, date_to)
    filename = f"summary_{date_from}_{date_to}.csv"
    return _make_csv_response(summary, filename)


@router.get("/csv/daily")
async def export_daily_csv(
    date_from: date = Query(..., description="Начало периода"),
    date_to: date = Query(..., description="Конец периода"),
    user_id: int | None = Query(None, description="ID пользователя"),
    db: AsyncSession = Depends(get_db),
):
    """Экспорт дневной активности в CSV."""
    analytics = AnalyticsService(db)
    daily = await analytics.get_daily_activity(date_from, date_to, user_id)
    filename = f"daily_{date_from}_{date_to}.csv"
    return _make_csv_response(daily, filename)
