"""Сервис синхронизации данных из GitLab в локальную БД."""

from datetime import date, datetime, timezone
from typing import Optional

import structlog


def _parse_dt(value) -> Optional[datetime]:
    """Преобразовать строку из GitLab API в datetime. Возвращает None если невалидно."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date) and not isinstance(value, datetime):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    if isinstance(value, str):
        # GitLab отдаёт ISO 8601: "2024-03-22T10:30:45.000Z" или "2024-03-22T10:30:45.000+03:00"
        val = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(val)
        except ValueError:
            return None
    return None
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    GitlabUser, GitlabProject, Commit, MergeRequest,
    Issue, Note, Pipeline, Event, SyncLog,
)
from app.services.gitlab_client import GitLabClient
from app.services.sync_state import sync_progress

logger = structlog.get_logger()


class SyncService:
    """Сервис загрузки данных из GitLab API и сохранения в PostgreSQL."""

    def __init__(self, session: AsyncSession, client: GitLabClient | None = None):
        self.session = session
        self.client = client or GitLabClient()
        self.counters: dict[str, int] = {}

    def _check_cancelled(self) -> None:
        """Проверить запрос отмены и прервать если нужно."""
        if sync_progress.cancelled:
            raise RuntimeError("Синхронизация отменена пользователем")

    async def sync_all(
        self,
        date_from: date,
        date_to: date,
        force: bool = False,
    ) -> SyncLog:
        """Запустить полную синхронизацию за указанный период."""
        sync_progress.reset()

        log = SyncLog(
            started_at=datetime.now(timezone.utc),
            date_from=date_from,
            date_to=date_to,
            status="running",
        )
        self.session.add(log)
        await self.session.commit()

        # Формируем план
        sync_progress.steps = []
        for name in ["Загрузка пользователей", "Загрузка проектов",
                      "Коммиты по проектам", "Merge Requests", "Issues",
                      "Пайплайны", "События пользователей", "Привязка коммитов"]:
            from app.services.sync_state import SyncStep
            sync_progress.steps.append(SyncStep(name=name))

        try:
            # Шаг 1: Пользователи
            sync_progress.set_step("Загрузка пользователей")
            sync_progress.add_log("Загрузка списка пользователей из GitLab...")
            await self.sync_users()
            sync_progress.complete_step("Загрузка пользователей")
            sync_progress.percent = 5
            self._check_cancelled()

            # Шаг 2: Проекты
            sync_progress.set_step("Загрузка проектов")
            sync_progress.add_log("Загрузка списка проектов из GitLab...")
            await self.sync_projects()
            sync_progress.complete_step("Загрузка проектов")
            sync_progress.percent = 10
            self._check_cancelled()

            # Получаем список проектов
            result = await self.session.execute(select(GitlabProject.id, GitlabProject.path_with_namespace))
            projects = result.fetchall()
            project_ids = [row[0] for row in projects]
            project_names = {row[0]: row[1] for row in projects}
            total_projects = len(project_ids)

            # Шаг 3: Коммиты
            sync_progress.set_step("Коммиты по проектам")
            for i, pid in enumerate(project_ids):
                self._check_cancelled()
                pname = project_names.get(pid, str(pid))
                sync_progress.add_log(f"Коммиты: {pname} ({i+1}/{total_projects})")
                sync_progress.percent = 10 + (i / max(total_projects, 1)) * 15
                await self.sync_project_commits(pid, date_from, date_to)
            sync_progress.complete_step("Коммиты по проектам")
            sync_progress.percent = 25

            # Шаг 4: MR
            sync_progress.set_step("Merge Requests")
            for i, pid in enumerate(project_ids):
                self._check_cancelled()
                pname = project_names.get(pid, str(pid))
                sync_progress.add_log(f"MR: {pname} ({i+1}/{total_projects})")
                sync_progress.percent = 25 + (i / max(total_projects, 1)) * 15
                await self.sync_project_merge_requests(pid, date_from, date_to)
            sync_progress.complete_step("Merge Requests")
            sync_progress.percent = 40

            # Шаг 5: Issues
            sync_progress.set_step("Issues")
            for i, pid in enumerate(project_ids):
                self._check_cancelled()
                pname = project_names.get(pid, str(pid))
                sync_progress.add_log(f"Issues: {pname} ({i+1}/{total_projects})")
                sync_progress.percent = 40 + (i / max(total_projects, 1)) * 15
                await self.sync_project_issues(pid, date_from, date_to)
            sync_progress.complete_step("Issues")
            sync_progress.percent = 55

            # Шаг 6: Пайплайны
            sync_progress.set_step("Пайплайны")
            for i, pid in enumerate(project_ids):
                self._check_cancelled()
                pname = project_names.get(pid, str(pid))
                sync_progress.add_log(f"Пайплайны: {pname} ({i+1}/{total_projects})")
                sync_progress.percent = 55 + (i / max(total_projects, 1)) * 15
                await self.sync_project_pipelines(pid, date_from, date_to)
            sync_progress.complete_step("Пайплайны")
            sync_progress.percent = 70

            # Шаг 7: События пользователей
            sync_progress.set_step("События пользователей")
            user_result = await self.session.execute(select(GitlabUser.id, GitlabUser.username))
            users = user_result.fetchall()
            total_users = len(users)

            for i, (uid, uname) in enumerate(users):
                self._check_cancelled()
                sync_progress.add_log(f"События: @{uname} ({i+1}/{total_users})")
                sync_progress.percent = 70 + (i / max(total_users, 1)) * 20
                await self.sync_user_events(uid, date_from, date_to)
            sync_progress.complete_step("События пользователей")
            sync_progress.percent = 90

            # Шаг 8: Привязка коммитов
            sync_progress.set_step("Привязка коммитов")
            sync_progress.add_log("Привязка осиротевших коммитов к пользователям...")
            await self._fix_orphaned_commits()
            sync_progress.complete_step("Привязка коммитов")

            log.status = "completed"
            log.entities_synced = self.counters
            log.finished_at = datetime.now(timezone.utc)
            await self.session.commit()

            sync_progress.add_log(f"Синхронизация завершена: {self.counters}")
            sync_progress.finish()
            logger.info("Синхронизация завершена", counters=self.counters)
            return log

        except Exception as e:
            log.status = "failed" if not sync_progress.cancelled else "cancelled"
            log.error_message = str(e)
            log.finished_at = datetime.now(timezone.utc)
            await self.session.commit()

            sync_progress.add_log(f"Ошибка: {e}")
            sync_progress.finish()
            logger.error("Ошибка синхронизации", error=str(e))
            if not sync_progress.cancelled:
                raise

    async def _fix_orphaned_commits(self) -> None:
        """Привязать коммиты без user_id к пользователям через различные маппинги."""
        from sqlalchemy import update

        # 1. Маппинг: username/name -> user_id (lower case)
        result = await self.session.execute(
            select(GitlabUser.id, GitlabUser.username, GitlabUser.name, GitlabUser.email)
        )
        users = result.fetchall()

        fixed = 0
        for user in users:
            # Обновляем коммиты где author_name совпадает с username или name (case-insensitive)
            names_to_try = set()
            if user.username:
                names_to_try.add(user.username.lower())
            if user.name:
                names_to_try.add(user.name.lower())

            for name in names_to_try:
                res = await self.session.execute(
                    update(Commit)
                    .where(Commit.user_id.is_(None))
                    .where(func.lower(Commit.author_name) == name)
                    .values(user_id=user.id)
                )
                fixed += res.rowcount

            # Обновляем по email (дополнительные email — в git может быть локальный email)
            if user.email:
                res = await self.session.execute(
                    update(Commit)
                    .where(Commit.user_id.is_(None))
                    .where(func.lower(Commit.author_email) == user.email.lower())
                    .values(user_id=user.id)
                )
                fixed += res.rowcount

        await self.session.commit()
        if fixed:
            logger.info("Привязано осиротевших коммитов", count=fixed)

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
                created_at=_parse_dt(u.get("created_at")),
                last_activity_at=_parse_dt(u.get("last_activity_on")),
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
                    "last_activity_at": _parse_dt(u.get("last_activity_on")),
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
                created_at=_parse_dt(p.get("created_at")),
                last_activity_at=_parse_dt(p.get("last_activity_at")),
                synced_at=datetime.now(timezone.utc),
            ).on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "name": p["name"],
                    "path_with_namespace": p["path_with_namespace"],
                    "description": p.get("description"),
                    "web_url": p.get("web_url"),
                    "visibility": p.get("visibility", "private"),
                    "last_activity_at": _parse_dt(p.get("last_activity_at")),
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

        # Построить маппинги для привязки коммитов к пользователям
        result = await self.session.execute(
            select(GitlabUser.id, GitlabUser.email, GitlabUser.username, GitlabUser.name)
        )
        email_to_user: dict[str, int] = {}
        username_to_user: dict[str, int] = {}
        name_to_user: dict[str, int] = {}
        for row in result.fetchall():
            if row.email:
                email_to_user[row.email.lower()] = row.id
            if row.username:
                username_to_user[row.username.lower()] = row.id
            if row.name:
                name_to_user[row.name.lower()] = row.id

        count = 0
        for c in commits_data:
            stats = c.get("stats") or {}
            author_email = c.get("author_email", "")
            author_name = c.get("author_name", "")
            # Пробуем привязать: сначала по email, потом по username, потом по имени
            user_id = (
                email_to_user.get(author_email.lower())
                or username_to_user.get(author_name.lower())
                or name_to_user.get(author_name.lower())
            )

            stmt = pg_insert(Commit).values(
                sha=c["id"],
                project_id=project_id,
                author_name=c.get("author_name", ""),
                author_email=author_email,
                user_id=user_id,
                message=c.get("message"),
                committed_at=_parse_dt(c.get("committed_date") or c.get("created_at")),
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
                created_at=_parse_dt(mr["created_at"]),
                updated_at=_parse_dt(mr.get("updated_at")),
                merged_at=_parse_dt(mr.get("merged_at")),
                closed_at=_parse_dt(mr.get("closed_at")),
                user_notes_count=mr.get("user_notes_count", 0),
            ).on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "state": mr["state"],
                    "updated_at": _parse_dt(mr.get("updated_at")),
                    "merged_at": _parse_dt(mr.get("merged_at")),
                    "closed_at": _parse_dt(mr.get("closed_at")),
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
                created_at=_parse_dt(issue["created_at"]),
                updated_at=_parse_dt(issue.get("updated_at")),
                closed_at=_parse_dt(issue.get("closed_at")),
                user_notes_count=issue.get("user_notes_count", 0),
            ).on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "state": issue["state"],
                    "updated_at": _parse_dt(issue.get("updated_at")),
                    "closed_at": _parse_dt(issue.get("closed_at")),
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
                created_at=_parse_dt(p["created_at"]),
                finished_at=_parse_dt(p.get("finished_at")),
            ).on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "status": p["status"],
                    "duration": p.get("duration"),
                    "finished_at": _parse_dt(p.get("finished_at")),
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
                created_at=_parse_dt(n["created_at"]),
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
            # Извлекаем данные о пуше (если есть)
            push_data = ev.get("push_data") or {}
            stmt = pg_insert(Event).values(
                id=ev["id"],
                user_id=user_id,
                project_id=ev.get("project_id"),
                action_name=ev.get("action_name", "unknown"),
                target_type=ev.get("target_type"),
                target_id=ev.get("target_id"),
                target_iid=ev.get("target_iid"),
                target_title=ev.get("target_title"),
                push_ref=push_data.get("ref"),
                push_commit_count=push_data.get("commit_count"),
                push_commit_title=push_data.get("commit_title"),
                push_commit_sha=push_data.get("commit_to"),
                created_at=_parse_dt(ev["created_at"]),
            ).on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "action_name": ev.get("action_name", "unknown"),
                    "target_type": ev.get("target_type"),
                    "target_id": ev.get("target_id"),
                    "target_iid": ev.get("target_iid"),
                    "target_title": ev.get("target_title"),
                    "push_ref": push_data.get("ref"),
                    "push_commit_count": push_data.get("commit_count"),
                    "push_commit_title": push_data.get("commit_title"),
                    "push_commit_sha": push_data.get("commit_to"),
                },
            )
            await self.session.execute(stmt)
            count += 1

        # Привязка коммитов к пользователям через push-события
        # Если у коммита нет user_id, но push-событие знает кто пушил — обновляем
        push_shas = [
            ev.get("push_data", {}).get("commit_to")
            for ev in events_data
            if ev.get("push_data", {}).get("commit_to")
        ]
        if push_shas:
            from sqlalchemy import update
            await self.session.execute(
                update(Commit)
                .where(Commit.sha.in_(push_shas))
                .where(Commit.user_id.is_(None))
                .values(user_id=user_id)
            )

        await self.session.commit()
        self.counters["events"] = self.counters.get("events", 0) + count
