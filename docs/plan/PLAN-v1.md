实现一套"每日 AI 对话复盘"系统（项目名 mindgap），分三个阶段，本次只做 Phase 1。

系统每天 19:00（America/New_York）做五件事：复盘我前一天和 AI 的对话，找出我最大的一个思维盲点，推荐一本针对这个盲点的经典书籍，生成一份 15 分钟内能读完的 HTML 网页报告并推送给我，同时把结果存档。存档要保留结构化数据，供以后迭代和做趋势分析。

代码放在 ~/github/my_projects/mindgap，存档放在 ~/Documents/my_mindgap。

---

## 零、已知事实（上一个 session 探查所得，直接用，不要重新假设）

- 主数据源是 ~/.claude/history.jsonl：Claude Code 的全局输入历史，每敲一次回车一行，跨所有项目，自 2026-09-29 起共约 490 行。每行字段：display（我敲的原文）、pastedContents（只存 contentHash，不存正文）、project（工作目录绝对路径）、sessionId、timestamp（毫秒 Unix 时间戳，字符串类型）。
- 粘贴内容在 display 里被折叠成 "[Pasted text #N +M lines]" 占位符，所以 AI 润色后粘贴的长 prompt 天然不会进入分析，只剩我手敲的文字。因此 500 字规则保留但基本是保底，被过滤条数仍要如实记录。
- 2026-10-15（America/New_York）试跑：history.jsonl 里 54 条，来自 7 个会话，其中 8 条是斜杠命令（/model、/goal、/cc-suite:… 等），5 条含粘贴占位符，0 条超过 500 字。
- 不要用 ~/.claude/projects/*.jsonl 做主数据源：同一天它给出 122 条 "user" 记录，多出的部分是 skill / cc-suite 子进程发出的程序化 prompt，不是我敲的。但它可以按 ~/.claude/projects/<project 路径转义名>/<sessionId>.jsonl 反查到 AI 回复和粘贴正文，留给 Phase 2 做上下文补充；转义规则是把路径里的 "/" 换成 "-"。
- history.jsonl 是单文件，Claude Code 是否截断或轮转未知。每次运行先把它整份快照到 ~/Documents/my_mindgap/raw/history-YYYY-MM-DD.jsonl，再从快照读取。
- ~/github/my_projects/mindgap/ 已存在，里面有 mindgap/extract.py（纯标准库，Python 3.13，针对 projects/*.jsonl 写的）。它的脱敏正则、系统注入文本判断、时区切窗口逻辑可以复用，数据源部分要改成读 history.jsonl。tests/、prompts/、launchd/ 目录已建但为空。~/Documents/my_mindgap/ 已存在且为空。没有注册任何定时任务。
- 运行 Python 用 `python3 -m mindgap.<module>`，不要用 `python3 -I`，它会找不到包。

---

## 一、每日复盘规格（各阶段通用）

### 输入范围
- 时间窗口：运行当天的前一天，America/New_York 时区 00:00–23:59。日期在运行时计算，不要写死。
- 只分析我亲手输入的 prompt，即 history.jsonl 的 display 字段。以下内容都不算：斜杠命令（display 以 "/" 开头的整行）、粘贴占位符本身（"[Pasted text …]" 要从文本里去掉，只保留我手敲的部分；去掉后为空的记录丢弃）、AI 回复、工具调用结果、系统注入内容。
- 润色过滤：去掉首尾空白后超过 500 个字符的 prompt，视为 AI 润色过，本阶段不纳入分析，但要把被过滤的条数写进报告和数据文件。
- 窗口内一条有效 prompt 都没有时，仍然生成一份极简报告，只写"昨日无有效对话记录"和被过滤的条数，不推荐书，然后结束。

### 盲点判定
- 只选一个盲点：在多段对话里反复出现、对结果影响最大的那个思维模式，例如过早下结论、忽略约束、用局部经验推断全局。问题要落在思维方式上，不能只是某个具体的知识点。
- 给出 2–4 条证据，每条包含：来源工具、会话文件名、时间、我的原话摘录（不超过 2 句）。
- 记录里出现的密钥、token、密码、内网地址一律替换为 [已脱敏]，HTML 和数据文件里都不能出现。

### 选书
- 选该盲点所属领域里公认的经典，并说明为什么是这本，而不是同领域的其他书。
- 去重：推荐的书不能和最近一次推荐的书相同。以存档里的 recommendations.jsonl 为准。

### 书中片段
- 选 3–5 个直接回应该盲点的片段，用原语言引用；原文不是英文时，可以改用公认英译本。
- 每段引文不超过 150 词，并注明章节（有页码就带上页码）和版本。
- 引文必须能通过联网搜索找到出处。找不到原文的，改写为转述并标明"转述"，不能凭记忆生成看起来像原文的引文。

### 报告内容
- 长度：中文正文不超过 5000 字，加上英文引文，总阅读时长不超过 15 分钟。
- 结构依次为：
  1. 一句话结论：盲点是什么
  2. 证据：来自昨日对话的摘录
  3. 为什么这是盲点：它导致了什么后果，正确的思考方式是什么
  4. 推荐书籍：书名、作者、出版年，以及选它的理由
  5. 书中片段：每段引文后附一段中文解读，说明它和我那条对话的对应关系
  6. 明天就能用的 1–3 个具体做法
- 页脚注明：数据来源及各来源条数、被过滤条数、生成时间。

### 存档结构
~/Documents/my_mindgap/
  YYYY/MM/YYYY-MM-DD.html   报告，单文件，CSS 内联，不依赖外部资源
  YYYY/MM/YYYY-MM-DD.json   结构化数据，字段见下
  recommendations.jsonl     每天追加一行：日期、书名、作者、盲点标签
  index.html                按日期倒序列出所有报告的链接

JSON 字段：date, sources（数组，每项包含 tool 和 session_count），prompts_total, prompts_filtered_long, blindspot {label, summary}, evidence[], book {title, author, year, reason}, excerpts[] {text, location, edition, is_paraphrase}, actions[], schema_version。
blindspot.label 从一个固定的标签表里选，表放在 ~/github/my_projects/mindgap/taxonomy.json，Phase 1 先给出初版。确实没有合适标签时可以新增，但要在 JSON 里标记 new_label: true。这样做是为了后续能统计趋势。

---

## 二、阶段划分

### Phase 1 — MVP（本次实现）
- 数据源：只接 ~/.claude/history.jsonl（先快照到存档 raw/ 目录再读）。
- 流水线分三步，每步可单独运行：
  1. extract：history.jsonl 快照 → 当日 prompts JSON（确定性代码，可单测）。每条保留 time、project、sessionId、text，并按 project 和 sessionId 推导出对应的 projects/*.jsonl 路径作为 session_file 字段，供证据引用和 Phase 2 反查。
  2. analyze：读 prompts JSON，做盲点判定、选书、联网查引文，输出符合上述字段的分析 JSON。这一步需要模型判断，用 `claude -p` 调用，prompt 模板放在 prompts/ 目录下，分析结果必须通过 schema 校验才能进入下一步。
  3. render：分析 JSON → HTML，写入存档，追加 recommendations.jsonl，重建 index.html。
- 定时：每天 19:00 America/New_York 自动运行。
  - 先确认所选方式能读到本机文件：云端 routine（/schedule）在云端运行，读不到本机的 ~/.claude/projects；/loop 依赖会话一直开着。
  - 这两种都不满足，就用本机 launchd（plist 放在 launchd/ 目录），通过 `claude -p` 运行，并处理 19:00 时机器处于睡眠的情况（launchd 的 StartCalendarInterval 在唤醒后会补跑一次，确认这一点并写进交付说明）。
  - 在交付说明里写明选了哪种方式，以及为什么。
- 推送：两者都要。
  - 本地 HTML 加 macOS 系统通知（通知点击后打开当日 HTML）。
  - Claude Artifact：把当日 HTML 发布为 Artifact，这样能在 Claude Code、claude.ai/code 里打开；Artifact 链接写进 JSON 的 artifact_url 字段和 index.html。
  - Orca 能否直接打开要实际验证；做不到就在交付说明里写明原因和替代方式（例如在 Orca 里打开本地 HTML 路径），不要假装支持。
  - 在 `claude -p` 非交互模式下 Artifact 工具是否可用，要实际测试；不可用就在交付说明里写明，并保留本地 HTML 加通知作为保底。
- 完成标准：
  1. 用 2026-10-15 的真实记录手动跑一次完整流水线，产出 ~/Documents/my_mindgap/2026/10/2026-10-15.html 和 .json，并且 JSON 能通过 schema 校验。
  2. 单元测试至少覆盖：时区切窗口、斜杠命令排除、粘贴占位符剥离、500 字过滤、脱敏。用 `python3 -m pytest` 或 `python3 -m unittest` 能跑通。
  3. 定时任务已注册，并展示下一次触发时间。
  4. 交付说明（README.md）列出：运行命令、各文件路径、已知限制。

### Phase 2 — 接入更多 CLI（本次不做）
- 数据源：Codex（~/.codex/sessions/ 等）、agy（Antigravity CLI）、Grok。路径和格式要先实际探查，不能假设。
- 上下文补充：按 sessionId 反查 ~/.claude/projects/*.jsonl，为每条证据附上 AI 当时的回复摘要，让盲点判断有对话上下文。
- 每个来源实现一个解析器，统一输出成同一种 prompt 记录结构。
- 完成标准：每个来源都能解析出昨日的 prompt；报告的数据来源统计列出各工具的条数。

### Phase 3 — ChatGPT 网页版与趋势分析（本次不做）
- 数据源：从 [ChatGPT 导出文件目录，待定] 读取 ChatGPT 网页版的导出文件（conversations.json）。
- 趋势分析：基于存档的 JSON 生成周报或月报，统计盲点标签的频次变化，以及推荐过的书目。
- 重新评估润色过滤：history.jsonl 已天然排除粘贴正文；评估是否需要从 projects/*.jsonl 取回粘贴正文，识别润色前后的对应关系。
- 完成标准：导入一份导出文件后，它的记录会出现在当日报告里；能生成一份覆盖至少 7 天的趋势页。

---

## 三、执行边界
- 可以直接执行：在 ~/github/my_projects/mindgap 和 ~/Documents/my_mindgap 内创建、修改文件；只读访问各个对话记录目录；联网搜索；发布 Artifact。
- 以下操作要先等我确认：注册 launchd 或 cron 任务、创建云端 routine、安装全局依赖、改动 ~/github/my_projects/mindgap 以外的任何配置。
- 只读：~/.claude/history.jsonl、~/.claude/projects/、~/.codex/ 等对话记录文件和目录，绝不能修改或删除。
- 不需要启动子代理。
- 本次的范围只到 Phase 1。Phase 2 和 Phase 3 只在交付说明里列出接口预留点，不写实现。
- 本次完成的标准：Phase 1 的四条完成标准全部满足，最后回复存档根目录、首份报告的绝对路径、Artifact 链接和定时方式。
