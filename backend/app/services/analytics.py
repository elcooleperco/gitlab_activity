"""Сервис аналитики — расчёт метрик и формирование отчётов."""

from datetime import date

from sqlalchemy import select, func, case, and_, or_, union_all, literal
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    GitlabUser, Commit, MergeRequest, Issue, Note, Pipeline, Event,
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

        total_score = (
            (commits.count or 0) * 3
            + mr_created * 5
            + mr_merged * 5
            + issues_created * 2
            + issues_closed * 3
            + notes_count * 1
            + (pipelines.total or 0) * 1
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
            "total_score": total_score,
        }
