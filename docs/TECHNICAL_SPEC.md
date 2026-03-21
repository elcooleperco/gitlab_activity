# Техническое задание: GitLab Analyzer

## 1. Общее описание

**Название проекта:** GitLab Analyzer

**Цель:** Веб-сервис для сбора, хранения и визуализации статистики активности пользователей локального GitLab CE. Позволяет оценивать продуктивность разработчиков, отслеживать вклад каждого участника и формировать отчёты за произвольные периоды.

**Целевая аудитория:** Руководители команд, тимлиды, PM — для мониторинга загрузки и активности разработчиков.

---

## 2. Функциональные требования

### 2.1. Подключение к GitLab

- Подключение к локальному GitLab CE через GitLab REST API v4
- Аутентификация по Personal Access Token (PAT) или Deploy Token
- Поддержка настройки URL GitLab-инстанса через конфигурацию
- Возможность подключения к нескольким инстансам GitLab (в перспективе)

### 2.2. Сбор данных

Система должна собирать и сохранять следующие сущности:

#### Пользователи (Users)
- ID, username, email, имя, состояние (active/blocked), дата создания
- Роль (admin, regular, external)
- Дата последней активности

#### Проекты (Projects)
- ID, название, namespace, описание, URL
- Видимость (private/internal/public)
- Дата создания, последней активности

#### Коммиты (Commits)
- SHA, автор, сообщение, дата
- Количество добавленных/удалённых строк
- Привязка к проекту и пользователю

#### Merge Requests (MR)
- ID, заголовок, описание, автор, assignee
- Статус (opened/closed/merged)
- Даты создания, обновления, мержа
- Количество комментариев, approvals
- Source/target branch

#### Issues
- ID, заголовок, описание, автор, assignee
- Статус (opened/closed)
- Метки (labels), milestone
- Даты создания, закрытия
- Количество комментариев

#### Комментарии (Notes)
- К MR и Issues
- Автор, текст (длина), дата
- Тип (обычный, review, system)

#### Pipelines (CI/CD)
- ID, статус (success/failed/canceled), длительность
- Привязка к проекту, коммиту, пользователю
- Дата запуска и завершения

#### События (Events)
- Все пользовательские события из GitLab Events API
- Тип действия (push, comment, merge, issue, etc.)
- Дата, автор, привязка к проекту

### 2.3. Управление данными

- **Сбор за период:** Пользователь указывает диапазон дат (от/до), система загружает данные за этот период
- **Ленивая загрузка:** Если данных за запрашиваемый период нет в БД — автоматически подгружать из GitLab API
- **Обновление данных:** Возможность принудительно обновить данные за указанный период (перезагрузить из API)
- **Инкрементальный сбор:** При повторном сборе — загружать только новые/изменённые данные
- **Фоновый сбор:** Возможность настроить периодический автоматический сбор (cron/scheduler)

### 2.4. Аналитика и метрики

#### Метрики по пользователю за период:
- Количество коммитов
- Количество добавленных/удалённых строк кода
- Количество созданных/закрытых MR
- Количество созданных/закрытых Issues
- Количество комментариев (к MR и Issues)
- Количество запущенных пайплайнов (успешных/неуспешных)
- Количество событий по типам
- Среднее время закрытия MR
- Среднее время закрытия Issues

#### Сводные отчёты:
- **Дневная сводка:** Кто что делал в конкретный день
- **Недельная/месячная сводка:** Агрегированная статистика по каждому пользователю
- **Рейтинг активности:** Ранжирование пользователей по совокупной активности
- **Выявление неактивных:** Подсветка пользователей с нулевой или минимальной активностью за период
- **Сравнительный анализ:** Сравнение метрик между пользователями

#### Визуализация:
- Графики активности по дням (тепловая карта / bar chart)
- Графики по типам активности (pie chart)
- Тренды по неделям/месяцам (line chart)
- Таблицы с сортировкой и фильтрацией

### 2.5. Экспорт данных

- Экспорт таблиц и отчётов в CSV
- Экспорт с фильтрацией по периоду и пользователям

### 2.6. Веб-интерфейс

