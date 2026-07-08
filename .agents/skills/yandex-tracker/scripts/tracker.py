#!/usr/bin/env python3
"""Small CLI helper for Yandex Tracker API tasks."""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_CONFIG = Path.home() / ".yandex-tracker.env"
DEFAULT_BASE_URL = "https://api.tracker.yandex.net/v3"
DEFAULT_FIELDS = "key,summary,status,assignee,queue,priority,type,sprint,updatedAt"
DEFAULT_SCRUM_BOARD_ID = "2"
DEFAULT_EPICFLOW_BOARD_ID = "214"
DEFAULT_DEV_EPICS_BOARD_ID = "658"
DEFAULT_DEV_QUEUE = "LT"
DEFAULT_EPIC_QUEUE = "EPICFLOW"
DEFAULT_TASK_TEAM_FIELD = "65ba668d034eb51c5204c8d4--team"
DEFAULT_EPIC_TEAM_FIELD = "69c2cd23dcc4e4691efad1ad--dev_team"
DEFAULT_STORY_POINTS_FIELD = "storyPoints"
DEFAULT_DONE_STATUSES = ("Завершено", "Готово к релизу", "ReadyToProduction")
DEFAULT_ACTIVE_STATUSES = (
    "В работе",
    "Ревью",
    "Тестируется",
    "Можно тестировать",
    "Требуются доработки",
    "Assembly",
)
DEFAULT_TERMINAL_STATUSES = ("Завершено", "Отменено", "Canceled")
DEFAULT_DEV_STAGE_EPICFLOW_STATUSES = (
    "Передано в разработку",
    "ТЗ",
    "В работе",
    "Ревью",
    "Тестируется",
    "Ждем другую команду",
    "Готово к релизу",
    "В релизе",
    "А/Б",
    "Доработки по итогам релиза",
)


class TrackerError(RuntimeError):
    pass


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def write_env_file(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(f"{key}={value}\n" for key, value in values.items())
    tmp_path = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, stat.S_IRUSR | stat.S_IWUSR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(content)
        os.replace(tmp_path, path)
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def load_config(args: argparse.Namespace) -> dict[str, str]:
    path = Path(args.config).expanduser()
    file_values = read_env_file(path)

    def value(name: str, legacy_name: str, default: str = "") -> str:
        return (
            os.environ.get(name)
            or os.environ.get(legacy_name)
            or file_values.get(name)
            or file_values.get(legacy_name)
            or default
        )

    values = {
        "api_base": value("YANDEX_TRACKER_API_BASE", "TRACKER_API_BASE", DEFAULT_BASE_URL),
        "token": value("YANDEX_TRACKER_TOKEN", "TRACKER_TOKEN"),
        "auth_type": value("YANDEX_TRACKER_AUTH_TYPE", "TRACKER_AUTH_TYPE", "OAuth"),
        "org_id": value("YANDEX_TRACKER_ORG_ID", "TRACKER_ORG_ID"),
        "org_header": value("YANDEX_TRACKER_ORG_HEADER", "TRACKER_ORG_HEADER", "X-Org-ID"),
        "default_user_name": value("YANDEX_TRACKER_DEFAULT_USER_NAME", "TRACKER_DEFAULT_USER_NAME"),
        "default_user_email": value("YANDEX_TRACKER_DEFAULT_USER_EMAIL", "TRACKER_DEFAULT_USER_EMAIL"),
        "default_boards": value("YANDEX_TRACKER_DEFAULT_BOARDS", "TRACKER_DEFAULT_BOARDS"),
        "scrum_board_id": value("YANDEX_TRACKER_SCRUM_BOARD_ID", "TRACKER_SCRUM_BOARD_ID", DEFAULT_SCRUM_BOARD_ID),
        "epicflow_board_id": value("YANDEX_TRACKER_EPICFLOW_BOARD_ID", "TRACKER_EPICFLOW_BOARD_ID", DEFAULT_EPICFLOW_BOARD_ID),
        "dev_epics_board_id": value("YANDEX_TRACKER_DEV_EPICS_BOARD_ID", "TRACKER_DEV_EPICS_BOARD_ID", DEFAULT_DEV_EPICS_BOARD_ID),
        "dev_queue": value("YANDEX_TRACKER_DEV_QUEUE", "TRACKER_DEV_QUEUE", DEFAULT_DEV_QUEUE),
        "epic_queue": value("YANDEX_TRACKER_EPIC_QUEUE", "TRACKER_EPIC_QUEUE", DEFAULT_EPIC_QUEUE),
        "task_team_field": value("YANDEX_TRACKER_TASK_TEAM_FIELD", "TRACKER_TASK_TEAM_FIELD", DEFAULT_TASK_TEAM_FIELD),
        "epic_team_field": value("YANDEX_TRACKER_EPIC_TEAM_FIELD", "TRACKER_EPIC_TEAM_FIELD", DEFAULT_EPIC_TEAM_FIELD),
        "story_points_field": value("YANDEX_TRACKER_STORY_POINTS_FIELD", "TRACKER_STORY_POINTS_FIELD", DEFAULT_STORY_POINTS_FIELD),
    }
    if not values["token"] or not values["org_id"]:
        raise TrackerError(
            f"Tracker credentials are missing. Run `tracker.py setup ...` or create {path}."
        )
    return values


def request_json(
    cfg: dict[str, str],
    method: str,
    path: str,
    *,
    query: dict[str, Any] | None = None,
    body: Any | None = None,
) -> Any:
    base = cfg["api_base"].rstrip("/")
    url = f"{base}{path}"
    query = {k: v for k, v in (query or {}).items() if v not in (None, "", [])}
    if query:
        url = f"{url}?{urlencode(query, doseq=True)}"

    data = None
    headers = {
        "Authorization": f"{cfg['auth_type']} {cfg['token']}",
        cfg["org_header"]: cfg["org_id"],
    }
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    for attempt in range(4):
        req = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=30) as response:
                raw = response.read()
                if not raw:
                    return None
                return json.loads(raw.decode("utf-8"))
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            if exc.code == 429 and attempt < 3:
                retry_after = exc.headers.get("Retry-After")
                delay = int(retry_after) if retry_after and retry_after.isdigit() else 2 ** attempt
                time.sleep(delay)
                continue
            raise TrackerError(f"{method} {url} failed: HTTP {exc.code}: {raw}") from exc
    raise TrackerError(f"{method} {url} failed after retries.")


def compact_user(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("display") or value.get("id") or value.get("key") or "")
    if isinstance(value, list):
        return ", ".join(compact_user(v) for v in value)
    return "" if value is None else str(value)


def compact_issue(issue: dict[str, Any]) -> dict[str, Any]:
    status = issue.get("status") or {}
    return {
        "id": issue.get("id"),
        "key": issue.get("key"),
        "summary": issue.get("summary"),
        "status": status.get("display") or status.get("key"),
        "statusKey": status.get("key"),
        "assignee": compact_user(issue.get("assignee")) or None,
        "queue": (issue.get("queue") or {}).get("key") or compact_user(issue.get("queue")) or None,
        "priority": compact_user(issue.get("priority")) or None,
        "type": compact_user(issue.get("type")) or None,
        "sprint": compact_user(issue.get("sprint")) or None,
        "createdAt": issue.get("createdAt"),
        "updatedAt": issue.get("updatedAt"),
    }


def compact_issue_response(value: Any) -> Any:
    if isinstance(value, list):
        return [compact_issue(issue) if isinstance(issue, dict) else issue for issue in value]
    if isinstance(value, dict):
        return compact_issue(value)
    return value


def compact_transition(transition: dict[str, Any]) -> dict[str, Any]:
    to_status = transition.get("to") or {}
    result: dict[str, Any] = {
        "id": transition.get("id"),
        "display": transition.get("display"),
        "to": {
            "key": to_status.get("key"),
            "display": to_status.get("display"),
        },
    }
    if transition.get("screen"):
        result["screen"] = transition.get("screen")
    return result


def compact_comment(comment: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": comment.get("id"),
        "longId": comment.get("longId"),
        "text": comment.get("text"),
        "createdBy": compact_user(comment.get("createdBy")) or None,
        "createdAt": comment.get("createdAt"),
        "updatedAt": comment.get("updatedAt"),
    }


def compact_ref(value: Any) -> str | None:
    text = compact_user(value)
    return text or None


def issue_url(issue_key: str | None) -> str | None:
    return f"https://tracker.yandex.ru/{issue_key}" if issue_key else None


def project_url(project_id: str | int | None) -> str | None:
    return f"https://tracker.yandex.ru/pages/projects/{project_id}/issues" if project_id else None


