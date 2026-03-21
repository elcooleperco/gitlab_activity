"""Модель merge request."""

from datetime import datetime

from sqlalchemy import String, DateTime, Integer, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MergeRequest(Base):
    """Merge Request в GitLab."""

    __tablename__ = "merge_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, comment="ID MR в GitLab")
    iid: Mapped[int] = mapped_column(Integer, nullable=False, comment="Номер MR в проекте")
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("gitlab_projects.id"), nullable=False, comment="ID проекта")
    author_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("gitlab_users.id"), nullable=True, comment="Автор")
    assignee_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("gitlab_users.id"), nullable=True, comment="Ответственный")
    title: Mapped[str] = mapped_column(String(500), nullable=False, comment="Заголовок")
    state: Mapped[str] = mapped_column(String(50), nullable=False, comment="Статус (opened/closed/merged)")
    source_branch: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="Исходная ветка")
    target_branch: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="Целевая ветка")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, comment="Дата создания")
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="Дата обновления")
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="Дата мержа")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="Дата закрытия")
    user_notes_count: Mapped[int] = mapped_column(Integer, default=0, comment="Количество комментариев")

    __table_args__ = (
        Index("ix_mr_created_at", "created_at"),
        Index("ix_mr_author_id", "author_id"),
        Index("ix_mr_project_id", "project_id"),
    )
