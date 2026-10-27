# 社群中"基于历史交互诊断专业知识缺口 + 判断准则 + 权威文献"的 Prompt 调研

> 调研日期：2026-10-24 ｜ 时间窗口：2024-10 至 2026-10
> 流程：agy（Gemini 3.8 Flash High）初调研 → Codex（gpt-6.1-sol）对抗审稿 + 补搜 → Claude 逐条抽查 URL 并合并
> 与 [09_community_prompts_audit.md](09_community_prompts_audit.md) 的区别：09 覆盖"聊天历史 → 认知偏误/性格盲点"；本篇聚焦**专业领域**的概念缺口与判断准则缺口。

---

## 一、结论

**截至 2026-10-24，没有找到一个可定位原文、同时明确满足 F1–F5 的公开 prompt。** 这是"未检索到"，不是"证明不存在"。

| 特征 | 含义 |
|---|---|
| F1 | 输入是人与 AI 的历史交互（多轮、跨会话或导出记录） |
| F2 | 诊断**该用户**在特定专业领域缺失的核心概念 |
| F3 | 诊断**该用户**缺失的判断依据、决策准则或启发式 |
| F4 | 检索权威文献并与每项缺口对齐，引用可核验 |
| F5 | 结构化输出（框架、概念图、学习路径等） |

社群现状可以概括为三条互不相连的路线：

1. **历史复盘类**（F1 + F5）：滑向性格、偏误和工作流，例如 Intellectual Autopsy、Personal Operating Manual、Claude Code `/insights`。
2. **专家视角类**（F3 雏形）：只针对单次提问或单个材料，例如 S Anand 的 expert lens、Ruben Hassid 的任务复盘。
3. **学习伴侣类**（F1 + F2 + F4 + F5）：**最接近**，以 Claude Code 的 `CLAUDE.md` 项目形态出现，而不是单条 prompt。例如 CFP-Study、Claude-Code-As-Teacher。

**真正的空白**有两处：(a) 把"用户缺失的判断准则"作为显式诊断对象（F3）；(b) 让每一项缺口逐条绑定一条经过核验的权威来源（F4 闭环）。

---

## 二、已核实候选（按接近程度排序）

✅ 明确要求 ｜ ◐ 部分覆盖 ｜ ❌ 未要求。"核实"列说明谁确认过原始来源。

