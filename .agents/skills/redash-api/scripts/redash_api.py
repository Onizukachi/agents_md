#!/usr/bin/env python3
"""Small Redash API helper for Codex skills."""

from __future__ import annotations

import argparse
import csv
import http.client
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "https://redash.level.travel"
DEFAULT_KEY_FILE = "~/.config/redash-api/api-key"
REPLICA_DATA_SOURCE_ID = 4


class RedashError(RuntimeError):
    pass


class TransientRedashError(RedashError):
    pass


def read_api_key(path: str) -> str:
    env_key = os.environ.get("REDASH_API_KEY")
    if env_key:
        return env_key.strip()

    key_path = Path(os.environ.get("REDASH_API_KEY_FILE", path)).expanduser()
    try:
        key = key_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise RedashError(f"API key file not found: {key_path}") from exc
    if not key:
        raise RedashError(f"API key file is empty: {key_path}")
    return key


def coerce_value(value: str) -> Any:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null":
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def parse_params(pairs: list[str], params_file: str | None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if params_file:
        with open(params_file, "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        if not isinstance(loaded, dict):
            raise RedashError("--params-file must contain a JSON object")
        params.update(loaded)

    for pair in pairs:
        if "=" not in pair:
            raise RedashError(f"Parameter must be name=value: {pair}")
        name, value = pair.split("=", 1)
        if not name:
            raise RedashError(f"Parameter name is empty: {pair}")
        params[name] = coerce_value(value)
    return params


class RedashClient:
    def __init__(self, base_url: str, api_key: str, timeout: int = 60) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def request(
        self,
        method: str,
        path: str,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        accept: str = "application/json",
    ) -> Any:
        url = self.base_url + path
        if query:
            clean_query = {k: v for k, v in query.items() if v is not None}
            url += "?" + urllib.parse.urlencode(clean_query, doseq=True)

        data = None
        headers = {
            "Authorization": f"Key {self.api_key}",
            "Accept": accept,
            "User-Agent": "codex-redash-api-skill/1.0",
        }
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                payload = response.read()
                content_type = response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RedashError(f"HTTP {exc.code} for {method} {path}: {detail}") from exc
        except (http.client.RemoteDisconnected, socket.timeout, TimeoutError) as exc:
            raise TransientRedashError(f"Transient request failure for {method} {path}: {exc}") from exc
        except urllib.error.URLError as exc:
            raise RedashError(f"Request failed for {method} {path}: {exc.reason}") from exc

        if not payload:
            return None
        if accept == "text/csv" or "text/csv" in content_type:
            return payload.decode("utf-8", errors="replace")
        return json.loads(payload.decode("utf-8"))

    def poll_job(self, job_id: str, interval: float, timeout: float) -> dict[str, Any]:
        deadline = time.time() + timeout
        while True:
            try:
                payload = self.request("GET", f"/api/jobs/{job_id}")
            except TransientRedashError:
                if time.time() >= deadline:
                    raise
                time.sleep(interval)
                continue
            job = payload.get("job", payload) if isinstance(payload, dict) else payload
            status = job.get("status")
            if status == 3:
                return job
            if status in {4, 5}:
                error = job.get("error") or job.get("exception") or "unknown error"
                raise RedashError(f"Redash job {job_id} failed with status {status}: {error}")
            if time.time() >= deadline:
                raise RedashError(f"Timed out waiting for Redash job {job_id}")
            time.sleep(interval)


def extract_result_id(payload: Any, client: RedashClient, wait: bool, interval: float, timeout: float) -> int | None:
    if not isinstance(payload, dict):
        return None
    if "query_result" in payload and isinstance(payload["query_result"], dict):
        return payload["query_result"].get("id")
    if "query_result_id" in payload:
        result_id = payload["query_result_id"]
        if result_id is not None:
            return result_id
    if "job" in payload and isinstance(payload["job"], dict):
        job = payload["job"]
        if "query_result_id" in job and job["query_result_id"] is not None:
            return job["query_result_id"]
        if wait and "id" in job:
            completed = client.poll_job(str(job["id"]), interval=interval, timeout=timeout)
            return completed.get("query_result_id")
    return None


def rows_from_result(payload: Any) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(payload, dict):
        return [], []
    query_result = payload.get("query_result", payload)
    data = query_result.get("data", {}) if isinstance(query_result, dict) else {}
    rows = data.get("rows", []) if isinstance(data, dict) else []
    columns_data = data.get("columns", []) if isinstance(data, dict) else []
    columns = [column.get("name") for column in columns_data if isinstance(column, dict) and column.get("name")]
    if not columns and rows:
        columns = list(rows[0].keys())
    return rows, columns


def output_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def output_table(payload: Any, limit: int | None) -> None:
    rows, columns = rows_from_result(payload)
    if not rows:
        output_json(payload)
        return

    selected_rows = rows[:limit] if limit else rows
    widths = {column: len(str(column)) for column in columns}
    for row in selected_rows:
        for column in columns:
            widths[column] = min(max(widths[column], len(str(row.get(column, "")))), 80)

    header = " | ".join(str(column).ljust(widths[column]) for column in columns)
    separator = "-+-".join("-" * widths[column] for column in columns)
    print(header)
    print(separator)
    for row in selected_rows:
        values = []
        for column in columns:
            value = str(row.get(column, ""))
            if len(value) > widths[column]:
                value = value[: widths[column] - 3] + "..."
            values.append(value.ljust(widths[column]))
        print(" | ".join(values))
    if limit and len(rows) > limit:
        print(f"... {len(rows) - limit} more rows")


def output_csv(payload: Any) -> None:
    rows, columns = rows_from_result(payload)
    writer = csv.DictWriter(sys.stdout, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)


def output_payload(payload: Any, fmt: str, limit: int | None) -> None:
    if fmt == "json":
        output_json(payload)
    elif fmt == "table":
        output_table(payload, limit)
    elif fmt == "csv":
        output_csv(payload)
    else:
        raise RedashError(f"Unknown output format: {fmt}")


def make_client(args: argparse.Namespace) -> RedashClient:
    base_url = os.environ.get("REDASH_BASE_URL", args.base_url)
    return RedashClient(base_url=base_url, api_key=read_api_key(args.key_file), timeout=args.timeout)


def cmd_data_sources(args: argparse.Namespace) -> None:
    output_payload(make_client(args).request("GET", "/api/data_sources"), args.format, args.limit)


def cmd_queries(args: argparse.Namespace) -> None:
    query = {"q": args.search, "page": args.page, "page_size": args.page_size}
    output_payload(make_client(args).request("GET", "/api/queries", query=query), args.format, args.limit)


def cmd_get_query(args: argparse.Namespace) -> None:
    output_payload(make_client(args).request("GET", f"/api/queries/{args.query_id}"), args.format, args.limit)


def fetch_result(client: RedashClient, result_id: int, fmt: str) -> Any:
    if fmt == "csv":
        return client.request("GET", f"/api/query_results/{result_id}.csv", accept="text/csv")
    return client.request("GET", f"/api/query_results/{result_id}.json")


def cmd_run_query(args: argparse.Namespace) -> None:
    client = make_client(args)
    params = parse_params(args.param, args.params_file)
    body = {"parameters": params, "max_age": args.max_age}
    payload = client.request("POST", f"/api/queries/{args.query_id}/results", body=body)
    result_id = extract_result_id(payload, client, wait=args.wait, interval=args.interval, timeout=args.wait_timeout)
    if result_id is None:
        output_json(payload)
        return
    result_payload = fetch_result(client, int(result_id), args.format)
    if args.format == "csv":
        print(result_payload, end="" if result_payload.endswith("\n") else "\n")
    else:
        output_payload(result_payload, args.format, args.limit)


def cmd_adhoc(args: argparse.Namespace) -> None:
    client = make_client(args)
    if args.query_file:
        sql = Path(args.query_file).read_text(encoding="utf-8")
    else:
        sql = args.query
    if not sql or not sql.strip():
        raise RedashError("SQL query is empty")

    params = parse_params(args.param, args.params_file)
    body = {
        "data_source_id": args.data_source_id,
        "query": sql,
        "parameters": params,
        "max_age": args.max_age,
    }
    payload = client.request("POST", "/api/query_results", body=body)
    result_id = extract_result_id(payload, client, wait=args.wait, interval=args.interval, timeout=args.wait_timeout)
    if result_id is None:
        output_json(payload)
        return
    result_payload = fetch_result(client, int(result_id), args.format)
    if args.format == "csv":
        print(result_payload, end="" if result_payload.endswith("\n") else "\n")
    else:
        output_payload(result_payload, args.format, args.limit)


def cmd_replica(args: argparse.Namespace) -> None:
    args.data_source_id = REPLICA_DATA_SOURCE_ID
    cmd_adhoc(args)


def cmd_job(args: argparse.Namespace) -> None:
    job = make_client(args).poll_job(str(args.job_id), interval=args.interval, timeout=args.wait_timeout)
    output_json(job)


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"Redash base URL (default: {DEFAULT_BASE_URL})")
    parser.add_argument("--key-file", default=DEFAULT_KEY_FILE, help=f"API key file (default: {DEFAULT_KEY_FILE})")
    parser.add_argument("--timeout", type=int, default=60, help="HTTP timeout in seconds")


def add_output_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=["json", "table", "csv"], default="json", help="Output format")
    parser.add_argument("--limit", type=int, default=50, help="Rows to show for table output; 0 means all rows")


