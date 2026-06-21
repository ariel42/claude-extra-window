#!/usr/bin/env bash
# uninstall.sh — remove the claude-extra-window systemd *user* units.
# Runtime files (checkpoint, session ID, log) are left in place.
set -euo pipefail

CURRENT_USER="$(whoami)"
USER_UNIT_DIR="$HOME/.config/systemd/user"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"

echo "Claude Code Extra Window — Uninstall"
echo "======================================"

systemctl --user disable --now claude-extra-window.timer 2>/dev/null && echo "Disabled timer." || true
systemctl --user stop claude-extra-window.service 2>/dev/null || true
rm -f "$USER_UNIT_DIR/claude-extra-window.service" \
      "$USER_UNIT_DIR/claude-extra-window.timer"
systemctl --user daemon-reload 2>/dev/null || true

# Note: linger is intentionally left untouched. It is a per-user setting that other
# user services may also depend on, and we cannot tell whether this tool enabled it.
# To disable it manually (only if nothing else needs it): loginctl disable-linger $USER

echo ""
echo "Uninstalled successfully."
echo ""
echo "Runtime files were left in place. To remove them:"
echo "  rm -f extra_window_session_id.txt extra_window_checkpoint.jsonl.bak claude_extra_window.log"
