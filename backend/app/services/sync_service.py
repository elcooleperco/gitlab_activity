"""Сервис синхронизации данных из GitLab в локальную БД."""

from datetime import date, datetime, timedelta, timezone
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

    @staticmethod
    def _week_chunks(d_from: date, d_to: date) -> list[tuple[date, date]]:
        """Разбить период на недельные чанки."""
        chunks = []
        cur = d_from
        while cur <= d_to:
            chunk_end = min(cur + timedelta(days=6), d_to)
            chunks.append((cur, chunk_end))
            cur = chunk_end + timedelta(days=1)
        return chunks

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
            total, new, updated = await self.sync_users()
            sync_progress.add_to_step("Загрузка пользователей", total=total, new=new, updated=updated)
            sync_progress.complete_step("Загрузка пользователей")
            sync_progress.percent = 5
            self._check_cancelled()

            # Шаг 2: Проекты
            sync_progress.set_step("Загрузка проектов")
            sync_progress.add_log("Загрузка списка проектов из GitLab...")
            total, new, updated = await self.sync_projects()
            sync_progress.add_to_step("Загрузка проектов", total=total, new=new, updated=updated)
            sync_progress.complete_step("Загрузка проектов")
            sync_progress.percent = 10
            self._check_cancelled()

            # Получаем список проектов
            result = await self.session.execute(select(GitlabProject.id, GitlabProject.path_with_namespace))
            projects = result.fetchall()
            project_ids = [row[0] for row in projects]
            project_names = {row[0]: row[1] for row in projects}
            total_projects = len(project_ids)

            # Разбиваем период на недельные чанки
            chunks = self._week_chunks(date_from, date_to)
            total_chunks = len(chunks)
            sync_progress.add_log(f"Период разбит на {total_chunks} нед. чанков")

            # Шаги 3-6: данные по проектам, по неделям
            project_steps = [
                ("Коммиты", "commits", Commit, self.sync_project_commits),
                ("Merge Requests", "merge_requests", MergeRequest, self.sync_project_merge_requests),
                ("Issues", "issues", Issue, self.sync_project_issues),
                ("Пайплайны", "pipelines", Pipeline, self.sync_project_pipelines),
            ]

            for step_idx, (step_name, counter_key, model, sync_fn) in enumerate(project_steps):
                sync_progress.set_step(step_name)
                before = await self._count_rows(model)
                base_pct = 10 + step_idx * 15
                total_ops = total_projects * total_chunks

                op = 0
                for ci, (ch_from, ch_to) in enumerate(chunks):
                    for pi, pid in enumerate(project_ids):
                        self._check_cancelled()
                        pname = project_names.get(pid, str(pid))
                        sync_progress.add_log(
                            f"{step_name}: {pname} [{ch_from}—{ch_to}] ({op+1}/{total_ops})"
                        )
                        sync_progress.percent = base_pct + (op / max(total_ops, 1)) * 15
                        try:
                            await sync_fn(pid, ch_from, ch_to)
                        except Exception as chunk_err:
                            # Fallback: разбиваем неделю на дни и пробуем по дням
                            if ch_from != ch_to:
                                sync_progress.add_log(
                                    f"⚠ Таймаут на неделе, перехожу на дни: {pname}"
                                )
                                day_chunks = self._week_chunks(ch_from, ch_to)
                                # _week_chunks с 1 днём вернёт [(d, d)]
                                cur_day = ch_from
                                while cur_day <= ch_to:
                                    self._check_cancelled()
                                    try:
                                        sync_progress.add_log(
                                            f"  {step_name}: {pname} [{cur_day}]"
                                        )
                                        await sync_fn(pid, cur_day, cur_day)
                                    except Exception as day_err:
                                        sync_progress.add_log(
                                            f"  ✗ Ошибка за {cur_day}: {day_err}"
                                        )
                                        logger.warning(
                                            "Ошибка синхронизации за день",
                                            step=step_name, project=pname,
                                            date=str(cur_day), error=str(day_err),
                                        )
                                    cur_day += timedelta(days=1)
                            else:
                                sync_progress.add_log(
                                    f"✗ Ошибка: {pname} [{ch_from}]: {chunk_err}"
                                )
                                logger.warning(
                                    "Ошибка синхронизации",
                                    step=step_name, project=pname, error=str(chunk_err),
                                )
                        op += 1

                after = await self._count_rows(model)
                step_total = self.counters.get(counter_key, 0)
                step_new = after - before
                sync_progress.add_to_step(step_name, total=step_total, new=max(step_new, 0), updated=max(step_total - step_new, 0))
                sync_progress.complete_step(step_name)

            sync_progress.percent = 70

            # Шаг 7: События пользователей (тоже по неделям)
            sync_progress.set_step("События пользователей")
            before_events = await self._count_rows(Event)
            user_result = await self.session.execute(select(GitlabUser.id, GitlabUser.username))
            users = user_result.fetchall()
            total_users = len(users)
            total_user_ops = total_users * total_chunks

            op = 0
            for ci, (ch_from, ch_to) in enumerate(chunks):
                for i, (uid, uname) in enumerate(users):
                    self._check_cancelled()
                    sync_progress.add_log(
                        f"События: @{uname} [{ch_from}—{ch_to}] ({op+1}/{total_user_ops})"
                    )
                    sync_progress.percent = 70 + (op / max(total_user_ops, 1)) * 20
                    await self.sync_user_events(uid, ch_from, ch_to)
                    op += 1

            after_events = await self._count_rows(Event)
            step_total = self.counters.get("events", 0)
            step_new = after_events - before_events
            sync_progress.add_to_step("События пользователей", total=step_total, new=max(step_new, 0), updated=max(step_total - step_new, 0))
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
        """Привязать коммиты без user_id к пользователям через различные стратегии."""
        from sqlalchemy import update, distinct

        fixed = 0

        # Стратегия 1: По данным из GitLab-профиля (username, name, email)
        result = await self.session.execute(
            select(GitlabUser.id, GitlabUser.username, GitlabUser.name, GitlabUser.email)
        )
        users = result.fetchall()

        for user in users:
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

            if user.email:
                res = await self.session.execute(
                    update(Commit)
                    .where(Commit.user_id.is_(None))
                    .where(func.lower(Commit.author_email) == user.email.lower())
                    .values(user_id=user.id)
                )
                fixed += res.rowcount

        await self.session.flush()

        # Стратегия 2: Распространение привязки — если хоть один коммит
        # с данным author_email привязан к user_id, привяжем ВСЕ коммиты
        # с этим author_email к тому же user_id.
        # Это покрывает случай когда git настроен с другим email,
        # но push-событие уже привязало один коммит по SHA.
        orphan_emails = await self.session.execute(
            select(distinct(Commit.author_email))
            .where(Commit.user_id.is_(None))
            .where(Commit.author_email != "")
        )
        for (email,) in orphan_emails.fetchall():
            # Найти user_id у уже привязанного коммита с таким же email
            known = await self.session.execute(
                select(Commit.user_id)
                .where(Commit.author_email == email)
                .where(Commit.user_id.is_not(None))
                .limit(1)
            )
            row = known.fetchone()
            if row:
                res = await self.session.execute(
                    update(Commit)
                    .where(Commit.user_id.is_(None))
                    .where(Commit.author_email == email)
                    .values(user_id=row[0])
                )
                fixed += res.rowcount

        # Стратегия 3: То же по author_name
        orphan_names = await self.session.execute(
            select(distinct(Commit.author_name))
            .where(Commit.user_id.is_(None))
            .where(Commit.author_name != "")
        )
        for (name,) in orphan_names.fetchall():
            known = await self.session.execute(
                select(Commit.user_id)
                .where(Commit.author_name == name)
                .where(Commit.user_id.is_not(None))
                .limit(1)
            )
            row = known.fetchone()
            if row:
                res = await self.session.execute(
                    update(Commit)
                    .where(Commit.user_id.is_(None))
                    .where(Commit.author_name == name)
                    .values(user_id=row[0])
                )
                fixed += res.rowcount

        await self.session.commit()
        if fixed:
            sync_progress.add_log(f"Привязано осиротевших коммитов: {fixed}")
            logger.info("Привязано осиротевших коммитов", count=fixed)

    async def _count_rows(self, model) -> int:
        """Посчитать кол-во записей в таблице."""
        result = await self.session.execute(select(func.count()).select_from(model))
        return result.scalar() or 0

    async def sync_users(self) -> tuple[int, int, int]:
        """Синхронизировать пользователей. Возвращает (total, new, updated)."""
        before = await self._count_rows(GitlabUser)
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
        after = await self._count_rows(GitlabUser)
        new = after - before
        updated = count - new
        self.counters["users"] = count
        logger.info("Пользователи синхронизированы", count=count, new=new, updated=updated)
        return count, max(new, 0), max(updated, 0)

    async def sync_projects(self) -> tuple[int, int, int]:
        """Синхронизировать проекты. Возвращает (total, new, updated)."""
        before = await self._count_rows(GitlabProject)
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
        after = await self._count_rows(GitlabProject)
        new = after - before
        updated = count - new
        self.counters["projects"] = count
        logger.info("Проекты синхронизированы", count=count, new=new, updated=updated)
        return count, max(new, 0), max(updated, 0)

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
        from sqlalchemy import update
        for ev in events_data:
            pd = ev.get("push_data") or {}
            commit_sha = pd.get("commit_to")
            project_id = ev.get("project_id")
            if not commit_sha or not project_id:
                continue
            # Пропускаем нулевой SHA (удаление ветки)
            if commit_sha == "0" * 40:
                continue

            # Проверяем существует ли коммит в БД
            existing = await self.session.execute(
                select(Commit.sha).where(Commit.sha == commit_sha).limit(1)
            )
            if existing.fetchone():
                # Коммит есть — просто обновляем user_id если не привязан
                await self.session.execute(
                    update(Commit)
                    .where(Commit.sha == commit_sha)
                    .where(Commit.user_id.is_(None))
                    .values(user_id=user_id)
                )
            else:
                # Коммита нет в БД — загружаем из GitLab API по SHA
                c = await self.client.get_commit_by_sha(project_id, commit_sha)
                if c:
                    stats = c.get("stats") or {}
                    stmt = pg_insert(Commit).values(
                        sha=c["id"],
                        project_id=project_id,
                        author_name=c.get("author_name", ""),
                        author_email=c.get("author_email", ""),
                        user_id=user_id,
                        message=c.get("message"),
                        committed_at=_parse_dt(c.get("committed_date") or c.get("created_at")),
                        additions=stats.get("additions", 0),
                        deletions=stats.get("deletions", 0),
                    ).on_conflict_do_nothing()
                    await self.session.execute(stmt)
                    sync_progress.add_log(
                        f"  Загружен коммит {commit_sha[:8]} для user_id={user_id}"
                    )

        await self.session.commit()
        self.counters["events"] = self.counters.get("events", 0) + count
