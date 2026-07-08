#!/usr/bin/env python3
"""Small guarded client for the local LevelTravel Sentry API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_URL = "https://sentry.lvtv.me"
DEFAULT_ORG = "sentry"
DEFAULT_TOKEN_FILE = "~/.config/sentry-local/token"


def load_token() -> str:
    token = os.environ.get("SENTRY_AUTH_TOKEN")
    if token:
        return token.strip()

    token_file = Path(os.environ.get("SENTRY_TOKEN_FILE", DEFAULT_TOKEN_FILE)).expanduser()
    try:
        return token_file.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        raise SystemExit(
            f"Missing Sentry token. Set SENTRY_AUTH_TOKEN or create {token_file}."
        )


def base_url() -> str:
    return os.environ.get("SENTRY_URL", DEFAULT_URL).rstrip("/")


def org_slug() -> str:
    return os.environ.get("SENTRY_ORG", DEFAULT_ORG)


def api_request(
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    data: Any | None = None,
    allow_write: bool = False,
) -> tuple[int, Any, dict[str, str]]:
    method = method.upper()
    if method != "GET":
        if not allow_write or os.environ.get("SENTRY_ALLOW_WRITE") != "1":
            raise SystemExit(
                "Refusing Sentry write. Pass --write and set SENTRY_ALLOW_WRITE=1."
            )

    if not path.startswith("/"):
        path = "/" + path

    query = urllib.parse.urlencode(params or {}, doseq=True)
    url = f"{base_url()}{path}"
    if query:
        url = f"{url}?{query}"

    body = None
    headers = {
        "Authorization": f"Bearer {load_token()}",
        "Accept": "application/json",
    }
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
            return response.status, parse_body(raw), dict(response.headers.items())
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return exc.code, parse_body(raw), dict(exc.headers.items())


def parse_body(raw: bytes) -> Any:
    if not raw:
        return None
    text = raw.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def print_json(value: Any) -> None:
    json.dump(value, sys.stdout, ensure_ascii=False, indent=2, sort_keys=False)
    sys.stdout.write("\n")


def add_common_issue_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project", action="append", default=["-1"])
    parser.add_argument("--query", default="is:unresolved")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--sort", default="date")
    parser.add_argument("--stats-period", default="24h")
    parser.add_argument("--environment", action="append")
    parser.add_argument("--short-id-lookup", action="store_true")


def cmd_projects(_args: argparse.Namespace) -> int:
    status, body, _headers = api_request("GET", "/api/0/projects/")
    if status >= 400:
        print_json({"status": status, "body": body})
        return 1
    print_json(body)
    return 0


def cmd_issues(args: argparse.Namespace) -> int:
    params: dict[str, Any] = {
        "project": args.project,
        "query": args.query,
        "limit": args.limit,
        "sort": args.sort,
        "statsPeriod": args.stats_period,
        "expand": ["owners", "inbox", "latestEventHasAttachments"],
    }
    if args.environment:
        params["environment"] = args.environment
    if args.short_id_lookup:
        params["shortIdLookup"] = "1"

    status, body, _headers = api_request(
        "GET", f"/api/0/organizations/{org_slug()}/issues/", params=params
    )
    if status >= 400:
        print_json({"status": status, "body": body})
        return 1
    print_json(body)
    return 0


def cmd_issue(args: argparse.Namespace) -> int:
    params = {"expand": ["owners", "inbox", "latestEventHasAttachments"]}
    status, body, _headers = api_request(
        "GET", f"/api/0/organizations/{org_slug()}/issues/{args.issue_id}/", params=params
    )
    if status >= 400:
        print_json({"status": status, "body": body})
        return 1
    print_json(body)
    return 0


def cmd_event(args: argparse.Namespace) -> int:
    status, body, _headers = api_request(
        "GET",
        f"/api/0/organizations/{org_slug()}/issues/{args.issue_id}/events/{args.event_id}/",
    )
    if status >= 400:
        print_json({"status": status, "body": body})
        return 1
    print_json(body)
    return 0


def cmd_raw(args: argparse.Namespace) -> int:
    params: dict[str, list[str]] = {}
    for pair in args.param:
        key, sep, value = pair.partition("=")
        if not sep:
            raise SystemExit(f"Invalid --param value {pair!r}; expected key=value.")
        params.setdefault(key, []).append(value)

    data = json.loads(args.data) if args.data else None
    status, body, headers = api_request(
        args.method, args.path, params=params, data=data, allow_write=args.write
    )
    if args.show_headers:
        print_json({"status": status, "headers": headers, "body": body})
    else:
        print_json(body)
    return 0 if status < 400 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    projects = subparsers.add_parser("projects", help="List visible projects.")
    projects.set_defaults(func=cmd_projects)

    issues = subparsers.add_parser("issues", help="List organization issues.")
    add_common_issue_args(issues)
    issues.set_defaults(func=cmd_issues)

    issue = subparsers.add_parser("issue", help="Retrieve one issue.")
    issue.add_argument("issue_id")
    issue.set_defaults(func=cmd_issue)

    event = subparsers.add_parser("event", help="Retrieve one issue event.")
    event.add_argument("issue_id")
    event.add_argument("event_id", nargs="?", default="latest")
    event.set_defaults(func=cmd_event)

    raw = subparsers.add_parser("raw", help="Call an arbitrary Sentry API path.")
    raw.add_argument("method")
    raw.add_argument("path")
    raw.add_argument("--param", action="append", default=[], help="Query param key=value.")
    raw.add_argument("--data", help="JSON request body.")
    raw.add_argument("--write", action="store_true", help="Allow non-GET methods.")
    raw.add_argument("--show-headers", action="store_true")
    raw.set_defaults(func=cmd_raw)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
