"""Модель проекта GitLab."""

from datetime import datetime

from sqlalchemy import String, DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GitlabProject(Base):
    """Проект (репозиторий) в GitLab."""

    __tablename__ = "gitlab_projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, comment="ID проекта в GitLab")
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="Название проекта")
    path_with_namespace: Mapped[str] = mapped_column(String(500), nullable=False, comment="Полный путь (namespace/project)")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Описание")
    web_url: Mapped[str | None] = mapped_column(String(1000), nullable=True, comment="URL проекта в GitLab")
    visibility: Mapped[str] = mapped_column(String(50), nullable=False, default="private", comment="Видимость (private/internal/public)")
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="Дата создания")
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="Последняя активность")
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="Дата последней синхронизации")
