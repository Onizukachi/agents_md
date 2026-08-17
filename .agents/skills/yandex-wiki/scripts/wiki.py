#!/usr/bin/env python3
"""Read-only helper for Yandex Wiki API."""

from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_CONFIG = Path.home() / ".yandex-wiki.env"
DEFAULT_TOKEN_FILE = Path.home() / ".config" / "yandex-wiki" / "iam-token"
DEFAULT_BASE_URL = "https://api.wiki.yandex.net/v1"
DEFAULT_FIELDS = "content,attributes,breadcrumbs"
TOKEN_MAX_AGE_SECONDS = 11 * 60 * 60


class WikiError(RuntimeError):
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
        values[key.strip()] = value.strip().strip("'\"")
    return values


def write_env_file(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(f"{key}={value}\n" for key, value in values.items() if value != "")
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


def write_secret_file(path: Path, value: str) -> None:
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, stat.S_IRUSR | stat.S_IWUSR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(value.strip() + "\n")
        os.replace(tmp_path, path)
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def expand_path(value: str | None, default: Path) -> Path:
    if not value:
        return default
    return Path(value).expanduser()


def load_config(args: argparse.Namespace) -> dict[str, str]:
    path = Path(getattr(args, "config", DEFAULT_CONFIG)).expanduser()
    file_values = read_env_file(path)

    def value(name: str, default: str = "") -> str:
        return os.environ.get(name) or file_values.get(name) or default

    cfg = {
        "config": str(path),
        "api_base": value("YANDEX_WIKI_API_BASE", DEFAULT_BASE_URL),
        "org_id": value("YANDEX_WIKI_ORG_ID"),
        "org_header": value("YANDEX_WIKI_ORG_HEADER", "X-Org-Id"),
        "auth_type": value("YANDEX_WIKI_AUTH_TYPE", "Bearer"),
        "token": value("YANDEX_WIKI_TOKEN"),
        "token_file": value("YANDEX_WIKI_TOKEN_FILE", str(DEFAULT_TOKEN_FILE)),
        "refresh_iam": value("YANDEX_WIKI_REFRESH_IAM", "0"),
        "yc_bin": value("YANDEX_WIKI_YC_BIN", "yc"),
    }
    if not cfg["org_id"]:
        raise WikiError(f"YANDEX_WIKI_ORG_ID is missing. Run `wiki.py setup ...` or create {path}.")
    ensure_token(cfg)
    return cfg


def token_file_is_fresh(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    return time.time() - path.stat().st_mtime < TOKEN_MAX_AGE_SECONDS


def create_iam_token(cfg: dict[str, str]) -> str:
    try:
        result = subprocess.run(
            [cfg["yc_bin"], "iam", "create-token"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise WikiError(f"Yandex Cloud CLI not found: {cfg['yc_bin']}") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip()
        raise WikiError(f"`yc iam create-token` failed: {stderr}") from exc
    token = result.stdout.strip()
    if not token:
        raise WikiError("`yc iam create-token` returned an empty token.")
    return token


def ensure_token(cfg: dict[str, str]) -> None:
    if cfg["token"]:
        return
    token_path = expand_path(cfg["token_file"], DEFAULT_TOKEN_FILE)
    if cfg["auth_type"] == "Bearer" and truthy(cfg["refresh_iam"]) and not token_file_is_fresh(token_path):
        token = create_iam_token(cfg)
        write_secret_file(token_path, token)
        cfg["token"] = token
        cfg["token_file"] = str(token_path)
        return
    if token_path.exists():
        cfg["token"] = token_path.read_text(encoding="utf-8").strip()
        cfg["token_file"] = str(token_path)
    if not cfg["token"]:
        raise WikiError(
            "YANDEX_WIKI_TOKEN is missing and token file is empty. "
            "Set YANDEX_WIKI_TOKEN_FILE or run `wiki.py setup --refresh-iam`."
        )


def request_json(
    cfg: dict[str, str],
    path: str,
    *,
    query: dict[str, Any] | list[tuple[str, Any]] | None = None,
) -> Any:
    base = cfg["api_base"].rstrip("/")
    api_path = path if path.startswith("/") else f"/{path}"
    url = f"{base}{api_path}"
    if isinstance(query, dict):
        query_items = [(k, v) for k, v in query.items() if v is not None and v != []]
    else:
        query_items = [(k, v) for k, v in (query or []) if v is not None and v != []]
    if query_items:
        url = f"{url}?{urlencode(query_items, doseq=True)}"

    headers = {
        "Authorization": f"{cfg['auth_type']} {cfg['token']}",
        cfg["org_header"]: cfg["org_id"],
    }
    req = Request(url, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=30) as response:
            raw = response.read()
            if not raw:
                return None
            return json.loads(raw.decode("utf-8"))
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise WikiError(f"GET {url} failed: HTTP {exc.code}: {raw}") from exc
    except URLError as exc:
        raise WikiError(f"GET {url} failed: {exc}") from exc


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def summarize_page(page: dict[str, Any]) -> dict[str, Any]:
    attrs = page.get("attributes") if isinstance(page.get("attributes"), dict) else {}
    content = page.get("content")
    return {
        "id": page.get("id"),
        "slug": page.get("slug"),
        "title": page.get("title"),
        "page_type": page.get("page_type"),
        "created_at": attrs.get("created_at"),
        "modified_at": attrs.get("modified_at"),
        "breadcrumbs": [
            {"title": item.get("title"), "slug": item.get("slug")}
            for item in page.get("breadcrumbs", [])
            if isinstance(item, dict)
        ],
        "content_chars": len(content) if isinstance(content, str) else None,
        "content": content,
    }


def cmd_setup(args: argparse.Namespace) -> None:
    path = Path(args.config).expanduser()
    values = read_env_file(path)
    values.update(
        {
            "YANDEX_WIKI_ORG_ID": args.org_id,
            "YANDEX_WIKI_AUTH_TYPE": args.auth_type,
            "YANDEX_WIKI_ORG_HEADER": args.org_header,
            "YANDEX_WIKI_API_BASE": args.api_base,
            "YANDEX_WIKI_TOKEN_FILE": args.token_file,
            "YANDEX_WIKI_REFRESH_IAM": "1" if args.refresh_iam else "0",
            "YANDEX_WIKI_YC_BIN": args.yc_bin,
        }
    )
    if args.token:
        write_secret_file(Path(args.token_file).expanduser(), args.token)
    write_env_file(path, values)
    if args.refresh_iam:
        token = create_iam_token({"yc_bin": args.yc_bin})
        write_secret_file(Path(args.token_file).expanduser(), token)
    print_json(
        {
            "config": str(path),
            "org_id": args.org_id,
            "auth_type": args.auth_type,
            "org_header": args.org_header,
            "token_file": args.token_file,
            "refresh_iam": args.refresh_iam,
        }
    )


def cmd_config(args: argparse.Namespace) -> None:
    cfg = load_config(args)
    token_path = expand_path(cfg["token_file"], DEFAULT_TOKEN_FILE)
    print_json(
        {
            "config": cfg["config"],
            "api_base": cfg["api_base"],
            "org_id": cfg["org_id"],
            "org_header": cfg["org_header"],
            "auth_type": cfg["auth_type"],
            "token_source": "env" if os.environ.get("YANDEX_WIKI_TOKEN") else str(token_path),
            "token_present": bool(cfg["token"]),
            "token_file_exists": token_path.exists(),
            "refresh_iam": truthy(cfg["refresh_iam"]),
            "yc_bin": cfg["yc_bin"],
        }
    )


def cmd_refresh_token(args: argparse.Namespace) -> None:
    cfg = load_config(args)
    if cfg["auth_type"] != "Bearer":
        raise WikiError("refresh-token only applies to Bearer IAM authentication.")
    token = create_iam_token(cfg)
    token_path = expand_path(cfg["token_file"], DEFAULT_TOKEN_FILE)
    write_secret_file(token_path, token)
    print_json({"token_file": str(token_path), "written": True})


def cmd_descendants(args: argparse.Namespace) -> None:
    cfg = load_config(args)
    page_size = min(max(args.page_size, 1), 100)
    results: list[dict[str, Any]] = []
    cursor = args.cursor
    while True:
        data = request_json(
            cfg,
            "/pages/descendants",
            query={
                "slug": args.slug,
                "include_self": str(args.include_self).lower(),
                "page_size": page_size,
                "cursor": cursor,
                "actuality": args.actuality,
            },
        )
        batch = data.get("results", []) if isinstance(data, dict) else []
        results.extend(batch)
        if args.limit and len(results) >= args.limit:
            results = results[: args.limit]
            break
        cursor = data.get("next_cursor") if isinstance(data, dict) else None
        if not cursor:
            break
    print_json({"results": results, "count": len(results)})


def cmd_page(args: argparse.Namespace) -> None:
    cfg = load_config(args)
    fields = args.fields
    data = request_json(
        cfg,
        "/pages",
        query={"slug": args.slug, "fields": fields, "revision_id": args.revision_id},
    )
    if args.raw:
        print_json(data)
        return
    if args.content_only:
        content = data.get("content") if isinstance(data, dict) else None
        if content is not None:
            print(content)
        return
    print_json(summarize_page(data))


def parse_query_items(values: list[str]) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for value in values:
        if "=" not in value:
            raise WikiError(f"Query item must be key=value: {value}")
        key, item_value = value.split("=", 1)
        items.append((key, item_value))
    return items


def cmd_raw(args: argparse.Namespace) -> None:
    cfg = load_config(args)
    data = request_json(cfg, args.path, query=parse_query_items(args.query))
    print_json(data)


def cmd_export(args: argparse.Namespace) -> None:
    cfg = load_config(args)
    page_size = min(max(args.page_size, 1), 100)
    slugs: list[str] = []
    cursor = None
    while True:
        data = request_json(
            cfg,
            "/pages/descendants",
            query={
                "slug": args.slug,
                "include_self": str(args.include_self).lower(),
                "page_size": page_size,
                "cursor": cursor,
                "actuality": args.actuality,
            },
        )
        batch = data.get("results", []) if isinstance(data, dict) else []
        slugs.extend(item["slug"] for item in batch if isinstance(item, dict) and item.get("slug"))
        if args.limit and len(slugs) >= args.limit:
            slugs = slugs[: args.limit]
            break
        cursor = data.get("next_cursor") if isinstance(data, dict) else None
        if not cursor:
            break

    fields = DEFAULT_FIELDS if args.content else "attributes,breadcrumbs"
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output.open("w", encoding="utf-8") as file:
        for slug in slugs:
            page = request_json(cfg, "/pages", query={"slug": slug, "fields": fields})
            file.write(json.dumps(page, ensure_ascii=False) + "\n")
            count += 1
    print_json({"output": str(output), "pages": count})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only Yandex Wiki API helper.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Config env file path.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    setup = subparsers.add_parser("setup", help="Write local helper config.")
    setup.add_argument("--org-id", required=True)
    setup.add_argument("--auth-type", default="Bearer", choices=["Bearer", "OAuth"])
    setup.add_argument("--org-header", default="X-Org-Id")
    setup.add_argument("--api-base", default=DEFAULT_BASE_URL)
    setup.add_argument("--token-file", default=str(DEFAULT_TOKEN_FILE))
    setup.add_argument("--token")
    setup.add_argument("--refresh-iam", action="store_true")
    setup.add_argument("--yc-bin", default="yc")
    setup.set_defaults(func=cmd_setup)

    config = subparsers.add_parser("config", help="Show non-secret effective config.")
    config.set_defaults(func=cmd_config)

    refresh = subparsers.add_parser("refresh-token", help="Create and store a new IAM token.")
    refresh.set_defaults(func=cmd_refresh_token)

    descendants = subparsers.add_parser("descendants", help="List descendants by slug.")
    descendants.add_argument("--slug", default="")
    descendants.add_argument("--include-self", action="store_true")
    descendants.add_argument("--limit", type=int, default=50)
    descendants.add_argument("--page-size", type=int, default=100)
    descendants.add_argument("--cursor")
    descendants.add_argument("--actuality", choices=["actual", "obsolete"])
    descendants.set_defaults(func=cmd_descendants)

    page = subparsers.add_parser("page", help="Read a page by slug.")
    page.add_argument("slug")
    page.add_argument("--fields", default=DEFAULT_FIELDS)
    page.add_argument("--revision-id", type=int)
    page.add_argument("--raw", action="store_true")
    page.add_argument("--content-only", action="store_true")
    page.set_defaults(func=cmd_page)

    export = subparsers.add_parser("export", help="Export page details under a slug to JSONL.")
    export.add_argument("--slug", default="")
    export.add_argument("--include-self", action="store_true")
    export.add_argument("--limit", type=int, default=100)
    export.add_argument("--page-size", type=int, default=100)
    export.add_argument("--actuality", choices=["actual", "obsolete"])
    export.add_argument("--output", required=True)
    export.add_argument("--no-content", dest="content", action="store_false")
    export.set_defaults(func=cmd_export, content=True)

    raw = subparsers.add_parser("raw", help="Call a read-only GET API path.")
    raw.add_argument("path")
    raw.add_argument("--query", action="append", default=[], help="Query parameter as key=value.")
    raw.set_defaults(func=cmd_raw)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
        return 0
    except WikiError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
