"""Клиент для работы с GitLab REST API v4."""

from datetime import date
from typing import Any

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger()


class GitLabClient:
    """Асинхронный HTTP-клиент для GitLab API."""

    def __init__(self, url: str | None = None, token: str | None = None):
        self.base_url = (url or settings.gitlab_url).rstrip("/")
        self.token = token or settings.gitlab_token
        self.api_url = f"{self.base_url}/api/v4"
        self.headers = {"PRIVATE-TOKEN": self.token}

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Выполнить HTTP-запрос к GitLab API."""
        url = f"{self.api_url}{path}"
        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            response = await client.request(
                method, url, headers=self.headers, params=params
            )
            response.raise_for_status()
            return response.json()

    async def _get_all_pages(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        max_pages: int = 100,
    ) -> list[dict[str, Any]]:
        """Получить все страницы результатов с пагинацией."""
        params = params or {}
        params.setdefault("per_page", 100)
        all_items: list[dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            for page in range(1, max_pages + 1):
                params["page"] = page
                url = f"{self.api_url}{path}"
                response = await client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                items = response.json()
                if not items:
                    break
                all_items.extend(items)
                # Если получили меньше элементов чем per_page — это последняя страница
                if len(items) < params["per_page"]:
                    break

        return all_items

    async def test_connection(self) -> dict[str, Any]:
        """Проверить подключение к GitLab. Возвращает информацию о текущем пользователе."""
        return await self._request("GET", "/user")

    async def get_users(self) -> list[dict[str, Any]]:
        """Получить список всех пользователей."""
        return await self._get_all_pages("/users", {"active": "true"})

    async def get_projects(self) -> list[dict[str, Any]]:
        """Получить список всех проектов."""
        return await self._get_all_pages("/projects", {"membership": "false", "archived": "false"})

    async def get_project_commits(
        self,
        project_id: int,
        since: date | None = None,
        until: date | None = None,
    ) -> list[dict[str, Any]]:
        """Получить коммиты проекта за период."""
        params: dict[str, Any] = {"with_stats": "true"}
        if since:
            params["since"] = since.isoformat()
        if until:
            params["until"] = until.isoformat()
        return await self._get_all_pages(f"/projects/{project_id}/repository/commits", params)

    async def get_commit_by_sha(
        self,
        project_id: int,
        sha: str,
    ) -> dict[str, Any] | None:
        """Получить конкретный коммит по SHA (с stats)."""
        try:
            return await self._request("GET", f"/projects/{project_id}/repository/commits/{sha}", params={"stats": "true"})
        except Exception:
            return None

    async def get_project_merge_requests(
        self,
        project_id: int,
        created_after: date | None = None,
        created_before: date | None = None,
    ) -> list[dict[str, Any]]:
        """Получить merge requests проекта за период."""
        params: dict[str, Any] = {"state": "all"}
        if created_after:
            params["created_after"] = created_after.isoformat()
        if created_before:
            params["created_before"] = created_before.isoformat()
        return await self._get_all_pages(f"/projects/{project_id}/merge_requests", params)

    async def get_project_issues(
        self,
        project_id: int,
        created_after: date | None = None,
        created_before: date | None = None,
    ) -> list[dict[str, Any]]:
        """Получить задачи проекта за период."""
        params: dict[str, Any] = {"state": "all"}
        if created_after:
            params["created_after"] = created_after.isoformat()
        if created_before:
            params["created_before"] = created_before.isoformat()
        return await self._get_all_pages(f"/projects/{project_id}/issues", params)

    async def get_project_pipelines(
        self,
        project_id: int,
        updated_after: date | None = None,
        updated_before: date | None = None,
    ) -> list[dict[str, Any]]:
        """Получить пайплайны проекта за период."""
        params: dict[str, Any] = {}
        if updated_after:
            params["updated_after"] = updated_after.isoformat()
        if updated_before:
            params["updated_before"] = updated_before.isoformat()
        return await self._get_all_pages(f"/projects/{project_id}/pipelines", params)

    async def get_project_mr_notes(
        self,
        project_id: int,
        mr_iid: int,
    ) -> list[dict[str, Any]]:
        """Получить комментарии к merge request."""
        return await self._get_all_pages(
            f"/projects/{project_id}/merge_requests/{mr_iid}/notes"
        )

    async def get_project_issue_notes(
        self,
        project_id: int,
        issue_iid: int,
    ) -> list[dict[str, Any]]:
        """Получить комментарии к задаче."""
        return await self._get_all_pages(
            f"/projects/{project_id}/issues/{issue_iid}/notes"
        )

    async def get_user_events(
        self,
        user_id: int,
        after: date | None = None,
        before: date | None = None,
    ) -> list[dict[str, Any]]:
        """Получить события пользователя за период."""
        params: dict[str, Any] = {}
        if after:
            params["after"] = after.isoformat()
        if before:
            params["before"] = before.isoformat()
        return await self._get_all_pages(f"/users/{user_id}/events", params)
