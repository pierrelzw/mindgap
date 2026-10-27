#!/usr/bin/env bash
# Register mindgap with launchd. Usage: ./install.sh [--dry-run] [--yes]
#   --dry-run  print the plist and what would happen, change nothing
#   --yes      do not ask for confirmation
set -euo pipefail

DRY=0; YES=0
for a in "$@"; do case "$a" in --dry-run) DRY=1;; --yes) YES=1;; *) echo "unknown arg: $a" >&2; exit 2;; esac; done

REPO="$(cd "$(dirname "$0")" && pwd)"
LABEL=com.mindgap.daily
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"

find_bin() {  # name -> absolute path; PATH first, then mise
  local p; p="$(command -v "$1" 2>/dev/null || true)"
  [ -z "$p" ] && command -v mise >/dev/null 2>&1 && p="$(mise which "$1" 2>/dev/null || true)"
  [ -n "$p" ] || { echo "找不到 $1" >&2; exit 1; }
  echo "$p"
}
CLAUDE="$(find_bin claude)"; PY="$(find_bin python3)"; UVX="$(find_bin uvx)"
NOTIFIER=/opt/homebrew/bin/terminal-notifier
[ -x "$NOTIFIER" ] || { echo "找不到 $NOTIFIER（brew install terminal-notifier）" >&2; exit 1; }

# claude's directory also holds `node`, which user-level plugin hooks need under launchd.
PATH_VALUE=""
for d in "$(dirname "$CLAUDE")" "$(dirname "$PY")" "$(dirname "$UVX")" /opt/homebrew/bin /usr/bin /bin /usr/sbin /sbin; do
  case ":$PATH_VALUE:" in *":$d:"*) ;; *) PATH_VALUE="${PATH_VALUE:+$PATH_VALUE:}$d";; esac
done
[ -x "$(dirname "$CLAUDE")/node" ] || echo "警告: $(dirname "$CLAUDE") 里没有 node，插件 hook 可能报 'node: command not found'" >&2

ARCHIVE="$("$PY" -c "import sys; sys.path.insert(0,'$REPO'); from mindgap.config import load_config; print(load_config().archive)")"
mkdir -p "$ARCHIVE/logs" "$HOME/Library/LaunchAgents"

TMP="$(mktemp)"
sed -e "s|@PYTHON@|$PY|g" -e "s|@REPO@|$REPO|g" -e "s|@PATH@|$PATH_VALUE|g" \
    -e "s|@HOME@|$HOME|g" -e "s|@ARCHIVE@|$ARCHIVE|g" "$REPO/launchd/$LABEL.plist.template" > "$TMP"
plutil -lint "$TMP" >/dev/null

echo "claude   : $CLAUDE"
echo "python3  : $PY"
echo "uvx      : $UVX"
echo "archive  : $ARCHIVE"
echo "plist    : $DEST"
echo "PATH     : $PATH_VALUE"
if [ "$DRY" = 1 ]; then echo "--- plist ---"; cat "$TMP"; rm -f "$TMP"; exit 0; fi

if [ "$YES" != 1 ]; then
  read -r -p "注册 launchd 任务 $LABEL（每 60 秒运行一次 tick）？[y/N] " ans
  [ "$ans" = y ] || [ "$ans" = Y ] || { echo "已取消"; rm -f "$TMP"; exit 1; }
fi

cp "$TMP" "$DEST"; rm -f "$TMP"
launchctl bootout "gui/$UID/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$UID" "$DEST"
launchctl kickstart -k "gui/$UID/$LABEL"
echo "已注册。查看: launchctl print gui/$UID/$LABEL | grep -E 'state|last exit'"
echo "日志: $ARCHIVE/logs/tick.log"
if ! "$NOTIFIER" -diagnose >/dev/null 2>&1; then
  echo "通知可能未授权：运行 'open -a terminal-notifier'，并在 系统设置 > 通知 里允许 terminal-notifier。"
fi
