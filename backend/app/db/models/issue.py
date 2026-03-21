"""Модель задачи (Issue)."""

from datetime import datetime

from sqlalchemy import String, DateTime, Integer, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Issue(Base):
    """Задача (Issue) в GitLab."""

    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, comment="ID задачи в GitLab")
    iid: Mapped[int] = mapped_column(Integer, nullable=False, comment="Номер задачи в проекте")
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("gitlab_projects.id"), nullable=False, comment="ID проекта")
    author_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("gitlab_users.id"), nullable=True, comment="Автор")
    assignee_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("gitlab_users.id"), nullable=True, comment="Ответственный")
    title: Mapped[str] = mapped_column(String(500), nullable=False, comment="Заголовок")
    state: Mapped[str] = mapped_column(String(50), nullable=False, comment="Статус (opened/closed)")
    labels: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="Метки")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, comment="Дата создания")
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="Дата обновления")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="Дата закрытия")
    user_notes_count: Mapped[int] = mapped_column(Integer, default=0, comment="Количество комментариев")

    __table_args__ = (
        Index("ix_issues_created_at", "created_at"),
        Index("ix_issues_author_id", "author_id"),
        Index("ix_issues_project_id", "project_id"),
    )
