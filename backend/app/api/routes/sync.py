"""API управления синхронизацией данных из GitLab."""

from datetime import date, datetime

from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select, desc, delete, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db.models import SyncLog, Commit, MergeRequest, Issue, Note, Pipeline, Event
from app.services.sync_service import SyncService
from app.services.sync_state import sync_progress

router = APIRouter(prefix="/sync", tags=["Синхронизация"])


class SyncRequest(BaseModel):
    """Запрос на запуск синхронизации."""
    date_from: date
    date_to: date
    force_update: bool = False


class SyncStatusResponse(BaseModel):
    """Статус синхронизации."""
    id: int
    status: str
    date_from: date
    date_to: date
    started_at: str
    finished_at: str | None = None
    entities_synced: dict | None = None
    error_message: str | None = None


async def _run_sync(date_from: date, date_to: date, force: bool) -> None:
    """Фоновая задача синхронизации."""
    from app.db.session import async_session_factory
    async with async_session_factory() as session:
        service = SyncService(session)
        await service.sync_all(date_from, date_to, force)


@router.post("/start")
async def start_sync(
    data: SyncRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Запустить синхронизацию данных за указанный период."""
    # Проверяем, нет ли уже запущенной синхронизации
    result = await db.execute(
        select(SyncLog).where(SyncLog.status == "running").limit(1)
    )
    running = result.scalar_one_or_none()
    if running:
        return {"status": "already_running", "sync_id": running.id}

    background_tasks.add_task(_run_sync, data.date_from, data.date_to, data.force_update)
    return {"status": "started"}


@router.get("/status", response_model=list[SyncStatusResponse])
async def get_sync_status(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """Получить историю синхронизаций."""
    result = await db.execute(
        select(SyncLog).order_by(desc(SyncLog.started_at)).limit(limit)
    )
    logs = result.scalars().all()
    return [
        SyncStatusResponse(
            id=log.id,
            status=log.status,
            date_from=log.date_from,
            date_to=log.date_to,
            started_at=log.started_at.isoformat(),
            finished_at=log.finished_at.isoformat() if log.finished_at else None,
            entities_synced=log.entities_synced,
            error_message=log.error_message,
        )
        for log in logs
    ]


@router.get("/progress")
async def get_sync_progress():
    """Получить текущий прогресс синхронизации."""
    return sync_progress.to_dict()


@router.post("/cancel")
async def cancel_sync(
    db: AsyncSession = Depends(get_db),
):
    """Отменить текущую синхронизацию или сбросить зависшую."""
    # Если синхронизация реально работает в этом процессе — ставим флаг отмены
    if sync_progress.running:
        sync_progress.cancel()

    # Сбрасываем все записи в БД со статусом "running" → "cancelled"
    from sqlalchemy import update
    result = await db.execute(
        update(SyncLog)
        .where(SyncLog.status == "running")
        .values(status="cancelled", finished_at=datetime.now(), error_message="Отменена пользователем")
    )
    await db.commit()
    cancelled_count = result.rowcount

    return {"status": "cancelled", "reset_count": cancelled_count}


class PurgeRequest(BaseModel):
    """Запрос на очистку данных за период."""
    date_from: date
    date_to: date


@router.post("/purge")
async def purge_data(
    data: PurgeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Удалить собранные данные за указанный период."""
    d_from = data.date_from
    d_to = data.date_to
    deleted = {}

    # Удаляем в порядке зависимостей (сначала дочерние таблицы)
    for model, date_field, name in [
        (Note, Note.created_at, "notes"),
        (Event, Event.created_at, "events"),
        (Pipeline, Pipeline.created_at, "pipelines"),
        (Issue, Issue.created_at, "issues"),
        (MergeRequest, MergeRequest.created_at, "merge_requests"),
        (Commit, Commit.committed_at, "commits"),
    ]:
        result = await db.execute(
            delete(model).where(
                and_(
                    func.date(date_field) >= d_from,
                    func.date(date_field) <= d_to,
                )
            )
        )
        deleted[name] = result.rowcount

    await db.commit()
    return {"status": "ok", "deleted": deleted}
