#!/usr/bin/env python3
"""Generate a private, standalone HTML report from local Codex rollout logs."""
import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROLLOUT = re.compile(r"([0-9a-f-]{36})\.jsonl(?:\.zst)?$")
TOKEN_FIELDS = {
    "input": "input_tokens",
    "cached": "cached_input_tokens",
    "output": "output_tokens",
    "reasoning": "reasoning_output_tokens",
}
TOOL_TYPES = ("function_call", "custom_tool_call", "web_search_call")
RECORD_TYPES = ("session_meta", "turn_context", "event_msg", "response_item")


def find_rollouts(home):
    paths = {}
    for folder in ("sessions", "archived_sessions"):
        for path in (home / folder).rglob("rollout-*.jsonl*"):
            match = ROLLOUT.search(path.name)
            if match:
                key = match[1]
                if key not in paths or path.stat().st_mtime > paths[key].stat().st_mtime:
                    paths[key] = path
    return paths.values()


def events(stream):
    # Rollouts can contain large tool outputs. Skip those before decoding JSON.
    type_markers = tuple(f'"{kind}"'.encode() for kind in RECORD_TYPES)
    tool_markers = tuple(f'"{kind}"'.encode() for kind in TOOL_TYPES)
    for line in stream:
        if not any(marker in line[:256] for marker in type_markers):
            continue
        if b'"response_item"' in line[:128] and not any(
            marker in line[:384] for marker in tool_markers
        ):
            continue
        try:
            yield json.loads(line)
        except (ValueError, UnicodeError):
            yield None


def scan(paths, start, end, zone, cutoff):
    days = defaultdict(Counter)
    models = Counter()
    chats = agents = usage = errors = skipped = 0
    zstd = shutil.which("zstd")
    for path in paths:
        compressed = path.suffix == ".zst"
        if compressed and not zstd:
            skipped += 1
            continue
        agent = active = has_usage = False
        model = "Unknown model"
        previous = None
        seen_calls = set()
        process = None
        try:
            if compressed:
                process = subprocess.Popen([zstd, "-qdc", str(path)], stdout=subprocess.PIPE)
            with (process.stdout if process else path.open("rb")) as stream:
                for event in events(stream):
                    if event is None:
                        errors += 1
                        continue
                    kind = event.get("type")
                    payload = event.get("payload") or {}
                    event_type = payload.get("type")
                    if kind == "session_meta":
                        source = payload.get("source")
                        agent |= isinstance(source, dict) and "subagent" in source
                        # Fork history can carry metadata from its parent.
                        if agent:
                            model = "Unknown model"
                        continue
                    if kind == "turn_context":
                        model = payload.get("model") or model
                        continue
                    try:
                        stamp = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
                        day = stamp.astimezone(zone).date()
                    except (KeyError, ValueError, TypeError, AttributeError):
                        errors += 1
                        continue
                    in_window = start <= day <= end and stamp <= cutoff
                    if kind == "event_msg" and event_type == "token_count":
                        info = payload.get("info") or {}
                        total = info.get("total_token_usage")
                        if not total or total == previous:
                            continue
                        previous = total
                        last = info.get("last_token_usage")
                        if not in_window or not last:
                            continue
                        token = {key: last.get(field, 0) or 0 for key, field in TOKEN_FIELDS.items()}
                        days[day.isoformat()].update(token)
                        models[model] += token["input"] + token["output"]
                        has_usage = True
                    elif kind == "event_msg" and event_type in ("task_started", "turn_started"):
                        if not in_window:
                            continue
                        days[day.isoformat()]["turns"] += 1
                    elif kind == "response_item" and event_type in TOOL_TYPES:
                        call = payload.get("call_id")
                        if call and call in seen_calls:
                            continue
                        if call:
                            seen_calls.add(call)
                        if not in_window:
                            continue
                        days[day.isoformat()]["tools"] += 1
                    else:
                        continue
                    active = True
        except OSError:
            errors += 1
        finally:
            if process and process.wait() != 0:
                errors += 1
        if active:
            agents += int(agent)
            chats += int(not agent)
            usage += int(has_usage)
    return {
        "days": days, "models": models, "chats": chats, "agents": agents,
        "usage": usage, "files": len(paths), "errors": errors, "skipped": skipped,
        "start": start.isoformat(), "end": end.isoformat(), "timezone": str(zone),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", type=Path, default=os.getenv("CODEX_HOME") or Path.home() / ".codex")
    parser.add_argument("--timezone", help="IANA timezone, for example America/Chicago. Defaults to UTC.")
    parser.add_argument("--end", type=date.fromisoformat, help="Last day to include, as YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--output", required=True, type=Path, help="New HTML file to write.")
    args = parser.parse_args()
    try:
        zone = ZoneInfo(args.timezone or "UTC")
    except ZoneInfoNotFoundError:
        parser.error("Unknown timezone or missing IANA timezone data.")
    cutoff = datetime.now(timezone.utc)
    end = args.end or cutoff.astimezone(zone).date()
    start = end - timedelta(days=364)
    paths = list(find_rollouts(args.codex_home.expanduser()))
    if not paths:
        parser.error("No rollout logs found under sessions or archived_sessions.")
    report = scan(paths, start, end, zone, cutoff)
    template = Path(__file__).resolve().parents[1] / "assets/report.html"
    html = template.read_text(encoding="utf-8").replace(
        "__DATA__", json.dumps(report).replace("<", r"\u003c")
    )
    output = args.output.expanduser().absolute()
    output.parent.mkdir(parents=True, exist_ok=True)
    # Link the fully written private file into place without replacing an existing report.
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, mode="w", encoding="utf-8") as file:
            file.write(html)
            file.flush()
            os.link(file.name, output)
    except FileExistsError:
        parser.error("The output file already exists. Choose a new path.")
    print(output)


if __name__ == "__main__":
    main()