- Без авторизации (внутренний инструмент)
- Дашборд с общей статистикой
- Страница пользователей со списком и поиском
- Детальная страница пользователя с его метриками
- Страница проектов
- Страница настроек (GitLab URL, токен, параметры сбора)
- Выбор периода на всех страницах (date range picker)

---

## 3. Нефункциональные требования

### 3.1. Платформы

- Windows 10/11
- Linux (Ubuntu 20.04+, Debian 11+)
- Docker (docker-compose для полного стека)

### 3.2. Производительность

- Сбор данных не должен блокировать UI (фоновые задачи)
- Отображение дашборда < 2 секунд при наличии данных в БД
- Поддержка GitLab-инстансов до 500 пользователей и 1000 проектов

### 3.3. Надёжность

- Graceful handling ошибок API (rate limiting, timeout, недоступность)
- Retry с exponential backoff
- Логирование всех операций сбора данных
- Сохранение прогресса при прерывании сбора

---

## 4. Архитектура

### 4.1. Общая схема

```
┌─────────────┐     ┌─────────────────┐     ┌────────────┐
│  React SPA  │────▶│  FastAPI Backend │────▶│ PostgreSQL │
│  (Frontend) │◀────│  (Python)        │◀────│    (DB)    │
└─────────────┘     └────────┬────────┘     └────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  GitLab CE API  │
                    │  (REST API v4)  │
                    └─────────────────┘
```

### 4.2. Backend (Python)

- **Фреймворк:** FastAPI
- **ORM:** SQLAlchemy 2.0 (async)
- **Миграции:** Alembic
- **HTTP-клиент:** httpx (async)
- **Фоновые задачи:** Celery + Redis (или встроенный BackgroundTasks для простых случаев)
- **Логирование:** structlog / стандартный logging
- **Конфигурация:** pydantic-settings (из .env файла)

### 4.3. Frontend (JavaScript)

- **Фреймворк:** React 18+ с TypeScript
- **Сборщик:** Vite
- **UI-библиотека:** Ant Design или MUI
- **Графики:** Recharts или Chart.js
- **HTTP-клиент:** axios
- **Роутинг:** React Router
- **Стейт:** React Query (TanStack Query) для серверного состояния

### 4.4. База данных (PostgreSQL)

- PostgreSQL 15+
- Миграции через Alembic с поддержкой upgrade/downgrade
- Индексы по полям дат и user_id для быстрых выборок

### 4.5. Docker

- `docker-compose.yml` с сервисами:
  - `backend` — Python FastAPI
  - `frontend` — Nginx + React build
  - `db` — PostgreSQL
  - `redis` — Redis (для Celery, если используется)
- Volumes для персистентности данных БД
- `.env` файл для конфигурации

---

## 5. Структура проекта

```
gitlab_analyzer/
├── backend/
│   ├── alembic/                 # Миграции
│   │   ├── versions/
│   │   └── env.py
│   ├── app/
│   │   ├── api/                 # REST API endpoints
│   │   │   ├── routes/
│   │   │   │   ├── users.py
│   │   │   │   ├── projects.py
│   │   │   │   ├── analytics.py
│   │   │   │   ├── sync.py      # Управление сбором данных
│   │   │   │   └── export.py
│   │   │   └── deps.py          # Зависимости (DB session и т.д.)
│   │   ├── core/
│   │   │   ├── config.py        # Настройки приложения
│   │   │   └── logging.py
│   │   ├── db/
│   │   │   ├── base.py
│   │   │   ├── session.py
│   │   │   └── models/          # SQLAlchemy модели
│   │   │       ├── user.py
│   │   │       ├── project.py
│   │   │       ├── commit.py
│   │   │       ├── merge_request.py
│   │   │       ├── issue.py
│   │   │       ├── note.py
│   │   │       ├── pipeline.py
│   │   │       └── event.py
│   │   ├── services/
│   │   │   ├── gitlab_client.py  # Клиент GitLab API
│   │   │   ├── sync_service.py   # Логика сбора данных
│   │   │   └── analytics.py     # Расчёт метрик
│   │   └── main.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── alembic.ini
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── api/
│   │   ├── hooks/
│   │   └── App.tsx
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
├── docs/
│   ├── TECHNICAL_SPEC.md         # Это ТЗ
│   ├── API.md                    # Документация API
│   └── DEPLOYMENT.md             # Инструкция по развёртыванию
├── CLAUDE.md
└── README.md
```

