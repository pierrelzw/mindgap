"""Run the diagnostic prompt through `claude -p` and return a validated v2 analysis."""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import time
from pathlib import Path

from .config import Config, MindgapError, REPO, resolve_bin
from .schema import ANALYSIS_SCHEMA, validate
from .verify import problems, summary, verify_evidence

TEMPLATE_PATH = REPO / "prompts" / "analyze.txt"


def build_prompt(template: str, day: str, prompts: list[dict], feedback: str = "") -> str:
    slim = [{k: p[k] for k in ("id", "time", "project", "sessionId", "text")} for p in prompts]
    body = (template.replace("{{DATE}}", day)
            .replace("{{SCHEMA_JSON}}", json.dumps(ANALYSIS_SCHEMA, ensure_ascii=False, indent=1))
            .replace("{{PROMPTS_JSON}}", json.dumps(slim, ensure_ascii=False, indent=1)))
    if feedback:
        body += "\n\n==== 上一轮输出必须修正的问题 ====\n" + feedback + "\n请重新输出完整的 JSON 对象。\n"
    return body


def build_cmd(cfg: Config) -> list[str]:
    cmd = [resolve_bin("claude", cfg.claude_bin), "-p", "--output-format", "json",
           "--json-schema", json.dumps(ANALYSIS_SCHEMA, ensure_ascii=False),
           "--tools", cfg.tools,
           "--no-session-persistence", "--permission-mode", "dontAsk",
           "--max-budget-usd", str(cfg.max_budget_usd)]
    if cfg.tools:
        cmd += ["--allowedTools", cfg.tools]
    if cfg.model:
        cmd += ["--model", cfg.model]
    if cfg.fallback_model:
        cmd += ["--fallback-model", cfg.fallback_model]
    return cmd


def call_claude(prompt: str, cfg: Config, cwd: Path, log=None) -> tuple[int, str, str, float]:
    """Prompt goes via stdin: --tools/--allowedTools are variadic and would swallow a positional prompt."""
    cmd = build_cmd(cfg)
    cwd.mkdir(parents=True, exist_ok=True)
    (cwd / "analyze-cmd.txt").write_text(" ".join(repr(c) if (not c or " " in c or "{" in c) else c for c in cmd), encoding="utf-8")
    t0 = time.time()
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, cwd=str(cwd), start_new_session=True)
    try:
        out, err = proc.communicate(prompt, timeout=cfg.timeout_s)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        out, err = proc.communicate()
        raise MindgapError(f"claude 超时（{cfg.timeout_s}s）")
    return proc.returncode, out, err, time.time() - t0


def parse_envelope(stdout: str) -> tuple[dict, dict]:
    """(envelope, analysis object). Prefers `structured_output`, then `.result` as JSON, then a fenced/braced block."""
    try:
        env = json.loads(stdout)
    except ValueError as e:
        raise MindgapError(f"claude 输出不是 JSON: {stdout[:200]!r}") from e
    if env.get("is_error") or str(env.get("subtype", "success")) != "success":
        raise MindgapError(f"claude 报错: subtype={env.get('subtype')} result={str(env.get('result'))[:300]}")
    so = env.get("structured_output")
    if isinstance(so, dict):
        return env, so
    res = env.get("result") or ""
    try:
        return env, json.loads(res)
    except ValueError:
        m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", res, re.S) or re.search(r"(\{.*\})", res, re.S)
        if not m:
            raise MindgapError("claude 没有返回 JSON 对象")
        try:
            return env, json.loads(m.group(1))
        except ValueError as e:
            raise MindgapError("claude 返回的 JSON 无法解析") from e


def analyze_day(day: str, cfg: Config, work: Path, prompts: dict, log) -> tuple[dict, dict]:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    recs = prompts["prompts"]
    best = None  # (verified_count, analysis, verify)
    cost = turns = 0.0
    secs = 0.0
    model = None
    feedback = ""
    attempts = 0
    last_err = None
    for attempt in (1, 2):
        attempts = attempt
        prompt = build_prompt(template, day, recs, feedback)
        (work / f"analyze-input-{attempt}.txt").write_text(prompt, encoding="utf-8")
        if attempt == 1:
            (work / "analyze-input.txt").write_text(prompt, encoding="utf-8")
        try:
            rc, out, err, dt = call_claude(prompt, cfg, work, log)
        except MindgapError as e:
            last_err = str(e)
            log.error("attempt %d: %s", attempt, e)
            feedback = ""
            continue
        secs += dt
        (work / f"analyze-raw-{attempt}.json").write_text(out, encoding="utf-8")
        (work / "analyze-raw.json").write_text(out, encoding="utf-8")
        (work / "analyze-stderr.txt").write_text(err, encoding="utf-8")
        try:
            env, obj = parse_envelope(out)
        except MindgapError as e:
            last_err = f"rc={rc} {e}"
            log.error("attempt %d: %s", attempt, last_err)
            feedback = "上一轮没有返回合法的 JSON 对象，请严格按 schema 只输出 JSON。"
            continue
        cost += float(env.get("total_cost_usd") or 0)
        turns += float(env.get("num_turns") or 0)
        model = ",".join(k for k in (env.get("modelUsage") or {}) if "haiku" not in k) or model
        errs = validate(obj)
        if errs:
            last_err = "schema 校验失败: " + "; ".join(errs[:5])
            log.warning("attempt %d: %s", attempt, last_err)
            feedback = "\n".join(errs)
            continue
        ver = verify_evidence(obj, recs, cfg.tz)
        nver, ntot = summary(ver)
        log.info("attempt %d: evidence verified %d/%d, cost $%.3f, %.0fs", attempt, nver, ntot, env.get("total_cost_usd") or 0, dt)
        if best is None or nver > best[0]:
            best = (nver, obj, ver)
        if nver >= min(2, ntot) and nver == ntot:
            break
        feedback = "\n".join(problems(ver))
        if attempt == 1 and nver >= 2:
            break  # good enough; do not pay for a second pass
    if best is None:
        raise MindgapError(last_err or "分析失败")
    nver, analysis, ver = best
    (work / "analysis.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    run = {"cost_usd": round(cost, 4), "turns": int(turns), "secs": round(secs), "model": model, "attempts": attempts}
    return analysis, run
