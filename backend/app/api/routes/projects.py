"""API для работы с проектами GitLab."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db.models import GitlabProject

router = APIRouter(prefix="/projects", tags=["Проекты"])


class ProjectResponse(BaseModel):
    """Данные проекта."""
    id: int
    name: str
    path_with_namespace: str
    description: str | None = None
    web_url: str | None = None
    visibility: str
    created_at: str | None = None
    last_activity_at: str | None = None


@router.get("", response_model=list[ProjectResponse])
async def get_projects(
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Получить список проектов с поиском."""
    query = select(GitlabProject).order_by(GitlabProject.name)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            GitlabProject.name.ilike(pattern) | GitlabProject.path_with_namespace.ilike(pattern)
        )
    result = await db.execute(query)
    projects = result.scalars().all()
    return [
        ProjectResponse(
            id=p.id,
            name=p.name,
            path_with_namespace=p.path_with_namespace,
            description=p.description,
            web_url=p.web_url,
            visibility=p.visibility,
            created_at=p.created_at.isoformat() if p.created_at else None,
            last_activity_at=p.last_activity_at.isoformat() if p.last_activity_at else None,
        )
        for p in projects
    ]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: int, db: AsyncSession = Depends(get_db)):
    """Получить данные конкретного проекта."""
    result = await db.execute(select(GitlabProject).where(GitlabProject.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        return {"error": "Проект не найден"}
    return ProjectResponse(
        id=project.id,
        name=project.name,
        path_with_namespace=project.path_with_namespace,
        description=project.description,
        web_url=project.web_url,
        visibility=project.visibility,
        created_at=project.created_at.isoformat() if project.created_at else None,
        last_activity_at=project.last_activity_at.isoformat() if project.last_activity_at else None,
    )
