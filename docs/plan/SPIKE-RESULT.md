# mindgap Spike 结果（2026-10-17 运行，对象日期 2026-10-15）

代码：`spike/`（可丢弃）。中间产物：`spike/out/`。报告：`~/Documents/my_mindgap/2026/10/2026-10-15.html`。
环境：macOS 26 (Darwin 25.6)，Claude Code 2.1.301，**本机时区是 Asia/Shanghai**（不是纽约）。

## 总览

| # | 问题 | 结论 |
|---|---|---|
| 1 | history.jsonl 数据够不够 | **能**（够用，但偏薄） |
| 2 | `claude -p` 能否分析并稳定输出 JSON | **能**（样本仅 1 次，"稳定"未证实） |
| 3 | `claude -p` 能否发布 Artifact | **不能**（工具不在 `-p` 的工具集中） |
| 4 | 系统通知，点击打开 HTML | **能**。terminal-notifier 3.1.0 发出通知，点击后打开 HTML（用户确认） |
| 5 | launchd 拉起 `claude -p` | **能**（kickstart / StartInterval 验证）；**StartCalendarInterval 3 次均未触发** |
| 6 | Orca 打开 HTML / 链接 | **本地 HTML 能打开**（用户确认）；Artifact 链接未测|

## 1. 提取数据（能）

- `spike/extract.py` 读 history.jsonl，America/New_York 切窗口，复用 `mindgap.extract.redact`。
- 2026-10-15：窗口内 54 行 → 斜杠命令 8 → 含粘贴占位符 5（剥离占位符后保留手敲部分）→ 剥离后为空 1 → 超长过滤 0 → **有效 prompt 45 条，来自 5 个会话，共 2535 字，最长 250 字**。
- 阈值按你的新指示改为 **400 字**（原 500），今天结果不变。
- 判断：45 条足以看出重复出现的思维模式（本次分析找到 4 条跨 2 个会话的证据）。但只有 5 个会话、均集中在白天一个项目，且无 AI 回复上下文，盲点判断依赖用户原话，置信度有限。
- 注：PLAN 写的"7 个会话"包含只有斜杠命令的会话；剥离后只剩 5 个。
- 未验证：raw/ 快照、history.jsonl 是否被轮转。

## 2. `claude -p` 分析（能）

- 命令：`claude -p --output-format json --allowedTools WebSearch,WebFetch --no-session-persistence --permission-mode dontAsk --max-budget-usd 3`，**prompt 经 stdin 传入**（见下方坑）。
- 耗时 **51.9 秒**，5 轮，成本 **$0.176**，rc=0。
- **`result` 字段直接就是合法 JSON**，没有 markdown 代码块（prompt 里明确写了"不要代码块"）。`--output-format json` 外层还有一层信封，需取 `.result`。脚本里保留了正则兜底，但本次没用上。
- 内容质量：盲点、4 条证据、选书（Manning《Introduction to Information Retrieval》）、4 个片段，其中 2 个主动标为转述（`is_paraphrase: true`），符合"不能编造原文"的要求。**我没有独立核对英文引文的原文**，只是模型声称已联网查证；正式版需要机器可核的校验（例如要求返回 URL 并抓取比对）。
- 不符合规格的地方：`blindspot.label` 是自由文本，没有从 taxonomy 选；证据里 `session` 是 sessionId，不是会话文件名，也没有 `tool` 字段；书名/作者等需 schema 校验。
- 坑：`--allowedTools` 是可变参数，**会吞掉紧随其后的位置参数 prompt**，报错 "Input must be provided either through stdin or as a prompt argument"。用 stdin 传 prompt 即可。
- 只跑了 1 次，"稳定输出合法 JSON"没有统计意义；正式版需 schema 校验 + 失败重试。

## 3. Artifact（不能）

- `claude -p ... --allowedTools Artifact` 返回：Artifact 工具不存在。让模型列工具，`-p` 会话的工具列表（含 deferred）里没有 Artifact，只有 claude.ai Claude Docs 连接器（batch/guide/update 等）。无需额外参数也无法绕过。
- 因此"链接能否在 Claude Code / claude.ai/code 打开"**无法验证**（没有产出链接）。
- 可能的替代（**未测试**）：用 Claude Docs 连接器在 `-p` 里建文档并拿链接；或交互式会话里手动发布。均不等价于 Artifact，需你决定是否值得。
- 保底：本地 HTML + 通知，已可用。

## 4. 通知（能发出；点击效果待确认）