def add_param_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--param", action="append", default=[], help="Query parameter as name=value; repeatable")
    parser.add_argument("--params-file", help="JSON object containing query parameters")
    parser.add_argument("--max-age", type=int, default=0, help="Redash cache max_age in seconds; 0 requests fresh results")
    parser.add_argument("--wait", action=argparse.BooleanOptionalAction, default=True, help="Wait for async jobs")
    parser.add_argument("--interval", type=float, default=1.0, help="Job polling interval in seconds")
    parser.add_argument("--wait-timeout", type=float, default=300.0, help="Max seconds to wait for a job")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Redash API helper")
    add_common(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)

    data_sources = subparsers.add_parser("data-sources", help="List Redash data sources")
    add_output_options(data_sources)
    data_sources.set_defaults(func=cmd_data_sources)

    queries = subparsers.add_parser("queries", help="Search/list saved Redash queries")
    queries.add_argument("--search", help="Search text")
    queries.add_argument("--page", type=int, default=1)
    queries.add_argument("--page-size", type=int, default=25)
    add_output_options(queries)
    queries.set_defaults(func=cmd_queries)

    get_query = subparsers.add_parser("get-query", help="Fetch a saved Redash query by ID")
    get_query.add_argument("query_id", type=int)
    add_output_options(get_query)
    get_query.set_defaults(func=cmd_get_query)

    run_query = subparsers.add_parser("run-query", help="Run a saved Redash query by ID")
    run_query.add_argument("query_id", type=int)
    add_param_options(run_query)
    add_output_options(run_query)
    run_query.set_defaults(func=cmd_run_query)

    adhoc = subparsers.add_parser("adhoc", help="Run an ad-hoc SQL query through Redash")
    adhoc.add_argument("--data-source-id", type=int, required=True)
    query_group = adhoc.add_mutually_exclusive_group(required=True)
    query_group.add_argument("--query", help="SQL text")
    query_group.add_argument("--query-file", help="Path to SQL file")
    add_param_options(adhoc)
    add_output_options(adhoc)
    adhoc.set_defaults(func=cmd_adhoc)

    replica = subparsers.add_parser("replica", help="Run an ad-hoc SQL query against the Level Travel Replica data source")
    query_group = replica.add_mutually_exclusive_group(required=True)
    query_group.add_argument("--query", help="SQL text")
    query_group.add_argument("--query-file", help="Path to SQL file")
    add_param_options(replica)
    add_output_options(replica)
    replica.set_defaults(func=cmd_replica)

    job = subparsers.add_parser("job", help="Poll a Redash job by ID")
    job.add_argument("job_id")
    job.add_argument("--interval", type=float, default=1.0)
    job.add_argument("--wait-timeout", type=float, default=300.0)
    job.set_defaults(func=cmd_job)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if getattr(args, "limit", None) == 0:
        args.limit = None
    try:
        args.func(args)
    except RedashError as exc:
        print(f"redash_api.py: error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
