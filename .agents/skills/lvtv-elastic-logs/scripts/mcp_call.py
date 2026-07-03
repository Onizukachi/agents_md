#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.request


DEFAULT_PROFILES = {
    "main": "https://logs-mcp.core.lvtv.me/mcp",
    "integrations": "https://logs-mcp.itgs-koa.lvtv.me/mcp",
    "dynamics": "https://logs-mcp.dynamic.lvtv.me/mcp",
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

TOKEN_PATH = os.path.expanduser(os.environ.get("LVTV_ELASTIC_MCP_TOKEN_PATH", "~/elastic-mcp-token"))


def parse_token_file(path):
    tokens = {}
    current = None
    with open(path, "r", encoding="utf-8") as token_file:
        for raw in token_file:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.endswith(":"):
                current = normalize_profile(line[:-1].strip())
                tokens[current] = ""
                continue
            if current:
                tokens[current] = line
                current = None
                continue
            if ":" in line:
                key, value = line.split(":", 1)
                tokens[normalize_profile(key.strip())] = value.strip()
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                tokens[normalize_profile(key.strip())] = value.strip()
                continue
            raise ValueError(f"token line without profile label: {line[:12]}...")
    return tokens


def normalize_profile(profile):
    normalized = profile.strip().lower()
    if normalized not in PROFILE_ALIASES:
        return normalized
    return PROFILE_ALIASES[normalized]


def profile_url(profile):
    env_name = f"LVTV_LOGS_MCP_URL_{profile.upper()}"
    return os.environ.get(env_name, DEFAULT_PROFILES[profile])


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


def call_mcp(profile, token, tool, arguments):
    payload = {
        "jsonrpc": "2.0",
        "id": f"{profile}:{tool}",
        "method": "tools/list" if tool == "tools/list" else "tools/call",
        "params": {} if tool == "tools/list" else {"name": tool, "arguments": arguments},
    }

    req = urllib.request.Request(
        profile_url(profile),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"ApiKey {token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as response:
        return response.read().decode("utf-8", "replace")


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


def call_profile(profile, token, tool, arguments):
    if tool == "find_index":
        tool = "list_indices"
        arguments = {"index_pattern": arguments.get("index_pattern") or arguments.get("pattern") or arguments.get("index") or "*"}
    raw = call_mcp(profile, token, tool, arguments)
    return render_response(raw)


def main():
    parser = argparse.ArgumentParser(description="Call LVTV logs MCP profiles.")
    parser.add_argument("--profile", "-p", default="main", help="main, integrations, dynamics, or all")
    parser.add_argument("tool", help="MCP tool name, tools/list, or find_index")
    parser.add_argument("arguments", nargs="?", default="{}", help="JSON arguments")
    args = parser.parse_args()

    tokens = parse_token_file(TOKEN_PATH)
    profile_arg = args.profile.strip().lower()
    profiles = list(DEFAULT_PROFILES) if profile_arg == "all" else [normalize_profile(profile_arg)]
    arguments = json.loads(args.arguments)

    results = {}
    for profile in profiles:
        if profile not in DEFAULT_PROFILES:
            raise SystemExit(f"unknown profile: {profile}")
        token = tokens.get(profile)
        if not token:
            raise SystemExit(f"missing token for profile: {profile}")
        try:
            results[profile] = call_profile(profile, token, args.tool, arguments)
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
