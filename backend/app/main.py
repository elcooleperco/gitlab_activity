"""Точка входа FastAPI-приложения."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.api.routes import settings as settings_routes
from app.api.routes import sync, users, projects, analytics, export


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Инициализация при запуске и очистка при остановке."""
    setup_logging()
    yield


app = FastAPI(
    title="GitLab Analyzer",
    description="Сервис анализа активности пользователей GitLab",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS для фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(settings_routes.router, prefix="/api")
app.include_router(sync.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(export.router, prefix="/api")


@app.get("/api/health")
async def health_check():
    """Проверка работоспособности сервиса."""
    return {"status": "ok"}
