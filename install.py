#!/usr/bin/env python3
"""Add (or with --uninstall, remove) the agent usage entry in herdr's tab_bar_right.

Only the entry pointing at this checkout's agent_usage.py is touched; every
other entry is kept as written. config.toml is backed up before it changes.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
import tomllib
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "agent_usage.py"
CONFIG = Path(os.environ.get("HERDR_CONFIG_DIR") or Path.home() / ".config/herdr") / "config.toml"


def entry(script: Path, extra_args: str = "") -> str:
  command = f"{script} {extra_args}".strip()
  return f'{{ type = "command", command = "{command}", interval_seconds = 60, timeout_seconds = 5 }}'


def find_array(text: str) -> tuple[int, int] | None:
  """(content_start, content_end) of `tab_bar_right = [...]`, brackets excluded."""
  match = re.search(r"^tab_bar_right\s*=\s*\[", text, re.MULTILINE)
  if not match:
    return None
  depth, pos, quoted = 1, match.end(), False
  while pos < len(text) and depth:
    char = text[pos]
    if char == '"' and text[pos - 1] != "\\":
      quoted = not quoted
    elif not quoted and char == "[":
      depth += 1
    elif not quoted and char == "]":
      depth -= 1
    pos += 1
  return (match.end(), pos - 1) if depth == 0 else None


def without_ours(body: str, script: Path) -> str:
  return "".join(line for line in body.splitlines(keepends=True) if str(script) not in line)


def install(text: str, script: Path, extra_args: str = "") -> str:
  span = find_array(text)
  line = f"  {entry(script, extra_args)},\n"
  if span is None:
    ui = re.search(r"^\[ui\][^\n]*\n", text, re.MULTILINE)
    block = f"tab_bar_right = [\n{line}]\n"
    if ui is None:
      return text.rstrip("\n") + f"\n\n[ui]\n{block}"
    return text[: ui.end()] + block + text[ui.end() :]
  start, end = span
  body = without_ours(text[start:end], script)
  if body and not body.endswith("\n"):
    body += "\n"
  if not body.startswith("\n"):
    body = "\n" + body
  return text[:start] + body + line + text[end:]


def uninstall(text: str, script: Path) -> str:
  span = find_array(text)
  if span is None:
    return text
  start, end = span
  return text[:start] + without_ours(text[start:end], script) + text[end:]


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
  parser.add_argument("--uninstall", action="store_true")
  parser.add_argument("--args", default="", help="extra agent_usage.py arguments, e.g. '--color --hide codex'")
  parser.add_argument("--config", type=Path, default=CONFIG)
  args = parser.parse_args(argv)

  text = args.config.read_text() if args.config.exists() else ""
  new = uninstall(text, SCRIPT) if args.uninstall else install(text, SCRIPT, args.args)
  if new == text:
    print(f"{args.config}: unchanged")
    return 0
  try:
    tomllib.loads(new)
  except tomllib.TOMLDecodeError as exc:
    print(f"error: refusing to write invalid TOML ({exc})", file=sys.stderr)
    return 1

  if args.config.exists():
    shutil.copy2(args.config, f"{args.config}.bak-agent-usage-{time.strftime('%Y%m%d%H%M%S')}")
  args.config.parent.mkdir(parents=True, exist_ok=True)
  args.config.write_text(new)
  print(f"{args.config}: {'removed' if args.uninstall else 'installed'} agent usage entry")

  herdr = os.environ.get("HERDR_BIN_PATH") or "herdr"
  try:
    reloaded = subprocess.run([herdr, "server", "reload-config"], capture_output=True).returncode == 0
  except OSError:
    reloaded = False
  print("herdr: config reloaded" if reloaded else "herdr: not reloaded; restart herdr to apply")
  return 0


if __name__ == "__main__":
  sys.exit(main())
