#!/usr/bin/env python3
import argparse
import json
import os
import urllib.request


DEFAULT_PROFILES = {
    "main": "http://127.0.0.1:32022/mcp",
    "integrations": "http://127.0.0.1:32012/mcp",
    "dynamics": "http://127.0.0.1:32002/mcp",
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
