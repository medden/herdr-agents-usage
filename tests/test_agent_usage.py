import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agent_usage as au

EMPTY, S1, S2, S4 = au.DIAL_EMPTY, *(au.DIAL_SLICES[i] for i in (0, 1, 3))

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
    self.assertEqual(au.render([claude()], NOW), f"claude {S2} 5h 19% ↻1h20m · {S1} wk 6%")

  def test_stale_record_is_marked(self):
    line = au.render([claude(updated=dt.timedelta(minutes=-30))], NOW)
    self.assertEqual(line, f"claude* {S2} 5h 19% ↻1h20m · {S1} wk 6%")

  def test_expired_sign_in_shows_login(self):
    record = claude(usageStatusText="Sign-in expired")
    self.assertEqual(au.render([record], NOW), "claude login")

  def test_passed_reset_reads_zero(self):
    record = claude()
    record["limits"][0]["resetsAt"] = iso(dt.timedelta(minutes=-5))
    self.assertEqual(au.render([record], NOW), f"claude {EMPTY} 5h 0% · {S1} wk 6%")

  def test_agents_without_limits_are_skipped(self):
    codex = {"id": "codex", "ready": True, "limits": []}
    fireworks = {"id": "fireworks", "ready": False, "limits": [], "usageStatusText": "Fireworks unavailable"}
    self.assertEqual(au.render([codex, fireworks], NOW), "")

  def test_several_agents_are_joined(self):
    other = claude(session=0.5)
    other["id"] = "codex"
    self.assertEqual(
      au.render([claude(), other], NOW),
      f"claude {S2} 5h 19% ↻1h20m · {S1} wk 6% │ codex {S4} 5h 50% ↻1h20m · {S1} wk 6%",
    )

  def test_rounds_half_up_like_omarchy(self):
    self.assertEqual(au.render([claude(session=0.125)], NOW), f"claude {S1} 5h 13% ↻1h20m · {S1} wk 6%")

  def test_dial_steps(self):
    self.assertEqual(au.dial(0), au.DIAL_EMPTY)
    self.assertEqual(au.dial(0.01), au.DIAL_SLICES[0])
    self.assertEqual(au.dial(0.5), au.DIAL_SLICES[3])
    self.assertEqual(au.dial(0.51), au.DIAL_SLICES[4])
    self.assertEqual(au.dial(1.2), au.DIAL_SLICES[7])

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
