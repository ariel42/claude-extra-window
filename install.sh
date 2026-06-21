#!/usr/bin/env bash
# install.sh — set up and deploy claude-extra-window.
# Creates the initial checkpoint session if needed, then installs the systemd timer.
# Requires sudo for the systemd steps.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURRENT_USER="$(whoami)"
SYSTEMD_DIR="/etc/systemd/system"

echo "Claude Code Extra Window — Install"
echo "===================================="

# ── Prerequisites ────────────────────────────────────────────────────────────

if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Install Python 3.6 or later." >&2
    exit 1
fi
python3 - <<'EOF'
import sys
if sys.version_info < (3, 6):
    print(f"ERROR: Python 3.6+ required (found {sys.version})", file=sys.stderr)
    sys.exit(1)
EOF

CLAUDE_BIN="$(command -v claude 2>/dev/null || echo "$HOME/.local/bin/claude")"
if [ ! -x "$CLAUDE_BIN" ]; then
    echo "ERROR: Claude Code CLI not found." >&2
    echo "       Install it from: https://claude.ai/download" >&2
    exit 1
fi

if ! command -v sudo &>/dev/null; then
    echo "ERROR: sudo is required to write to $SYSTEMD_DIR." >&2
    exit 1
fi

echo "  python : $(python3 --version)"
echo "  claude : $("$CLAUDE_BIN" --version 2>/dev/null || echo 'version unknown')"
echo ""

# ── Checkpoint session (one-time) ────────────────────────────────────────────

if [ -f "$SCRIPT_DIR/extra_window_session_id.txt" ] && \
   [ -f "$SCRIPT_DIR/extra_window_checkpoint.jsonl.bak" ]; then
    echo "Checkpoint already exists (session $(head -c 8 "$SCRIPT_DIR/extra_window_session_id.txt")...) — skipping init."
else
    echo "Creating checkpoint session (opens an interactive Claude session briefly)..."
    cd "$SCRIPT_DIR"
    python3 claude_extra_window.py --init

    if [ ! -f "$SCRIPT_DIR/extra_window_session_id.txt" ] || \
       [ ! -f "$SCRIPT_DIR/extra_window_checkpoint.jsonl.bak" ]; then
        echo "ERROR: Checkpoint creation failed. See log for details:" >&2
        echo "  $SCRIPT_DIR/claude_extra_window.log" >&2
        exit 1
    fi
    echo "Checkpoint created: $(cat "$SCRIPT_DIR/extra_window_session_id.txt")"
fi
echo ""

# ── Systemd deployment ───────────────────────────────────────────────────────

echo "Deploying systemd service and timer..."

sudo tee "$SYSTEMD_DIR/claude-extra-window.service" > /dev/null << EOF
[Unit]
Description=Claude Code Extra Window
After=network.target

[Service]
Type=oneshot
User=$CURRENT_USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=/usr/bin/python3 $SCRIPT_DIR/claude_extra_window.py
Environment=HOME=$HOME
Environment=PATH=$HOME/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
Environment=TERM=xterm-256color
Environment=USER=$CURRENT_USER
Environment=SHELL=/bin/bash

[Install]
WantedBy=multi-user.target
EOF

sudo tee "$SYSTEMD_DIR/claude-extra-window.timer" > /dev/null << 'EOF'
[Unit]
Description=Claude Code Extra Window — ping every 59 minutes

[Timer]
OnBootSec=1min
OnUnitActiveSec=59min

[Install]
WantedBy=timers.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable claude-extra-window.timer
sudo systemctl restart claude-extra-window.timer

# ── Done ─────────────────────────────────────────────────────────────────────

echo ""
echo "Installed successfully."
echo ""
systemctl status claude-extra-window.timer --no-pager
echo ""
echo "Logs : $SCRIPT_DIR/claude_extra_window.log"
echo ""
echo "To reset the checkpoint:  rm extra_window_session_id.txt extra_window_checkpoint.jsonl.bak && ./install.sh"
echo ""
echo "To uninstall:  ./uninstall.sh"
