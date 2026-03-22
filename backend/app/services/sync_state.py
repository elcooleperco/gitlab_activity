"""Глобальное состояние синхронизации — прогресс, логи, управление."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class SyncStep:
    """Шаг плана синхронизации."""
    name: str
    status: str = "pending"  # pending, running, completed, skipped, failed
    total: int = 0    # Всего обработано
    new: int = 0      # Из них новых
    updated: int = 0  # Из них обновлённых (ранее загруженные)


@dataclass
class SyncProgress:
    """Текущий прогресс синхронизации."""
    running: bool = False
    cancelled: bool = False
    percent: float = 0.0
    current_step: str = ""
    steps: list[SyncStep] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    max_logs: int = 100

    def reset(self) -> None:
        """Сбросить состояние перед новой синхронизацией."""
        self.running = True
        self.cancelled = False
        self.percent = 0.0
        self.current_step = ""
        self.steps = []
        self.logs = []

    def add_log(self, message: str) -> None:
        """Добавить запись в лог."""
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self.logs.append(f"[{ts}] {message}")
        if len(self.logs) > self.max_logs:
            self.logs = self.logs[-self.max_logs:]

    def set_step(self, name: str) -> None:
        """Начать новый шаг."""
        # Завершить предыдущий запущенный шаг
        for s in self.steps:
            if s.status == "running":
                s.status = "completed"
        # Найти или создать шаг
        for s in self.steps:
            if s.name == name:
                s.status = "running"
                self.current_step = name
                return
        step = SyncStep(name=name, status="running")
        self.steps.append(step)
        self.current_step = name

    def complete_step(self, name: str) -> None:
        """Завершить шаг."""
        for s in self.steps:
            if s.name == name:
                s.status = "completed"

    def add_to_step(self, name: str, total: int = 0, new: int = 0, updated: int = 0) -> None:
        """Добавить к счётчикам шага."""
        for s in self.steps:
            if s.name == name:
                s.total += total
                s.new += new
                s.updated += updated
                return

    def fail_step(self, name: str) -> None:
        """Пометить шаг как неудачный."""
        for s in self.steps:
            if s.name == name:
                s.status = "failed"

    def finish(self) -> None:
        """Синхронизация завершена."""
        self.running = False
        self.percent = 100.0
        for s in self.steps:
            if s.status == "running":
                s.status = "completed"

    def cancel(self) -> None:
        """Запрос на отмену."""
        self.cancelled = True
        self.add_log("⚠ Запрошена отмена синхронизации...")

    def to_dict(self) -> dict:
        """Сериализация для API."""
        return {
            "running": self.running,
            "cancelled": self.cancelled,
            "percent": round(self.percent, 1),
            "current_step": self.current_step,
            "steps": [
                {"name": s.name, "status": s.status, "total": s.total, "new": s.new, "updated": s.updated}
                for s in self.steps
            ],
            "logs": self.logs[-30:],  # Последние 30 записей
        }


# Глобальный синглтон
sync_progress = SyncProgress()
