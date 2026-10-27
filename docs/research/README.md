# MindGap 深度调研体系总览与执行摘要
> 本地 AI Agent 对话复盘、思维盲区挖掘与成长荐书体系  
> 对应执行计划：`deep_research_plan.md` | 状态：全部交付完成 (Phases 1-5)

---

## 调研成果交付全景

本项目围绕“如何从工程师与本地 CLI AI Agent（Claude Code / Codex / AGY / Grok）的交互轨迹中，科学挖掘认知偏误与思维盲区，并构建有效的干预与心智成长机制”这一命题，完成了全方位的实证研究、逆向工程、理论构建与架构设计。

所有交付成果已归档于 `docs/research/` 目录下，并形成了机械可执行的分类学配置文件与测试套件：

| 阶段 | 交付物文档 | 核心内容与实测突破 | 关联代码/配置 |
| :--- | :--- | :--- | :--- |
| **Phase 1: 生态评测与理论框架** | [01_landscape_audit.md](file:///Users/ai/github/my_projects/mindgap/docs/research/01_landscape_audit.md) | 四大技术谱系（chathist、DoT、Mindsera、Readwise）与基础设施（Instructor、Outlines、Pydantic-AI、Langfuse）评测。 | - |
| **Phase 1: 理论框架透镜** | [02_theoretical_lenses.md](file:///Users/ai/github/my_projects/mindgap/docs/research/02_theoretical_lenses.md) | 认知科学（IOED、认知卸载）、HCI（自动化偏见、谄媚陷阱）、系统工程（XY问题、高尔定律）理论演绎。 | - |
| **Phase 2: 多 Agent 协议逆向** | [03_agent_log_protocols.md](file:///Users/ai/github/my_projects/mindgap/docs/research/03_agent_log_protocols.md) | 实测逆向 Claude Code、Codex CLI、AGY、Grok 真实数据；**实测揭示纯手敲 Prompt 存在 36.8% 指代缺失，验证了轻量上下文注入（1.42x Token）可将归因准确率从 61.5% 跃升至 94.2%**。 | `scratch/analyze_agents_data.py` |
| **Phase 3: 实证分类学构建** | [04_taxonomy_v1.md](file:///Users/ai/github/my_projects/mindgap/docs/research/04_taxonomy_v1.md) | 扎根理论质性编码；定义三大维度、10 大正交工程盲点；制定严格判定边界、必要证据链与合法工程反例。 | [taxonomy.json](file:///Users/ai/github/my_projects/mindgap/mindgap/taxonomy.json) |
| **Phase 4: 诊断架构比选** | [05_diagnosis_benchmark.md](file:///Users/ai/github/my_projects/mindgap/docs/research/05_diagnosis_benchmark.md) | 对比单阶段生成 vs 生成-审计双阶段对抗架构（Generator-Critic）vs 动态 Few-Shot；**红队审计将虚假指控率从 36.7% 断崖式压制至 6.7%**。 | `scratch/sample_qualitative_turns.py` |
| **Phase 4: 防伪引文核验** | [06_citation_verification.md](file:///Users/ai/github/my_projects/mindgap/docs/research/06_citation_verification.md) | 专家金标准书库 vs 实时全网检索对比；Open Library 元数据权威化；滑动窗口 N-Gram 机械对齐比对与 Text Fragment 高亮生成。 | `scratch/test_book_apis.py` |
| **Phase 5: 认知干预体验设计** | [07_intervention_design.md](file:///Users/ai/github/my_projects/mindgap/docs/research/07_intervention_design.md) | 福格行为模型（B=MAP）在疲惫工程师场景的应用；15 分钟阅读预算与单文件零跳转；长期元认知度量模型（盲点复发周期 MRI、盲点熵 CBE）。 | - |
| **Phase 5: 系统落地技术方案** | [08_system_architecture.md](file:///Users/ai/github/my_projects/mindgap/docs/research/08_system_architecture.md) | 端到端工程架构；**实证破解 launchd 日历触发缺陷，确立 StartInterval=60 状态轮询 + 脚本内时区判定 + 幂等标记的标准解法**。 | `spike/` / `launchd/` |
| **专题调研: 多 Agent 作战指挥室** | [11_claude_code_command_center_architecture.md](file:///Users/ai/github/my_projects/mindgap/docs/research/11_claude_code_command_center_architecture.md) | 将 Claude Code 单 Session 设计为多 Agent 作战指挥室的完整架构方案、角色分类体系、契约规范与实跑配置。 | `.claude/` / 架构规范 |

---

## 核心研究结论摘要（Key Findings）

1. **认知信号提取必须采用“精选前驱上下文注入（Selective Context Injection）”**：
   - 纯分析手敲 Prompt 存在致命盲区——实测人类在终端中有 36.8% 的 Prompt 属于“这个报错修一下”、“为什么还是挂了”等指代性短语；
   - 注入前驱 300 字符错误堆栈仅增加 42% 的 Token 开销，却能使可归因率达到 94% 以上。
2. **必须引入“对抗性红队审计（Adversarial Critic）”以消除模型谄媚与虚假指控**：
   - 单阶段端到端生成（Single-pass）极易陷入“强行挑刺与讨好用户”的陷阱，对正常敏捷妥协的误判率高达 36.7%；
   - 设立专职为工程师辩护的对抗性红队角色，能够把虚假指控率压低至 6.7%。
3. **引文必须机器确定性防伪，建立 Tier-1 优先的双层知识体系**：
   - Google Books API 存在严格限流（HTTP 429）且无法提供段落级查询；Open Library API 适合做作者/年份元数据校准；
   - 建立涵盖 Pólya、Brooks、Ousterhout 等传世专著的 Tier-1 金标准书库，搭配滑动窗口 N-Gram 文本对齐与 Text Fragment 直达高亮，彻底根除“引文幻觉”。
4. **macOS 定时任务的生产级防坑标准**：
   - 摒弃脆弱的 `StartCalendarInterval`，采用 `StartInterval=60` 状态驱动轮询，配合脚本内 America/New_York 时区自省与 `.last_run_date` 幂等标记，完美兼顾睡眠唤醒补跑与跨夏令时稳定性。
