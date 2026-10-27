做一个 spike，验证"每日 AI 对话复盘"系统（mindgap）的全流程能否跑通。目标是回答下面 6 个未知问题，不是做出可维护的代码。代码一律放在 ~/github/my_projects/mindgap/spike/ 里，允许粗糙，允许硬编码，之后会被丢弃。完整计划在 ~/github/my_projects/mindgap/docs/plan/PLAN.md，先读一遍，但本次只做下面列出的事。

## 要回答的 6 个问题
1. 从 ~/.claude/history.jsonl 提取 2026-10-15（America/New_York）的手敲 prompt，数据够不够做盲点分析？
2. `claude -p` 非交互模式能否完成分析（盲点判定、选书、联网查引文），并稳定输出合法 JSON？
3. `claude -p` 非交互模式能否发布 Claude Artifact？能的话，链接能否在 Claude Code 和 claude.ai/code 打开？
4. macOS 系统通知能否发出，点击后能否打开本地 HTML？
5. launchd 能否在指定时间拉起 `claude -p`？重点是 PATH、登录态、工作目录这三样在 launchd 环境下是否正常。
6. Orca 能否打开本地 HTML 或 Artifact 链接？

## 已知事实（直接用，不要重新探查）
- ~/.claude/history.jsonl 每行字段：display、pastedContents（只有 contentHash）、project、sessionId、timestamp（毫秒 Unix 时间戳，字符串）。粘贴内容在 display 里是 "[Pasted text #N +M lines]" 占位符。
- 2026-10-15 当天有 54 条，7 个会话，8 条是斜杠命令（display 以 "/" 开头），5 条含粘贴占位符，0 条超过 500 字。
- ~/github/my_projects/mindgap/mindgap/extract.py 里有可复用的脱敏正则和时区切窗口逻辑，但它读的是 projects/*.jsonl，不要直接用它的数据源。
- ~/Documents/my_mindgap/ 已存在且为空。
- 用 `python3`，不要用 `python3 -I`。

## 步骤
1. extract：写 spike/extract.py，读 ~/.claude/history.jsonl，取 2026-10-15 的记录，去掉斜杠命令和粘贴占位符，去掉空行，脱敏密钥和内网地址，输出 spike/out/prompts.json。把条数打印出来。
2. analyze：写 spike/analyze.md 作为 prompt 模板，内容是 PLAN.md "一、每日复盘规格"里盲点判定、选书、书中片段三节的要求，外加"只输出一个 JSON 对象，字段：blindspot {label, summary}, evidence[], book {title, author, year, reason}, excerpts[] {text, location, edition, is_paraphrase}, actions[]"。然后用 `claude -p` 把模板和 prompts.json 一起喂进去，结果存到 spike/out/analysis.json。记录：用了什么命令行参数、花了多久、输出是否直接就是合法 JSON，还是要从 markdown 代码块里抠出来。失败就重试一次，两次都失败记录原因。
3. render：写 spike/render.py，把 analysis.json 渲染成单文件 HTML（CSS 内联），按 PLAN.md 的 6 段结构，写到 ~/Documents/my_mindgap/2026/10/2026-10-15.html。样式够读就行。
4. artifact：在 `claude -p` 里尝试发布这个 HTML 为 Artifact。记录：工具是否可用、是否需要额外参数（例如 --allowedTools）、返回的链接。不可用就记录原因，不要绕路。
5. notify：用 osascript 或 terminal-notifier 发一条系统通知，标题"mindgap 2026-10-15"，点击后打开那个 HTML。记录用的命令和实际效果。
6. launchd：写一个 plist 放在 spike/，StartCalendarInterval 设为当前时间往后 3 分钟，ProgramArguments 是一个 shell 脚本，脚本里用绝对路径调用 `claude -p "echo ok 并把当前时间写到 ~/github/my_projects/mindgap/spike/out/launchd-ok.txt"`。注册前先问我确认。触发后检查文件是否生成，然后 `launchctl unload` 卸掉。记录：claude 的绝对路径、是否需要在 plist 里设 PATH 或 HOME、有没有登录态问题。
7. orca：告诉我 HTML 的绝对路径和 Artifact 链接（如果有），我自己在 Orca 里试，你在结果里留一个待我填写的位置。

## 产出
- ~/github/my_projects/mindgap/docs/plan/SPIKE-RESULT.md，对 6 个问题逐条回答：能 / 不能 / 部分能，附证据（命令、输出摘要、耗时）。最后一节列出 PLAN.md 需要修改的地方。
- spike/out/ 下保留所有中间产物。
- 2026-10-15 的报告 HTML 已写入存档目录。

## 边界
- 允许直接做：在 ~/github/my_projects/mindgap/spike/ 和 ~/Documents/my_mindgap/ 内读写；联网搜索；调用 `claude -p`；发系统通知。
- 先问我确认：注册 launchd 任务、安装任何东西。
- 只读：~/.claude/ 下的所有文件。
- 不写单元测试，不做 taxonomy，不做 schema 校验，不做 index.html，这些留给正式 Phase 1。
- 不启动子代理。
- 完成标准：SPIKE-RESULT.md 写完，6 个问题都有答案。