| # | 候选 | 来源 | F1 | F2 | F3 | F4 | F5 | 核实 | 要点 / 缺口 |
|---|---|---|:-:|:-:|:-:|:-:|:-:|---|---|
| 1 | **CFP-Study `CLAUDE.md`**（chenran818） | [GitHub](https://github.com/chenran818/CFP-Study/blob/main/CLAUDE.md) | ✅ | ✅ | ◐ | ◐ | ✅ | Codex + Claude | 每次会话先读历史笔记，记录 "Knowledge gaps identified" 并维护缺口追踪表；技术问题要求 "ALWAYS search online FIRST" 并 "CITE YOUR SOURCE"（IRS、CFP Board）。缺口：其中的决策规则是给**导师**用的，没有诊断**学生**缺哪些判断准则；引用是按问答给的，不是按缺口对齐 |
| 2 | **Claude-Code-As-Teacher**（consistentJake） | [GitHub](https://github.com/consistentJake/Claude-Code-As-Teacher) | ✅ | ✅ | ◐ | ◐ | ✅ | Codex + Claude | 系统设计面试的苏格拉底式教学；会话自动记录知识缺口，`/review-progress` 分析进展；`/search-topic` 检索权威来源，但没确认输出里是否带引用 |
| 3 | **Bridge**（Rose E. Wang 等，Stanford） | [GitHub](https://github.com/rosewang2008/bridge) · [arXiv 2310.10648](https://arxiv.org/abs/2310.10648) | ◐ | ◐ | ✅ | ❌ | ◐ | 三方 | NAACL 2024。用**认知任务分析（CTA）**把专家教师的隐性决策显式化为"错误识别 → 补救策略 → 意图"三步，数据是 700 段辅导对话。这是 F3 在学术上最严谨的源头，但诊断对象是学生的数学错误，不是通用的用户专业判断 |
| 4 | **Dialogue Knowledge Tracing**（Scarlatos 等，LAK 2025） | [GitHub](https://github.com/umass-ml4ed/dialogue-kt) | ◐ | ✅ | ❌ | ❌ | ◐ | Codex | 从辅导对话逐轮抽取知识组件并追踪掌握度，是 F2 的学术方法源头 |
| 5 | **Ruben Hassid 任务复盘 prompt** | [Substack note](https://substack.com/@ruben/note/c-283759371) | ✅ | ◐ | ◐ | ❌ | ✅ | Codex | 复盘刚完成的任务：方案取舍、弃选理由、专家会注意什么。说明历史复盘不只能做心理分析，但没有显式诊断用户缺失 |
| 6 | **S Anand "expert lens"** | [blog, 2026-03-01](https://www.s-anand.net/blog/ai-expert-lens/) | ❌ | ◐ | ✅ | ❌ | ◐ | Claude | "What patterns would an expert in this field check / recognize that beginners would miss?" 是 F3 最干净的 prompt 片段，但只针对单次提问 |
| 7 | **Fabric** `analyze_mistakes` / `t_find_blindspots` / `create_reading_plan` | [patterns 目录](https://github.com/danielmiessler/fabric/tree/main/data/patterns) | ◐ | ❌/◐ | ◐ | ❌ | ✅ | Claude（reading_plan）、Codex（其余） | `create_reading_plan` 分为 Core / Extended / Exploratory 三阶段，可作为 F4/F5 的输出模板；`t_find_blindspots` 基于 TELOS 个人上下文找盲点 |
| 8 | **Personal Operating Manual**（u/Independent_Fan_3915） | [r/ChatGPT 帖](https://www.reddit.com/r/ChatGPT/comments/1wsxtk0/i_asked_chatgpt_for_the_most_useful_prompt_user/) | ✅ | ❌ | ❌ | ❌ | ✅ | 仅 Codex（Reddit 拒绝 Claude 抓取） | 2026-09 发布；"for every inference, state the evidence… confidence… alternative explanation" 是很好的防巴纳姆结构，但分析对象是个人工作流 |
| 9 | **Claude Code `/insights`** | [第三方介绍](https://blog.vincentqiao.com/en/posts/claude-code-insights/) | ✅ | ❌ | ◐ | ❌ | ✅ | Claude | 内置命令，基于本地会话生成 HTML 报告；关注的是工作流和协作习惯 |
| 10 | **Tom Morgan "From all of our interactions…"** | [TechRadar 报道](https://www.techradar.com/computing/artificial-intelligence/new-chatgpt-prompt-goes-viral-with-sam-altmans-approval) | ✅ | ❌ | ❌ | ❌ | ❌ | Claude | 2024-10 在 X 走红，Sam Altman 回复 "love it"；Simon Willison 称其为 "horoscope generator" |
| 11 | **Intellectual Autopsy** | [r/ChatGPTPromptGenius](https://www.reddit.com/r/ChatGPTPromptGenius/comments/1ry35ae/your_chatgpt_memory_is_the_most_honest/) | ✅ | ❌ | ❌ | ❌ | ◐ | 仅 Codex | 能找到的原帖是 2026-03-19，作者已删号；agy 和 09 号报告里"2024-10 起源"的说法没有找到证据 |

---

## 三、agy 初稿被 grill 出的问题

| 问题 | 发现者 | 处理 |
|---|---|---|
| "Active Recall Canon Scaffold" 找不到任何出处 | Claude + Codex | **删除**，疑似编造 |
| "What Would an Expert Notice"给的是 EmergentMind 首页，引文搜不到 | Claude + Codex | **删除**，改用可核实的 S Anand 和 Ruben Hassid 版本 |
| Fabric `create_reading_plan` 三阶段描述错误（agy 写成 Foundational / Deep Dives / Contrarian） | Claude + Codex | 更正为 Core / Extended / Exploratory |
| Bridge 写成 "arXiv 2402.x、覆盖临床/代码重构" | Codex | 更正为 2310.10648、仅限数学辅导 |
| Personal Operating Manual 日期写成 2024-10（实际约 2026-09），并且把"只用已有信息"夸大成"禁止外部文献" | Codex | 更正 |
| 多个 URL 只指向 subreddit 首页 | Claude | 已替换为具体帖子或标注未核实 |
| 把"未检索到"写成"从未""不存在"；"几乎 100% 引文幻觉"没有统计依据（实测 GPT-4 虚构文献约 18%，[PMC10484980](https://pmc.ncbi.nlm.nih.gov/articles/PMC10484980/)） | Codex | 结论改为"尚未找到可核实的完整匹配" |
| 漏掉最接近的一类：Claude Code 学习伴侣项目 | Codex | 补入第 1、2 条 |
| F1–F5 打分口径不一致（例如 Fabric 的 F2 给了 ✅） | Codex | 统一口径：F2/F3 必须诊断**该用户**的缺失，展示专家知识不算 |

**附带发现**：09 号报告里"Intellectual Autopsy 2024 秋起源"和"Mark Manson 版 prompt"同样缺少可核实的出处，建议回头用本篇的方法复查。

---

## 四、为什么完整版本少见（已去掉无证据的推断）

可以较有把握地说的：
- **F4 需要工具，单靠 prompt 做不到。** 纯 prompt 模式下要求"精确引用"有明确的幻觉风险。社群中做到 F4 的（CFP-Study 等）都依赖 agent 的联网搜索能力，所以自然以 `CLAUDE.md` 或 skill 的形态出现，而不是一段可以复制粘贴的 prompt。
- **F3 的方法论（CTA、NDM）停留在学术侧。** Bridge 已经证明能把专家决策建模成可提示的步骤，但目前没看到它被转化成面向终端用户的复盘 prompt。
- **传播得广的历史复盘 prompt 都偏向自我认知话题**（Tom Morgan、Autopsy、Operating Manual）。这是观察到的现象，不是已证明的因果。

---

## 五、对 MindGap 的启示

1. **缺口就是机会**：F3（判断准则缺口）+ F4（逐缺口对齐的核验引用）正是社群空白，也是 MindGap 的差异化定位。
2. **可直接借鉴的零件**：
   - Personal Operating Manual 的"推断 + 证据 + 置信度 + 替代解释"四元组 → 用于诊断输出格式（与 05 号报告的红队审计互补）
   - S Anand expert lens 的四个问题 → 用于 F3 的诊断提示
   - Bridge 的 CTA 三步（识别错误 → 选择策略 → 陈述意图）→ 用于判断准则的分类骨架
   - CFP-Study 的"缺口追踪表 + Recently Resolved" → 对应 07 号报告的盲点复发度量
   - Fabric `create_reading_plan` 的三层阅读结构 → 用于 F5 的荐书输出
3. **F4 必须机器核验**，这与 06 号报告的结论一致。

---

## 附：过程记录

- agy 原始输出：job `agy-mvme6xu9-99pd4f`，约 9.8k 字符
- Codex grill：`codex exec -s read-only -c tools.web_search=true`。第一次运行因为 stdin 没关闭，卡在 "Reading additional input from stdin…" 约 40 分钟；加上 `</dev/null` 后正常完成
- Claude 独立核实了：Bridge、Fabric create_reading_plan、S Anand、Tom Morgan、`/insights`、CFP-Study、Claude-Code-As-Teacher。Reddit 两帖只有 Codex 确认过，因为 Reddit 屏蔽了 Claude 的抓取
