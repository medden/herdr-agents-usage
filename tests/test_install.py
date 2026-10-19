import sys
import tomllib
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import install

SCRIPT = Path("/opt/herdr-agent-usage/agent_usage.py")

CONFIG = """[ui]
accent = "blue"

tab_bar_right = [
  { type = "zoom" },
  { type = "command", command = "~/.config/herdr/agent-usage/agent_usage.py", interval_seconds = 300, timeout_seconds = 5 },
]

window_title = "{hostname}: {workspace}"
"""


def right(text: str) -> list[dict]:
  return tomllib.loads(text)["ui"]["tab_bar_right"]


class InstallTest(unittest.TestCase):
  def test_appends_after_existing_entries(self):
    entries = right(install.install(CONFIG, SCRIPT))
    self.assertEqual(len(entries), 3)
    self.assertEqual(entries[0], {"type": "zoom"})
    self.assertEqual(entries[-1]["command"], str(SCRIPT))
    self.assertEqual(entries[-1]["interval_seconds"], 60)

  def test_is_idempotent_and_updates_args(self):
    once = install.install(CONFIG, SCRIPT)
    self.assertEqual(install.install(once, SCRIPT), once)
    entries = right(install.install(once, SCRIPT, "--color"))
    self.assertEqual(len(entries), 3)
    self.assertEqual(entries[-1]["command"], f"{SCRIPT} --color")

  def test_uninstall_restores_original(self):
    self.assertEqual(install.uninstall(install.install(CONFIG, SCRIPT), SCRIPT), CONFIG)

  def test_creates_array_when_missing(self):
    entries = right(install.install('[ui]\naccent = "blue"\n', SCRIPT))
    self.assertEqual([e["command"] for e in entries], [str(SCRIPT)])
    self.assertEqual(right(install.install("", SCRIPT))[0]["command"], str(SCRIPT))

  def test_keeps_keys_after_the_array(self):
    parsed = tomllib.loads(install.install(CONFIG, SCRIPT))
    self.assertEqual(parsed["ui"]["window_title"], "{hostname}: {workspace}")


if __name__ == "__main__":
  unittest.main()