- `osascript display notification`：能发出，但点击无法自定义（系统默认唤起脚本编辑器，我没有观察到点击）。
- **决策**：咨询 codex / agy / grok。codex 与 grok 选 A（terminal-notifier 3.x，已改用 UserNotifications，`-open` 在点击时触发，且附出处）；agy 选 C（自写 Swift app），并称 A 已废弃，该说法被另两方带来源的反例推翻。采用 A，已 `brew install terminal-notifier`（3.1.0）。
- `spike/notify.sh`：首次运行报 "Notifications are not allowed for this application"，先 `open -a terminal-notifier.app` 触发授权后，第二次已发出，**进程会一直挂着等点击**（意味着在脚本/launchd 里要后台运行或加超时，否则会阻塞流水线）。
- **用户确认：点击通知能打开 HTML。** 注意：通知权限按 app 单独授权（terminal-notifier 自己要开，与 Orca 的权限无关）；曾出现一次 "Notifications are turned off for this application"（原因不明），重新开启后恢复，正式版需在安装说明里写明授权步骤。

## 5. launchd（能；日历触发有问题）

- claude 绝对路径：`/Users/ai/.local/share/mise/installs/node/lts/bin/claude`（mise 管理，升级 node 版本路径可能变）。
- plist 里**故意没设 PATH 和 HOME**。`kickstart` 触发，15 秒内 `claude -p` 成功执行 Bash 并写出文件（`spike/out/launchd-ok-kickstart.txt`）：
  - **登录态：正常**（无需任何额外设置，能调用模型和工具）。
  - **PATH：** `/usr/bin:/bin:/usr/sbin:/sbin`（launchd 默认）；claude 用绝对路径即可，但脚本里调 python3、brew 装的工具必须写绝对路径或自设 PATH。
  - **工作目录：`/`**，必须用绝对路径或设 `WorkingDirectory`。
  - **HOME：** `/Users/ai` 正常。
  - stdout/stderr 日志为空（`claude -p` 没打印内容，结果由它写文件）。
  - 用了 `--permission-mode bypassPermissions` 才能让 Bash 写文件；正式版应改成最小授权。
- **`StartCalendarInterval` 未触发**：注册后 2–3 分钟的时间点，`load` 两次、`bootstrap` 一次，共 3 次，到点后 `runs = 0`，机器全程唤醒。`StartInterval=30` 的同一 plist 正常触发（39 秒）。plutil 通过，Hour/Minute 为 integer。原因未查明（codex：未发现与此吻合的 macOS 26 已知缺陷；grok 提到 DarkWake 行为；agy 推测类型/对齐问题，但类型已核对无误）。
- **决策**：咨询三方，**一致选 B**：`StartInterval=60`（加 RunAtLoad）+ 脚本内用 `TZ=America/New_York` 判断"最近一个已到期的纽约 19:00 是否已成功运行"，用标记文件做幂等。理由：①本机是 Shanghai 时区，日历项只认本机时区，纽约夏令时（11 月 1 日切换）会让写死的 Hour 偏一小时；②自带补跑，睡过点后下一次 tick 即补；③已验证 StartInterval 可靠。codex 的补充：用"最近已到期的 19:00"而非"今天是否 ≥19:00"，否则会漏掉睡过纽约午夜的情况。
- 未验证：睡眠后补跑（没有让机器睡眠）。
- 清理：`launchctl bootout` + 删除 `~/Library/LaunchAgents/com.mindgap.spike*.plist`，`launchctl list` 已无 mindgap。

## 6. Orca（本地 HTML 能）

- 已执行 `open <html>`（默认浏览器）和 `open -a Orca <html>`，均返回 0。无法从命令行验证 Orca 是否真的显示了页面。
- 绝对路径：`/Users/ai/Documents/my_mindgap/2026/10/2026-10-15.html`
- Artifact 链接：无（见第 3 项）。
- **用户确认：Orca 里可以打开本地 HTML（`open -a Orca <path>`）。** Artifact 链接因第 3 项无法产出，未测。

## PLAN.md 需要修改的地方

