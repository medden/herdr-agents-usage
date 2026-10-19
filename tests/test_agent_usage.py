import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agent_usage as au

NOW = dt.datetime(2026, 10, 19, 13, 0, tzinfo=dt.timezone.utc)


def iso(delta: dt.timedelta) -> str:
  return (NOW + delta).isoformat()


def claude(session=0.19, weekly=0.06, updated=dt.timedelta(minutes=-1), **extra) -> dict:
  return {
    "id": "claude",
    "ready": True,
    "updatedAt": iso(updated),
    "usageStatusText": "",
    "limits": [
      {"label": "Session (5-hour)", "percent": session, "resetsAt": iso(dt.timedelta(hours=1, minutes=20))},
      {"label": "Weekly (7-day)", "percent": weekly, "resetsAt": iso(dt.timedelta(days=2, hours=5))},
    ],
    **extra,
  }


class FormatTest(unittest.TestCase):
  def test_fresh_record(self):
    self.assertEqual(au.render([claude()], NOW, color=False), "claude 5h 19% ↻1h20m · wk 6%")

  def test_stale_record_is_marked(self):
    line = au.render([claude(updated=dt.timedelta(minutes=-30))], NOW, color=False)
    self.assertEqual(line, "claude* 5h 19% ↻1h20m · wk 6%")

  def test_expired_sign_in_shows_login(self):
    record = claude(usageStatusText="Sign-in expired")
    self.assertEqual(au.render([record], NOW, color=False), "claude login")

  def test_passed_reset_reads_zero(self):
    record = claude()
    record["limits"][0]["resetsAt"] = iso(dt.timedelta(minutes=-5))
    self.assertEqual(au.render([record], NOW, color=False), "claude 5h 0% · wk 6%")

  def test_agents_without_limits_are_skipped(self):
    codex = {"id": "codex", "ready": True, "limits": []}
    fireworks = {"id": "fireworks", "ready": False, "limits": [], "usageStatusText": "Fireworks unavailable"}
    self.assertEqual(au.render([codex, fireworks], NOW, color=False), "")

  def test_several_agents_are_joined(self):
    other = claude(session=0.5)
    other["id"] = "codex"
    self.assertEqual(
      au.render([claude(), other], NOW, color=False),
      "claude 5h 19% ↻1h20m · wk 6% │ codex 5h 50% ↻1h20m · wk 6%",
    )

  def test_colour_thresholds(self):
    line = au.render([claude(session=0.85, weekly=0.55)], NOW, color=True)
    self.assertIn(f"{au.RED}5h 85%", line)
    self.assertIn(f"{au.YELLOW}wk 55%", line)

  def test_stale_colour_is_dimmed_whole(self):
    line = au.render([claude(session=0.85, updated=dt.timedelta(hours=-1))], NOW, color=True)
    self.assertEqual(line, f"{au.DIM}claude* 5h 85% ↻1h20m · wk 6%{au.RESET}")

  def test_durations(self):
    self.assertEqual(au.short_duration(30), "1m")
    self.assertEqual(au.short_duration(42 * 60), "42m")
    self.assertEqual(au.short_duration(3 * 3600), "3h")
    self.assertEqual(au.short_duration(3 * 86400), "3d")


class RecordsTest(unittest.TestCase):
  def test_load_skips_hidden_and_broken_files(self):
    with tempfile.TemporaryDirectory() as tmp:
      usage = Path(tmp)
      (usage / "claude.json").write_text(json.dumps(claude()))
      (usage / "codex.json").write_text(json.dumps({"id": "codex", "limits": []}))
      (usage / "broken.json").write_text("{not json")
      ids = [record["id"] for record in au.load_records(usage, hidden={"codex"})]
    self.assertEqual(ids, ["claude"])

  def test_refresh_only_for_old_records_with_limits(self):
    old = claude(updated=dt.timedelta(minutes=-5))
    fresh = dict(claude(), id="fresh")
    empty = {"id": "codex", "limits": [], "updatedAt": iso(dt.timedelta(hours=-5))}
    self.assertEqual(au.needs_refresh([old, fresh, empty], NOW), ["claude"])


if __name__ == "__main__":
  unittest.main()
