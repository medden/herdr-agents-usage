# Agent Usage for herdr

Shows subscription usage for your AI agents in herdr's tab bar:

```
claude 󰪟 5h 19% ↻1h20m · 󰪞 wk 6%
```

The numbers come from Omarchy's agent usage records (`~/.local/state/omarchy/agents/usage/*.json`), so any agent Omarchy has a collector for shows up without changes here. An agent with no limits is skipped. When a record is more than 3 minutes old, the script runs `omarchy agent usage-update --limits-only <agents>` in the background. It never reads credentials or calls a usage API itself.

| Shown | Meaning |
| --- | --- |
| `󰪟` | dial filling in eighths as the window is used (needs a Nerd Font) |
| `↻1h20m` | time until that window resets (only shown when under a day) |
| `claude*` | record older than 10 minutes; refreshing is failing |
| `claude login` | Claude Code's saved sign-in expired; start Claude Code or run `claude auth login` |

## Requirements

Omarchy (for the usage records and the `omarchy` command), herdr ≥ 0.9, and Python 3.11+.

## Install

```sh
git clone https://github.com/medden/herdr-agents-usage
cd herdr-agents-usage
herdr plugin link "$PWD"
herdr plugin action invoke simrog.agent-usage.install
```

Or run `./install.py` directly. Options it does not know are passed on to the script, for example `./install.py --hide codex`. Running it again replaces its own entry. `./install.py --uninstall` removes it. Before changing `~/.config/herdr/config.toml`, it saves a backup next to it (`config.toml.bak-agent-usage-*`).

## Options

- `--hide a,b`: leave out agent ids
- `--no-refresh`: only read records, never trigger an Omarchy refresh
