#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


DEFAULT_PROFILES = {
    "main": "http://127.0.0.1:32022/mcp",
    "integrations": "http://127.0.0.1:32012/mcp",
    "dynamics": "http://127.0.0.1:32002/mcp",
}

BOUNDARY_TARGETS = {
    "main": {
        "name": "[RO] Elasticsearch MCP: k8s-core",
        "port": 32022,
    },
    "integrations": {
        "name": "[RO] Elasticsearch MCP: k8s-integrations",
        "port": 32012,
    },
    "dynamics": {
        "name": "[RO] Elasticsearch MCP: k8s-dynamic",
        "port": 32002,
    },
}

PROFILE_ALIASES = {
    "core": "main",
    "main": "main",
    "itgs": "integrations",
    "itgs-koa": "integrations",
    "itgs-core": "integrations",
    "integration": "integrations",
    "integrations": "integrations",
    "dynamic": "dynamics",
    "dynamics": "dynamics",
}

REQUEST_TIMEOUT_SECONDS = float(os.environ.get("LVTV_LOGS_MCP_TIMEOUT", "120"))
BOUNDARY_START_TIMEOUT_SECONDS = float(os.environ.get("LVTV_LOGS_BOUNDARY_START_TIMEOUT", "20"))
BOUNDARY_CONFIG_PATHS = [
    Path(os.environ["LVTV_LOGS_BOUNDARY_CONFIG"]).expanduser()
    if os.environ.get("LVTV_LOGS_BOUNDARY_CONFIG")
    else None,
    Path("~/.config/lvtv-elastic-logs/boundary.json").expanduser(),
]
BOUNDARY_CACHE_DB = Path(os.environ.get("LVTV_LOGS_BOUNDARY_CACHE_DB", "~/.boundary/cache.db")).expanduser()
BOUNDARY_LOG_DIR = Path(os.environ.get("LVTV_LOGS_BOUNDARY_LOG_DIR", "~/.cache/lvtv-elastic-logs")).expanduser()


def normalize_profile(profile):
    normalized = profile.strip().lower()
    if normalized not in PROFILE_ALIASES:
        return normalized
    return PROFILE_ALIASES[normalized]


def profile_url(profile):
    env_name = f"LVTV_LOGS_MCP_URL_{profile.upper()}"
    return os.environ.get(env_name, DEFAULT_PROFILES[profile])


def is_local_mcp_url(url):
    parsed = urlparse(url)
    return parsed.hostname in {"127.0.0.1", "localhost", "::1"} and parsed.port is not None


def local_port(url):
    return urlparse(url).port


def port_is_open(port):
    with socket.socket() as sock:
        sock.settimeout(1)
        try:
            sock.connect(("127.0.0.1", int(port)))
            return True
        except OSError:
            return False


def boundary_cli_path():
    configured = os.environ.get("LVTV_LOGS_BOUNDARY_BIN")
    if configured:
        return configured
    from_path = shutil.which("boundary")
    if from_path:
        return from_path
    return None


def load_boundary_config():
    for path in BOUNDARY_CONFIG_PATHS:
        if path and path.exists():
            with path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
    return {}


def boundary_profile_config(profile):
    config = load_boundary_config()
    profiles = config.get("profiles", {})
    merged = dict(BOUNDARY_TARGETS.get(profile, {}))
    if config.get("addr"):
        merged["addr"] = config["addr"]
    merged.update(profiles.get(profile, {}))
    return merged


def boundary_addr(config):
    if config.get("addr"):
        return config["addr"]
    if os.environ.get("BOUNDARY_ADDR"):
        return os.environ["BOUNDARY_ADDR"]
    return None


def target_id_from_cache(target_name):
    if not BOUNDARY_CACHE_DB.exists():
        return None
    try:
        with sqlite3.connect(str(BOUNDARY_CACHE_DB)) as conn:
            row = conn.execute(
                "select id from target where name = ? order by id limit 1",
                (target_name,),
            ).fetchone()
    except sqlite3.Error:
        return None
    return row[0] if row else None


def tail_text(path, max_bytes=4000):
    try:
        with path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - max_bytes), os.SEEK_SET)
            return fh.read().decode("utf-8", "replace").strip()
    except OSError:
        return ""


def redact_sensitive(text):
    text = re.sub(r"at_[A-Za-z0-9]+", "at_REDACTED", text)
    text = re.sub(r"Bearer\s+\S+", "Bearer REDACTED", text)
    text = re.sub(r"(?i)(token|secret|password|key)=\S+", r"\1=REDACTED", text)
    return text


def wait_for_port(port, timeout_seconds, process=None):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if port_is_open(port):
            return True
        if process is not None and process.poll() is not None:
            return False
        time.sleep(0.5)
    return port_is_open(port)


