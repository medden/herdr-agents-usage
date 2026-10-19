#!/usr/bin/env python3
"""Print one line of agent subscription usage for herdr's tab bar.

Reads the per-agent records Omarchy's collectors write to
~/.local/state/omarchy/agents/usage/<agent>.json and, when a record with
limits has gone stale, asks Omarchy to regenerate it in the background. The
token and the usage endpoint stay Omarchy's business; this only reads files.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

STATE_HOME = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
CACHE_HOME = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
USAGE_DIR = STATE_HOME / "omarchy/agents/usage"
REFRESH_STAMP = CACHE_HOME / "herdr-agent-usage/refresh.stamp"

# A record older than this gets a background refresh; one older than STALE_AFTER
# means refreshing has been failing, so its numbers are marked as old.
REFRESH_AFTER = 180
STALE_AFTER = 600

# Omarchy keeps the last numbers when the saved sign-in lapses and says so here.
AUTH_STATUSES = {"Sign-in expired", "Waiting for auth"}

DIM, YELLOW, RED, RESET = "\033[2m", "\033[33m", "\033[31m", "\033[0m"


def parse_time(raw: str) -> dt.datetime | None:
  try:
    value = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
  except (AttributeError, ValueError):
    return None
  return value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)


def short_label(label: str) -> str:
  lower = label.lower()
  if "5-hour" in lower or "session" in lower:
    return "5h"
  if "7-day" in lower or "weekly" in lower:
    return "wk"
  return lower.split(" ")[0] if lower else "?"


def short_duration(seconds: float) -> str:
  minutes = max(1, int(seconds // 60))
  if minutes < 60:
    return f"{minutes}m"
  hours, minutes = divmod(minutes, 60)
  if hours < 24:
    return f"{hours}h{minutes:02d}m" if minutes else f"{hours}h"
  return f"{hours // 24}d"


def paint(text: str, code: str, color: bool) -> str:
  return f"{code}{text}{RESET}" if color and code else text


def format_limit(limit: dict, now: dt.datetime, color: bool) -> str:
  percent = float(limit.get("percent") or 0)
  resets_at = parse_time(limit.get("resetsAt") or "")
  # A window whose reset has passed has started over, whatever the record says.
  if resets_at and resets_at <= now:
    percent, resets_at = 0.0, None

  text = f"{short_label(limit.get('label', ''))} {round(percent * 100)}%"
  # Only the near reset is worth the room; a weekly reset days away is noise.
  if resets_at and (resets_at - now).total_seconds() < 86400:
    text += f" ↻{short_duration((resets_at - now).total_seconds())}"

  code = RED if percent >= 0.8 else YELLOW if percent >= 0.5 else DIM
  return paint(text, code, color)


def format_agent(record: dict, now: dt.datetime, color: bool) -> str | None:
  agent = record.get("id") or "?"
  if record.get("usageStatusText") in AUTH_STATUSES:
    return paint(f"{agent} login", RED, color)

  limits = [limit for limit in record.get("limits") or [] if isinstance(limit, dict)]
  if not limits:
    return None

  updated_at = parse_time(record.get("updatedAt") or "")
  if updated_at is None or (now - updated_at).total_seconds() > STALE_AFTER:
    # Old numbers are dimmed as a whole rather than coloured as if they were current.
    body = " · ".join(format_limit(limit, now, color=False) for limit in limits)
    return paint(f"{agent}* {body}", DIM, color)
  return f"{agent} " + " · ".join(format_limit(limit, now, color) for limit in limits)


def load_records(usage_dir: Path, hidden: set[str]) -> list[dict]:
  records = []
  for path in sorted(usage_dir.glob("*.json")):
    try:
      record = json.loads(path.read_text())
    except (OSError, ValueError):
      continue
    if isinstance(record, dict) and record.get("id") not in hidden:
      records.append(record)
  return records


def render(records: list[dict], now: dt.datetime, color: bool) -> str:
  segments = [segment for record in records if (segment := format_agent(record, now, color))]
  return " │ ".join(segments)


def needs_refresh(records: list[dict], now: dt.datetime) -> list[str]:
  due = []
  for record in records:
    if not record.get("limits"):
      continue
    updated_at = parse_time(record.get("updatedAt") or "")
    if updated_at is None or (now - updated_at).total_seconds() > REFRESH_AFTER:
      due.append(record["id"])
  return due


def refresh(agents: list[str], stamp: Path) -> None:
  # Every herdr instance runs this on its own timer, so a shared stamp keeps them
  # from piling up probes; Omarchy's own reuse window and 429 handling do the rest.
  try:
    if time.time() - stamp.stat().st_mtime < REFRESH_AFTER:
      return
  except OSError:
    pass
  try:
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.touch()
    subprocess.Popen(
      ["omarchy", "agent", "usage-update", "--limits-only", *agents],
      stdin=subprocess.DEVNULL,
      stdout=subprocess.DEVNULL,
      stderr=subprocess.DEVNULL,
      start_new_session=True,
    )
  except OSError:
    pass


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
  parser.add_argument("--color", action="store_true", help="colour segments with ANSI codes")
  parser.add_argument("--hide", default="", help="comma-separated agent ids to leave out")
  parser.add_argument("--no-refresh", action="store_true", help="never trigger an Omarchy refresh")
  parser.add_argument("--usage-dir", type=Path, default=USAGE_DIR, help=argparse.SUPPRESS)
  args = parser.parse_args(argv)

  hidden = {agent.strip() for agent in args.hide.split(",") if agent.strip()}
  now = dt.datetime.now(dt.timezone.utc)
  records = load_records(args.usage_dir, hidden)

  if not args.no_refresh and (due := needs_refresh(records, now)):
    refresh(due, REFRESH_STAMP)

  # herdr shows the last stdout line; an empty one hides the entry.
  print(render(records, now, args.color))
  return 0


if __name__ == "__main__":
  sys.exit(main())
