"""
Диагностический скрипт: вытягивает все данные по SHA коммита из GitLab API.

Использование:
  python debug_commit.py <GITLAB_URL> <TOKEN> <SHA>

Пример:
  python debug_commit.py https://gitlab.example.com glpat-xxxxxxxxxxxx abc123def456
"""

import sys
import json
import urllib.request
import urllib.error
import ssl

def api_get(base_url: str, token: str, path: str) -> dict | list | None:
    """GET-запрос к GitLab API."""
    url = f"{base_url.rstrip('/')}/api/v4{path}"
    req = urllib.request.Request(url, headers={"PRIVATE-TOKEN": token})
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"__error": e.code, "__url": url, "__body": e.read().decode(errors="replace")}
    except Exception as e:
        return {"__error": str(e), "__url": url}


def main():
    if len(sys.argv) != 4:
        print("Использование: python debug_commit.py <GITLAB_URL> <TOKEN> <SHA>")
        sys.exit(1)

    base_url, token, sha = sys.argv[1], sys.argv[2], sys.argv[3]
    output_lines = []

    def log(text: str):
        print(text)
        output_lines.append(text)

    def dump(label: str, data):
        text = json.dumps(data, indent=2, ensure_ascii=False, default=str)
        log(f"\n{'='*60}")
        log(f"  {label}")
        log(f"{'='*60}")
        log(text)

    # 1. Проверка подключения
    log(f"GitLab: {base_url}")
    log(f"SHA: {sha}")
    user_info = api_get(base_url, token, "/user")
    dump("1. Текущий пользователь (токен)", user_info)

    # 2. Ищем коммит по всем проектам
    log("\n\nИщу проекты...")
    projects = api_get(base_url, token, "/projects?per_page=100&membership=true")
    if isinstance(projects, dict) and "__error" in projects:
        dump("Ошибка получения проектов", projects)
        # Попробуем без membership
        projects = api_get(base_url, token, "/projects?per_page=100")

    if not isinstance(projects, list):
        dump("Ошибка: projects не список", projects)
        sys.exit(1)

    log(f"Найдено проектов: {len(projects)}")

    found_project = None
    found_commit = None

    for proj in projects:
        pid = proj["id"]
        pname = proj.get("path_with_namespace", str(pid))
        commit = api_get(base_url, token, f"/projects/{pid}/repository/commits/{sha}?stats=true")
        if isinstance(commit, dict) and "__error" not in commit and "id" in commit:
            log(f"\nКоммит найден в проекте: {pname} (id={pid})")
            found_project = proj
            found_commit = commit
            break

    if not found_commit:
        log(f"\nКоммит {sha} не найден ни в одном проекте!")
        with open("debug_commit_output.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(output_lines))
        sys.exit(1)

    pid = found_project["id"]
    pname = found_project.get("path_with_namespace", str(pid))

    # 3. Данные коммита
    dump("2. Коммит (полные данные)", found_commit)

    # 4. Ищем пользователя по author_email
    author_email = found_commit.get("author_email", "")
    author_name = found_commit.get("author_name", "")
    log(f"\nauthor_email: {author_email}")
    log(f"author_name: {author_name}")

    users_by_email = api_get(base_url, token, f"/users?search={author_email}")
    dump("3. Поиск пользователей по author_email", users_by_email)

    users_by_name = api_get(base_url, token, f"/users?search={author_name}")
    dump("4. Поиск пользователей по author_name", users_by_name)

    # 5. Все пользователи (для сравнения)
    all_users = api_get(base_url, token, "/users?per_page=100&active=true")
    if isinstance(all_users, list):
        users_summary = [
            {"id": u["id"], "username": u["username"], "name": u.get("name"), "email": u.get("email", "N/A")}
            for u in all_users
        ]
        dump("5. Все активные пользователи (id, username, name, email)", users_summary)

    # 6. Ищем события (push) в проекте, связанные с этим коммитом
    events = api_get(base_url, token, f"/projects/{pid}/events?action=pushed&per_page=100")
    push_events_with_sha = []
    if isinstance(events, list):
        for ev in events:
            pd = ev.get("push_data") or {}
            if pd.get("commit_to") == sha or pd.get("commit_from") == sha:
                push_events_with_sha.append(ev)
            # Также ищем по commit_title
            if found_commit.get("title") and pd.get("commit_title") == found_commit.get("title"):
                if ev not in push_events_with_sha:
                    push_events_with_sha.append(ev)

    if push_events_with_sha:
        dump("6. Push-события связанные с этим коммитом", push_events_with_sha)
    else:
        log("\n6. Push-события с этим SHA не найдены в проекте")
        # Покажем последние push-события для контекста
        recent_pushes = [ev for ev in (events if isinstance(events, list) else []) if ev.get("push_data")][:5]
        dump("6b. Последние 5 push-событий в проекте (для контекста)", recent_pushes)

    # 7. События пользователя (если нашли автора)
    # Ищем по author_name в списке пользователей
    candidate_user_ids = set()
    if isinstance(users_by_email, list):
        for u in users_by_email:
            candidate_user_ids.add(u["id"])
    if isinstance(users_by_name, list):
        for u in users_by_name:
            candidate_user_ids.add(u["id"])

    for uid in candidate_user_ids:
        user_events = api_get(base_url, token, f"/users/{uid}/events?per_page=20")
        user_pushes = [ev for ev in (user_events if isinstance(user_events, list) else []) if ev.get("push_data")][:5]
        dump(f"7. Последние push-события пользователя id={uid}", user_pushes)

    # 8. Refs (ветки содержащие коммит)
    refs = api_get(base_url, token, f"/projects/{pid}/repository/commits/{sha}/refs")
    dump("8. Ветки/теги содержащие этот коммит", refs)

    # Сохраняем в файл
    with open("debug_commit_output.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))

    log(f"\n\nРезультат сохранён в debug_commit_output.txt")


if __name__ == "__main__":
    main()
