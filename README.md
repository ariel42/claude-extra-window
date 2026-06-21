# claude-extra-window

A lightweight systemd service that gives you an extra Claude Code usage window by keeping a background session ticking around the clock, so a fresh full window is always imminent when you sit down to work.

## Background

Claude Code subscriptions operate within a rolling 5-hour usage window. If you have not been using Claude Code, the window has not started — it begins the moment you open a session and runs from there. Start working at 9 am with no prior activity, and by 2 pm you may hit the limit in the middle of your most productive hours.

This tool runs a minimal background session around the clock, sending a short ping every 59 minutes. By the time you sit down to work, two things are true simultaneously:

1. **The current usage window is nearly expired.** It has been ticking since the overnight session began, so a fresh full 5-hour window is imminent — often within the next hour.
2. **The current window is nearly untouched.** Because each run reuses the exact same frozen 2-turn session and reads from Anthropic's prompt cache, actual token consumption overnight is negligible. The window is old in time, but still almost entirely full in capacity.

The result is two adjacent periods of effectively full capacity: the barely-consumed remainder of the current window, immediately followed by the fresh window that resets shortly after you start. You open your own new work session as normal; the background session runs entirely in the background and is never something you interact with directly.

## How it works

1. **Setup** creates a frozen checkpoint: a single interactive Claude session containing just `hi` → response. The session file is backed up at this state and never modified again.
2. **Every 59 minutes**, the systemd timer runs the script, which:
   - Restores the session file to the frozen checkpoint (always just the original `hi` state)
   - Resumes that session and sends `how are you?`
   - Exits cleanly
3. Because the checkpoint is always restored before resuming, the server sees a fixed 2-turn context on every run — messages never accumulate, and token cost stays constant regardless of how long the tool has been running.

The 59-minute interval is deliberate: Anthropic caches session context for one hour. Running just under that threshold keeps the cache warm on every ping, so the cached system prompt is read rather than reprocessed on each run.

Sessions run in **interactive mode** (not `--print`), so they count against the subscription usage window rather than API billing.

## Features

- **Minimal token cost** — `--tools ""` strips tool definitions from the system prompt; Anthropic's 1-hour prompt cache is kept warm by the 59-minute interval, so each run reads from cache rather than reprocessing
- **Constant context size** — a frozen checkpoint is restored before every run, so the server always sees exactly the same 2-turn session; context never grows no matter how long the tool has been running
- **Single reused session** — the same session ID is used on every run; the session history on disk is always restored to the frozen `hi` state before resuming, so there is effectively no accumulation
- **Automatic log rotation** — log trimmed to the last 48 hours on each run, with run separators preserved
- **No dependencies** — pure Python standard library; no pip installs required
- **Fully generic** — all paths are derived at runtime from the script location and current user; no hardcoded values

## Requirements

- Linux with systemd
- Python 3.6 or later
- [Claude Code CLI](https://claude.ai/download) installed and authenticated

## Quick start

```bash
git clone <repo-url>
cd claude-extra-window

chmod +x install.sh uninstall.sh
./install.sh
```

`install.sh` handles everything in one step: prerequisite checks, checkpoint session creation, and systemd deployment. The timer starts immediately and runs every 59 minutes.

## Files

| File | Purpose |
|---|---|
| `claude_extra_window.py` | Main script. Runs as the systemd service; `--init` flag for setup. |
| `install.sh` | One-step install: prereq checks, checkpoint init, systemd deployment. |
| `uninstall.sh` | Removes the systemd units. Runtime files are left in place. |

### Runtime files (gitignored, created by install.sh)

| File | Purpose |
|---|---|
| `extra_window_session_id.txt` | UUID of the checkpoint session. |
| `extra_window_checkpoint.jsonl.bak` | Backup of the frozen `hi` session state. |
| `claude_extra_window.log` | Rolling 48-hour log. |

## Resetting the checkpoint

To start fresh (e.g. if the session becomes invalid):

```bash
rm extra_window_session_id.txt extra_window_checkpoint.jsonl.bak
./install.sh
```

## Uninstalling

```bash
./uninstall.sh
```

To also remove runtime files (checkpoint, session ID, log):

```bash
rm -f extra_window_session_id.txt extra_window_checkpoint.jsonl.bak claude_extra_window.log
```

## Notes

- This tool is not affiliated with or endorsed by Anthropic.
- It relies on the Claude Code CLI's session storage format (`~/.claude/projects/`), which is an implementation detail that may change in future versions.
- Only tested on Linux with systemd. Does not support macOS launchd or Windows.

## License

[MIT](LICENSE)