def story_points(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) else 0.0


def tracker_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(value, fmt).astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def date_start_utc(value: str) -> datetime:
    return datetime.fromisoformat(f"{value}T00:00:00+03:00").astimezone(timezone.utc)


def date_end_utc(value: str) -> datetime:
    return datetime.fromisoformat(f"{value}T23:59:59+03:00").astimezone(timezone.utc)


def in_datetime_window(value: str | None, start: datetime, end: datetime) -> bool:
    parsed = tracker_datetime(value)
    return parsed is not None and start <= parsed <= end


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False))


def parse_json_arg(value: str, arg_name: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise TrackerError(f"{arg_name} must be valid JSON: {exc}") from exc


def parse_json_object_arg(value: str, arg_name: str) -> dict[str, Any]:
    parsed = parse_json_arg(value, arg_name)
    if not isinstance(parsed, dict):
        raise TrackerError(f"{arg_name} must be a JSON object.")
    return parsed


def parse_csv_arg(value: str | None) -> list[str] | None:
    if not value:
        return None
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or None


def parse_id_csv_arg(value: str | None) -> list[str | int] | None:
    items = parse_csv_arg(value)
    if not items:
        return None
    return [int(item) if item.isdigit() else item for item in items]


def parse_ref_csv_arg(value: str | None) -> list[dict[str, str]] | None:
    items = parse_csv_arg(value)
    if not items:
        return None
    return [{"id": item} if item.isdigit() else {"key": item} for item in items]


def read_text_arg(text: str | None, text_file: str | None, arg_name: str) -> str:
    if text and text_file:
        raise TrackerError(f"Specify only one of --text and --text-file for {arg_name}.")
    if text_file:
        if text_file == "-":
            value = sys.stdin.read()
        else:
            value = Path(text_file).expanduser().read_text(encoding="utf-8")
    else:
        value = text or ""
    if not value.strip():
        raise TrackerError(f"{arg_name} must not be empty.")
    return value


def read_optional_text_arg(text: str | None, text_file: str | None, arg_name: str) -> str | None:
    if text is None and text_file is None:
        return None
    return read_text_arg(text, text_file, arg_name)


def ref_arg(value: str | None) -> str | dict[str, str] | None:
    if not value:
        return None
    if value.isdigit():
        return {"id": value}
    return value


def merge_field_json(body: dict[str, Any], field_json: str | None, arg_name: str) -> dict[str, Any]:
    if not field_json:
        return body
    extra = parse_json_object_arg(field_json, arg_name)
    if "status" in extra:
        raise TrackerError("Do not update status with field JSON; use `transitions`, `move`, or `transition`.")
    duplicate_keys = sorted(set(body).intersection(extra))
    if duplicate_keys:
        raise TrackerError(
            f"{arg_name} duplicates explicit arguments: {', '.join(duplicate_keys)}. "
            "Pass each field only once."
        )
    return {**body, **extra}


def parse_board_list(value: str) -> list[dict[str, Any]]:
    boards: list[dict[str, Any]] = []
    for raw_item in value.split(","):
        item = raw_item.strip()
        if not item:
            continue
        if ":" in item:
            board_id, name = item.split(":", 1)
        else:
            board_id, name = item, ""
        board_id = board_id.strip()
        if not board_id:
            continue
        boards.append({"id": board_id, "name": name.strip() or None})
    return boards


def board_ref(board: dict[str, Any]) -> str:
    if board.get("name"):
        return f"{board['name']} ({board['id']})"
    return str(board["id"])


def project_refs(issue: dict[str, Any]) -> list[dict[str, Any]]:
    project = issue.get("project") or {}
    refs: list[dict[str, Any]] = []
    primary = project.get("primary")
    if isinstance(primary, dict):
        refs.append({**primary, "relation": "primary"})
    for secondary in project.get("secondary") or []:
        if isinstance(secondary, dict):
            refs.append({**secondary, "relation": "secondary"})
    return refs


def dedupe_by_key(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for item in items:
        key = str(item.get("key") or item.get("id") or "")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        result.append(item)
    return result


def search_all(
    cfg: dict[str, str],
    body: dict[str, Any],
    fields: str,
    *,
    per_page: int = 100,
    max_pages: int | None = None,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    page = 1
    while True:
        chunk = request_json(
            cfg,
            "POST",
            "/issues/_search",
            query={"fields": fields, "perPage": per_page, "page": page},
            body=body,
        )
        if not isinstance(chunk, list):
            raise TrackerError(f"Unexpected search response: {json.dumps(chunk, ensure_ascii=False)}")
        issues.extend(chunk)
        if len(chunk) < per_page:
            return issues
        page += 1
        if max_pages is not None and page > max_pages:
            return issues


def issue_field_list(*fields: str) -> str:
    return ",".join(field for field in fields if field)


def get_current_sprint(cfg: dict[str, str], board_id: str) -> dict[str, Any]:
    sprints = request_json(cfg, "GET", f"/boards/{board_id}/sprints")
    if not isinstance(sprints, list):
        raise TrackerError(f"Unexpected sprint response for board {board_id}.")
    active = [sprint for sprint in sprints if sprint.get("status") == "in_progress"]
    if active:
        return sorted(active, key=lambda sprint: str(sprint.get("startDate") or ""), reverse=True)[0]
    today = date.today().isoformat()
    covering = [
        sprint for sprint in sprints
        if str(sprint.get("startDate") or "") <= today <= str(sprint.get("endDate") or "")
    ]
    if covering:
        return sorted(covering, key=lambda sprint: str(sprint.get("startDate") or ""), reverse=True)[0]
    openish = [sprint for sprint in sprints if not sprint.get("archived")]
    if openish:
        return sorted(openish, key=lambda sprint: str(sprint.get("startDate") or ""), reverse=True)[0]
    raise TrackerError(f"No current or non-archived sprint found for board {board_id}.")


def resolve_sprint_id(cfg: dict[str, str], sprint: str, board_id: str) -> str:
    if sprint == "current":
        return str(get_current_sprint(cfg, board_id).get("id"))
    return sprint


def compact_project(project: dict[str, Any]) -> dict[str, Any]:
    project_id = project.get("id")
    return {
        "id": project_id,
        "display": project.get("display"),
        "relation": project.get("relation"),
        "url": project_url(project_id),
    }


def compact_analysis_task(issue: dict[str, Any], team_field: str, story_points_field: str) -> dict[str, Any]:
    return {
        "key": issue.get("key"),
        "url": issue_url(issue.get("key")),
        "summary": issue.get("summary"),
        "status": compact_ref(issue.get("status")),
        "assignee": compact_ref(issue.get("assignee")),
        "team": issue.get(team_field),
        "storyPoints": issue.get(story_points_field),
        "projects": [compact_project(project) for project in project_refs(issue)],
    }


def compact_analysis_epic(issue: dict[str, Any], team_field: str) -> dict[str, Any]:
    return {
        "key": issue.get("key"),
        "url": issue_url(issue.get("key")),
        "summary": issue.get("summary"),
        "status": compact_ref(issue.get("status")),
        "teams": issue.get(team_field),
        "projects": [compact_project(project) for project in project_refs(issue)],
    }


def build_project_epic_index(epics: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for epic in epics:
        for project in project_refs(epic):
            project_id = project.get("id")
            if project_id is not None:
                result[str(project_id)].append(epic)
    return {project_id: dedupe_by_key(items) for project_id, items in result.items()}


def analyze_epicflow_coverage(
    cfg: dict[str, str],
    *,
    sprint_id: str,
    team: str | None,
) -> dict[str, Any]:
    task_team_field = cfg["task_team_field"]
    epic_team_field = cfg["epic_team_field"]
    story_points_field = cfg["story_points_field"]
    dev_queue = cfg["dev_queue"]
    epic_queue = cfg["epic_queue"]
    task_fields = issue_field_list(
        "key", "summary", "status", "assignee", "sprint", "project", "queue",
        story_points_field, task_team_field,
    )
    task_filter: dict[str, Any] = {
        "sprint": int(sprint_id) if str(sprint_id).isdigit() else sprint_id,
        "queue": dev_queue,
    }
    if team and team != "NO_TEAM":
        task_filter[task_team_field] = team
    tasks = search_all(cfg, {"filter": task_filter}, task_fields)
    if team == "NO_TEAM":
        tasks = [task for task in tasks if not task.get(task_team_field)]

    epic_fields = issue_field_list("key", "summary", "status", "project", epic_team_field)
    all_epics = search_all(cfg, {"filter": {"queue": epic_queue}}, epic_fields)
    team_epics = [
        epic for epic in all_epics
        if not team or (team != "NO_TEAM" and team in (epic.get(epic_team_field) or []))
    ]
    all_epics_by_project = build_project_epic_index(all_epics)
    team_epics_by_project = build_project_epic_index(team_epics)

    project_to_tasks: dict[str, list[dict[str, Any]]] = defaultdict(list)
    no_project_tasks: list[dict[str, Any]] = []
    enriched_tasks: list[dict[str, Any]] = []
    for task in tasks:
        projects = project_refs(task)
        if not projects:
            no_project_tasks.append(task)
        team_matches: list[dict[str, Any]] = []
        all_matches: list[dict[str, Any]] = []
        for project in projects:
            project_id = project.get("id")
            if project_id is None:
                continue
            project_to_tasks[str(project_id)].append(task)
            team_matches.extend(team_epics_by_project.get(str(project_id), []))
            all_matches.extend(all_epics_by_project.get(str(project_id), []))
        item = compact_analysis_task(task, task_team_field, story_points_field)
        item["teamEpics"] = [compact_analysis_epic(epic, epic_team_field) for epic in dedupe_by_key(team_matches)]
        item["anyEpicFlowEpics"] = [compact_analysis_epic(epic, epic_team_field) for epic in dedupe_by_key(all_matches)]
        enriched_tasks.append(item)

    projects: list[dict[str, Any]] = []
    for project_id, project_tasks in project_to_tasks.items():
        project_ref: dict[str, Any] | None = None
        for task in project_tasks:
            for project in project_refs(task):
                if str(project.get("id")) == project_id:
                    project_ref = project
                    break
            if project_ref:
                break
        epics = all_epics_by_project.get(project_id, [])
        compact_tasks = [compact_analysis_task(task, task_team_field, story_points_field) for task in dedupe_by_key(project_tasks)]
        teams: dict[str, int] = defaultdict(int)
        statuses: dict[str, int] = defaultdict(int)
        story_points = 0.0
        for task in compact_tasks:
            teams[str(task.get("team") or "NO_TEAM")] += 1
            statuses[str(task.get("status") or "unknown")] += 1
            value = task.get("storyPoints")
            if isinstance(value, (int, float)):
                story_points += float(value)
        projects.append({
            "project": compact_project(project_ref or {"id": project_id, "display": None}),
            "taskCount": len(compact_tasks),
            "storyPoints": story_points,
            "teams": dict(sorted(teams.items(), key=lambda item: (-item[1], item[0]))),
            "statuses": dict(sorted(statuses.items(), key=lambda item: (-item[1], item[0]))),
            "epicCount": len(epics),
            "epics": [compact_analysis_epic(epic, epic_team_field) for epic in epics],
            "tasks": compact_tasks,
        })
    projects.sort(key=lambda item: (item["epicCount"] != 0, -item["taskCount"], item["project"].get("display") or ""))

    team_counts: dict[str, int] = defaultdict(int)
    status_counts: dict[str, int] = defaultdict(int)
    assignee_counts: dict[str, int] = defaultdict(int)
    for task in enriched_tasks:
        team_counts[str(task.get("team") or "NO_TEAM")] += 1
        status_counts[str(task.get("status") or "unknown")] += 1
        assignee_counts[str(task.get("assignee") or "unassigned")] += 1

    summary = {
        "sprint": {"id": str(sprint_id)},
        "team": team,
        "taskCount": len(enriched_tasks),
        "tasksWithProject": sum(bool(task["projects"]) for task in enriched_tasks),
        "tasksWithoutProject": sum(not task["projects"] for task in enriched_tasks),
        "projectCount": len(projects),
        "projectsWithoutEpicFlow": sum(project["epicCount"] == 0 for project in projects),
        "projectsWithOneEpicFlow": sum(project["epicCount"] == 1 for project in projects),
        "projectsWithMultipleEpicFlow": sum(project["epicCount"] > 1 for project in projects),
        "tasksWithTeamEpic": sum(bool(task["teamEpics"]) for task in enriched_tasks),
        "tasksWithAnyEpicFlowEpic": sum(bool(task["anyEpicFlowEpics"]) for task in enriched_tasks),
        "tasksWithProjectButNoEpicFlow": sum(bool(task["projects"]) and not task["anyEpicFlowEpics"] for task in enriched_tasks),
        "tasksWithEpicFlowButNotTeam": sum(bool(task["anyEpicFlowEpics"]) and not task["teamEpics"] for task in enriched_tasks),
        "teamCounts": dict(sorted(team_counts.items(), key=lambda item: (-item[1], item[0]))),
        "statusCounts": dict(sorted(status_counts.items(), key=lambda item: (-item[1], item[0]))),
        "assigneeCounts": dict(sorted(assignee_counts.items(), key=lambda item: (-item[1], item[0]))),
        "fields": {
            "taskTeam": task_team_field,
            "epicTeam": epic_team_field,
            "storyPoints": story_points_field,
            "devQueue": dev_queue,
            "epicQueue": epic_queue,
        },
    }
    return {
        "summary": summary,
        "projects": projects,
        "tasks": enriched_tasks,
        "tasksWithoutProject": [task for task in enriched_tasks if not task["projects"]],
    }


NO_PROJECT_CLUSTER_RULES: list[dict[str, Any]] = [
    {
        "title": "Checkout and order lifecycle",
        "confidence": "strong",
        "patterns": ["чекаут", "checkout", "заказ", "orders/", "orders/show", "ваучер", "отмена"],
    },
    {
        "title": "Authorization and user data",
        "confidence": "strong",
        "patterns": ["авторизац", "звон", "passport", "паспорт", "турист", "email", "почт", "phone", "телефон"],
    },
    {
        "title": "Mobile payments",
        "confidence": "strong",
        "patterns": ["оплат", "карты", "япей", "yapay", "платеж"],
    },
    {
        "title": "Hotel reviews",
        "confidence": "strong",
        "patterns": ["отзыв"],
    },
    {
        "title": "Chat and CRM messages",
        "confidence": "strong",
        "patterns": ["чат", "сообщ", "telegram", "chat2desk", "typing"],
    },
    {
        "title": "Wishlist and WL flows",
        "confidence": "strong",
        "patterns": ["wishlist", "wish list", "вишлист", "избран", " wl", "white label"],
    },
    {
        "title": "Search filters and hotel results",
        "confidence": "strong",
        "patterns": ["поиск", "фильтр", "автокомплит", "матриц", "турфид", "похожие отели", "карточк"],
    },
    {
        "title": "Supplier integrations and actualization",
        "confidence": "strong",
        "patterns": ["актуализац", "поставщик", "оператор", "интурист", "алеан", "pegas", "корал", "санмар", "бронир", "трансфер", "доплат"],
    },
    {
        "title": "Dynamic admin and supplier tooling",
        "confidence": "strong",
        "patterns": ["админка динамики", "инструмент", "поставщиков", "альтернатив"],
    },
    {
        "title": "Payments, registries, and certificates",
        "confidence": "strong",
        "patterns": ["реестр", "сертификат", "купон", "платеж", "оплат", "переплат", "chargeback", "тариф"],
    },
    {
        "title": "CRM notifications and emails",
        "confidence": "medium",
        "patterns": ["уведом", "письм", "напоминан", "лидмейлер", "нотификац", "push", "пуш"],
    },
    {
        "title": "Mobile UI polish",
        "confidence": "medium",
        "patterns": ["android", "ios", "навбар", "баннер", "заглуш", "экран", "кнопк", "иконк", "лейбл"],
    },
    {
        "title": "App modularization and automated tests",
        "confidence": "medium",
        "patterns": ["модуль", "koin", "appium", "локатор", "snapshot", "скриншот", "тест"],
    },
    {
        "title": "Infrastructure monitoring and reliability",
        "confidence": "medium",
        "patterns": ["алерт", "монитор", "redis", "шардинг", "event-driven", "go до", "сервис"],
    },
    {
        "title": "Hotel content facts and editor",
        "confidence": "medium",
        "patterns": ["отель", "факт", "фото", "редактор", "контент", "блок"],
    },
]


def cluster_no_project_tasks(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    clusters: list[dict[str, Any]] = [
        {"title": rule["title"], "confidence": rule["confidence"], "tasks": []}
        for rule in NO_PROJECT_CLUSTER_RULES
    ]
    unclustered: list[dict[str, Any]] = []
    for task in tasks:
        text = f"{task.get('key') or ''} {task.get('summary') or ''} {task.get('team') or ''}".casefold()
        matched_index: int | None = None
        for index, rule in enumerate(NO_PROJECT_CLUSTER_RULES):
            if any(pattern.casefold() in text for pattern in rule["patterns"]):
                matched_index = index
                break
        if matched_index is None:
            unclustered.append(task)
        else:
            clusters[matched_index]["tasks"].append(task)
    clusters = [cluster for cluster in clusters if cluster["tasks"]]
    return {
        "summary": {
            "taskCount": len(tasks),
            "clustered": sum(len(cluster["tasks"]) for cluster in clusters),
            "unclustered": len(unclustered),
            "clusterCount": len(clusters),
        },
        "clusters": clusters,
        "unclustered": unclustered,
    }


def compact_activity_issue(issue: dict[str, Any], team_field: str, story_points_field: str) -> dict[str, Any]:
    item = compact_analysis_task(issue, team_field, story_points_field)
    item["updatedAt"] = issue.get("updatedAt")
    item["createdAt"] = issue.get("createdAt")
    item["queue"] = compact_ref(issue.get("queue"))
    item["type"] = compact_ref(issue.get("type"))
    item["priority"] = compact_ref(issue.get("priority"))
    return item


def summarize_activity_tasks(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    done_statuses = set(DEFAULT_DONE_STATUSES)
    active_statuses = set(DEFAULT_ACTIVE_STATUSES)
    done_tasks = [task for task in tasks if task.get("status") in done_statuses]
    active_tasks = [task for task in tasks if task.get("status") in active_statuses]
    team_counts: dict[str, int] = defaultdict(int)
    status_counts: dict[str, int] = defaultdict(int)
    assignee_counts: dict[str, int] = defaultdict(int)
    project_counts: dict[str, int] = defaultdict(int)
    for task in tasks:
        team_counts[str(task.get("team") or "NO_TEAM")] += 1
        status_counts[str(task.get("status") or "unknown")] += 1
        assignee_counts[str(task.get("assignee") or "unassigned")] += 1
        projects = task.get("projects") or []
        project = projects[0] if projects else {}
        project_counts[str((project or {}).get("display") or "NO_PROJECT")] += 1

    return {
        "updatedTasks": len(tasks),
        "updatedStoryPoints": round(sum(story_points(task.get("storyPoints")) for task in tasks), 1),
        "doneByCurrentStatusTasks": len(done_tasks),
        "doneByCurrentStatusStoryPoints": round(sum(story_points(task.get("storyPoints")) for task in done_tasks), 1),
        "activeTasks": len(active_tasks),
        "activeStoryPoints": round(sum(story_points(task.get("storyPoints")) for task in active_tasks), 1),
        "teamCounts": dict(sorted(team_counts.items(), key=lambda item: (-item[1], item[0]))),
        "statusCounts": dict(sorted(status_counts.items(), key=lambda item: (-item[1], item[0]))),
        "assigneeCounts": dict(sorted(assignee_counts.items(), key=lambda item: (-item[1], item[0]))),
        "projectCounts": dict(sorted(project_counts.items(), key=lambda item: (-item[1], item[0]))),
    }


def issue_done_events_in_window(
    cfg: dict[str, str],
    task: dict[str, Any],
    *,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    changes = request_json(cfg, "GET", f"/issues/{task['key']}/changelog")
    if not isinstance(changes, list):
        return []
    events: list[dict[str, Any]] = []
    for change in changes:
        updated_at = change.get("updatedAt")
        if not in_datetime_window(updated_at, start, end):
            continue
        for field_change in change.get("fields") or []:
            field = field_change.get("field") or {}
            if field.get("id") != "status":
                continue
            to_value = field_change.get("to") or {}
            to_display = to_value.get("display") if isinstance(to_value, dict) else str(to_value)
            if to_display in DEFAULT_DONE_STATUSES:
                events.append({
                    **task,
                    "doneAt": updated_at,
                    "doneTo": to_display,
                    "changedBy": compact_ref(change.get("updatedBy")),
                })
    return events


def summarize_done_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    latest_by_key: dict[str, dict[str, Any]] = {}
    for event in events:
        key = str(event.get("key") or "")
        if not key:
            continue
        if key not in latest_by_key or str(event.get("doneAt") or "") > str(latest_by_key[key].get("doneAt") or ""):
            latest_by_key[key] = event
    tasks = list(latest_by_key.values())
    team_counts: dict[str, int] = defaultdict(int)
    assignee_counts: dict[str, int] = defaultdict(int)
    for task in tasks:
        team_counts[str(task.get("team") or "NO_TEAM")] += 1
        assignee_counts[str(task.get("assignee") or "unassigned")] += 1
    return {
        "doneTasks": len(tasks),
        "doneStoryPoints": round(sum(story_points(task.get("storyPoints")) for task in tasks), 1),
        "teamCounts": dict(sorted(team_counts.items(), key=lambda item: (-item[1], item[0]))),
        "assigneeCounts": dict(sorted(assignee_counts.items(), key=lambda item: (-item[1], item[0]))),
        "tasks": tasks,
    }


def analyze_activity(
    cfg: dict[str, str],
    *,
    since: str,
    until: str,
    with_changelog: bool,
) -> dict[str, Any]:
    fields = issue_field_list(
        "key", "summary", "status", "assignee", "updatedAt", "createdAt", "project", "queue",
        "type", "priority", cfg["task_team_field"], cfg["story_points_field"],
    )
    raw_tasks = search_all(cfg, {"query": f"Queue: {cfg['dev_queue']} AND Updated: >= {since}"}, fields)
    tasks = [compact_activity_issue(task, cfg["task_team_field"], cfg["story_points_field"]) for task in raw_tasks]
    start = date_start_utc(since)
    end = date_end_utc(until)
    tasks = [task for task in tasks if in_datetime_window(task.get("updatedAt"), start, end)]
    summary = summarize_activity_tasks(tasks)
    result: dict[str, Any] = {
        "period": {"from": since, "to": until},
        "summary": summary,
        "tasks": tasks,
    }
    if with_changelog:
        events: list[dict[str, Any]] = []
        for task in tasks:
            events.extend(issue_done_events_in_window(cfg, task, start=start, end=end))
        result["doneTransitions"] = summarize_done_events(events)
    return result


def issue_has_terminal_status(issue: dict[str, Any]) -> bool:
    return str(issue.get("status") or "") in DEFAULT_TERMINAL_STATUSES


def analyze_scrum_epicflow_alignment(
    cfg: dict[str, str],
    *,
    sprint_id: str,
    epicflow_board_id: str,
) -> dict[str, Any]:
    task_fields = issue_field_list(
        "key", "summary", "status", "assignee", "sprint", "project", "queue", "updatedAt",
        cfg["story_points_field"], cfg["task_team_field"],
    )
    raw_tasks = search_all(
        cfg,
        {"filter": {"queue": cfg["dev_queue"], "sprint": int(sprint_id) if str(sprint_id).isdigit() else sprint_id}},
        task_fields,
    )
    tasks = [compact_activity_issue(task, cfg["task_team_field"], cfg["story_points_field"]) for task in raw_tasks]

    epic_fields = issue_field_list("key", "summary", "status", "assignee", "project", "queue", "updatedAt", cfg["epic_team_field"])
    raw_epics = search_all(cfg, {"query": f"Boards: {epicflow_board_id}"}, epic_fields)
    epics = [
        compact_analysis_epic(epic, cfg["epic_team_field"])
        for epic in raw_epics
        if (epic.get("queue") or {}).get("key") == cfg["epic_queue"]
    ]
    active_epics = [epic for epic in epics if not issue_has_terminal_status(epic)]

    epic_by_project: dict[str, list[dict[str, Any]]] = defaultdict(list)
    epic_no_project: list[dict[str, Any]] = []
    for epic in active_epics:
        if not epic.get("projects"):
            epic_no_project.append(epic)
        for project in epic.get("projects") or []:
            if project.get("id") is not None:
                epic_by_project[str(project["id"])].append(epic)

    task_by_project: dict[str, list[dict[str, Any]]] = defaultdict(list)
    task_no_project: list[dict[str, Any]] = []
    tasks_with_epic: list[dict[str, Any]] = []
    tasks_with_project_no_epic: list[dict[str, Any]] = []
    team_mismatches: list[dict[str, Any]] = []
    for task in tasks:
        projects = task.get("projects") or []
        if not projects:
            task_no_project.append(task)
            continue
        task_epics: list[dict[str, Any]] = []
        for project in projects:
            project_id = project.get("id")
            if project_id is None:
                continue
            task_by_project[str(project_id)].append(task)
            task_epics.extend(epic_by_project.get(str(project_id), []))
        task_epics = dedupe_by_key(task_epics)
        if task_epics:
            item = {**task, "epics": task_epics}
            tasks_with_epic.append(item)
            team = task.get("team")
            if team and not any(team in (epic.get("teams") or []) for epic in task_epics):
                team_mismatches.append(item)
        else:
            tasks_with_project_no_epic.append(task)

    scrum_project_ids = set(task_by_project)
    epic_project_ids = set(epic_by_project)
    projects_without_epic = [
        {
            "project": task_by_project[project_id][0]["projects"][0],
            "tasks": dedupe_by_key(task_by_project[project_id]),
        }
        for project_id in sorted(scrum_project_ids - epic_project_ids, key=lambda value: (-len(task_by_project[value]), value))
    ]
    multi_epic_projects = [
        {
            "project": task_by_project[project_id][0]["projects"][0],
            "tasks": dedupe_by_key(task_by_project[project_id]),
            "epics": dedupe_by_key(epic_by_project.get(project_id, [])),
        }
        for project_id in sorted(scrum_project_ids)
        if len(dedupe_by_key(epic_by_project.get(project_id, []))) > 1
    ]
    epic_dev_stage_projects_without_scrum = [
        {
            "project": epic_by_project[project_id][0]["projects"][0],
            "epics": dedupe_by_key(epic_by_project[project_id]),
        }
        for project_id in sorted(epic_project_ids - scrum_project_ids, key=lambda value: (-len(epic_by_project[value]), value))
        if any(epic.get("status") in DEFAULT_DEV_STAGE_EPICFLOW_STATUSES for epic in epic_by_project[project_id])
    ]
    return {
        "summary": {
            "sprint": {"id": str(sprint_id)},
            "scrumTasks": len(tasks),
            "scrumTasksWithoutProject": len(task_no_project),
            "scrumTasksWithProject": len(tasks) - len(task_no_project),
            "scrumTasksWithEpicFlow": len(tasks_with_epic),
            "scrumTasksWithProjectButNoEpicFlow": len(tasks_with_project_no_epic),
            "scrumTasksWithEpicFlowButNotTeam": len(team_mismatches),
            "scrumProjects": len(scrum_project_ids),
            "scrumProjectsWithoutEpicFlow": len(projects_without_epic),
            "scrumProjectsWithMultipleEpicFlow": len(multi_epic_projects),
            "activeEpicFlowIssues": len(active_epics),
            "activeEpicFlowWithoutProject": len(epic_no_project),
            "activeEpicFlowProjects": len(epic_project_ids),
            "epicFlowDevStageProjectsWithoutScrum": len(epic_dev_stage_projects_without_scrum),
        },
        "tasksWithoutProject": task_no_project,
        "tasksWithProjectButNoEpicFlow": tasks_with_project_no_epic,
        "tasksWithEpicFlowButNotTeam": team_mismatches,
        "projectsWithoutEpicFlow": projects_without_epic,
        "projectsWithMultipleEpicFlow": multi_epic_projects,
        "epicFlowDevStageProjectsWithoutScrum": epic_dev_stage_projects_without_scrum,
    }


def cmd_setup(args: argparse.Namespace) -> None:
    path = Path(args.config).expanduser()
    values = read_env_file(path)
    if args.default_user_name is not None:
        values["YANDEX_TRACKER_DEFAULT_USER_NAME"] = args.default_user_name
    if args.default_user_email is not None:
        values["YANDEX_TRACKER_DEFAULT_USER_EMAIL"] = args.default_user_email
    if args.default_boards is not None:
        values["YANDEX_TRACKER_DEFAULT_BOARDS"] = args.default_boards

    values = {
        **values,
        "YANDEX_TRACKER_ORG_ID": args.org_id,
        "YANDEX_TRACKER_TOKEN": args.token,
        "YANDEX_TRACKER_AUTH_TYPE": args.auth_type,
        "YANDEX_TRACKER_ORG_HEADER": args.org_header,
        "YANDEX_TRACKER_API_BASE": args.api_base,
    }
    write_env_file(path, values)
    print(f"Wrote Tracker credentials to {path}")


def cmd_config(args: argparse.Namespace) -> None:
    cfg = load_config(args)
    print_json({
        "apiBase": cfg["api_base"],
        "authType": cfg["auth_type"],
        "orgHeader": cfg["org_header"],
        "orgId": cfg["org_id"],
        "tokenPresent": bool(cfg["token"]),
        "defaultUser": {
            "name": cfg["default_user_name"] or None,
            "email": cfg["default_user_email"] or None,
        },
        "defaultBoards": parse_board_list(cfg["default_boards"]),
        "levelTravel": {
            "scrumBoardId": cfg["scrum_board_id"],
            "epicflowBoardId": cfg["epicflow_board_id"],
            "devEpicsBoardId": cfg["dev_epics_board_id"],
            "devQueue": cfg["dev_queue"],
            "epicQueue": cfg["epic_queue"],
            "taskTeamField": cfg["task_team_field"],
            "epicTeamField": cfg["epic_team_field"],
            "storyPointsField": cfg["story_points_field"],
        },
    })


def cmd_issue(args: argparse.Namespace) -> None:
    cfg = load_config(args)
    issue = request_json(
        cfg,
        "GET",
        f"/issues/{args.issue}",
        query={"fields": args.fields, "expand": args.expand},
    )
    print_json(issue if args.raw else compact_issue(issue))


def cmd_search(args: argparse.Namespace) -> None:
    cfg = load_config(args)
    selectors = [
        ("queue", args.queue),
        ("keys", args.keys),
        ("filter", args.filter_json),
        ("filterId", args.filter_id),
        ("query", args.query_text),
    ]
    used = [name for name, value in selectors if value]
    if len(used) != 1:
        raise TrackerError("Specify exactly one of --queue, --keys, --filter-json, --filter-id, --query.")

    body: dict[str, Any] = {}
    if args.queue:
        body["queue"] = args.queue
    elif args.keys:
        body["keys"] = args.keys.split(",") if "," in args.keys else args.keys
    elif args.filter_json:
        body["filter"] = parse_json_arg(args.filter_json, "--filter-json")
    elif args.filter_id:
        body["filterId"] = int(args.filter_id)
    else:
        body["query"] = args.query_text

    if args.order:
        body["order"] = args.order

    query = {"fields": args.fields, "expand": args.expand, "perPage": args.per_page}
    if args.queue:
        if args.page_id:
            query["id"] = args.page_id
    else:
        query["page"] = args.page

    issues = request_json(cfg, "POST", "/issues/_search", query=query, body=body)
    print_json(issues if args.raw else [compact_issue(issue) for issue in issues])


def build_create_issue_body(args: argparse.Namespace) -> dict[str, Any]:
    body: dict[str, Any] = {
        "queue": args.queue,
        "summary": args.summary,
    }
    description = read_optional_text_arg(args.description, args.description_file, "description")
    if description is not None:
        body["description"] = description
    for key, value in {
        "markupType": args.markup_type,
        "parent": ref_arg(args.parent),
        "type": ref_arg(args.type),
        "priority": ref_arg(args.priority),
        "assignee": args.assignee,
        "unique": args.unique,
    }.items():
        if value:
            body[key] = value
    for key, value in {
        "followers": parse_id_csv_arg(args.followers),
        "attachmentIds": parse_id_csv_arg(args.attachment_ids),
        "tags": parse_csv_arg(args.tags),
        "sprint": parse_ref_csv_arg(args.sprint_ids),
    }.items():
        if value:
            body[key] = value
    if args.links_json:
        links = parse_json_arg(args.links_json, "--links-json")
        if not isinstance(links, list):
            raise TrackerError("--links-json must be a JSON array.")
        body["links"] = links
    return merge_field_json(body, args.field_json, "--field-json")


def cmd_create(args: argparse.Namespace) -> None:
    cfg = load_config(args)
    result = request_json(
        cfg,
        "POST",
        "/issues/",
        query={"notify": str(args.notify).lower() if args.notify is not None else None},
        body=build_create_issue_body(args),
    )
    print_json(result if args.raw else compact_issue_response(result))


def build_update_issue_body(args: argparse.Namespace) -> dict[str, Any]:
    body: dict[str, Any] = {}
    description = read_optional_text_arg(args.description, args.description_file, "description")
    for key, value in {
        "summary": args.summary,
        "description": description,
        "markupType": args.markup_type,
        "parent": ref_arg(args.parent),
        "type": ref_arg(args.type),
        "priority": ref_arg(args.priority),
        "assignee": args.assignee,
    }.items():
        if value is not None:
            body[key] = value
    tag_patch: dict[str, list[str]] = {}
    if args.add_tags:
        tag_patch["add"] = parse_csv_arg(args.add_tags) or []
    if args.remove_tags:
        tag_patch["remove"] = parse_csv_arg(args.remove_tags) or []
    if tag_patch:
        body["tags"] = tag_patch
    followers_patch: dict[str, list[str | int]] = {}
    if args.add_followers:
        followers_patch["add"] = parse_id_csv_arg(args.add_followers) or []
    if args.remove_followers:
        followers_patch["remove"] = parse_id_csv_arg(args.remove_followers) or []
    if followers_patch:
        body["followers"] = followers_patch
    sprint = parse_ref_csv_arg(args.sprint_ids)
    if sprint:
        body["sprint"] = sprint
    body = merge_field_json(body, args.field_json, "--field-json")
    if not body:
        raise TrackerError("No fields to update. Pass explicit fields or --field-json.")
    return body


def cmd_update(args: argparse.Namespace) -> None:
    cfg = load_config(args)
    result = request_json(
        cfg,
        "PATCH",
        f"/issues/{args.issue}",
        query={"version": args.version},
        body=build_update_issue_body(args),
    )
    print_json(result if args.raw else compact_issue_response(result))


def cmd_transitions(args: argparse.Namespace) -> None:
    cfg = load_config(args)
    transitions = request_json(cfg, "GET", f"/issues/{args.issue}/transitions")
    print_json(transitions if args.raw else [compact_transition(item) for item in transitions])


def transition_matches(transition: dict[str, Any], target: str) -> bool:
    normalized_target = target.casefold()
    to_status = transition.get("to") or {}
    values = [
        transition.get("id"),
        transition.get("display"),
        to_status.get("key"),
        to_status.get("display"),
    ]
    return any(str(value).casefold() == normalized_target for value in values if value)


def find_transition_by_target(transitions: list[dict[str, Any]], target: str) -> dict[str, Any]:
    matches = [transition for transition in transitions if transition_matches(transition, target)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        available = [compact_transition(transition) for transition in transitions]
        raise TrackerError(f"No transition matches {target!r}. Available transitions: {json.dumps(available, ensure_ascii=False)}")
    available_matches = [compact_transition(transition) for transition in matches]
    raise TrackerError(f"Transition target {target!r} is ambiguous: {json.dumps(available_matches, ensure_ascii=False)}")


def build_transition_body(args: argparse.Namespace) -> dict[str, Any]:
    body = parse_json_object_arg(args.field_json, "--field-json") if args.field_json else {}
    if args.comment:
        body["comment"] = args.comment
    return body


def execute_transition(args: argparse.Namespace, transition_id: str) -> None:
    cfg = load_config(args)
    result = request_json(
        cfg,
        "POST",
        f"/issues/{args.issue}/transitions/{transition_id}/_execute",
        body=build_transition_body(args),
    )
    print_json(result if args.raw else [compact_transition(item) for item in result])


def cmd_transition(args: argparse.Namespace) -> None:
    execute_transition(args, args.transition_id)


def cmd_move(args: argparse.Namespace) -> None:
    cfg = load_config(args)
    transitions = request_json(cfg, "GET", f"/issues/{args.issue}/transitions")
    transition = find_transition_by_target(transitions, args.target)
    result = request_json(
        cfg,
        "POST",
        f"/issues/{args.issue}/transitions/{transition['id']}/_execute",
        body=build_transition_body(args),
    )
    output = {
        "executedTransition": compact_transition(transition),
        "availableTransitionsAfterMove": result if args.raw else [compact_transition(item) for item in result],
    }
    print_json(output)


def cmd_comment(args: argparse.Namespace) -> None:
    cfg = load_config(args)
    body: dict[str, Any] = {"text": read_text_arg(args.text, args.text_file, "comment text")}
    if args.markup_type:
        body["markupType"] = args.markup_type
    attachment_ids = parse_id_csv_arg(args.attachment_ids)
    if attachment_ids:
        body["attachmentIds"] = attachment_ids
    summonees = parse_csv_arg(args.summonees)
    if summonees:
        body["summonees"] = summonees
    maillist_summonees = parse_csv_arg(args.maillist_summonees)
    if maillist_summonees:
        body["maillistSummonees"] = maillist_summonees
    result = request_json(
        cfg,
        "POST",
        f"/issues/{args.issue}/comments",
        query={"isAddToFollowers": "false" if args.no_follow else None},
        body=body,
    )
    print_json(result if args.raw else compact_comment(result))


def cmd_boards(args: argparse.Namespace) -> None:
    cfg = load_config(args)
    boards = request_json(cfg, "GET", "/boards")
    if args.raw:
        print_json(boards)
        return
    print_json([
        {
            "id": board.get("id"),
            "name": board.get("name"),
            "defaultQueue": compact_user(board.get("defaultQueue")) or None,
            "query": board.get("query"),
            "filter": board.get("filter"),
        }
        for board in boards
    ])


def cmd_board(args: argparse.Namespace) -> None:
    cfg = load_config(args)
    board = request_json(cfg, "GET", f"/boards/{args.board_id}")
    print_json(board)


def cmd_columns(args: argparse.Namespace) -> None:
    cfg = load_config(args)
    columns = request_json(cfg, "GET", f"/boards/{args.board_id}/columns")
    print_json(columns)


def board_search_body(board: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    if args.query_text:
        return {"query": args.query_text}
    if args.filter_json:
        return {"filter": parse_json_arg(args.filter_json, "--filter-json")}
    if board.get("query"):
        return {"query": board["query"]}
    if board.get("filter"):
        body = {"filter": board["filter"]}
        order_by = board.get("orderBy")
        if order_by:
            body["order"] = ("+" if board.get("orderAsc") else "-") + order_by
        return body
    default_queue = board.get("defaultQueue") or {}
    if default_queue.get("key"):
        return {"queue": default_queue["key"]}
    board_id = board.get("id")
    if board_id:
        return {"query": f'"Sprints By Board": {board_id}'}
    raise TrackerError("Board has no query/filter/defaultQueue/id; pass --query or --filter-json.")


def cmd_board_status(args: argparse.Namespace) -> None:
    cfg = load_config(args)
    board = request_json(cfg, "GET", f"/boards/{args.board_id}")
    columns = request_json(cfg, "GET", f"/boards/{args.board_id}/columns")
    issues = request_json(
        cfg,
        "POST",
        "/issues/_search",
        query={"fields": args.fields, "perPage": args.limit, "page": 1},
        body=board_search_body(board, args),
    )

    status_to_column: dict[str, str] = {}
    column_order: list[str] = []
    for column in columns:
        column_name = column.get("name") or column.get("display") or str(column.get("id"))
        column_order.append(column_name)
        for status in column.get("statuses") or []:
            if isinstance(status, dict) and status.get("key"):
                status_to_column[status["key"]] = column_name

    groups: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "statuses": defaultdict(int), "samples": []})
    for issue in issues:
        item = compact_issue(issue)
        status_key = item.get("statusKey") or "unknown"
        column = status_to_column.get(status_key, "Unmapped")
        group = groups[column]
        group["count"] += 1
        group["statuses"][item.get("status") or status_key] += 1
        if len(group["samples"]) < args.samples:
            group["samples"].append({"key": item.get("key"), "summary": item.get("summary"), "status": item.get("status")})

    ordered_groups: dict[str, Any] = {}
    for name in column_order + ["Unmapped"]:
        if name in groups:
            ordered_groups[name] = {
                "count": groups[name]["count"],
                "statuses": dict(groups[name]["statuses"]),
                "samples": groups[name]["samples"],
            }

    print_json({
        "board": {"id": board.get("id"), "name": board.get("name"), "query": board.get("query"), "filter": board.get("filter")},
        "loadedIssues": len(issues),
        "limit": args.limit,
        "columns": ordered_groups,
    })


def cmd_default_board_status(args: argparse.Namespace) -> None:
    cfg = load_config(args)
    boards = parse_board_list(cfg["default_boards"])
    if args.board:
        boards = parse_board_list(",".join(args.board))
    if not boards:
        raise TrackerError("No default boards configured. Set YANDEX_TRACKER_DEFAULT_BOARDS or pass --board id:name.")

    result: list[dict[str, Any]] = []
    for configured_board in boards:
        board = request_json(cfg, "GET", f"/boards/{configured_board['id']}")
        columns = request_json(cfg, "GET", f"/boards/{configured_board['id']}/columns")
        issues = request_json(
            cfg,
            "POST",
            "/issues/_search",
            query={"fields": args.fields, "perPage": args.limit, "page": 1},
            body=board_search_body(board, args),
        )
        status_to_column: dict[str, str] = {}
        column_order: list[str] = []
        for column in columns:
            column_name = column.get("name") or column.get("display") or str(column.get("id"))
            column_order.append(column_name)
            for status in column.get("statuses") or []:
                if isinstance(status, dict) and status.get("key"):
                    status_to_column[status["key"]] = column_name

        groups: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "statuses": defaultdict(int), "tasks": []})
        for issue in issues:
            item = compact_issue(issue)
            status_key = item.get("statusKey") or "unknown"
            column = status_to_column.get(status_key, "Unmapped")
            group = groups[column]
            group["count"] += 1
            group["statuses"][item.get("status") or status_key] += 1
            if len(group["tasks"]) < args.samples:
                group["tasks"].append({"key": item.get("key"), "summary": item.get("summary"), "status": item.get("status")})

        ordered_groups: dict[str, Any] = {}
        for name in column_order + ["Unmapped"]:
            if name in groups:
                ordered_groups[name] = {
                    "count": groups[name]["count"],
                    "statuses": dict(groups[name]["statuses"]),
                    "tasks": groups[name]["tasks"],
                }
        result.append({
            "board": {
                "id": board.get("id"),
                "name": board.get("name") or configured_board.get("name"),
                "configuredAs": board_ref(configured_board),
            },
            "defaultUser": {
                "name": cfg["default_user_name"] or None,
                "email": cfg["default_user_email"] or None,
            },
            "loadedIssues": len(issues),
            "limit": args.limit,
            "columns": ordered_groups,
        })

    print_json(result)


def cmd_current_sprint(args: argparse.Namespace) -> None:
    cfg = load_config(args)
    board_id = args.board or cfg["scrum_board_id"]
    sprint = get_current_sprint(cfg, board_id)
    if args.raw:
        print_json(sprint)
        return
    print_json({
        "id": sprint.get("id"),
        "name": sprint.get("name"),
        "board": compact_ref(sprint.get("board")),
        "status": sprint.get("status"),
        "archived": sprint.get("archived"),
        "startDate": sprint.get("startDate"),
        "endDate": sprint.get("endDate"),
    })


def cmd_epicflow_coverage(args: argparse.Namespace) -> None:
    cfg = load_config(args)
    board_id = args.board or cfg["scrum_board_id"]
    sprint_id = resolve_sprint_id(cfg, args.sprint, board_id)
    analysis = analyze_epicflow_coverage(cfg, sprint_id=sprint_id, team=args.team)
    if args.details:
        print_json(analysis)
        return
    summary = analysis["summary"]
    projects = analysis["projects"]
    summary["projectsWithoutEpicFlowList"] = [
        project["project"] for project in projects if project["epicCount"] == 0
    ][:args.samples]
    summary["projectsWithMultipleEpicFlowList"] = [
        {
            "project": project["project"],
            "epics": project["epics"],
        }
        for project in projects if project["epicCount"] > 1
    ][:args.samples]
    summary["tasksWithoutProjectSamples"] = analysis["tasksWithoutProject"][:args.samples]
    print_json(summary)


def cmd_no_project_clusters(args: argparse.Namespace) -> None:
    cfg = load_config(args)
    board_id = args.board or cfg["scrum_board_id"]
    sprint_id = resolve_sprint_id(cfg, args.sprint, board_id)
    analysis = analyze_epicflow_coverage(cfg, sprint_id=sprint_id, team=args.team)
    clusters = cluster_no_project_tasks(analysis["tasksWithoutProject"])
    if args.details:
        print_json(clusters)
        return
    compact_clusters = []
    for cluster in clusters["clusters"]:
        compact_clusters.append({
            "title": cluster["title"],
            "confidence": cluster["confidence"],
            "taskCount": len(cluster["tasks"]),
            "samples": cluster["tasks"][:args.samples],
        })
    print_json({
        "summary": clusters["summary"],
        "clusters": compact_clusters,
        "unclusteredSamples": clusters["unclustered"][:args.samples],
    })


def cmd_activity_summary(args: argparse.Namespace) -> None:
    cfg = load_config(args)
    since = args.since or (date.today() - timedelta(days=args.days)).isoformat()
    until = args.until or date.today().isoformat()
    analysis = analyze_activity(cfg, since=since, until=until, with_changelog=args.with_changelog)
    if args.details:
        print_json(analysis)
        return
    summary = analysis["summary"]
    if "doneTransitions" in analysis:
        summary["doneTransitions"] = {
            key: value for key, value in analysis["doneTransitions"].items()
            if key != "tasks"
        }
        summary["doneTransitionSamples"] = analysis["doneTransitions"]["tasks"][:args.samples]
    summary["taskSamples"] = analysis["tasks"][:args.samples]
    print_json({
        "period": analysis["period"],
        "summary": summary,
    })


def cmd_scrum_epicflow_alignment(args: argparse.Namespace) -> None:
    cfg = load_config(args)
    board_id = args.board or cfg["scrum_board_id"]
    sprint_id = resolve_sprint_id(cfg, args.sprint, board_id)
    epicflow_board_id = args.epicflow_board or cfg["epicflow_board_id"]
    analysis = analyze_scrum_epicflow_alignment(cfg, sprint_id=sprint_id, epicflow_board_id=epicflow_board_id)
    if args.details:
        print_json(analysis)
        return
    summary = analysis["summary"]
    summary["projectsWithoutEpicFlowSamples"] = [
        {"project": item["project"], "taskCount": len(item["tasks"])}
        for item in analysis["projectsWithoutEpicFlow"][:args.samples]
    ]
    summary["tasksWithoutProjectSamples"] = analysis["tasksWithoutProject"][:args.samples]
    summary["teamMismatchSamples"] = analysis["tasksWithEpicFlowButNotTeam"][:args.samples]
    summary["epicFlowDevStageProjectsWithoutScrumSamples"] = [
        {"project": item["project"], "epicCount": len(item["epics"])}
        for item in analysis["epicFlowDevStageProjectsWithoutScrum"][:args.samples]
    ]
    print_json(summary)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Yandex Tracker API helper")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Credential env file")
    sub = parser.add_subparsers(dest="command", required=True)

    setup = sub.add_parser("setup", help="Store Tracker credentials")
    setup.add_argument("--token", required=True)
    setup.add_argument("--org-id", required=True)
    setup.add_argument("--org-header", choices=["X-Org-ID", "X-Cloud-Org-ID"], default="X-Org-ID")
    setup.add_argument("--auth-type", choices=["OAuth", "Bearer"], default="OAuth")
    setup.add_argument("--api-base", default=DEFAULT_BASE_URL)
    setup.add_argument("--default-user-name")
    setup.add_argument("--default-user-email")
    setup.add_argument("--default-boards", help="Comma-separated id:name board list, for example 2:Scrum,214:EpicFlow")
    setup.set_defaults(func=cmd_setup)

    config = sub.add_parser("config", help="Show non-secret effective configuration")
    config.set_defaults(func=cmd_config)

    issue = sub.add_parser("issue", help="Read one issue")
    issue.add_argument("issue")
    issue.add_argument("--fields", default="")
    issue.add_argument("--expand", default="")
    issue.add_argument("--raw", action="store_true")
    issue.set_defaults(func=cmd_issue)

    search = sub.add_parser("search", help="Search issues")
    search.add_argument("--queue")
    search.add_argument("--keys")
    search.add_argument("--filter-json")
    search.add_argument("--filter-id")
    search.add_argument("--query", dest="query_text")
    search.add_argument("--order")
    search.add_argument("--fields", default=DEFAULT_FIELDS)
    search.add_argument("--expand", default="")
    search.add_argument("--per-page", type=int, default=50)
    search.add_argument("--page", type=int, default=1)
    search.add_argument("--id", dest="page_id", help="Relative pagination page id for --queue searches")
    search.add_argument("--raw", action="store_true")
    search.set_defaults(func=cmd_search)

    create = sub.add_parser("create", help="Create an issue")
    create.add_argument("--queue", required=True, help="Queue key or ID")
    create.add_argument("--summary", required=True)
    create.add_argument("--description")
    create.add_argument("--description-file", help="Read description from file, or '-' for stdin")
    create.add_argument("--markup-type", choices=["md"], help="Description markup type")
    create.add_argument("--parent", help="Parent issue key or ID")
    create.add_argument("--type", help="Issue type key or ID")
    create.add_argument("--priority", help="Priority key or ID")
    create.add_argument("--assignee", help="Assignee user ID or login")
    create.add_argument("--followers", help="Comma-separated follower IDs or logins")
    create.add_argument("--tags", help="Comma-separated tags")
    create.add_argument("--sprint-ids", help="Comma-separated sprint IDs or keys")
    create.add_argument("--attachment-ids", help="Comma-separated temporary attachment IDs")
    create.add_argument("--links-json", help="JSON array of issue links")
    create.add_argument("--unique", help="Unique idempotency value")
    create.add_argument("--notify", choices=["true", "false"], help="Override creation notification flag")
    create.add_argument("--field-json", help="JSON object with additional issue fields")
    create.add_argument("--raw", action="store_true")
    create.set_defaults(func=cmd_create)

    update = sub.add_parser("update", help="Patch issue fields")
    update.add_argument("issue")
    update.add_argument("--summary")
    update.add_argument("--description")
    update.add_argument("--description-file", help="Read description from file, or '-' for stdin")
    update.add_argument("--markup-type", choices=["md"], help="Description markup type")
    update.add_argument("--parent", help="Parent issue key or ID")
    update.add_argument("--type", help="Issue type key or ID")
    update.add_argument("--priority", help="Priority key or ID")
    update.add_argument("--assignee", help="Assignee user ID or login")
    update.add_argument("--sprint-ids", help="Comma-separated sprint IDs or keys")
    update.add_argument("--add-tags", help="Comma-separated tags to add")
    update.add_argument("--remove-tags", help="Comma-separated tags to remove")
    update.add_argument("--add-followers", help="Comma-separated follower IDs or logins to add")
    update.add_argument("--remove-followers", help="Comma-separated follower IDs or logins to remove")
    update.add_argument("--field-json", help="JSON object with additional issue fields")
    update.add_argument("--version", type=int, help="Expected issue version")
    update.add_argument("--raw", action="store_true")
    update.set_defaults(func=cmd_update)

    transitions = sub.add_parser("transitions", help="List available issue status transitions")
    transitions.add_argument("issue")
    transitions.add_argument("--raw", action="store_true")
    transitions.set_defaults(func=cmd_transitions)

    transition = sub.add_parser("transition", help="Execute an issue status transition by transition id")
    transition.add_argument("issue")
    transition.add_argument("transition_id")
    transition.add_argument("--comment", help="Comment to attach to the transition")
    transition.add_argument("--field-json", help="JSON object with additional transition fields")
    transition.add_argument("--raw", action="store_true")
    transition.set_defaults(func=cmd_transition)

    move = sub.add_parser("move", help="Move an issue by target status or transition display/id")
    move.add_argument("issue")
    move.add_argument("target", help="Transition id/display or target status key/display")
    move.add_argument("--comment", help="Comment to attach to the transition")
    move.add_argument("--field-json", help="JSON object with additional transition fields")
    move.add_argument("--raw", action="store_true")
    move.set_defaults(func=cmd_move)

    comment = sub.add_parser("comment", help="Add a comment to an issue")
    comment.add_argument("issue")
    comment.add_argument("--text")
    comment.add_argument("--text-file", help="Read comment text from file, or '-' for stdin")
    comment.add_argument("--markup-type", choices=["md"], help="Comment markup type")
    comment.add_argument("--attachment-ids", help="Comma-separated temporary attachment IDs")
    comment.add_argument("--summonees", help="Comma-separated user IDs or logins to mention")
    comment.add_argument("--maillist-summonees", help="Comma-separated mailing lists to mention")
    comment.add_argument("--no-follow", action="store_true", help="Do not add comment author to issue followers")
    comment.add_argument("--raw", action="store_true")
    comment.set_defaults(func=cmd_comment)

    boards = sub.add_parser("boards", help="List boards")
    boards.add_argument("--raw", action="store_true")
    boards.set_defaults(func=cmd_boards)

    board = sub.add_parser("board", help="Read board")
    board.add_argument("board_id")
    board.set_defaults(func=cmd_board)

    columns = sub.add_parser("columns", help="Read board columns")
    columns.add_argument("board_id")
    columns.set_defaults(func=cmd_columns)

    board_status = sub.add_parser("board-status", help="Summarize issues on a board")
    board_status.add_argument("board_id")
    board_status.add_argument("--query", dest="query_text")
    board_status.add_argument("--filter-json")
    board_status.add_argument("--fields", default=DEFAULT_FIELDS)
    board_status.add_argument("--limit", type=int, default=200)
    board_status.add_argument("--samples", type=int, default=5)
    board_status.set_defaults(func=cmd_board_status)

    default_board_status = sub.add_parser("default-board-status", help="Summarize configured default boards")
    default_board_status.add_argument("--board", action="append", help="Override default board as id:name; can be repeated")
    default_board_status.add_argument("--query", dest="query_text")
    default_board_status.add_argument("--filter-json")
    default_board_status.add_argument("--fields", default=DEFAULT_FIELDS)
    default_board_status.add_argument("--limit", type=int, default=200)
    default_board_status.add_argument("--samples", type=int, default=5)
    default_board_status.set_defaults(func=cmd_default_board_status)

    current_sprint = sub.add_parser("current-sprint", help="Show the current sprint for a board")
    current_sprint.add_argument("--board", help="Board ID; defaults to configured Scrum board")
    current_sprint.add_argument("--raw", action="store_true")
    current_sprint.set_defaults(func=cmd_current_sprint)

    epicflow_coverage = sub.add_parser(
        "epicflow-coverage",
        help="Analyze Scrum sprint tasks against EpicFlow project linkage",
    )
    epicflow_coverage.add_argument("--sprint", default="current", help="Sprint ID or `current`")
    epicflow_coverage.add_argument("--board", help="Board ID used to resolve `current`; defaults to Scrum")
    epicflow_coverage.add_argument("--team", help="Optional task team value, for example WebFront or NO_TEAM")
    epicflow_coverage.add_argument("--details", action="store_true", help="Print projects and tasks, not only summary")
    epicflow_coverage.add_argument("--samples", type=int, default=10, help="Sample size in compact output")
    epicflow_coverage.set_defaults(func=cmd_epicflow_coverage)

    no_project_clusters = sub.add_parser(
        "no-project-clusters",
        help="Cluster Scrum sprint tasks that have no development project",
    )
    no_project_clusters.add_argument("--sprint", default="current", help="Sprint ID or `current`")
    no_project_clusters.add_argument("--board", help="Board ID used to resolve `current`; defaults to Scrum")
    no_project_clusters.add_argument("--team", help="Optional task team value, for example WebFront or NO_TEAM")
    no_project_clusters.add_argument("--details", action="store_true", help="Print full task lists for each cluster")
    no_project_clusters.add_argument("--samples", type=int, default=10, help="Sample size in compact output")
    no_project_clusters.set_defaults(func=cmd_no_project_clusters)

    activity_summary = sub.add_parser(
        "activity-summary",
        help="Summarize LT activity and productivity for a date window",
    )
    activity_summary.add_argument("--since", help="Start date YYYY-MM-DD; defaults to today minus --days")
    activity_summary.add_argument("--until", help="End date YYYY-MM-DD; defaults to today")
    activity_summary.add_argument("--days", type=int, default=14, help="Lookback days when --since is omitted")
    activity_summary.add_argument(
        "--with-changelog",
        action="store_true",
        help="Fetch per-issue changelog to count exact transitions into done statuses",
    )
    activity_summary.add_argument("--details", action="store_true", help="Print full task and transition lists")
    activity_summary.add_argument("--samples", type=int, default=10, help="Sample size in compact output")
    activity_summary.set_defaults(func=cmd_activity_summary)

    scrum_epicflow_alignment = sub.add_parser(
        "scrum-epicflow-alignment",
        help="Compare the Scrum sprint with active EpicFlow project linkage",
    )
    scrum_epicflow_alignment.add_argument("--sprint", default="current", help="Sprint ID or `current`")
    scrum_epicflow_alignment.add_argument("--board", help="Board ID used to resolve `current`; defaults to Scrum")
    scrum_epicflow_alignment.add_argument("--epicflow-board", help="EpicFlow board ID; defaults to configured EpicFlow board")
    scrum_epicflow_alignment.add_argument("--details", action="store_true", help="Print projects and tasks, not only summary")
    scrum_epicflow_alignment.add_argument("--samples", type=int, default=10, help="Sample size in compact output")
    scrum_epicflow_alignment.set_defaults(func=cmd_scrum_epicflow_alignment)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
        return 0
    except TrackerError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
