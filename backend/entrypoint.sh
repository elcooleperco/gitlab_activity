#!/bin/bash
# Скрипт запуска: применяем миграции и запускаем сервер

set -e

echo "Ожидание готовности PostgreSQL..."
until python -c "
import asyncio, asyncpg, os
async def check():
    url = os.environ.get('DATABASE_URL', '')
    url = url.replace('postgresql+asyncpg://', 'postgresql://')
    conn = await asyncpg.connect(url)
    await conn.close()
asyncio.run(check())
" 2>/dev/null; do
    echo "PostgreSQL недоступен, повтор через 2 секунды..."
    sleep 2
done

echo "PostgreSQL готов. Применяем миграции..."
PYTHONPATH=. python -c "from alembic.config import main; import sys; sys.argv = ['alembic', 'upgrade', 'head']; main()"

echo "Запускаем сервер..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