---

## 6. API Endpoints (Backend)

### Настройки
- `GET /api/settings` — Получить текущие настройки
- `PUT /api/settings` — Обновить настройки (GitLab URL, токен)
- `GET /api/settings/test` — Проверить подключение к GitLab

### Синхронизация данных
- `POST /api/sync/start` — Запустить сбор данных `{date_from, date_to, force_update: bool}`
- `GET /api/sync/status` — Статус текущего сбора
- `POST /api/sync/stop` — Остановить текущий сбор

### Пользователи
- `GET /api/users` — Список пользователей (с пагинацией, поиском)
- `GET /api/users/{id}` — Детали пользователя
- `GET /api/users/{id}/activity` — Активность пользователя за период

### Проекты
- `GET /api/projects` — Список проектов
- `GET /api/projects/{id}` — Детали проекта
- `GET /api/projects/{id}/activity` — Активность по проекту

### Аналитика
- `GET /api/analytics/summary` — Сводка за период `?date_from=&date_to=`
- `GET /api/analytics/daily` — Дневная разбивка активности
- `GET /api/analytics/ranking` — Рейтинг пользователей
- `GET /api/analytics/inactive` — Неактивные пользователи
- `GET /api/analytics/compare` — Сравнение пользователей

### Экспорт
- `GET /api/export/csv/summary` — Сводка в CSV
- `GET /api/export/csv/users` — Данные по пользователям в CSV
- `GET /api/export/csv/activity` — Детальная активность в CSV

---

## 7. Модель данных (основные таблицы)

### gitlab_users
| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER PK | GitLab user ID |
| username | VARCHAR(255) | Логин |
| name | VARCHAR(255) | Полное имя |
| email | VARCHAR(255) | Email |
| state | VARCHAR(50) | Статус (active/blocked) |
| is_admin | BOOLEAN | Является ли администратором |
| created_at | TIMESTAMP | Дата создания в GitLab |
| last_activity_at | TIMESTAMP | Последняя активность |
| synced_at | TIMESTAMP | Дата последней синхронизации |

### gitlab_projects
| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER PK | GitLab project ID |
| name | VARCHAR(255) | Название |
| path_with_namespace | VARCHAR(500) | Полный путь |
| description | TEXT | Описание |
| visibility | VARCHAR(50) | Видимость |
| created_at | TIMESTAMP | Дата создания |
| last_activity_at | TIMESTAMP | Последняя активность |
| synced_at | TIMESTAMP | Дата последней синхронизации |

### commits
| Поле | Тип | Описание |
|------|-----|----------|
| id | SERIAL PK | Внутренний ID |
| sha | VARCHAR(40) UNIQUE | SHA коммита |
| project_id | INTEGER FK | Проект |
| author_name | VARCHAR(255) | Имя автора |
| author_email | VARCHAR(255) | Email автора |
| user_id | INTEGER FK NULL | Привязка к gitlab_users |
| message | TEXT | Сообщение коммита |
| committed_at | TIMESTAMP | Дата коммита |
| additions | INTEGER | Добавленные строки |
| deletions | INTEGER | Удалённые строки |

### merge_requests
| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER PK | GitLab MR ID |
| iid | INTEGER | MR номер в проекте |
| project_id | INTEGER FK | Проект |
| author_id | INTEGER FK | Автор |
| assignee_id | INTEGER FK NULL | Assignee |
| title | VARCHAR(500) | Заголовок |
| state | VARCHAR(50) | Статус |
| created_at | TIMESTAMP | Дата создания |
| updated_at | TIMESTAMP | Дата обновления |
| merged_at | TIMESTAMP NULL | Дата мержа |
| closed_at | TIMESTAMP NULL | Дата закрытия |
| user_notes_count | INTEGER | Количество комментариев |

