"""macOS notification via terminal-notifier. In -open mode it hands off to the system and exits."""
from __future__ import annotations

import subprocess
from pathlib import Path

from .config import Config


def notify(cfg: Config, title: str, message: str, open_url: str | None, log) -> int | None:
    """Fire and forget. Returns the exit code, or None if still running after 5 s (never killed)."""
    if not cfg.notify:
        return 0
    if not Path(cfg.notifier_bin).exists():
        log.warning("找不到 terminal-notifier: %s", cfg.notifier_bin)
        return 127
    cmd = [cfg.notifier_bin, "-title", title, "-message", message or " ", "-group", "mindgap", "-sound", "Glass"]
    if open_url:
        cmd += ["-open", open_url]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, start_new_session=True, text=True)
        rc = proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        log.info("通知进程 5 秒后仍在运行（可能在等待授权），不再等待")
        return None
    except OSError as e:
        log.warning("通知失败: %s", e)
        return 127
    if rc != 0:
        log.warning("terminal-notifier 退出码 %s: %s", rc, (proc.stderr.read() if proc.stderr else "")[:200])
    return rc


def notify_ok(cfg: Config, day: str, analysis: dict, html_path: Path, log):
    return notify(cfg, f"mindgap {day} · {analysis['blindspot']['label_zh']}", analysis["one_liner"], html_path.resolve().as_uri(), log)


def notify_insufficient(cfg: Config, day: str, n: int, html_path: Path, log):
    return notify(cfg, f"mindgap {day} · 数据不足", f"有效 prompt {n} 条 < {cfg.min_prompts}，未生成诊断", html_path.resolve().as_uri(), log)


def notify_failure(cfg: Config, day: str, stage: str, log_path: Path, log):
    return notify(cfg, f"mindgap {day} 失败", f"mindgap 失败：{stage}，日志见 {log_path}", log_path.resolve().as_uri(), log)
