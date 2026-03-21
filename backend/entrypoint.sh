#!/bin/bash
# Скрипт запуска: применяем миграции и запускаем сервер

set -e

echo "Ожидание готовности PostgreSQL..."
while ! python -c "
import asyncio, asyncpg, os
async def check():
    url = os.environ.get('DATABASE_URL', '').replace('+asyncpg', '')
    url = url.replace('postgresql://', 'postgresql://')
    conn = await asyncpg.connect(url.replace('postgresql+asyncpg://', 'postgresql://'))
    await conn.close()
asyncio.run(check())
" 2>/dev/null; do
    echo "PostgreSQL недоступен, повторная попытка через 2 секунды..."
    sleep 2
done

echo "PostgreSQL готов. Применяем миграции..."
alembic upgrade head

echo "Запускаем сервер..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
