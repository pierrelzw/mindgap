实现一套"每日 AI 对话复盘"系统（项目名 mindgap），分三个阶段，本次只做 Phase 1。旧版计划在 PLAN-v1.md，spike 结论在 SPIKE-RESULT.md，本文已把 spike 的 13 条修改全部合并，以本文为准。

系统每天在设定时刻（默认 19:00 America/New_York，可配置）做这几件事：复盘我前一天和 AI 的对话，找出当天最主要且之前没写过的一个认知偏差，按领域指出我可能缺的基础知识、know-how 和判断标准，推荐一本经典书并引用带上下文的原文段落，把我的 prompt 改写成该领域专家的问法供我复制测试，生成一份 15 分钟内能读完的 HTML 报告并推送给我，同时把结果存档。报告由写手 Agent 起草、验证 Agent 审核、不通过退回重写，每一轮都存档。

代码放在 ~/github/my_projects/mindgap，存档放在 ~/Documents/my_mindgap。

---

## 零、已知事实（spike 探查所得，直接用，不要重新假设）

### 数据源
- 主数据源是 ~/.claude/history.jsonl：Claude Code 的全局输入历史，每敲一次回车一行，跨所有项目。每行字段：display（我敲的原文）、pastedContents（只存 contentHash，不存正文）、project（工作目录绝对路径）、sessionId、timestamp（毫秒 Unix 时间戳，字符串类型）。
- 粘贴内容在 display 里被折叠成 "[Pasted text #N +M lines]" 占位符，所以 AI 润色后粘贴的长 prompt 天然不会进入分析，只剩我手敲的文字。400 字规则保留作为保底，被过滤条数仍要如实记录。
- 实测：2026-10-15（America/New_York）54 行 → 斜杠命令 8 → 剥离占位符后为空 1 → 有效 prompt 45 条，5 个会话，2535 字；2026-10-16：126 行 → 斜杠命令 30 → 剥离后为空 5 → 有效 91 条，31 个会话，6100 字。
- 不要用 ~/.claude/projects/*.jsonl 做主数据源：同一天它多出的 "user" 记录是 skill / cc-suite 子进程发出的程序化 prompt。但它可以按 ~/.claude/projects/<project 路径转义名>/<sessionId>.jsonl 反查到 AI 回复和粘贴正文，留给 Phase 2；转义规则是把路径里的 "/" 换成 "-"。
- history.jsonl 是单文件，是否截断或轮转未知。每次运行先整份快照到 ~/Documents/my_mindgap/raw/history-YYYY-MM-DD.jsonl，再从快照读取。
- 本机时区是 Asia/Shanghai，不是纽约。代码里"前一天"必须显式用配置里的时区计算，禁止 datetime.now() 不带时区。

### 环境与工具
- macOS 26（Darwin 25.6），Claude Code 2.1.301。claude 绝对路径 /Users/ai/.local/share/mise/installs/node/lts/bin/claude，由 mise 管理，node 升级后路径可能变，安装脚本要解析而不是写死。
- 运行 Python 用 `python3 -m mindgap.<module>`，不要用 `python3 -I`。
- ~/github/my_projects/mindgap/mindgap/extract.py 里的脱敏正则、系统注入文本判断、时区切窗口逻辑可以复用。spike/ 目录是可丢弃代码，但 spike/render.py 的多天设计（存档 json 为数据源、每次全量重渲所有日报和 index、相对链接、无 JS）已验证可用，正式版沿用这个设计。
- ~/Documents/my_mindgap/ 里已有 spike 产出的 2026-10-15 到 10-21 的 html/json 和 index.html，schema 是旧的。正式流水线跑通后用新 schema 重跑覆盖这几天。
- 截图工具：/Applications/Google Chrome.app 可用 headless 截整页；/usr/sbin/screencapture 截屏需给终端开屏幕录制权限。没有 playwright。

### `claude -p` 调用约定
- prompt 经 stdin 传入。`--allowedTools` 是可变参数，会吞掉紧随其后的位置参数 prompt。
- 用 `--output-format json`，结果在外层信封的 `.result` 字段；两次样本 `.result` 都直接是合法 JSON，但代码保留从 markdown 代码块抠 JSON 的兜底。
- 参考命令：`claude -p --output-format json --allowedTools WebSearch,WebFetch --no-session-persistence --permission-mode dontAsk --max-budget-usd <N>`。正式版不用 bypassPermissions，只放行需要的工具。
- 耗时与成本：45 条 prompt 时 52 秒、$0.18；91 条时 252 秒、$0.87，开销主要在联网核实引文的轮数。加上改写和写验循环后，单日按最多 4 美元、15 分钟预算。
- Artifact 工具在 `-p` 下不存在，无法发布 Artifact，不要再试。`-p` 下只有 Claude Docs 连接器。

### 定时与推送
- launchd `StartCalendarInterval` 注册 3 次均未触发，原因未查明；`StartInterval` 可靠。正式版用 StartInterval=60 加脚本内到期判断。
- launchd 环境：PATH 是 /usr/bin:/bin:/usr/sbin:/sbin，工作目录是 /，HOME 正常，claude 登录态正常。plist 必须写 EnvironmentVariables.PATH、WorkingDirectory，脚本内全部用绝对路径。
- 通知用 terminal-notifier 3.1.0（/opt/homebrew/bin/terminal-notifier，brew 安装），`-open` 点击后打开 HTML 已由用户确认。首次需 `open -a terminal-notifier.app` 授权；进程会挂住等点击，必须后台运行并加超时。osascript 不能自定义点击动作，不用。通知权限曾被系统关掉一次，脚本要检测退出码。
- Orca 能打开本地 HTML（`open -a Orca <path>`），用户已确认。

---

## 一、每日复盘规格（各阶段通用）

### 配置
所有可调项放 ~/github/my_projects/mindgap/config.json，改一处即生效，代码里不许写死：
- timezone（默认 America/New_York）、hour、minute：触发时刻。
- long_prompt_chars：400。
- max_rounds：3（起草 1 轮加最多 2 轮修订）。
- budget_usd_per_day：4。
- body_max_chars：5000。
- rewrites_in_body：8。
- catchup_days：7。
- book_dedupe_days：30。

### 输入范围
- 时间窗口：运行当天的前一天，按配置时区 00:00–23:59。日期在运行时计算。
- 只分析我亲手输入的 prompt，即 history.jsonl 的 display 字段。以下都不算：斜杠命令（display 以 "/" 开头的整行）、粘贴占位符本身（从文本里去掉，只保留手敲部分；去掉后为空的记录丢弃）、AI 回复、工具调用结果、系统注入内容。
- 润色过滤：去掉首尾空白后超过 400 个字符的 prompt 视为 AI 润色过，不纳入分析，但被过滤条数要写进报告和数据文件。
- 每条有效 prompt 生成稳定 id（日期加序号，如 2026-10-22-017），后续证据、缺口、引文、改写全部通过 id 引用。每条记录字段：id、time、project、sessionId、session_file（推导出的 projects/*.jsonl 路径）、text、type、domain。type 和 domain 由写手标注，取值见 taxonomy.json。
- 窗口内一条有效 prompt 都没有时，仍生成一份极简报告，只写"昨日无有效对话记录"和被过滤条数，不推荐书，不跑写验循环，然后结束。index 里要有这一天。

### 认知偏差判定
- 从 taxonomy.json 的偏差表里选，不许自由命名。初版 12 条：锚定效应、确认偏误、沉没成本、计划谬误、过度自信、可得性启发、框架效应、现状偏差、幸存者偏差、达克效应、知识的诅咒、损失厌恶。每条有名称、定义、在开发和产品对话里的识别信号，写手和验证者共用。
- 写手输出按影响力排序的候选列表（最多 5 条，每条带出现次数和影响说明），不是只给一个。
- 去重规则：从候选列表第一条开始，跳过所有在 recommendations.jsonl 里出现过的偏差标签，取第一个没出现过的。也就是说当天最大的那个之前某天写过，就写第二大的，以此类推。
- 候选全部出现过时：取距上次出现最久的那条，JSON 标 repeat: true，报告里写明"此偏差上次出现于某日"。写手确认表里没有合适条目时可以新增标签，JSON 标 new_label: true，并给出定义和识别信号，由验证者判断是否成立。
- 选定的偏差给出 2–4 条证据，每条包含：prompt id、会话文件名、时间、原话摘录（不超过 2 句）、触发了识别信号里的哪一条。
- 写明这个偏差在昨天导致了什么后果，以及不带偏差时应该怎么判断。
- 记录里的密钥、token、密码、内网地址一律替换为 [已脱敏]，HTML 和数据文件里都不能出现。

### 领域知识缺口
- 写手先给每条有效 prompt 标领域（后端、前端、产品、数据、运维、AI 工程、项目管理、写作沟通等，表在 taxonomy.json，可新增并标 new_label）和问题类型（操作、排查、设计、决策、学习、写作）。
- 对 prompt 最多的至多 3 个领域，分别指出我可能缺的：
  1. 基础知识：该领域有定论的概念或原理，我的提问显示不知道。
  2. know-how：有经验的人会先做、先问、先查的事。
  3. 判断标准：专家用来判断"够不够好、该不该做"的具体标准。
- 每条缺口必须写成可检验形式："如果知道 X，这条 prompt 会改成问 Y"，并引用触发它的 prompt id。不接受"缺乏经验""理解不深"这类说法。
- 其余领域只在附录列出领域名和 prompt 条数。

### 选书
- 一本主书：针对当天的认知偏差或最大的领域缺口，二选一并写明针对的是哪一个。说明为什么是它而不是同领域另一本，至少点名一本被排除的候选。
- 其他缺口只给延伸书目：书名、作者、一句话理由，不引用原文。
- 去重：主书不与最近 30 天推荐过的书相同，以 recommendations.jsonl 为准。

### 原文片段
- 3–5 段，每段 150–400 词，必须是书中连续的一段或相邻两段，不许跳着拼接。原文不是英文时可用公认英译本。
- 注明章节、页码（有就带）、版本，以及一个可访问的来源 URL。
- 机器核验：抓取 URL 后，引文中至少 20 个字符的连续子串能在页面文本中命中才算原文；否则自动改为转述，is_paraphrase 置 true，报告里标"转述"。不能凭记忆生成看起来像原文的引文。
- 每段后附中文解读，写明对应我昨天哪一条 prompt（引用 id）。

### 专家会怎么问
筛选：
- 硬过滤：少于 15 字；纯确认或纯指令（"继续""好的""run it" 等）；斜杠命令；剥离占位符后只剩零碎文字的。
- 同一会话里连续几条讲同一件事的合并为一组，只改写最能代表的那条，标注"同组 N 条"。
- 剩下的每条按四个维度各打 0–2 分：目标是否说清（要什么结果、做到什么程度）、上下文是否给够（现状、约束、已试过什么）、验收标准是否存在、问题类型（决策、设计、排查加分，操作不加分）。总分低者改写收益高。按收益排序，正文放前 8 条，其余放折叠附录。分数写进 JSON，验证者可复核。

改写规则：
- 只做一件事：补上缺的要素。六要素是背景现状、目标、约束、已知与已试、期望输出形式、验收标准。只补缺的，至少补 2 项，不强求六项全有。
- 原意不变：目标和需求不能被替换成改写者认为更好的问题。
- 不编造事实：新增的具体信息要么来自同一会话里我说过的话（引用 prompt id），要么用 [方括号] 占位让我填，占位符不超过 3 个。
- 长度：不超过原文 4 倍，且不超过 300 个中文字符。
- 自包含：不依赖报告上下文，直接粘贴就能发。
- 体现领域 know-how：排查类先要日志、版本、复现步骤；设计类先列约束和非目标；决策类要求列选项、判断标准和推荐。"改了什么"里要点名用了哪条 know-how，尽量对应到当天的领域缺口。
- 禁止：角色套话（"你是资深专家"）、与问题无关的格式要求、堆 checklist。

效果追踪：
- 改写存进当天 JSON 的 rewrites[]。第二天 extract 时在新快照里查前一天每条改写的前 40 个字符，命中即算复用，写进当天 JSON 的 reuse 字段。报告页脚和 index 卡片显示"昨天复用了 N 条专家版提问"。

### 报告内容
- 长度：正文中文不超过 5000 字，加上英文引文总阅读时长不超过 15 分钟。附录（改写第 9 条起、其余领域、验证记录）折叠，不计入上限。
- 结构依次为：
  1. 一句话结论：今天的认知偏差和涉及的领域
  2. 认知偏差：定义、证据、后果、正确判断方式；repeat 或 new_label 时说明
  3. 领域知识缺口：按领域分组，每组基础知识、know-how、判断标准三类
  4. 推荐书籍：主书、作者、出版年、针对什么、选它而不选另一本的理由；延伸书目
  5. 原文片段：每段带章节版本和来源，转述标明，后附中文解读和对应 prompt
  6. 专家会怎么问：每条含原文、领域、问题类型、专家版、改了什么；正文 8 条，附录其余
  7. 明天就能用的 1–3 个具体做法
  8. 页脚：数据来源及各来源条数、被过滤条数、生成时间、是否补跑、验证轮数与通过项数、昨日改写复用数
- 单文件，CSS 内联，无 JS、无外部资源，用 CSS 变量适配深浅色。页首页尾有"前一天 / 总览 / 后一天"导航，跳过没有报告的日期。

### 存档结构
~/Documents/my_mindgap/
  config 不在这里，在代码目录
  raw/history-YYYY-MM-DD.jsonl         每次运行的 history.jsonl 整份快照
  raw/YYYY-MM-DD/prompts.json          当日有效 prompt
  raw/YYYY-MM-DD/round-N-analysis.json 第 N 轮写手输出
  raw/YYYY-MM-DD/round-N-check.json    第 N 轮机器检查结果
  raw/YYYY-MM-DD/round-N-verdict.json  第 N 轮验证 Agent 结论
  YYYY/MM/YYYY-MM-DD.html              报告
  YYYY/MM/YYYY-MM-DD.json              最终结构化数据
  recommendations.jsonl                每天追加一行：date、bias_label、book_title、book_author；同一 date 重跑时覆盖该行而不是追加
  runs.jsonl                           每次实际执行追加一行：date、started、finished、status、rounds、cost_usd、duration_s、catchup、error
  index.html                           由所有 YYYY/MM/*.json 重建

JSON 字段（schema 放 ~/github/my_projects/mindgap/schema/report.schema.json，schema_version 从 2 起）：
- date、schema_version、generated_at、catchup（bool）
- sources[] {tool, session_count, rows}、prompts_total、prompts_filtered_long、prompts_filtered_trivial
- bias {label, summary, consequence, correction, repeat, new_label, candidates[] {label, count, impact}}
- evidence[] {prompt_id, session_file, time, quote, signal}
- domains[] {name, prompt_count, in_body}
- gaps[] {domain, kind, statement, if_known_would_ask, prompt_ids[]}，kind 取 knowledge、knowhow、criteria
- book {title, author, year, targets, reason, rejected_alternative}
- further_reading[] {title, author, reason, gap_ref}
- excerpts[] {text, location, edition, source_url, is_paraphrase, verified, commentary, prompt_id}
- rewrites[] {prompt_id, original, domain, type, scores {goal, context, criteria, type}, expert_version, what_changed, knowhow_used, group_size, in_body}
- reuse {checked_date, reused_count, reused_prompt_ids[]}
- actions[]
- verification {rounds, status, failed_checks[]}，status 取 accepted、rejected、skipped
- artifact_url 可选，Phase 1 不填

taxonomy.json 放 ~/github/my_projects/mindgap/taxonomy.json，含三张表：biases（名称、定义、识别信号）、domains、prompt_types。Phase 1 给初版。

### 写手与验证者循环
analyze 拆成四步，每步可单独运行，由 run 命令串起来：
1. draft（写手 Agent）：输入 prompts.json、taxonomy.json、recommendations.jsonl 里已用过的偏差标签和近 30 天书目；输出 analysis.json。prompt 里写明"输出会被另一个 Agent 审查，不要自评"。
2. check（确定性脚本，零成本）：schema 校验；bias.label 在表内且去重规则执行正确；所有 prompt_id 存在；每条证据 quote 能在 prompts.json 精确匹配；每段引文按 URL 抓取核验；主书不与 30 天内重复；正文字数；改写长度与占位符数量；改写里出现的数字、路径、产品名必须在原文、同会话 prompt 或方括号里；脱敏 grep。任一不过直接退回写手，不进验证。
3. verify（验证 Agent）：另开 `claude -p` 会话，不共享上下文，不给写手推理过程。输入 analysis.json、prompts.json、check 结果、规则清单；输出 verdict.json，只给结论和修改要求，不许改写内容。规则编号 V1 起，放 prompts/verifier.md，与 prompts/writer.md 共用同一份规则文本：
   - V1 证据确实命中该偏差的识别信号，逐条判"支持 / 勉强 / 不支持"，至少 2 条"支持"。
   - V2 偏差落在判断方式上，不是知识点。
   - V3 每条缺口是"知道 X 就会问 Y"的形式，且 Y 确实比原 prompt 更接近专家问法。
   - V4 选书理由含对比，被排除的候选是同领域真实存在的书。
   - V5 每段引文的中文解读指向具体 prompt，且关系成立。
   - V6 每条改写保留原意；比原文至少多了六要素中的 2 项；没有引入方括号外的新事实；没有角色套话。
   - V7 做法可以在一次对话里执行。
   - V8 即使通过，也必须写出"最薄弱的一处"。
   verdict.json 字段：round、verdict（accept / revise）、checks[] {id, result, severity, reason, evidence_ref[], fix_hint}、weakest_point。
4. revise（写手 Agent）：输入上一轮 analysis.json 和 verdict.json，输出完整的新 analysis.json 和 changes[]，逐条说明针对哪个 FAIL 改了什么。回到 check。

收敛规则：
- 最多 max_rounds 轮，verdict 为 accept 即停。验证者每轮能看到上一轮 verdict，只允许提新问题或确认旧问题已修，不许反复摇摆。
- 到上限仍不通过：照常渲染并推送，报告顶部加"未通过验证"横幅列出未过的规则编号，verification.status 记 rejected。不因验证不过而不推送。
- 单日成本超过 budget_usd_per_day 时停止循环，按当前最新一轮渲染，runs.jsonl 记录。
- 每一轮的 analysis、check、verdict 都存到 raw/YYYY-MM-DD/。报告附录有折叠的"验证记录"：每轮 FAIL 项和写手的 changes。

---

## 二、阶段划分

### Phase 1 — MVP（本次实现）

数据源只接 ~/.claude/history.jsonl。流水线命令全部形如 `python3 -m mindgap.<cmd> --date YYYY-MM-DD`，每步可单独运行，`--date` 可重放任意日期：
1. extract：快照 history.jsonl → raw/<date>/prompts.json，并计算前一天改写的复用数。确定性代码，可单测。
2. draft / check / verify / revise：见写验循环。`run` 命令按收敛规则串起来，产出最终 analysis。
3. render：最终 analysis → YYYY/MM/<date>.html 和 .json，更新 recommendations.jsonl（同日覆盖），全量重渲所有日报和 index.html。
4. notify：terminal-notifier 后台发出，超时 5 秒，标题含日期和偏差标签，点击打开当日 HTML；失败时发"mindgap 失败：<阶段>，日志见 <路径>"。
5. tick：launchd 每 60 秒调用的入口脚本。用配置时区计算"最近一个已到期的触发时刻"，对比标记文件判断是否已跑；未跑则按日期顺序补齐缺的天数（上限 catchup_days），每天一次完整流水线，补跑的报告 catchup 置 true。

定时：
- launchd plist 放 launchd/com.mindgap.daily.plist，StartInterval=60，RunAtLoad，ProgramArguments 指向 tick 脚本，plist 内写 EnvironmentVariables.PATH（含 python3、terminal-notifier 所在目录）、WorkingDirectory、StandardOutPath、StandardErrorPath。
- 安装脚本 install.sh 解析 claude 绝对路径写进配置，注册 plist，并提示 terminal-notifier 授权步骤。注册前先问我确认。
- 云端 routine 读不到本机文件，/loop 依赖会话常开，两者都不用，交付说明里写明。

推送：
- 本地 HTML 加 terminal-notifier 通知，这是唯一正式渠道。
- Artifact 在 `-p` 下不可用，Phase 1 不做；artifact_url 字段保留为空。Claude Docs 连接器方案待我决定，交付说明里列为可选。
- Orca 打开本地 HTML 已验证，交付说明写操作方式。

验收清单（编号固定，自验证按此逐条出证据）：

A 定时与补跑
- A1 把 config 触发时刻改成 3 分钟后，注册后 5 分钟内存档出现当日 html 和 json，通知发出。证据：runs.jsonl 新行、ls 输出、通知截图。
- A2 同一天内后续 tick 不重跑：10 分钟内 runs.jsonl 只有一行。
- A3 删除标记文件后能重跑，recommendations.jsonl 行数不变，html 被覆盖。
- A4 `pmset sleepnow` 跨过触发点，唤醒后 2 分钟内补跑，报告页脚标"补跑"。
- A5 把标记文件改成 3 天前，唤醒后按日期顺序补齐 3 天，index 无缺口。
- A6 单测固定时间戳验证 2026-11-01 夏令时切换当天窗口仍是配置时区 00:00–23:59；机器时区改成任意值结果不变。
- A7 `launchctl kickstart` 从干净环境启动跑通；plist 含 PATH 和 WorkingDirectory；claude 路径来自 install.sh 解析。

B 推送
- B1 通知标题含日期和偏差标签，点击打开当日 html。人工点一次，AI 截通知横幅。
- B2 notifier 不阻塞：流水线总耗时不超过分析耗时加 10 秒。
- B3 人为把 claude 路径改错，收到失败通知，内容含阶段和日志路径。
- B4 notifier 退出码非 0 时写入日志。

C 报告与累计
- C1 index 条目数等于存档 json 数，倒序，每张卡片可点。
- C2 日报前后导航正确，首尾显示"无"，跳过缺失日期。
- C3 断网下 file:// 打开完整；html 里没有外部 src 或 href 到网络（引文来源链接除外）。
- C4 重跑同一天：html、json 覆盖，recommendations.jsonl 按 date 去重。
- C5 无 prompt 的日期有极简页并出现在 index。
- C6 用含假 token、假内网地址的 fixture 跑完整流水线，grep 整个存档目录命中为 0。
- C7 json 过 schema；bias.label 在 taxonomy 或带 new_label。
- C8 浅色和深色各截一张 index 和最新日报，布局无溢出。

D 分析与循环
- D1 每条证据 quote 在 prompts.json 精确匹配（机器）。
- D2 每段引文 URL 可抓取且子串命中，否则自动转述（机器）；人工抽查一段。
- D3 偏差去重：构造 recommendations.jsonl 含写手候选第一条的标签，最终选的是第二条；全部用过时选最久的并标 repeat。
- D4 主书不与 30 天内重复。
- D5 验证者有效性：向 analysis.json 植入三类缺陷（证据与偏差不对应、选书无对比、改写加入了原文没有的事实），验证者全部标 FAIL；对一份人工认定合格的 analysis 不标 major FAIL。
- D6 机器 check 有效性：植入假证据、假引文、超长改写、占位符 4 个，全部被拦。
- D7 改写筛选：硬过滤规则对 "继续""好的" 和少于 15 字的 prompt 生效；正文不超过 8 条。
- D8 复用追踪：把前一天某条 expert_version 的前 40 字写进测试快照，第二天 reuse.reused_count 为 1。
- D9 runs.jsonl 记录每次 rounds、成本、耗时；单次超过预算或 15 分钟时通知告警。

E 可观测
- E1 index 顶部显示最近一次运行状态、耗时、轮数、下次预计触发时间。
- E2 日志路径固定，README 列出。

单元测试至少覆盖：时区切窗口、斜杠命令排除、粘贴占位符剥离、400 字过滤、脱敏、prompt id 稳定性、偏差去重选择、改写硬过滤、复用匹配、引文子串核验。`python3 -m pytest` 或 `python3 -m unittest` 能跑通。

自验证规则（实现完成后执行）：
1. 按上面的编号逐条验证，产出 verify/<今天日期>/ 目录和 verify/<今天日期>/verify.html。
2. 每条只能是 PASS / FAIL / UNVERIFIED。结论必须来自实际执行的命令或实际截取的图片。写"应该""预期""理论上"的一律记 UNVERIFIED。
3. 每条 PASS 至少附一个证据文件：命令输出存 verify/<日期>/<编号>.txt，截图存 verify/<日期>/<编号>.png。没有证据文件的 PASS 按 UNVERIFIED 处理。
4. 截图规范：html 用 headless Chrome，宽 1280，整页，浅色和深色各一张（-light / -dark）。index 和最新日报必截。通知和 Orca 窗口用 screencapture -x 截全屏，通知发出后 2 秒内截。
5. 需要模拟时间的标准必须通过 config 改触发时刻真实触发，不能直接调用流水线函数代替。
6. 需要人工操作的标准（点击通知、Orca 里点页内链接）记 UNVERIFIED，verify.html 里写清楚我要做什么、应该看到什么。
7. 遇到 FAIL 先记录再修复，修复后重新验证该条并生成新证据，旧证据保留并标 superseded。不允许删 FAIL 记录。
8. verify.html 单文件、CSS 内联、图片相对路径。每行：编号、标准原文、结论、证据缩略图、命令输出前 10 行、FAIL 或 UNVERIFIED 原因。顶部汇总三种结论数量。
9. 最后回复只需三样：verify.html 绝对路径、FAIL 和 UNVERIFIED 编号列表、每个 UNVERIFIED 需要我做的操作。

完成定义：
1. 用 2026-10-15 和 2026-10-16 的真实快照各跑一次完整流水线，产出新 schema 的 html 和 json，并覆盖存档里的旧版本。
2. 单元测试通过。
3. verify.html 里没有 FAIL，UNVERIFIED 只剩需要人工点击的条目。
4. 定时任务已注册（经我确认后）。
5. 交付说明 README.md 列出：运行命令、各文件路径、config 说明、安装与授权步骤、成本与耗时实测、已知限制、Phase 2 预留接口。

### Phase 2 — 接入更多 CLI 与上下文（本次不做）
- 数据源：Codex（~/.codex/sessions/ 等）、agy、Grok。路径和格式先实际探查。每个来源一个解析器，统一输出 prompt 记录结构，id 前缀带来源。
- 上下文补充：按 sessionId 反查 ~/.claude/projects/*.jsonl，为每条证据和改写附 AI 当时的回复摘要。
- 改写效果盲评（可选）：对正文前 2 条改写，用原 prompt 和专家版各跑一次 `claude -p`，由验证 Agent 盲评哪个回答更好，记录胜率。
- 验证 Agent 换用 Codex 或 agy（可选），减少同模型盲区。
- 完成标准：每个来源都能解析出昨日 prompt；报告来源统计列出各工具条数。

### Phase 3 — ChatGPT 网页版与趋势分析（本次不做）
- 数据源：ChatGPT 导出文件（conversations.json），目录待定。
- 趋势分析：基于存档 json 生成周报或月报：偏差标签频次、领域分布变化、缺口类型分布、改写复用率走势、书单。
- 人工校准：每周抽一天报告按验证规则人工打分，与验证 Agent 结论比对，分歧率高的规则重写。
- 重新评估润色过滤和条形图在几十天后的布局（按月分组或只显示最近 30 天）。
- 完成标准：导入一份导出文件后记录出现在当日报告；能生成一份覆盖至少 7 天的趋势页。

---

## 三、执行边界
- 可以直接执行：在 ~/github/my_projects/mindgap 和 ~/Documents/my_mindgap 内创建、修改文件；只读访问各个对话记录目录；联网搜索；调用 `claude -p`；发系统通知；用 headless Chrome 和 screencapture 截图。
- 以下操作要先等我确认：注册 launchd 或 cron 任务、创建云端 routine、安装全局依赖、改动 ~/github/my_projects/mindgap 以外的任何配置、让机器睡眠（A4）。
- 只读：~/.claude/history.jsonl、~/.claude/projects/、~/.codex/ 等对话记录文件和目录，绝不能修改或删除。
- 不需要启动子代理。写手和验证者是两个独立的 `claude -p` 进程，不是子代理。
- 本次范围只到 Phase 1。Phase 2 和 Phase 3 只在交付说明里列出接口预留点。
- 本次完成的标准：Phase 1 的五条完成定义全部满足，最后回复存档根目录、verify.html 和最新报告的绝对路径、定时方式。
