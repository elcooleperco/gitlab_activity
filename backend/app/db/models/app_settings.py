"""Модель настроек приложения — хранение в БД для персистентности."""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AppSetting(Base):
    """Настройка приложения (ключ-значение)."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(255), primary_key=True, comment="Ключ настройки")
    value: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="Значение настройки")
