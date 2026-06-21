#!/usr/bin/env bash
# uninstall.sh — remove claude-extra-window systemd units.
# Runtime files (checkpoint, session ID, log) are left in place.
set -euo pipefail

SYSTEMD_DIR="/etc/systemd/system"

echo "Claude Code Extra Window — Uninstall"
echo "======================================"

sudo systemctl stop claude-extra-window.timer 2>/dev/null && echo "Stopped timer." || true
sudo systemctl disable claude-extra-window.timer 2>/dev/null && echo "Disabled timer." || true
sudo rm -f "$SYSTEMD_DIR/claude-extra-window.service" \
           "$SYSTEMD_DIR/claude-extra-window.timer"
sudo systemctl daemon-reload

echo ""
echo "Uninstalled successfully."
echo ""
echo "Runtime files were left in place. To remove them:"
echo "  rm -f extra_window_session_id.txt extra_window_checkpoint.jsonl.bak claude_extra_window.log"