def start_boundary_tunnel(profile):
    cfg = boundary_profile_config(profile)
    port = int(cfg.get("port") or local_port(profile_url(profile)))
    if port_is_open(port):
        return

    cli = boundary_cli_path()
    if not cli:
        raise RuntimeError("Boundary CLI not found; add boundary to PATH or set LVTV_LOGS_BOUNDARY_BIN")

    target_id = cfg.get("target_id") or target_id_from_cache(cfg.get("name", ""))
    command = [cli, "connect"]
    addr = boundary_addr(cfg)
    if addr:
        command.extend(["-addr", addr])
    command.extend(["-listen-addr", "127.0.0.1", "-listen-port", str(port)])
    if target_id:
        command.extend(["-target-id", target_id])
    else:
        target_name = cfg.get("name")
        scope_id = cfg.get("scope_id")
        scope_name = cfg.get("scope_name")
        if not target_name:
            raise RuntimeError(f"Boundary target is not configured for profile {profile}")
        command.extend(["-target-name", target_name])
        if scope_id:
            command.extend(["-target-scope-id", scope_id])
        elif scope_name:
            command.extend(["-target-scope-name", scope_name])
        else:
            raise RuntimeError(
                f"Boundary target id not found in {BOUNDARY_CACHE_DB}; set target_id or scope_id in boundary config"
            )

    BOUNDARY_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = BOUNDARY_LOG_DIR / f"boundary-{profile}.log"
    log_file = log_path.open("ab")
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        close_fds=True,
    )
    log_file.close()
    if not wait_for_port(port, BOUNDARY_START_TIMEOUT_SECONDS, process):
        details = redact_sensitive(tail_text(log_path))
        suffix = f"; last log: {details}" if details else ""
        raise RuntimeError(f"Boundary tunnel for {profile} did not open 127.0.0.1:{port}; see {log_path}{suffix}")


def ensure_boundary_tunnel(profile):
    if os.environ.get("LVTV_LOGS_BOUNDARY_AUTOSTART", "1") in {"0", "false", "False", "no"}:
        return
    url = profile_url(profile)
    if not is_local_mcp_url(url):
        return
    port = local_port(url)
    if port and not port_is_open(port):
        start_boundary_tunnel(profile)


def parse_sse(raw):
    events = []
    for line in raw.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


def extract_content(event):
    content = event.get("result", {}).get("content", [])
    texts = [item.get("text", "") for item in content]
    parsed = []
    for text in texts:
        stripped = text.strip()
        if stripped[:1] in ("{", "["):
            try:
                parsed.append(json.loads(stripped))
            except json.JSONDecodeError:
                pass
    return texts, parsed


def call_mcp(profile, tool, arguments):
    payload = {
        "jsonrpc": "2.0",
        "id": f"{profile}:{tool}",
        "method": "tools/list" if tool == "tools/list" else "tools/call",
        "params": {} if tool == "tools/list" else {"name": tool, "arguments": arguments},
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    req = urllib.request.Request(
        profile_url(profile),
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return read_mcp_response(response)


def read_mcp_response(response):
    chunks = []
    while True:
        raw_line = response.readline()
        if not raw_line:
            break
        line = raw_line.decode("utf-8", "replace")
        chunks.append(line)
        if line.startswith("data: "):
            try:
                event = json.loads(line[6:])
            except json.JSONDecodeError:
                continue
            if "result" in event or "error" in event:
                break
    return "".join(chunks)


def render_response(raw):
    events = parse_sse(raw)
    if not events:
        return raw
    texts, parsed = extract_content(events[-1])
    if parsed:
        return parsed[-1]
    if len(texts) == 1:
        return texts[0]
    return texts


def call_profile(profile, tool, arguments):
    if tool == "find_index":
        tool = "list_indices"
        arguments = {"index_pattern": arguments.get("index_pattern") or arguments.get("pattern") or arguments.get("index") or "*"}
    ensure_boundary_tunnel(profile)
    raw = call_mcp(profile, tool, arguments)
    return render_response(raw)


def main():
    parser = argparse.ArgumentParser(description="Call LVTV logs MCP profiles.")
    parser.add_argument("--profile", "-p", default="main", help="main, integrations, dynamics, or all")
    parser.add_argument("tool", help="MCP tool name, tools/list, or find_index")
    parser.add_argument("arguments", nargs="?", default="{}", help="JSON arguments")
    args = parser.parse_args()

    profile_arg = args.profile.strip().lower()
    profiles = list(DEFAULT_PROFILES) if profile_arg == "all" else [normalize_profile(profile_arg)]
    arguments = json.loads(args.arguments)

    results = {}
    for profile in profiles:
        if profile not in DEFAULT_PROFILES:
            raise SystemExit(f"unknown profile: {profile}")
        try:
            results[profile] = call_profile(profile, args.tool, arguments)
        except Exception as exc:
            results[profile] = {"error": f"{type(exc).__name__}: {exc}"}

    output = results[profiles[0]] if len(profiles) == 1 else results
    if isinstance(output, str):
        print(output)
    else:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