### issues
| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER PK | GitLab Issue ID |
| iid | INTEGER | Issue номер в проекте |
| project_id | INTEGER FK | Проект |
| author_id | INTEGER FK | Автор |
| assignee_id | INTEGER FK NULL | Assignee |
| title | VARCHAR(500) | Заголовок |
| state | VARCHAR(50) | Статус |
| labels | JSONB | Метки |
| created_at | TIMESTAMP | Дата создания |
| updated_at | TIMESTAMP | Дата обновления |
| closed_at | TIMESTAMP NULL | Дата закрытия |
| user_notes_count | INTEGER | Количество комментариев |

### notes
| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER PK | GitLab Note ID |
| author_id | INTEGER FK | Автор |
| project_id | INTEGER FK | Проект |
| noteable_type | VARCHAR(50) | Тип (MergeRequest/Issue) |
| noteable_id | INTEGER | ID сущности |
| body_length | INTEGER | Длина текста |
| system | BOOLEAN | Системный комментарий |
| created_at | TIMESTAMP | Дата создания |

### pipelines
| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER PK | GitLab Pipeline ID |
| project_id | INTEGER FK | Проект |
| user_id | INTEGER FK | Запустивший |
| status | VARCHAR(50) | Статус |
| ref | VARCHAR(255) | Ветка/тег |
| sha | VARCHAR(40) | SHA коммита |
| duration | INTEGER NULL | Длительность (сек) |
| created_at | TIMESTAMP | Дата создания |
| finished_at | TIMESTAMP NULL | Дата завершения |

### events
| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER PK | GitLab Event ID |
| user_id | INTEGER FK | Автор |
| project_id | INTEGER FK NULL | Проект |
| action_name | VARCHAR(100) | Тип действия |
| target_type | VARCHAR(100) NULL | Тип объекта |
| target_id | INTEGER NULL | ID объекта |
| created_at | TIMESTAMP | Дата события |

### sync_log
| Поле | Тип | Описание |
|------|-----|----------|
| id | SERIAL PK | Внутренний ID |
| started_at | TIMESTAMP | Начало синхронизации |
| finished_at | TIMESTAMP NULL | Конец синхронизации |
| date_from | DATE | Начало периода |
| date_to | DATE | Конец периода |
| status | VARCHAR(50) | Статус (running/completed/failed) |
| entities_synced | JSONB | Счётчики по типам сущностей |
| error_message | TEXT NULL | Ошибка (если была) |

---

## 8. Этапы реализации

### Этап 1: Инфраструктура
- Инициализация проекта (backend + frontend)
- Настройка Docker Compose
- Настройка PostgreSQL + Alembic миграции
- Базовые модели данных

### Этап 2: Сбор данных
- GitLab API клиент
- Синхронизация пользователей и проектов
- Синхронизация коммитов, MR, Issues
- Синхронизация комментариев, пайплайнов, событий
- Управление периодом сбора, инкрементальное обновление

### Этап 3: API аналитики
- Эндпоинты сводки и метрик
- Расчёт рейтингов и сравнений
- Выявление неактивных пользователей
- Экспорт в CSV

### Этап 4: Frontend
- Каркас React-приложения
- Дашборд с графиками
- Страницы пользователей и проектов
- Детальные страницы с метриками
- Управление синхронизацией
- Настройки

### Этап 5: Документация и деплой
- README с инструкцией запуска
- Документация API
- Инструкция по развёртыванию
- Финальное тестирование

---

## 9. Конфигурация

Через `.env` файл:

```env
# GitLab
GITLAB_URL=https://gitlab.local
GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx

# PostgreSQL
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/gitlab_analyzer

# Redis (если используется Celery)
REDIS_URL=redis://localhost:6379/0

# Приложение
BACKEND_PORT=8000
FRONTEND_PORT=3000
LOG_LEVEL=INFO
```

---

## 10. Ограничения и допущения

- GitLab CE API v4 — некоторые эндпоинты могут быть недоступны без admin-токена
- Rate limiting GitLab API — необходимо учитывать лимиты запросов
- Привязка коммитов к пользователям происходит по email (может быть неточной, если у пользователя разные email в Git и GitLab)
- Подсчёт строк кода — приблизительный, считается по данным GitLab API
- Без авторизации в веб-интерфейсе — подходит только для внутренних сетей
