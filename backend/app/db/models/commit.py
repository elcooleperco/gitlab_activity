"""Модель коммита."""

from datetime import datetime

from sqlalchemy import String, DateTime, Integer, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Commit(Base):
    """Коммит в репозитории GitLab."""

    __tablename__ = "commits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sha: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, comment="SHA хэш коммита")
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("gitlab_projects.id"), nullable=False, comment="ID проекта")
    author_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="Имя автора коммита")
    author_email: Mapped[str] = mapped_column(String(255), nullable=False, comment="Email автора коммита")
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("gitlab_users.id"), nullable=True, comment="Привязка к пользователю GitLab")
    message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Сообщение коммита")
    committed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, comment="Дата коммита")
    additions: Mapped[int] = mapped_column(Integer, default=0, comment="Добавленные строки")
    deletions: Mapped[int] = mapped_column(Integer, default=0, comment="Удалённые строки")

    __table_args__ = (
        Index("ix_commits_committed_at", "committed_at"),
        Index("ix_commits_user_id", "user_id"),
        Index("ix_commits_project_id", "project_id"),
    )
