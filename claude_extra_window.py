"""
Claude Code Extra Window
Keeps a Claude Code usage window ticking in the background so that a fresh full
window is always imminent when you sit down to work. Requires Python 3.6+,
Linux, and the Claude Code CLI.

Usage:
  python3 claude_extra_window.py --init   # one-time setup (called by install.sh)
  python3 claude_extra_window.py          # extra-window run (called by systemd timer)
"""

import os
import pty
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Paths — all derived from the script's own location, no hardcoded user paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HOME       = os.path.expanduser("~")
USER       = os.environ.get("USER") or os.environ.get("LOGNAME") or "user"

# Claude CLI: prefer PATH lookup, fall back to ~/.local/bin/claude
CLAUDE_PATH = shutil.which("claude") or os.path.join(HOME, ".local", "bin", "claude")

# Claude Code stores session files under ~/.claude/projects/<cwd-as-path>/
# where every "/" in the cwd is replaced with "-".
SESSION_DIR = os.path.join(
    HOME, ".claude", "projects", SCRIPT_DIR.replace("/", "-")
)

LOG_FILE          = os.path.join(SCRIPT_DIR, "claude_extra_window.log")
SESSION_ID_FILE   = os.path.join(SCRIPT_DIR, "extra_window_session_id.txt")
CHECKPOINT_BACKUP = os.path.join(SCRIPT_DIR, "extra_window_checkpoint.jsonl.bak")

CLAUDE_ENV = {
    "HOME":  HOME,
    "PATH":  os.path.join(HOME, ".local", "bin")
             + ":/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    "TERM":  "xterm-256color",
    "USER":  USER,
    "SHELL": "/bin/bash",
}

LOG_RETENTION_HOURS = 48


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")
    print(line)


def rotate_log():
    if not os.path.exists(LOG_FILE):
        return
    cutoff = datetime.now() - timedelta(hours=LOG_RETENTION_HOURS)
    with open(LOG_FILE, "r") as f:
        lines = f.readlines()
    kept = []
    for line in lines:
        try:
            ts = datetime.strptime(line[1:20], "%Y-%m-%d %H:%M:%S")
            if ts >= cutoff:
                kept.append(line)
        except ValueError:
            if not line.strip():
                kept.append(line)  # preserve blank separator lines between runs
    with open(LOG_FILE, "w") as f:
        f.writelines(kept)


# ---------------------------------------------------------------------------
# Checkpoint backup / restore
# ---------------------------------------------------------------------------

def _session_file(session_id):
    return os.path.join(SESSION_DIR, f"{session_id}.jsonl")


def backup_checkpoint(session_id):
    src = _session_file(session_id)
    shutil.copy2(src, CHECKPOINT_BACKUP)
    log(f"Checkpoint backed up ({os.path.getsize(CHECKPOINT_BACKUP)} bytes)")


def restore_checkpoint(session_id):
    shutil.copy2(CHECKPOINT_BACKUP, _session_file(session_id))
    log("Checkpoint restored to frozen 'hi' state")


# ---------------------------------------------------------------------------
# Interactive Claude session (PTY)
# ---------------------------------------------------------------------------

def run_interactive(extra_args, prompt_text, startup_wait=6, response_wait=8):
    """
    Spawn an interactive Claude session in a PTY, send prompt_text, then /exit.
    Uses --tools "" to minimise the system-prompt token footprint.
    Returns True on clean exit (code 0), False otherwise.
    """
    if not os.path.isfile(CLAUDE_PATH):
        log(f"ERROR: Claude CLI not found at {CLAUDE_PATH}. "
            "Install Claude Code from https://claude.ai/download")
        return False

    master_fd, slave_fd = pty.openpty()
    cmd = [CLAUDE_PATH, "--tools", "", "--model", "haiku", "--effort", "low"] + extra_args

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            cwd=SCRIPT_DIR,
            preexec_fn=os.setsid,
            env=CLAUDE_ENV,
        )
    except Exception as e:
        log(f"ERROR: Failed to spawn Claude: {e}")
        os.close(master_fd)
        os.close(slave_fd)
        return False

    os.close(slave_fd)
    os.set_blocking(master_fd, False)

    time.sleep(startup_wait)
    try:
        os.read(master_fd, 8192)  # drain startup output
    except BlockingIOError:
        pass

    log(f"Sending: '{prompt_text}'")
    os.write(master_fd, (prompt_text + "\r").encode())

    time.sleep(response_wait)
    try:
        snippet = os.read(master_fd, 8192).decode("utf-8", errors="ignore")
        log(f"Response snippet: {snippet.replace(chr(10), ' ').strip()[:80]}")
    except BlockingIOError:
        log("Response buffer empty")

    os.write(master_fd, b"/exit\r")

    for _ in range(8):
        if proc.poll() is not None:
            break
        time.sleep(1)

    if proc.poll() is None:
        log("Process still running — sending SIGTERM")
        proc.terminate()
        proc.wait()

    try:
        os.close(master_fd)
    except OSError:
        pass

    log(f"Exited with code: {proc.returncode}")
    return proc.returncode == 0


# ---------------------------------------------------------------------------
# Init (one-time, called by install.sh)
# ---------------------------------------------------------------------------

def init():
    """
    Create the frozen checkpoint session with a single 'hi' message and back it up.
    Must be run once before the systemd timer starts. Called via --init flag.
    """
    if os.path.exists(SESSION_ID_FILE) and os.path.exists(CHECKPOINT_BACKUP):
        print("Checkpoint already exists.")
        print(f"  Session: {open(SESSION_ID_FILE).read().strip()}")
        print(f"  Backup:  {CHECKPOINT_BACKUP} "
              f"({os.path.getsize(CHECKPOINT_BACKUP)} bytes)")
        print("To reset, delete extra_window_session_id.txt and "
              "extra_window_checkpoint.jsonl.bak, then re-run ./install.sh.")
        return

    # Clean any partial state
    for f in (SESSION_ID_FILE, CHECKPOINT_BACKUP):
        if os.path.exists(f):
            os.remove(f)

    checkpoint_id = str(uuid.uuid4())
    log(f"Creating checkpoint session {checkpoint_id[:8]}... with 'hi'")

    ok = run_interactive(["--session-id", checkpoint_id], "hi")
    if not ok:
        log("ERROR: Failed to create checkpoint session.")
        sys.exit(1)

    with open(SESSION_ID_FILE, "w") as f:
        f.write(checkpoint_id)

    backup_checkpoint(checkpoint_id)
    log(f"Checkpoint ready: {checkpoint_id}")


# ---------------------------------------------------------------------------
# Extra-window run (called by systemd timer every 59 minutes)
# ---------------------------------------------------------------------------

def main():
    rotate_log()
    log("Starting extra-window run...")

    if not os.path.exists(SESSION_ID_FILE) or not os.path.exists(CHECKPOINT_BACKUP):
        log("ERROR: No checkpoint found. Run ./install.sh to initialise.")
        sys.exit(1)

    with open(SESSION_ID_FILE) as f:
        checkpoint_id = f.read().strip()

    # Restore the frozen 'hi' state so --resume always sees the same 2-message
    # context, regardless of what the previous run left behind.
    restore_checkpoint(checkpoint_id)

    log(f"Resuming checkpoint {checkpoint_id[:8]}... with 'how are you?'")
    run_interactive(["--resume", checkpoint_id], "how are you?")
    log("Extra-window run finished.\n")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if "--init" in sys.argv:
        init()
    else:
        main()
