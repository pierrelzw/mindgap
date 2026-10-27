# mindgap

每天纽约时间 18:00，自动分析**纽约时间前一整天**你敲给 Claude Code 的 prompts，找出单一最关键的认知盲点，生成 HTML 报告并弹通知。

- 报告：`~/Documents/my_mindgap/index.html`（每天一页：`YYYY/MM/YYYY-MM-DD.html`）
- 诊断 prompt：`prompts/analyze.txt`（前半部分是原文，后半部分是输入与输出契约）
- 调参：`config.json`（时刻、阈值、模型、预算、重试次数，改完立即生效）

## 流程

`extract`（history.jsonl → 当天 prompts）→ 数据门槛（少于 `min_prompts` 条出"数据不足"页）→ `analyze`（`claude -p --json-schema`，单轮）→ `verify`（引文必须是 prompt 的逐字子串，脚本判定，失败标红不删除）→ `link`（链到 claude-code-transcripts 的消息锚点）→ `render` → 通知。

## 调度

launchd 每 60 秒运行 `python3 -m mindgap tick`。tick 用 `config.json` 的时区（America/New_York）算"最近一个已到期的 18:00"，对照 `state.json` 判断是否已跑。因此：

- 本机时区是 Asia/Shanghai 也没关系，11 月 1 日纽约切换冬令时后自动改到上海 07:00。
- 电脑睡过点，醒来后的第一次 tick 会补跑，最多补 `catchup_days`（7）天。
- 失败时每小时重试一次，最多 `max_attempts`（3）次，每次失败都会弹通知。

## 命令

```bash
python3 -m mindgap run --day 2026-10-26     # 立即分析某一天（已结束的日子）
python3 -m mindgap run --day 2026-10-26 --no-notify
python3 -m mindgap extract --day 2026-10-26 # 只提取，不调用 LLM
python3 -m mindgap render                   # 重渲染所有页面
python3 -m mindgap tick --dry-run           # 看现在有哪些天待跑
python3 -m mindgap state                    # 看 state.json
python3 -m pytest tests -q                  # 测试
./install.sh [--dry-run] [--yes]            # 注册 launchd
./uninstall.sh                              # 卸载（不删存档）
```

## 文件

仓库外的存档 `~/Documents/my_mindgap/`：`work/<DAY>/` 保存每天的输入、模型原始输出、核验结果和 `run.log`；`logs/tick.log` 是调度日志；`runs.jsonl` 每次运行一行；`state.json` 记录完成情况；`archive-v1/` 是 spike 时期的旧版报告。

## 注意

- `transcripts/` 是未脱敏的完整对话页，只在本机，不要分享。
- 通知需要 terminal-notifier 的系统授权：`open -a terminal-notifier`，然后在系统设置 > 通知里允许。`./install.sh` 会检测。
- 分析模型默认继承 `claude -p` 的默认模型。想固定模型，改 `config.json` 的 `model`。
- 想让模型联网核对书里的原文，把 `tools` 改成 `"WebSearch,WebFetch"`（会变慢变贵，当前 prompt 不需要）。
- `claude` 所在的目录必须同时有 `node`：用户级插件 hook 在 launchd 下需要它。`install.sh` 会检查并把该目录写进 PATH。
- `spike/` 是早期验证脚本，不再使用。
