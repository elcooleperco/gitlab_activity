"""Сервис аналитики — расчёт метрик и формирование отчётов."""

from datetime import date

from sqlalchemy import select, func, case, and_, or_, union_all, literal, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings as app_settings

from app.db.models import (
    GitlabUser, GitlabProject, Commit, MergeRequest, Issue, Note, Pipeline, Event,
)


class AnalyticsService:
    """Сервис расчёта метрик активности пользователей."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_summary(
        self,
        date_from: date,
        date_to: date,
        user_id: int | None = None,
        user_ids: list[int] | None = None,
    ) -> list[dict]:
        """Получить сводку активности по каждому пользователю за период."""
        users_result = await self.session.execute(select(GitlabUser))
        users = users_result.scalars().all()

        summary = []
        for user in users:
            if user_id and user.id != user_id:
                continue
            if user_ids and user.id not in user_ids:
                continue

            metrics = await self._calc_user_metrics(user.id, date_from, date_to)
            last_activity = await self._get_last_activity_date(user.id)
            summary.append({
                "user_id": user.id,
                "username": user.username,
                "name": user.name,
                "avatar_url": user.avatar_url,
                "last_seen": last_activity,
                **metrics,
            })

        summary.sort(key=lambda x: x["total_score"], reverse=True)
        return summary

    async def get_daily_activity(
        self,
        date_from: date,
        date_to: date,
        user_id: int | None = None,
        user_ids: list[int] | None = None,
    ) -> list[dict]:
        """Получить дневную разбивку активности."""
        # Фильтр по пользователям
        def _user_filter(col):
            filters = [col.is_not(None)]
            if user_id:
                filters.append(col == user_id)
            elif user_ids:
                filters.append(col.in_(user_ids))
            return filters

        # Коммиты по дням
        commits_q = (
            select(
                func.date(Commit.committed_at).label("day"),
                Commit.user_id,
                func.count().label("commits"),
                func.coalesce(func.sum(Commit.additions), 0).label("additions"),
                func.coalesce(func.sum(Commit.deletions), 0).label("deletions"),
            )
            .where(
                and_(
                    func.date(Commit.committed_at) >= date_from,
                    func.date(Commit.committed_at) <= date_to,
                    *_user_filter(Commit.user_id),
                )
            )
            .group_by(func.date(Commit.committed_at), Commit.user_id)
        )
        commits_result = await self.session.execute(commits_q)

        daily: dict[tuple, dict] = {}
        for row in commits_result.fetchall():
            key = (str(row.day), row.user_id)
            daily[key] = {
                "date": str(row.day),
                "user_id": row.user_id,
                "commits": row.commits,
                "additions": row.additions,
                "deletions": row.deletions,
                "merge_requests": 0,
                "issues": 0,
                "notes": 0,
            }

        # MR по дням
        mr_q = (
            select(
                func.date(MergeRequest.created_at).label("day"),
                MergeRequest.author_id,
                func.count().label("count"),
            )
            .where(
                and_(
                    func.date(MergeRequest.created_at) >= date_from,
                    func.date(MergeRequest.created_at) <= date_to,
                    *_user_filter(MergeRequest.author_id),
                )
            )
            .group_by(func.date(MergeRequest.created_at), MergeRequest.author_id)
        )
        for row in (await self.session.execute(mr_q)).fetchall():
            key = (str(row.day), row.author_id)
            if key not in daily:
                daily[key] = {
                    "date": str(row.day), "user_id": row.author_id,
                    "commits": 0, "additions": 0, "deletions": 0,
                    "merge_requests": 0, "issues": 0, "notes": 0,
                }
            daily[key]["merge_requests"] = row.count

        # Issues по дням
        issue_q = (
            select(
                func.date(Issue.created_at).label("day"),
                Issue.author_id,
                func.count().label("count"),
            )
            .where(
                and_(
                    func.date(Issue.created_at) >= date_from,
                    func.date(Issue.created_at) <= date_to,
                    *_user_filter(Issue.author_id),
                )
            )
            .group_by(func.date(Issue.created_at), Issue.author_id)
        )
        for row in (await self.session.execute(issue_q)).fetchall():
            key = (str(row.day), row.author_id)
            if key not in daily:
                daily[key] = {
                    "date": str(row.day), "user_id": row.author_id,
                    "commits": 0, "additions": 0, "deletions": 0,
                    "merge_requests": 0, "issues": 0, "notes": 0,
                }
            daily[key]["issues"] = row.count

        # Комментарии по дням
        notes_q = (
            select(
                func.date(Note.created_at).label("day"),
                Note.author_id,
                func.count().label("count"),
            )
            .where(
                and_(
                    func.date(Note.created_at) >= date_from,
                    func.date(Note.created_at) <= date_to,
                    Note.system.is_(False),
                    *_user_filter(Note.author_id),
                )
            )
            .group_by(func.date(Note.created_at), Note.author_id)
        )
        for row in (await self.session.execute(notes_q)).fetchall():
            key = (str(row.day), row.author_id)
            if key not in daily:
                daily[key] = {
                    "date": str(row.day), "user_id": row.author_id,
                    "commits": 0, "additions": 0, "deletions": 0,
                    "merge_requests": 0, "issues": 0, "notes": 0,
                }
            daily[key]["notes"] = row.count

        return sorted(daily.values(), key=lambda x: x["date"])

    async def get_contribution_map(
        self, user_id: int, date_from: date, date_to: date
    ) -> list[dict]:
        """Тепловая карта вкладов (как в GitLab) — количество действий по дням."""
        # Считаем общее количество действий по дням из всех таблиц
        commits_q = (
            select(
                func.date(Commit.committed_at).label("day"),
                func.count().label("cnt"),
            )
            .where(and_(Commit.user_id == user_id, func.date(Commit.committed_at) >= date_from, func.date(Commit.committed_at) <= date_to))
            .group_by(func.date(Commit.committed_at))
        )
        mr_q = (
            select(
                func.date(MergeRequest.created_at).label("day"),
                func.count().label("cnt"),
            )
            .where(and_(MergeRequest.author_id == user_id, func.date(MergeRequest.created_at) >= date_from, func.date(MergeRequest.created_at) <= date_to))
            .group_by(func.date(MergeRequest.created_at))
        )
        issues_q = (
            select(
                func.date(Issue.created_at).label("day"),
                func.count().label("cnt"),
            )
            .where(and_(Issue.author_id == user_id, func.date(Issue.created_at) >= date_from, func.date(Issue.created_at) <= date_to))
            .group_by(func.date(Issue.created_at))
        )
        notes_q = (
            select(
                func.date(Note.created_at).label("day"),
                func.count().label("cnt"),
            )
            .where(and_(Note.author_id == user_id, Note.system.is_(False), func.date(Note.created_at) >= date_from, func.date(Note.created_at) <= date_to))
            .group_by(func.date(Note.created_at))
        )
        events_q = (
            select(
                func.date(Event.created_at).label("day"),
                func.count().label("cnt"),
            )
            .where(and_(Event.user_id == user_id, func.date(Event.created_at) >= date_from, func.date(Event.created_at) <= date_to))
            .group_by(func.date(Event.created_at))
        )

        # Собираем все дни и суммируем
        day_counts: dict[str, int] = {}
        for q in [commits_q, mr_q, issues_q, notes_q, events_q]:
            for row in (await self.session.execute(q)).fetchall():
                d = str(row.day)
                day_counts[d] = day_counts.get(d, 0) + row.cnt

        return [{"date": d, "count": c} for d, c in sorted(day_counts.items())]

    async def get_user_day_details(
        self, user_id: int, target_date: date
    ) -> dict:
        """Детальный список действий пользователя за конкретный день."""
        result: dict = {"date": str(target_date), "user_id": user_id, "actions": []}

        # Коммиты
        commits_q = select(Commit).where(
            and_(Commit.user_id == user_id, func.date(Commit.committed_at) == target_date)
        )
        for c in (await self.session.execute(commits_q)).scalars().all():
            result["actions"].append({
                "type": "commit",
                "time": c.committed_at.isoformat() if c.committed_at else None,
                "title": (c.message or "")[:120],
                "details": f"+{c.additions} -{c.deletions}",
                "project_id": c.project_id,
            })

        # MR
        mr_q = select(MergeRequest).where(
            and_(MergeRequest.author_id == user_id, func.date(MergeRequest.created_at) == target_date)
        )
        for mr in (await self.session.execute(mr_q)).scalars().all():
            result["actions"].append({
                "type": "merge_request",
                "time": mr.created_at.isoformat() if mr.created_at else None,
                "title": mr.title,
                "details": f"!{mr.iid} ({mr.state})",
                "project_id": mr.project_id,
            })

        # Issues
        issues_q = select(Issue).where(
            and_(Issue.author_id == user_id, func.date(Issue.created_at) == target_date)
        )
        for issue in (await self.session.execute(issues_q)).scalars().all():
            result["actions"].append({
                "type": "issue",
                "time": issue.created_at.isoformat() if issue.created_at else None,
                "title": issue.title,
                "details": f"#{issue.iid} ({issue.state})",
                "project_id": issue.project_id,
            })

        # Комментарии
        notes_q = select(Note).where(
            and_(Note.author_id == user_id, Note.system.is_(False), func.date(Note.created_at) == target_date)
        )
        for n in (await self.session.execute(notes_q)).scalars().all():
            result["actions"].append({
                "type": "note",
                "time": n.created_at.isoformat() if n.created_at else None,
                "title": f"Комментарий к {n.noteable_type} #{n.noteable_id}",
                "details": f"{n.body_length} символов",
                "project_id": n.project_id,
            })

        # Пайплайны
        pipelines_q = select(Pipeline).where(
            and_(Pipeline.user_id == user_id, func.date(Pipeline.created_at) == target_date)
        )
        for p in (await self.session.execute(pipelines_q)).scalars().all():
            result["actions"].append({
                "type": "pipeline",
                "time": p.created_at.isoformat() if p.created_at else None,
                "title": f"Pipeline #{p.id} ({p.status})",
                "details": f"{p.duration or 0} сек, ветка: {p.ref}",
                "project_id": p.project_id,
            })

        # Сортируем по времени
        result["actions"].sort(key=lambda a: a.get("time") or "")
        result["total_actions"] = len(result["actions"])
        return result

    async def get_inactive_users(
        self, date_from: date, date_to: date
    ) -> list[dict]:
        """Получить список неактивных пользователей за период."""
        summary = await self.get_summary(date_from, date_to)
        return [u for u in summary if u["total_score"] == 0]

    async def _get_last_activity_date(self, user_id: int) -> str | None:
        """Получить дату последней активности пользователя из всех собранных данных."""
        dates = []

        # Последний коммит
        q = select(func.max(Commit.committed_at)).where(Commit.user_id == user_id)
        r = (await self.session.execute(q)).scalar()
        if r:
            dates.append(r)

        # Последний MR
        q = select(func.max(MergeRequest.created_at)).where(MergeRequest.author_id == user_id)
        r = (await self.session.execute(q)).scalar()
        if r:
            dates.append(r)

        # Последняя Issue
        q = select(func.max(Issue.created_at)).where(Issue.author_id == user_id)
        r = (await self.session.execute(q)).scalar()
        if r:
            dates.append(r)

        # Последний комментарий
        q = select(func.max(Note.created_at)).where(and_(Note.author_id == user_id, Note.system.is_(False)))
        r = (await self.session.execute(q)).scalar()
        if r:
            dates.append(r)

        # Последнее событие
        q = select(func.max(Event.created_at)).where(Event.user_id == user_id)
        r = (await self.session.execute(q)).scalar()
        if r:
            dates.append(r)

        if dates:
            return max(dates).isoformat()
        return None

    async def _calc_user_metrics(
        self, user_id: int, date_from: date, date_to: date
    ) -> dict:
        """Рассчитать метрики для одного пользователя за период."""
        commits_q = select(
            func.count().label("count"),
            func.coalesce(func.sum(Commit.additions), 0).label("additions"),
            func.coalesce(func.sum(Commit.deletions), 0).label("deletions"),
        ).where(and_(Commit.user_id == user_id, func.date(Commit.committed_at) >= date_from, func.date(Commit.committed_at) <= date_to))
        commits = (await self.session.execute(commits_q)).fetchone()

        mr_created_q = select(func.count()).where(and_(MergeRequest.author_id == user_id, func.date(MergeRequest.created_at) >= date_from, func.date(MergeRequest.created_at) <= date_to))
        mr_created = (await self.session.execute(mr_created_q)).scalar() or 0

        mr_merged_q = select(func.count()).where(and_(MergeRequest.author_id == user_id, MergeRequest.state == "merged", func.date(MergeRequest.merged_at) >= date_from, func.date(MergeRequest.merged_at) <= date_to))
        mr_merged = (await self.session.execute(mr_merged_q)).scalar() or 0

        issues_created_q = select(func.count()).where(and_(Issue.author_id == user_id, func.date(Issue.created_at) >= date_from, func.date(Issue.created_at) <= date_to))
        issues_created = (await self.session.execute(issues_created_q)).scalar() or 0

        issues_closed_q = select(func.count()).where(and_(Issue.assignee_id == user_id, Issue.state == "closed", func.date(Issue.closed_at) >= date_from, func.date(Issue.closed_at) <= date_to))
        issues_closed = (await self.session.execute(issues_closed_q)).scalar() or 0

        notes_q = select(func.count()).where(and_(Note.author_id == user_id, Note.system.is_(False), func.date(Note.created_at) >= date_from, func.date(Note.created_at) <= date_to))
        notes_count = (await self.session.execute(notes_q)).scalar() or 0

        pipelines_q = select(
            func.count().label("total"),
            func.sum(case((Pipeline.status == "success", 1), else_=0)).label("success"),
        ).where(and_(Pipeline.user_id == user_id, func.date(Pipeline.created_at) >= date_from, func.date(Pipeline.created_at) <= date_to))
        pipelines = (await self.session.execute(pipelines_q)).fetchone()

        events_q = select(func.count()).where(and_(Event.user_id == user_id, func.date(Event.created_at) >= date_from, func.date(Event.created_at) <= date_to))
        events_count = (await self.session.execute(events_q)).scalar() or 0

        # Approve-события (approved MR)
        approves_q = select(func.count()).where(and_(
            Event.user_id == user_id,
            Event.action_name == "approved",
            func.date(Event.created_at) >= date_from,
            func.date(Event.created_at) <= date_to,
        ))
        approves_count = (await self.session.execute(approves_q)).scalar() or 0

        total_score = (
            (commits.count or 0) * 3
            + mr_created * 5
            + mr_merged * 5
            + issues_created * 2
            + issues_closed * 3
            + notes_count * 1
            + (pipelines.total or 0) * 1
            + approves_count * 4
        )

        return {
            "commits": commits.count or 0,
            "additions": commits.additions or 0,
            "deletions": commits.deletions or 0,
            "mr_created": mr_created,
            "mr_merged": mr_merged,
            "issues_created": issues_created,
            "issues_closed": issues_closed,
            "notes": notes_count,
            "pipelines_total": pipelines.total or 0,
            "pipelines_success": pipelines.success or 0,
            "events": events_count,
            "approves": approves_count,
            "total_score": total_score,
        }

    async def get_user_action_types(
        self, user_id: int, date_from: date, date_to: date
    ) -> list[dict]:
        """Группировка событий пользователя по типу действия (action_name) за период."""
        q = (
            select(
                Event.action_name,
                func.count().label("count"),
            )
            .where(and_(
                Event.user_id == user_id,
                func.date(Event.created_at) >= date_from,
                func.date(Event.created_at) <= date_to,
            ))
            .group_by(Event.action_name)
            .order_by(func.count().desc())
        )
        result = await self.session.execute(q)
        return [{"action": row.action_name, "count": row.count} for row in result.fetchall()]

    async def get_user_projects(
        self, user_id: int, date_from: date, date_to: date
    ) -> list[dict]:
        """В каких проектах работал пользователь и сколько действий в каждом."""
        # Собираем project_id из коммитов, MR, issues, notes, events
        sources = [
            select(Commit.project_id.label("pid")).where(and_(
                Commit.user_id == user_id,
                func.date(Commit.committed_at) >= date_from,
                func.date(Commit.committed_at) <= date_to,
            )),
            select(MergeRequest.project_id.label("pid")).where(and_(
                MergeRequest.author_id == user_id,
                func.date(MergeRequest.created_at) >= date_from,
                func.date(MergeRequest.created_at) <= date_to,
            )),
            select(Issue.project_id.label("pid")).where(and_(
                Issue.author_id == user_id,
                func.date(Issue.created_at) >= date_from,
                func.date(Issue.created_at) <= date_to,
            )),
            select(Note.project_id.label("pid")).where(and_(
                Note.author_id == user_id,
                func.date(Note.created_at) >= date_from,
                func.date(Note.created_at) <= date_to,
            )),
            select(Event.project_id.label("pid")).where(and_(
                Event.user_id == user_id,
                Event.project_id.is_not(None),
                func.date(Event.created_at) >= date_from,
                func.date(Event.created_at) <= date_to,
            )),
        ]
        combined = union_all(*sources).subquery()
        q = (
            select(combined.c.pid, func.count().label("count"))
            .group_by(combined.c.pid)
            .order_by(func.count().desc())
        )
        result = await self.session.execute(q)
        rows = result.fetchall()

        # Подтягиваем названия проектов
        project_ids = [r.pid for r in rows if r.pid]
        projects_map: dict[int, str] = {}
        if project_ids:
            pq = select(GitlabProject.id, GitlabProject.name, GitlabProject.path_with_namespace).where(
                GitlabProject.id.in_(project_ids)
            )
            for p in (await self.session.execute(pq)).fetchall():
                projects_map[p.id] = p.path_with_namespace

        return [
            {
                "project_id": r.pid,
                "project_name": projects_map.get(r.pid, f"Проект #{r.pid}"),
                "actions_count": r.count,
            }
            for r in rows if r.pid
        ]

    async def get_project_summary(
        self, project_id: int, date_from: date, date_to: date
    ) -> dict:
        """Сводка активности по проекту — общие метрики и топ пользователей."""
        # Общие метрики проекта
        commits_q = select(
            func.count().label("count"),
            func.coalesce(func.sum(Commit.additions), 0).label("additions"),
            func.coalesce(func.sum(Commit.deletions), 0).label("deletions"),
        ).where(and_(
            Commit.project_id == project_id,
            func.date(Commit.committed_at) >= date_from,
            func.date(Commit.committed_at) <= date_to,
        ))
        commits = (await self.session.execute(commits_q)).fetchone()

        mr_q = select(func.count()).where(and_(
            MergeRequest.project_id == project_id,
            func.date(MergeRequest.created_at) >= date_from,
            func.date(MergeRequest.created_at) <= date_to,
        ))
        mr_count = (await self.session.execute(mr_q)).scalar() or 0

        issues_q = select(func.count()).where(and_(
            Issue.project_id == project_id,
            func.date(Issue.created_at) >= date_from,
            func.date(Issue.created_at) <= date_to,
        ))
        issues_count = (await self.session.execute(issues_q)).scalar() or 0

        notes_q = select(func.count()).where(and_(
            Note.project_id == project_id,
            Note.system.is_(False),
            func.date(Note.created_at) >= date_from,
            func.date(Note.created_at) <= date_to,
        ))
        notes_count = (await self.session.execute(notes_q)).scalar() or 0

        pipelines_q = select(func.count()).where(and_(
            Pipeline.project_id == project_id,
            func.date(Pipeline.created_at) >= date_from,
            func.date(Pipeline.created_at) <= date_to,
        ))
        pipelines_count = (await self.session.execute(pipelines_q)).scalar() or 0

        # Топ пользователей по количеству действий в проекте
        user_sources = [
            select(Commit.user_id.label("uid")).where(and_(
                Commit.project_id == project_id,
                Commit.user_id.is_not(None),
                func.date(Commit.committed_at) >= date_from,
                func.date(Commit.committed_at) <= date_to,
            )),
            select(MergeRequest.author_id.label("uid")).where(and_(
                MergeRequest.project_id == project_id,
                MergeRequest.author_id.is_not(None),
                func.date(MergeRequest.created_at) >= date_from,
                func.date(MergeRequest.created_at) <= date_to,
            )),
            select(Issue.author_id.label("uid")).where(and_(
                Issue.project_id == project_id,
                Issue.author_id.is_not(None),
                func.date(Issue.created_at) >= date_from,
                func.date(Issue.created_at) <= date_to,
            )),
            select(Note.author_id.label("uid")).where(and_(
                Note.project_id == project_id,
                Note.author_id.is_not(None),
                func.date(Note.created_at) >= date_from,
                func.date(Note.created_at) <= date_to,
            )),
            select(Event.user_id.label("uid")).where(and_(
                Event.project_id == project_id,
                Event.user_id.is_not(None),
                func.date(Event.created_at) >= date_from,
                func.date(Event.created_at) <= date_to,
            )),
        ]
        combined = union_all(*user_sources).subquery()
        users_q = (
            select(combined.c.uid, func.count().label("count"))
            .group_by(combined.c.uid)
            .order_by(func.count().desc())
        )
        user_rows = (await self.session.execute(users_q)).fetchall()

        # Подтягиваем имена
        user_ids = [r.uid for r in user_rows]
        users_map: dict[int, dict] = {}
        if user_ids:
            uq = select(GitlabUser.id, GitlabUser.username, GitlabUser.name, GitlabUser.avatar_url).where(
                GitlabUser.id.in_(user_ids)
            )
            for u in (await self.session.execute(uq)).fetchall():
                users_map[u.id] = {"username": u.username, "name": u.name, "avatar_url": u.avatar_url}

        contributors = [
            {
                "user_id": r.uid,
                "username": users_map.get(r.uid, {}).get("username", f"user#{r.uid}"),
                "name": users_map.get(r.uid, {}).get("name", ""),
                "avatar_url": users_map.get(r.uid, {}).get("avatar_url"),
                "actions_count": r.count,
            }
            for r in user_rows
        ]

        return {
            "commits": commits.count or 0,
            "additions": commits.additions or 0,
            "deletions": commits.deletions or 0,
            "merge_requests": mr_count,
            "issues": issues_count,
            "notes": notes_count,
            "pipelines": pipelines_count,
            "contributors": contributors,
        }

    async def get_user_activity_log(
        self, user_id: int, date_from: date, date_to: date,
        project_id: int | None = None, action_type: str | None = None,
    ) -> list[dict]:
        """Детальный лог действий пользователя за период с фильтрацией и ссылками на GitLab."""
        gitlab_url = app_settings.gitlab_url.rstrip("/")
        actions: list[dict] = []

        # Маппинг project_id -> path_with_namespace для формирования URL
        pq = select(GitlabProject.id, GitlabProject.path_with_namespace)
        projects_map: dict[int, str] = {}
        for p in (await self.session.execute(pq)).fetchall():
            projects_map[p.id] = p.path_with_namespace

        def _project_url(pid: int | None) -> str:
            if pid and pid in projects_map:
                return f"{gitlab_url}/{projects_map[pid]}"
            return ""

        # Коммиты
        if not action_type or action_type == "commit":
            q = select(Commit).where(and_(
                Commit.user_id == user_id,
                func.date(Commit.committed_at) >= date_from,
                func.date(Commit.committed_at) <= date_to,
            ))
            if project_id:
                q = q.where(Commit.project_id == project_id)
            q = q.order_by(desc(Commit.committed_at))
            for c in (await self.session.execute(q)).scalars().all():
                base = _project_url(c.project_id)
                actions.append({
                    "type": "commit",
                    "date": c.committed_at.isoformat() if c.committed_at else None,
                    "project_id": c.project_id,
                    "project_name": projects_map.get(c.project_id, ""),
                    "title": (c.message or "").split("\n")[0][:200],
                    "details": f"+{c.additions} -{c.deletions}",
                    "gitlab_url": f"{base}/-/commit/{c.sha}" if base else "",
                })

        # Merge Requests
        if not action_type or action_type == "merge_request":
            q = select(MergeRequest).where(and_(
                MergeRequest.author_id == user_id,
                func.date(MergeRequest.created_at) >= date_from,
                func.date(MergeRequest.created_at) <= date_to,
            ))
            if project_id:
                q = q.where(MergeRequest.project_id == project_id)
            q = q.order_by(desc(MergeRequest.created_at))
            for mr in (await self.session.execute(q)).scalars().all():
                base = _project_url(mr.project_id)
                actions.append({
                    "type": "merge_request",
                    "date": mr.created_at.isoformat() if mr.created_at else None,
                    "project_id": mr.project_id,
                    "project_name": projects_map.get(mr.project_id, ""),
                    "title": mr.title,
                    "details": f"!{mr.iid} ({mr.state})",
                    "gitlab_url": f"{base}/-/merge_requests/{mr.iid}" if base else "",
                })

        # Issues
        if not action_type or action_type == "issue":
            q = select(Issue).where(and_(
                Issue.author_id == user_id,
                func.date(Issue.created_at) >= date_from,
                func.date(Issue.created_at) <= date_to,
            ))
            if project_id:
                q = q.where(Issue.project_id == project_id)
            q = q.order_by(desc(Issue.created_at))
            for issue in (await self.session.execute(q)).scalars().all():
                base = _project_url(issue.project_id)
                actions.append({
                    "type": "issue",
                    "date": issue.created_at.isoformat() if issue.created_at else None,
                    "project_id": issue.project_id,
                    "project_name": projects_map.get(issue.project_id, ""),
                    "title": issue.title,
                    "details": f"#{issue.iid} ({issue.state})",
                    "gitlab_url": f"{base}/-/issues/{issue.iid}" if base else "",
                })

        # Комментарии
        if not action_type or action_type == "note":
            q = select(Note).where(and_(
                Note.author_id == user_id,
                Note.system.is_(False),
                func.date(Note.created_at) >= date_from,
                func.date(Note.created_at) <= date_to,
            ))
            if project_id:
                q = q.where(Note.project_id == project_id)
            q = q.order_by(desc(Note.created_at))
            for n in (await self.session.execute(q)).scalars().all():
                base = _project_url(n.project_id)
                # Ссылка на MR или Issue
                if n.noteable_type == "MergeRequest":
                    url = f"{base}/-/merge_requests/{n.noteable_id}#note_{n.id}" if base else ""
                else:
                    url = f"{base}/-/issues/{n.noteable_id}#note_{n.id}" if base else ""
                actions.append({
                    "type": "note",
                    "date": n.created_at.isoformat() if n.created_at else None,
                    "project_id": n.project_id,
                    "project_name": projects_map.get(n.project_id, ""),
                    "title": f"Комментарий к {n.noteable_type}",
                    "details": f"{n.body_length} символов",
                    "gitlab_url": url,
                })

        # Пайплайны
        if not action_type or action_type == "pipeline":
            q = select(Pipeline).where(and_(
                Pipeline.user_id == user_id,
                func.date(Pipeline.created_at) >= date_from,
                func.date(Pipeline.created_at) <= date_to,
            ))
            if project_id:
                q = q.where(Pipeline.project_id == project_id)
            q = q.order_by(desc(Pipeline.created_at))
            for p in (await self.session.execute(q)).scalars().all():
                base = _project_url(p.project_id)
                actions.append({
                    "type": "pipeline",
                    "date": p.created_at.isoformat() if p.created_at else None,
                    "project_id": p.project_id,
                    "project_name": projects_map.get(p.project_id, ""),
                    "title": f"Pipeline #{p.id} ({p.status})",
                    "details": f"{p.duration or 0} сек, ветка: {p.ref}",
                    "gitlab_url": f"{base}/-/pipelines/{p.id}" if base else "",
                })

        # События (pushed to, commented on, и т.д.)
        if not action_type or action_type == "event":
            q = select(Event).where(and_(
                Event.user_id == user_id,
                func.date(Event.created_at) >= date_from,
                func.date(Event.created_at) <= date_to,
            ))
            if project_id:
                q = q.where(Event.project_id == project_id)
            q = q.order_by(desc(Event.created_at))
            for ev in (await self.session.execute(q)).scalars().all():
                base = _project_url(ev.project_id)
                # Формируем URL в зависимости от типа события
                url = ""
                title = ev.action_name or "событие"
                details = ""
                if ev.push_ref:
                    # Push-событие — ссылка на коммит или ветку
                    if ev.push_commit_sha and base:
                        url = f"{base}/-/commit/{ev.push_commit_sha}"
                    elif base:
                        url = f"{base}/-/tree/{ev.push_ref}"
                    title = f"push → {ev.push_ref}"
                    parts = []
                    if ev.push_commit_count:
                        parts.append(f"{ev.push_commit_count} коммит(ов)")
                    if ev.push_commit_title:
                        parts.append(ev.push_commit_title[:120])
                    details = ", ".join(parts) if parts else ""
                elif ev.target_type and ev.target_iid:
                    # Событие над объектом (MR, Issue, и т.д.)
                    if ev.target_type == "MergeRequest" and base:
                        url = f"{base}/-/merge_requests/{ev.target_iid}"
                    elif ev.target_type == "Issue" and base:
                        url = f"{base}/-/issues/{ev.target_iid}"
                    title = f"{ev.action_name} {ev.target_type}"
                    if ev.target_title:
                        details = ev.target_title[:120]
                elif ev.target_type and ev.target_id and base:
                    title = f"{ev.action_name} {ev.target_type} #{ev.target_id}"

                actions.append({
                    "type": "event",
                    "date": ev.created_at.isoformat() if ev.created_at else None,
                    "project_id": ev.project_id,
                    "project_name": projects_map.get(ev.project_id, "") if ev.project_id else "",
                    "title": title,
                    "details": details,
                    "gitlab_url": url,
                })

        # Сортируем по дате (новые сверху)
        actions.sort(key=lambda a: a.get("date") or "", reverse=True)
        return actions
