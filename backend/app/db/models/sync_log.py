"""Модель журнала синхронизации."""

from datetime import datetime, date

from sqlalchemy import String, DateTime, Integer, Date, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SyncLog(Base):
    """Запись о выполненной синхронизации данных из GitLab."""

    __tablename__ = "sync_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, comment="Начало синхронизации")
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="Конец синхронизации")
    date_from: Mapped[date] = mapped_column(Date, nullable=False, comment="Начало периода")
    date_to: Mapped[date] = mapped_column(Date, nullable=False, comment="Конец периода")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="running", comment="Статус (running/completed/failed)")
    entities_synced: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="Счётчики по типам сущностей")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Сообщение об ошибке")
