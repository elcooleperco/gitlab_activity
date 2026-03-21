"""Модель пользователя GitLab."""

from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GitlabUser(Base):
    """Пользователь GitLab."""

    __tablename__ = "gitlab_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, comment="ID пользователя в GitLab")
    username: Mapped[str] = mapped_column(String(255), nullable=False, comment="Логин")
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="Полное имя")
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="Email")
    state: Mapped[str] = mapped_column(String(50), nullable=False, default="active", comment="Статус (active/blocked)")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, comment="Является ли администратором")
    avatar_url: Mapped[str | None] = mapped_column(String(1000), nullable=True, comment="URL аватара")
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="Дата создания в GitLab")
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="Последняя активность")
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="Дата последней синхронизации")
