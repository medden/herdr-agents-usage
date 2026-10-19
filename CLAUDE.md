# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```sh
python3 -m unittest discover -s tests                     # all tests
python3 -m unittest tests.test_agent_usage.FormatTest.test_fresh_record   # one test
./agent_usage.py --no-refresh [--color]                   # live output without triggering a refresh
./install.py --config /path/to/copy.toml                  # try the installer on a copy, not the real config
```

Python 3.11+ standard library only (`tomllib`); there are no dependencies or build step.

## How it fits together

- herdr runs `agent_usage.py` as a `type = "command"` entry in `[ui] tab_bar_right` of `~/.config/herdr/config.toml`. herdr uses only the last stdout line, an empty line hides the entry, and a herdr plugin cannot add tab-bar widgets itself, which is why `install.py` edits `config.toml`.
- Data comes only from Omarchy's per-agent records in `~/.local/state/omarchy/agents/usage/<agent>.json`, which `/usr/share/omarchy/bin/omarchy-agent-usage-<agent>` collectors write. Freshness is driven by spawning `omarchy agent usage-update --limits-only <ids>`. This project must not read credentials, call usage APIs, or edit anything under `/usr/share/omarchy` or Omarchy's state dir.
- Expired Claude sign-in is signalled by `usageStatusText` (`"Sign-in expired"`, `"Waiting for auth"`), not by `ready`. Omarchy keeps `ready: true` and the last limits in that case.
- `install.py` identifies its own entry by this checkout's absolute script path. Moving the checkout needs `./install.py` re-run (and the old entry removed by hand).

## Background

`code-brief.MD` is the original brief. The design was modelled on `speardragon/herdr-status-ui-bar` (installed under `~/.config/herdr/plugins/github/`) and Omarchy's agents plugin (`/usr/share/omarchy/shell/plugins/agents/`).