1. **长度过滤阈值 500 → 400 字**（你的新指示），并同步改"零、已知事实"和完成标准。
2. **定时方式**：不要用 `StartCalendarInterval`。改为 `StartInterval=60` + RunAtLoad + 脚本内纽约时间判断 + 幂等标记；补跑逻辑用"最近一个已到期的纽约 19:00"。
3. **launchd 环境**：plist 须写绝对路径、`WorkingDirectory`、`EnvironmentVariables.PATH`（含 python3 和 terminal-notifier 所在目录）；claude 路径由 mise 管理，需在安装步骤里解析而非写死，或提示升级后重装。
4. **Artifact**：`claude -p` 下不可用，PLAN 里"Artifact 链接写进 JSON/index.html"这条要降级为可选；保底是本地 HTML + 通知。需决定是否改用 Claude Docs 连接器或手动发布。
5. **通知**：把 terminal-notifier（brew）列为依赖，需首次 `open -a` 授权；调用必须不阻塞（后台/超时）。osascript 不能作为方案。
6. **`claude -p` 调用约定**：prompt 走 stdin；`--output-format json` 取 `.result`；`--allowedTools` 后不能直接跟位置参数；分析 prompt 必须强制从 taxonomy 选 label、evidence 带 `tool` 和会话文件名；必须有 schema 校验和重试；引文校验需机器可核（返回 URL 并抓取比对），不能只信模型。
7. **时区**：本机时区是 Asia/Shanghai，代码里"前一天"必须显式用 America/New_York，不能用 `datetime.now()`。
8. **会话数**：PLAN 的"7 个会话"改成"5 个含手敲文字的会话"。
9. **成本/耗时预算**：单次分析约 52 秒、$0.18，可写入交付说明。
10. 未验证项挪到 Phase 1 验收：raw/ 快照、睡眠补跑、通知点击、Orca 打开。

---

# 追加：第二天（2026-10-16）+ 多天报告（2026-10-22 运行）

## 第二天跑通
- 脚本改为按日期参数运行：`python3 spike/extract.py 2026-10-16 && python3 spike/analyze.py 2026-10-16 && python3 spike/render.py 2026-10-16`；中间产物放在 `spike/out/days/<日期>/`（10-15 旧产物已复制过去；用新版 extract 重跑 10-15，结果与旧 prompts.json 一致）。
- 提取：126 行 → 斜杠命令 30 → 剥离后为空 5 → 超长 0 → **91 条有效 prompt，31 个会话，6100 字**。
- 分析：rc=0，**结果直接就是合法 JSON**（第 2 个样本，两次都没用上兜底正则）。但**耗时 252 秒、19 轮、$0.87**，约为 10-15 的 5 倍。数据量只翻了一倍多，主要开销在联网核实引文的轮数上，所以预算要按"单次最多约 $1、约 5 分钟"估，launchd 脚本也不能设太短的超时。
- 结果：盲点"把'定义问题'外包给'打磨措辞'"，4 条证据，选书 Pólya《How to Solve It》，4 个片段都标为原文（`is_paraphrase` 全为 false，**未独立核对**）。
- 两天的 label 都是自由文本，无法跨天归类。要做多天的"重复盲点"统计，taxonomy 必须先落地。

## 多天报告 HTML 设计（已验证）
- **存档即数据源**：每天在 `~/Documents/my_mindgap/YYYY/MM/` 下写 `YYYY-MM-DD.json`（含 date、stats、analysis）和 `.html`。总览页只扫描存档里的 `*.json` 生成，不依赖 spike/out，可以随时重建。
- **`~/Documents/my_mindgap/index.html`**：顶部是汇总数字（天数、prompt 总数、覆盖范围）；然后是每日 prompt 量的纯 CSS 条形图，每根柱子可点；主体是按时间倒序的每日卡片（日期、星期、prompt/会话数、盲点标签、摘要、书），整张卡片可点；最后是书单。
- **日报**：页首和页尾都有"← 前一天 / 总览 / 后一天 →"，跳过没有报告的日期。新增一天会改变前一天的"后一天"链接，所以 render 每次重渲全部日报，几天到几百天都是毫秒级。
- 全部使用相对链接，没有 JS 和 fetch（file:// 下 fetch 会被拦），用 CSS 变量适配深浅色。
- 验证：脚本检查了 14 个 href，全部指向存在的文件；用 headless Chrome 截取 index 和 10-16 日报，渲染正常（导航、条形图、卡片、深色模式）。
- 未验证：Orca 中点击页内跳转（预期没问题，因为是普通相对链接）；几十天以后条形图会挤，届时改为按月分组或只显示最近 30 天。

## 对 PLAN.md 的追加修改
11. 存档结构加上每日 `.json`，`index.html` 由这些 json 生成；每次运行都重渲全部日报和 index。
12. 单次分析预算上调为 ≤$1、≤5 分钟（`--max-budget-usd` 保持 3 作为上限）。
13. 通知点击后可以考虑打开 index.html 而不是当天日报，或在通知里同时提供两者（待定）。

