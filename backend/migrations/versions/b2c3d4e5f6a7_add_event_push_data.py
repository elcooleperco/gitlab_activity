"""Расширение таблицы events — данные о пуше и деталях

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-22 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Идентификаторы ревизии
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('events', sa.Column('target_iid', sa.Integer(), nullable=True, comment='IID объекта в проекте'))
    op.add_column('events', sa.Column('target_title', sa.Text(), nullable=True, comment='Заголовок объекта'))
    op.add_column('events', sa.Column('push_ref', sa.String(500), nullable=True, comment='Ветка/тег пуша'))
    op.add_column('events', sa.Column('push_commit_count', sa.Integer(), nullable=True, comment='Количество коммитов в пуше'))
    op.add_column('events', sa.Column('push_commit_title', sa.Text(), nullable=True, comment='Заголовок последнего коммита'))
    op.add_column('events', sa.Column('push_commit_sha', sa.String(40), nullable=True, comment='SHA последнего коммита'))


def downgrade() -> None:
    op.drop_column('events', 'push_commit_sha')
    op.drop_column('events', 'push_commit_title')
    op.drop_column('events', 'push_commit_count')
    op.drop_column('events', 'push_ref')
    op.drop_column('events', 'target_title')
    op.drop_column('events', 'target_iid')
