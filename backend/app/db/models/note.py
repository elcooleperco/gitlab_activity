"""Модель комментария (Note)."""

from datetime import datetime

from sqlalchemy import String, DateTime, Integer, Boolean, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Note(Base):
    """Комментарий к MR или Issue."""

    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, comment="ID комментария в GitLab")
    author_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("gitlab_users.id"), nullable=True, comment="Автор")
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("gitlab_projects.id"), nullable=False, comment="ID проекта")
    noteable_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="Тип сущности (MergeRequest/Issue)")
    noteable_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="ID сущности")
    body_length: Mapped[int] = mapped_column(Integer, default=0, comment="Длина текста комментария")
    system: Mapped[bool] = mapped_column(Boolean, default=False, comment="Системный комментарий")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, comment="Дата создания")

    __table_args__ = (
        Index("ix_notes_created_at", "created_at"),
        Index("ix_notes_author_id", "author_id"),
    )