---

# 追加：可核验的报告（超链接 + 机械核对，2026-10-22）

目标：报告里的每条证据和每段引文，读者都能点过去亲眼核对，并且由脚本而不是模型给出"核对通过 / 未通过"的结论。

## 数据在哪
- **对话原文**：`~/.claude/projects/<项目>/<sessionId>.jsonl`。证据里的 sessionId 可以直接对应到文件；用户消息的 `timestamp` 比 history.jsonl 早 0–4 秒。
- **对话 HTML**：`uvx claude-code-transcripts json <jsonl> -o <dir>`（Simon Willison 的工具，用 uvx 临时运行，没有全局安装）。它把会话分页生成 `page-00N.html`，每条消息都有锚点 `id="msg-<UTC 时间戳，: 和 . 换成 ->"`。坑：`-o` 的父目录必须事先存在。
- **引文出处**：分析时用了 `--no-session-persistence`，模型实际访问过哪些网址没有保存下来。所以另起一个 `claude -p`（`spike/cite.py`），只让它为每段引文找公开网址并返回页面上的原句，**结论由脚本自己抓网页比对得出**。

## 实现
- `spike/link.py DAY`：为每条证据定位那条用户消息，规则是"去掉 `…` 和 `[已脱敏]` 后每个片段都在消息里出现，再取时间最近的一条"。这样能区分同一句话发了两次的情况（10-16 的 "grill yourself, 重新生成" 出现在 13:06 和 13:11，正确选中 13:11）。生成的对话 HTML 放在 `~/Documents/my_mindgap/transcripts/<sid>/`，结果写入 `links.json`：是否在分析输入中、是否在会话原文中、时间差、跳转链接。
- `spike/cite.py DAY`：找网址的步骤结果缓存在 `cite-found.json`，重跑只做核验，不再花钱。核验方法：按 `…` 拆段，去掉标点和空格后比对字母串，OCR 只容忍一处局部错误（12 字母一片，最多缺 1 片）。转述不做逐字比对，改为核对它对应的原句是否在页面上。跳转链接用 Text Fragment（`#:~:text=开头,结尾`，每段一个 `text=`）。
- `render.py`：证据下方显示"✓ 在分析输入中 · ✓ 在会话原文中（时间差 N 秒）· 查看原对话 ↗"；引文下方显示核对状态和"打开出处并高亮 ↗"。每天末尾有"核验"一节，列出汇总数字和原始数据目录；总览卡片上也显示"核验：证据 x/y · 引文 x/y"。

## 结果
| 日期 | 证据（输入 ∧ 会话原文） | 引文 |
|---|---|---|
| 10-15 | 4/4，时间差 0.2–2.5 秒 | 1 段逐字找到；2 段转述，对应原句已找到；**1 段网页上未找到** |
| 10-16 | 4/4，时间差 1.4–3.9 秒 | 4/4 逐字找到（archive.org 的 OCR 全文） |

- 10-15 那段未找到的原因已查明：斯坦福在线版由 latex2html 转换时，把 "relative to an *information need*, not a query" 里的 "information need" 变成了空锚点，网页上确实缺这几个词。引文本身大概率没错，但脚本按网页实际内容如实标红，**没有为了好看去放宽规则**。
- 发现并修复了检查器的一个假阳性：中文转述去掉英文字母后是空串，空串"包含于"任何页面，因此被误判为"逐字找到"。现在长度 < 20 的字母串一律判为不匹配，转述改为核对对应原句。**教训：核验器本身也要用反例测一遍。**
- 本地链接校验：24 个本地 href（含锚点）全部存在。

## 未验证 / 风险
- **Text Fragment 高亮未实测**：无头 Chrome 截不到滚动后的画面，带锚点的页面截图都是空白（不带锚点渲染正常）。需要人工在 Chrome 或 Safari 里点一下；Orca 是否支持 Text Fragment 也未知。archive.org 的 OCR 文本有断行连字符（如 "writ- ten"），高亮可能在这类地方失败，但核验结论不受影响，核验用的是脚本比对。
- **隐私**：transcripts 是**完整、未脱敏**的会话，包括 AI 回复和工具输出，存放在 `~/Documents/my_mindgap/transcripts/`。本地自用问题不大，但这个目录不能同步或分享；正式版要么对 transcript 做脱敏，要么只截取引用前后几条消息。
- **成本**：每天的找出处步骤约 $1、1.5–3.5 分钟，和分析本身差不多，日成本因此翻倍。我写缓存的脚本出错，导致两天各多调用了一次（多花约 $1.5）；之后已改为缓存优先。
- 会话 jsonl 会持续增长，transcript 只在第一次生成，之后不会更新（锚点不会失效，但后续对话不会出现在页面里）。

