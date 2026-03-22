"""Модель события (Event)."""

from datetime import datetime

from sqlalchemy import String, DateTime, Integer, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Event(Base):
    """Событие пользователя в GitLab."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, comment="ID события в GitLab")
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("gitlab_users.id"), nullable=True, comment="Автор")
    project_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("gitlab_projects.id"), nullable=True, comment="ID проекта")
    action_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="Тип действия (pushed/commented/...)")
    target_type: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="Тип объекта")
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="ID объекта")
    target_iid: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="IID объекта в проекте")
    target_title: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Заголовок объекта")
    # Данные о пуше (если action_name = pushed to / pushed new)
    push_ref: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="Ветка/тег пуша")
    push_commit_count: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="Количество коммитов в пуше")
    push_commit_title: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Заголовок последнего коммита")
    push_commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True, comment="SHA последнего коммита")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, comment="Дата события")

    __table_args__ = (
        Index("ix_events_created_at", "created_at"),
        Index("ix_events_user_id", "user_id"),
    )
