"""Модель пайплайна CI/CD."""

from datetime import datetime

from sqlalchemy import String, DateTime, Integer, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Pipeline(Base):
    """Пайплайн CI/CD в GitLab."""

    __tablename__ = "pipelines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, comment="ID пайплайна в GitLab")
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("gitlab_projects.id"), nullable=False, comment="ID проекта")
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("gitlab_users.id"), nullable=True, comment="Кто запустил")
    status: Mapped[str] = mapped_column(String(50), nullable=False, comment="Статус (success/failed/canceled/...)")
    ref: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="Ветка или тег")
    sha: Mapped[str | None] = mapped_column(String(40), nullable=True, comment="SHA коммита")
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="Длительность в секундах")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, comment="Дата создания")
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="Дата завершения")

    __table_args__ = (
        Index("ix_pipelines_created_at", "created_at"),
        Index("ix_pipelines_user_id", "user_id"),
    )
