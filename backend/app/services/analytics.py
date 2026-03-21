"""Сервис аналитики — расчёт метрик и формирование отчётов."""

from datetime import date

from sqlalchemy import select, func, case, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    GitlabUser, Commit, MergeRequest, Issue, Note, Pipeline, Event,
)


class AnalyticsService:
    """Сервис расчёта метрик активности пользователей."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_summary(
        self, date_from: date, date_to: date, user_id: int | None = None
    ) -> list[dict]:
        """Получить сводку активности по каждому пользователю за период."""
        users_result = await self.session.execute(select(GitlabUser))
        users = users_result.scalars().all()

        summary = []
        for user in users:
            if user_id and user.id != user_id:
                continue

            metrics = await self._calc_user_metrics(user.id, date_from, date_to)
            summary.append({
                "user_id": user.id,
                "username": user.username,
                "name": user.name,
                "avatar_url": user.avatar_url,
                **metrics,
            })

        # Сортируем по общей активности (убывание)
        summary.sort(key=lambda x: x["total_score"], reverse=True)
        return summary

    async def get_daily_activity(
        self, date_from: date, date_to: date, user_id: int | None = None
    ) -> list[dict]:
        """Получить дневную разбивку активности."""
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
                    Commit.user_id.is_not(None),
                    *([Commit.user_id == user_id] if user_id else []),
                )
            )
            .group_by(func.date(Commit.committed_at), Commit.user_id)
        )
        commits_result = await self.session.execute(commits_q)
        commits_rows = commits_result.fetchall()

        # Собираем по (день, пользователь)
        daily: dict[tuple, dict] = {}
        for row in commits_rows:
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
                    MergeRequest.author_id.is_not(None),
                    *([MergeRequest.author_id == user_id] if user_id else []),
                )
            )
            .group_by(func.date(MergeRequest.created_at), MergeRequest.author_id)
        )
        mr_result = await self.session.execute(mr_q)
        for row in mr_result.fetchall():
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
                    Issue.author_id.is_not(None),
                    *([Issue.author_id == user_id] if user_id else []),
                )
            )
            .group_by(func.date(Issue.created_at), Issue.author_id)
        )
        issue_result = await self.session.execute(issue_q)
        for row in issue_result.fetchall():
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
                    Note.author_id.is_not(None),
                    Note.system.is_(False),
                    *([Note.author_id == user_id] if user_id else []),
                )
            )
            .group_by(func.date(Note.created_at), Note.author_id)
        )
        notes_result = await self.session.execute(notes_q)
        for row in notes_result.fetchall():
            key = (str(row.day), row.author_id)
            if key not in daily:
                daily[key] = {
                    "date": str(row.day), "user_id": row.author_id,
                    "commits": 0, "additions": 0, "deletions": 0,
                    "merge_requests": 0, "issues": 0, "notes": 0,
                }
            daily[key]["notes"] = row.count

        result = sorted(daily.values(), key=lambda x: x["date"])
        return result

    async def get_inactive_users(
        self, date_from: date, date_to: date
    ) -> list[dict]:
        """Получить список неактивных пользователей за период."""
        summary = await self.get_summary(date_from, date_to)
        return [u for u in summary if u["total_score"] == 0]

    async def _calc_user_metrics(
        self, user_id: int, date_from: date, date_to: date
    ) -> dict:
        """Рассчитать метрики для одного пользователя за период."""
        # Коммиты
        commits_q = select(
            func.count().label("count"),
            func.coalesce(func.sum(Commit.additions), 0).label("additions"),
            func.coalesce(func.sum(Commit.deletions), 0).label("deletions"),
        ).where(
            and_(
                Commit.user_id == user_id,
                func.date(Commit.committed_at) >= date_from,
                func.date(Commit.committed_at) <= date_to,
            )
        )
        commits = (await self.session.execute(commits_q)).fetchone()

        # MR созданные
        mr_created_q = select(func.count()).where(
            and_(
                MergeRequest.author_id == user_id,
                func.date(MergeRequest.created_at) >= date_from,
                func.date(MergeRequest.created_at) <= date_to,
            )
        )
        mr_created = (await self.session.execute(mr_created_q)).scalar() or 0

        # MR замерженные
        mr_merged_q = select(func.count()).where(
            and_(
                MergeRequest.author_id == user_id,
                MergeRequest.state == "merged",
                func.date(MergeRequest.merged_at) >= date_from,
                func.date(MergeRequest.merged_at) <= date_to,
            )
        )
        mr_merged = (await self.session.execute(mr_merged_q)).scalar() or 0

        # Issues созданные
        issues_created_q = select(func.count()).where(
            and_(
                Issue.author_id == user_id,
                func.date(Issue.created_at) >= date_from,
                func.date(Issue.created_at) <= date_to,
            )
        )
        issues_created = (await self.session.execute(issues_created_q)).scalar() or 0

        # Issues закрытые (как assignee)
        issues_closed_q = select(func.count()).where(
            and_(
                Issue.assignee_id == user_id,
                Issue.state == "closed",
                func.date(Issue.closed_at) >= date_from,
                func.date(Issue.closed_at) <= date_to,
            )
        )
        issues_closed = (await self.session.execute(issues_closed_q)).scalar() or 0

        # Комментарии (не системные)
        notes_q = select(func.count()).where(
            and_(
                Note.author_id == user_id,
                Note.system.is_(False),
                func.date(Note.created_at) >= date_from,
                func.date(Note.created_at) <= date_to,
            )
        )
        notes_count = (await self.session.execute(notes_q)).scalar() or 0

        # Пайплайны
        pipelines_q = select(
            func.count().label("total"),
            func.sum(case((Pipeline.status == "success", 1), else_=0)).label("success"),
        ).where(
            and_(
                Pipeline.user_id == user_id,
                func.date(Pipeline.created_at) >= date_from,
                func.date(Pipeline.created_at) <= date_to,
            )
        )
        pipelines = (await self.session.execute(pipelines_q)).fetchone()

        # События
        events_q = select(func.count()).where(
            and_(
                Event.user_id == user_id,
                func.date(Event.created_at) >= date_from,
                func.date(Event.created_at) <= date_to,
            )
        )
        events_count = (await self.session.execute(events_q)).scalar() or 0

        # Общий балл активности (простая формула)
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
