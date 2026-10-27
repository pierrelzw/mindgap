#!/usr/bin/env bash
# Unregister the mindgap launchd job. The archive and work files are left untouched.
set -euo pipefail
LABEL=com.mindgap.daily
launchctl bootout "gui/$UID/$LABEL" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/$LABEL.plist"
echo "已卸载 $LABEL"
