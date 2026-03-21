"""Сервис синхронизации данных из GitLab в локальную БД."""

from datetime import date, datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    GitlabUser, GitlabProject, Commit, MergeRequest,
    Issue, Note, Pipeline, Event, SyncLog,
)
from app.services.gitlab_client import GitLabClient

logger = structlog.get_logger()


class SyncService:
    """Сервис загрузки данных из GitLab API и сохранения в PostgreSQL."""

    def __init__(self, session: AsyncSession, client: GitLabClient | None = None):
        self.session = session
        self.client = client or GitLabClient()
        self.counters: dict[str, int] = {}

    async def sync_all(
        self,
        date_from: date,
        date_to: date,
        force: bool = False,
    ) -> SyncLog:
        """Запустить полную синхронизацию за указанный период."""
        log = SyncLog(
            started_at=datetime.now(timezone.utc),
            date_from=date_from,
            date_to=date_to,
            status="running",
        )
        self.session.add(log)
        await self.session.commit()

        try:
            await self.sync_users()
            await self.sync_projects()

            # Получаем список проектов для синхронизации содержимого
            result = await self.session.execute(select(GitlabProject.id))
            project_ids = [row[0] for row in result.fetchall()]

            for project_id in project_ids:
                await self.sync_project_commits(project_id, date_from, date_to)
                await self.sync_project_merge_requests(project_id, date_from, date_to)
                await self.sync_project_issues(project_id, date_from, date_to)
                await self.sync_project_pipelines(project_id, date_from, date_to)

            # Синхронизируем события пользователей
            user_result = await self.session.execute(select(GitlabUser.id))
            user_ids = [row[0] for row in user_result.fetchall()]

            for user_id in user_ids:
                await self.sync_user_events(user_id, date_from, date_to)

            log.status = "completed"
            log.entities_synced = self.counters
            log.finished_at = datetime.now(timezone.utc)
            await self.session.commit()

            logger.info("Синхронизация завершена", counters=self.counters)
            return log

        except Exception as e:
            log.status = "failed"
            log.error_message = str(e)
            log.finished_at = datetime.now(timezone.utc)
            await self.session.commit()
            logger.error("Ошибка синхронизации", error=str(e))
            raise

    async def sync_users(self) -> None:
        """Синхронизировать пользователей."""
        users_data = await self.client.get_users()
        count = 0

        for u in users_data:
            stmt = pg_insert(GitlabUser).values(
                id=u["id"],
                username=u["username"],
                name=u.get("name", u["username"]),
                email=u.get("email"),
                state=u.get("state", "active"),
                is_admin=u.get("is_admin", False),
                avatar_url=u.get("avatar_url"),
                created_at=u.get("created_at"),
                last_activity_at=u.get("last_activity_on"),
                synced_at=datetime.now(timezone.utc),
            ).on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "username": u["username"],
                    "name": u.get("name", u["username"]),
                    "email": u.get("email"),
                    "state": u.get("state", "active"),
                    "is_admin": u.get("is_admin", False),
                    "avatar_url": u.get("avatar_url"),
                    "last_activity_at": u.get("last_activity_on"),
                    "synced_at": datetime.now(timezone.utc),
                },
            )
            await self.session.execute(stmt)
            count += 1

        await self.session.commit()
        self.counters["users"] = count
        logger.info("Пользователи синхронизированы", count=count)

    async def sync_projects(self) -> None:
        """Синхронизировать проекты."""
        projects_data = await self.client.get_projects()
        count = 0

        for p in projects_data:
            stmt = pg_insert(GitlabProject).values(
                id=p["id"],
                name=p["name"],
                path_with_namespace=p["path_with_namespace"],
                description=p.get("description"),
                web_url=p.get("web_url"),
                visibility=p.get("visibility", "private"),
                created_at=p.get("created_at"),
                last_activity_at=p.get("last_activity_at"),
                synced_at=datetime.now(timezone.utc),
            ).on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "name": p["name"],
                    "path_with_namespace": p["path_with_namespace"],
                    "description": p.get("description"),
                    "web_url": p.get("web_url"),
                    "visibility": p.get("visibility", "private"),
                    "last_activity_at": p.get("last_activity_at"),
                    "synced_at": datetime.now(timezone.utc),
                },
            )
            await self.session.execute(stmt)
            count += 1

        await self.session.commit()
        self.counters["projects"] = count
        logger.info("Проекты синхронизированы", count=count)

    async def sync_project_commits(
        self, project_id: int, date_from: date, date_to: date
    ) -> None:
        """Синхронизировать коммиты проекта за период."""
        try:
            commits_data = await self.client.get_project_commits(project_id, date_from, date_to)
        except Exception as e:
            logger.warning("Не удалось получить коммиты", project_id=project_id, error=str(e))
            return

        # Построить маппинг email -> user_id для привязки
        result = await self.session.execute(select(GitlabUser.id, GitlabUser.email))
        email_to_user = {row[1]: row[0] for row in result.fetchall() if row[1]}

        count = 0
        for c in commits_data:
            stats = c.get("stats") or {}
            author_email = c.get("author_email", "")
            user_id = email_to_user.get(author_email)

            stmt = pg_insert(Commit).values(
                sha=c["id"],
                project_id=project_id,
                author_name=c.get("author_name", ""),
                author_email=author_email,
                user_id=user_id,
                message=c.get("message"),
                committed_at=c.get("committed_date") or c.get("created_at"),
                additions=stats.get("additions", 0),
                deletions=stats.get("deletions", 0),
            ).on_conflict_do_update(
                index_elements=["sha"],
                set_={
                    "user_id": user_id,
                    "additions": stats.get("additions", 0),
                    "deletions": stats.get("deletions", 0),
                },
            )
            await self.session.execute(stmt)
            count += 1

        await self.session.commit()
        self.counters["commits"] = self.counters.get("commits", 0) + count

    async def sync_project_merge_requests(
        self, project_id: int, date_from: date, date_to: date
    ) -> None:
        """Синхронизировать merge requests проекта за период."""
        try:
            mrs_data = await self.client.get_project_merge_requests(project_id, date_from, date_to)
        except Exception as e:
            logger.warning("Не удалось получить MR", project_id=project_id, error=str(e))
            return

        count = 0
        for mr in mrs_data:
            author = mr.get("author") or {}
            assignee = mr.get("assignee") or {}
            stmt = pg_insert(MergeRequest).values(
                id=mr["id"],
                iid=mr["iid"],
                project_id=project_id,
                author_id=author.get("id"),
                assignee_id=assignee.get("id"),
                title=mr["title"],
                state=mr["state"],
                source_branch=mr.get("source_branch"),
                target_branch=mr.get("target_branch"),
                created_at=mr["created_at"],
                updated_at=mr.get("updated_at"),
                merged_at=mr.get("merged_at"),
                closed_at=mr.get("closed_at"),
                user_notes_count=mr.get("user_notes_count", 0),
            ).on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "state": mr["state"],
                    "updated_at": mr.get("updated_at"),
                    "merged_at": mr.get("merged_at"),
                    "closed_at": mr.get("closed_at"),
                    "user_notes_count": mr.get("user_notes_count", 0),
                },
            )
            await self.session.execute(stmt)
            count += 1

            # Синхронизируем комментарии к MR
            await self._sync_notes(project_id, "MergeRequest", mr["iid"], mr["id"])

        await self.session.commit()
        self.counters["merge_requests"] = self.counters.get("merge_requests", 0) + count

    async def sync_project_issues(
        self, project_id: int, date_from: date, date_to: date
    ) -> None:
        """Синхронизировать задачи проекта за период."""
        try:
            issues_data = await self.client.get_project_issues(project_id, date_from, date_to)
        except Exception as e:
            logger.warning("Не удалось получить задачи", project_id=project_id, error=str(e))
            return

        count = 0
        for issue in issues_data:
            author = issue.get("author") or {}
            assignee = issue.get("assignee") or {}
            stmt = pg_insert(Issue).values(
                id=issue["id"],
                iid=issue["iid"],
                project_id=project_id,
                author_id=author.get("id"),
                assignee_id=assignee.get("id"),
                title=issue["title"],
                state=issue["state"],
                labels=issue.get("labels"),
                created_at=issue["created_at"],
                updated_at=issue.get("updated_at"),
                closed_at=issue.get("closed_at"),
                user_notes_count=issue.get("user_notes_count", 0),
            ).on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "state": issue["state"],
                    "updated_at": issue.get("updated_at"),
                    "closed_at": issue.get("closed_at"),
                    "user_notes_count": issue.get("user_notes_count", 0),
                    "labels": issue.get("labels"),
                },
            )
            await self.session.execute(stmt)
            count += 1

            # Синхронизируем комментарии к задаче
            await self._sync_notes(project_id, "Issue", issue["iid"], issue["id"])

        await self.session.commit()
        self.counters["issues"] = self.counters.get("issues", 0) + count

    async def sync_project_pipelines(
        self, project_id: int, date_from: date, date_to: date
    ) -> None:
        """Синхронизировать пайплайны проекта за период."""
        try:
            pipelines_data = await self.client.get_project_pipelines(project_id, date_from, date_to)
        except Exception as e:
            logger.warning("Не удалось получить пайплайны", project_id=project_id, error=str(e))
            return

        count = 0
        for p in pipelines_data:
            user = p.get("user") or {}
            stmt = pg_insert(Pipeline).values(
                id=p["id"],
                project_id=project_id,
                user_id=user.get("id"),
                status=p["status"],
                ref=p.get("ref"),
                sha=p.get("sha"),
                duration=p.get("duration"),
                created_at=p["created_at"],
                finished_at=p.get("finished_at"),
            ).on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "status": p["status"],
                    "duration": p.get("duration"),
                    "finished_at": p.get("finished_at"),
                },
            )
            await self.session.execute(stmt)
            count += 1

        await self.session.commit()
        self.counters["pipelines"] = self.counters.get("pipelines", 0) + count

    async def _sync_notes(
        self, project_id: int, noteable_type: str, noteable_iid: int, noteable_id: int
    ) -> None:
        """Синхронизировать комментарии к MR или Issue."""
        try:
            if noteable_type == "MergeRequest":
                notes_data = await self.client.get_project_mr_notes(project_id, noteable_iid)
            else:
                notes_data = await self.client.get_project_issue_notes(project_id, noteable_iid)
        except Exception:
            return

        count = 0
        for n in notes_data:
            author = n.get("author") or {}
            stmt = pg_insert(Note).values(
                id=n["id"],
                author_id=author.get("id"),
                project_id=project_id,
                noteable_type=noteable_type,
                noteable_id=noteable_id,
                body_length=len(n.get("body", "")),
                system=n.get("system", False),
                created_at=n["created_at"],
            ).on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "body_length": len(n.get("body", "")),
                },
            )
            await self.session.execute(stmt)
            count += 1

        self.counters["notes"] = self.counters.get("notes", 0) + count

    async def sync_user_events(
        self, user_id: int, date_from: date, date_to: date
    ) -> None:
        """Синхронизировать события пользователя за период."""
        try:
            events_data = await self.client.get_user_events(user_id, date_from, date_to)
        except Exception as e:
            logger.warning("Не удалось получить события", user_id=user_id, error=str(e))
            return

        count = 0
        for ev in events_data:
            stmt = pg_insert(Event).values(
                id=ev["id"],
                user_id=user_id,
                project_id=ev.get("project_id"),
                action_name=ev.get("action_name", "unknown"),
                target_type=ev.get("target_type"),
                target_id=ev.get("target_id"),
                created_at=ev["created_at"],
            ).on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "action_name": ev.get("action_name", "unknown"),
                },
            )
            await self.session.execute(stmt)
            count += 1

        await self.session.commit()
        self.counters["events"] = self.counters.get("events", 0) + count
