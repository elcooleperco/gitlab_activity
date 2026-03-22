"""Таблица настроек приложения

Revision ID: a1b2c3d4e5f6
Revises: 58c88342d2f2
Create Date: 2026-03-22 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Идентификаторы ревизии
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '58c88342d2f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'app_settings',
        sa.Column('key', sa.String(255), primary_key=True, comment='Ключ настройки'),
        sa.Column('value', sa.Text(), nullable=False, server_default='', comment='Значение настройки'),
    )


def downgrade() -> None:
    op.drop_table('app_settings')