## 对 PLAN.md 的追加修改
14. 分析 prompt 要求每段引文返回 `source_url` 和页面上的原句；找出处和核验作为独立步骤，**核验结论只由脚本给出**。
15. 证据必须带 sessionId 和精确时间，渲染时链接到 claude-code-transcripts 的消息锚点；把 claude-code-transcripts 列为依赖（uvx）。
16. 报告固定有"核验"一节；总览页显示每天的核验比例；核验失败的条目标红，不能删掉。
17. transcripts 目录的隐私策略（脱敏或只截取局部）。

---

# 追加：补齐 10-17 ～ 10-21（2026-10-22 运行）

## 结果
| 日期 | 有效 prompt / 会话 | 分析 $ / 秒 | 找出处 $ / 秒 | 证据 | 引文逐字找到 |
|---|---|---|---|---|---|
| 10-17 | 19 / 8 | 0.54 / 120 | 0.63 / 194 | 4/4 | 2/4 |
| 10-18 | 0 | — | — | 无记录 | — |
| 10-19 | 0 | — | — | 无记录 | — |
| 10-20 | 4 / 2 | 0.49 / 147 | 0.55 / 119 | 4/4 | 2/5（另 2 段转述已找到对应原句） |
| 10-21 | 8 / 3 | 0.40 / 82 | 0.35 / 84 | 4/4 | 0/4 |

5 天的分析输出都是合法 JSON，没有用到兜底解析。这一轮合计约 $3。总览页改为按连续日期显示：空白日期在柱状图上是灰色空柱，在列表里显示"无记录"。

## 新发现
1. **插队消息**：在 AI 回复中途发出的 prompt，在会话 jsonl 里不是 `type=user`，而是 `queue-operation`（enqueue/remove）和 `attachment.type=queued_command`。**history.jsonl 的时间等于 `remove`（送达）时间**。claude-code-transcripts 不渲染这类消息。第一版 link.py 因此匹配到了几小时后的**压缩摘要**（`isCompactSummary`，摘要里会转述旧 prompt），时间差 4387 秒和 9143 秒，链接是错的。修复后：把 remove 和 queued_command 也作为候选，排除压缩摘要，插队消息链接到它送达后的下一条消息；时间差超过 60 秒标为 ⚠，不算通过。现在 20 条证据全部在 5 秒以内。
2. **检查器抓到了真实的引文错误**：
   - 10-17：Kahneman 的 premortem 原话是 "The outcome **has been** a disaster"，模型写成了 "was a disaster"。
   - 10-21：模型把 dwheeler.com 上的**书评摘要**（小写，夹着括号注释）重新排版后，当成 Agans 原书文字引用。
   - 10-21 第 4 段：找出处的模型直说找不到，返回 null，没有硬编网址。
3. **来源质量**：不少出处是 goodreads 等用户摘抄站。在那里"逐字找到"只说明别人也这么引过，不能证明原书原文就是这样。报告里已按域名把出处标为"一手：全文/官方"或"二手转引"。正式版应优先找一手全文；只有二手出处的，在核验数字里单独计数。
4. **数据太薄的日子**：10-20 只有 4 条 prompt，模型把全部 4 条都当成证据，其中一条是 "背景：20261020"，本身不构成证据。10-21 有 8 条，结论还算具体，但都来自同一件事（代理 403）。结论：**需要最低数据门槛**，比如有效 prompt ≥ 15 条或 ≥ 2 个主题会话，不够就生成"数据不足"页，或并入周报，不要硬凑盲点。
5. **隐私**：10-20 的内容是个人日记和家庭情绪，被原样写进了证据和 transcript。正式版要考虑按项目或目录的排除名单（例如非工作目录不分析），或者在分析前让用户确认。

## 对 PLAN.md 的追加修改
18. 提取会话时，处理 `queue-operation` / `queued_command`，排除 `isCompactSummary`；证据定位必须做时间一致性检查。
19. 设最低数据门槛，不够就输出"数据不足"或并入周报。
20. 引文出处分为一手和二手；核验指标只把"一手逐字找到"算作通过。
21. 敏感或个人内容的排除机制。
