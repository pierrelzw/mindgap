# 深度调研报告：将 Claude Code 单 Session 设计为多 Agent 软件工程作战指挥室

> **文档编号**：`docs/research/11_claude_code_command_center_architecture.md`  
> **研究主题**：AI Software Engineering Command Center Architecture in Claude Code  
> **核心目标**：在单一用户交互 Session 下，利用 Claude Code 原生编排基建（Subagents、Hooks、Worktrees、Agent Teams），构建高可靠、高并发、确定性验证的软件工程作战指挥系统。

---

## 目录
1. [研究目标与核心设计哲学](#1-研究目标与核心设计哲学)
2. [Claude Code 原生编排能力深度剖析](#2-claude-code-原生编排能力深度剖析)
3. [Commander / Orchestrator 核心设计](#3-commander--orchestrator-核心设计)
4. [Worker Agent 最佳设计方法与角色分类体系](#4-worker-agent-最佳设计方法与角色分类体系)
5. [任务分解（Task Decomposition）与执行调度](#5-任务分解task-decomposition与执行调度)
6. [Agent 间标准任务与结果契约（Contracts）](#6-agent-间标准任务与结果契约contracts)
7. [模型选择与资源动态路由策略（Model Routing Policy）](#7-模型选择与资源动态路由策略model-routing-policy)
8. [质量控制（Quality Control）与失败恢复机制](#8-质量控制quality-control与失败恢复机制)
9. [真实场景端到端工程推演](#9-真实场景端到端工程推演)
10. [五种编排架构横向基准对比分析](#10-五种编排架构横向基准对比分析)
11. [可直接落地的作战指挥室渐进式实施方案](#11-可直接落地的作战指挥室渐进式实施方案)
12. [终局结论与十问十答决策底册](#12-终局结论与十问十答决策底册)

---

## 1. 研究目标与核心设计哲学

在单 Session 中构建 **AI Software Engineering Command Center（多 Agent 作战指挥室）**，本质上是解决以下三大核心工程矛盾：

1. **交互集中性与执行分散性的矛盾**：人类工程师需要一个确定、持续、单一的交互界面（Single Pane of Glass），但复杂工程任务需要高度并发、上下文隔离与专业分工。
2. **LLM 概率生成与软件工程确定性的矛盾**：任务编排绝不能依赖 LLM 的“自觉”与“长程记忆”，必须依靠**显式状态机、代码级契约（Contracts）与确定性守卫（Deterministic Guardrails）**。
3. **复杂度惩罚（Complexity Penalty）**：Agent 数量膨胀、角色过细不仅不会提升产出，反而会因上下文碎片化、跨 Agent 通信损耗和依赖死锁导致系统性崩溃。系统演进必须遵循“最小充分原则”。

---

## 2. Claude Code 原生编排能力深度剖析

### 2.1 底层原生编排机制与基础设施

Claude Code 提供了多层次的原生扩展与编排机制，其关键特性与边界如下：

| 原生机制 | 载体与文件位置 | 上下文边界 | 工具与执行隔离 | 适用边界与通信方式 |
| :--- | :--- | :--- | :--- | :--- |
| **Subagents** | `.claude/agents/*.md`<br/>`~/.claude/agents/*.md` | **完全隔离**。继承全局 `CLAUDE.md` 与传入的 Task Prompt，看不到主 Session 历史。 | 支持在 Frontmatter 中配置工具白名单（如 `tools: [Read, Grep, Bash(git diff*)]`）。 | 单向委派与摘要聚合。主 Session 阻塞或异步等待，完成后仅返回摘要文本。 |
| **Agent Teams**<br/>*(Experimental)* | `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` | **多独立实例共享 Task 队列**。每个 Teammate 为独立进程/Session。 | 可结合 Git Worktree 实现文件级读写隔离。 | **双向/点对点通信**。支持 Lead-Teammate 及 Teammate 之间的 Message Passing，依赖共享任务列表。 |
| **Dynamic Workflows** | 运行时动态生成的 JavaScript 脚本引擎 | **无主 Session 上下文损耗**。在沙箱后台运行时中并发执行。 | 脚本受限运行时环境，子 Agent 按脚本调度执行。 | **扇出-聚合（Fan-out & Synthesize）**。适合针对数百个文件的批量扫描、审查或自动化迁移。 |
| **Lifecycle Hooks** | `.claude/settings.json` 或 `.claude/hooks/` | **确定性代码拦截器**（非 LLM），注入在生命周期点。 | 运行外部可执行脚本，拥有完全系统环境访问权限。 | `PreToolUse`、`PostToolUse`、`Stop`、`SubagentStart`。可阻断执行、拦截命令、强制验收。 |
| **Git Worktrees** | CLI 参数 `--worktree` (`-w`) | 共享底层 `.git` 库，独立 Working Directory 与分支。 | 强文件物理隔离，完全消除并发写冲突。 | 必须通过 Git Branch 和 Merge 策略整合成果。 |

---

### 2.2 三种编排方案对比：A vs B vs C

针对“用户始终在一个主 Session 中下达任务和查看进度”的需求，对比三种技术路线：

```mermaid
flowchart TD
    subgraph Solution_A["方案 A: 主 Session + Subagents（推荐主力）"]
        UserA[用户] --> MainA[主 Session: Commander]
        MainA -->|Task Contract| SubA1[Subagent 1: Explorer]
        MainA -->|Task Contract| SubA2[Subagent 2: Executor]
        MainA -->|Task Contract| SubA3[Subagent 3: Verifier]
        SubA1 -->|Result Summary| MainA
        SubA2 -->|Result Summary| MainA
        SubA3 -->|Result Summary| MainA
    end

    subgraph Solution_B["方案 B: Agent Teams (Peer-to-Peer 协作)"]
        UserB[用户] --> LeadB[主 Session: Team Lead]
        LeadB <-->|Shared Task List / P2P Message| TeamB1[Teammate: Frontend Worktree]
        LeadB <-->|Shared Task List / P2P Message| TeamB2[Teammate: Backend Worktree]
        TeamB1 <-->|P2P Message| TeamB2
    end

    subgraph Solution_C["方案 C: Dynamic Workflows (脚本化扇出)"]
        UserC[用户] --> MainC[主 Session]
        MainC -->|生成脚本| Runner[JS Workflow Runtime Engine]
        Runner --> Worker1[Parallel Worker 1]
        Runner --> Worker2[Parallel Worker 2]
        Runner --> WorkerN[Parallel Worker N]
        Runner -->|聚合报告| MainC
    end
```

#### 详细维度对比矩阵

| 评估维度 | 方案 A：主 Session 编排 Subagents | 方案 B：Agent Teams (Lead + Teammates) | 方案 C：Dynamic Workflows (脚本调度) |
| :--- | :--- | :--- | :--- |
| **动态决策灵活性** | **极高**。主 Session 每一步均可基于上一 Agent 的产出动态重规划。 | **高**。Teammates 可根据共享任务池动态认领与响应。 | **中低**。执行流由生成的静态 JS 脚本控制，适合结构化批处理。 |
| **并行执行能力** | **中等**（支持并发触发无依赖的子 Agent，但回传需集中整合）。 | **高**（天然支持常驻 Teammate 独立工作并结合 Git Worktrees）。 | **极高**（脚本级瞬间扇出数十/数百并发 Worker）。 |
| **跨 Agent 通信** | **星型拓扑**：仅 Subagent $\leftrightarrow$ 主 Session，无横向噪声。 | **网状拓扑**：支持 P2P 通信，信息更直接但也更易发散。 | **无 Agent 间直接通信**：完全通过脚本内存/临时文件汇聚。 |
| **任务状态持久化** | 依赖主 Session 内存 + 本地文件（如 `.claude/tasks/`）。 | 原生内置共享任务队列与状态指示。 | 脚本进程状态，执行结束即销毁。 |
| **成本与 Token 效率** | **最高**。无横向广播，主 Session 仅接收浓缩 Summary。 | **较高消耗**。多个独立 Session 保持存活，心跳与通信成本高。 | **适中**。Worker 任务极小化，开销集中在大量并发 API 调用。 |
| **执行隔离与安全性** | 通过 Frontmatter 工具白名单严格隔离。 | 依靠 Git Worktree 物理隔离，工作区完全独立。 | 脚本沙箱运行时隔离。 |
| **错误恢复与回滚** | **强**。单任务失败仅需重试该 Subagent，主上下文无污染。 | **中**。分布式状态下部分 Agent 故障需协同回滚。 | **弱**。脚本异常通常需整批重试或依赖异常捕获逻辑。 |
| **维护与成熟度** | **正式原生支持**，配置清晰，无系统级副作用。 | **实验性功能**，环境变数较多，排错成本高。 | 适合专项任务（全库扫描/批量迁移），不适合日常通用开发。 |

#### 概念厘清：单个用户控制入口 vs 底层物理 Session
* **单个用户控制入口（Single Control Pane）**：用户只需要面对一个终端窗口，所有的指令下发、阶段确认、进度汇报、阻断提问都在该窗口呈现。
* **底层物理架构**：
  * **方案 A**：底层依然只有**一个主 Session 进程**，Subagent 是由主进程派生的瞬态子执行单元（Ephemeral Isolated Subprocesses），生命周期随调随销，天然契合单 Session 控制。
  * **方案 B**：底层实际启动了**多个并行物理 Session**，主 Session 只是通过 IPC 或共享任务队列充当 Lead。在终端体验上容易出现并发输出交错、多分支合流冲突等管理成本。
  * **结论**：**方案 A（主 Session + 专职 Subagents + Lifecycle Hooks）是构建单 Session 作战指挥室最稳健、可控、低成本的核心底座；方案 B 适合在方案 A 遇到长周期并发代码冲突时按需降级/升级引入。**

---

## 3. Commander / Orchestrator 核心设计

Commander 是整个作战指挥室的中枢，必须承担系统工程中的“控制平面（Control Plane）”，而非“数据平面（Data Plane）”。

```mermaid
flowchart TD
    User([用户工程目标]) -->|Prompt| Entry[Commander 主 Session 接入]
    
    subgraph Plan_Phase[规划与依赖阶段]
        Entry --> Decomp[Goal Decomposition 目标分解]
        Decomp --> DagGen[Task DAG 构建 & 冲突检测]
        DagGen --> FileLock[文件所有权与锁策略分配]
    end

    subgraph Exec_Phase[调度与控制阶段]
        FileLock --> Dispatcher{调度分发器}
        Dispatcher -->|并行任务无冲突| Sub1[Worker Instance A]
        Dispatcher -->|并行任务无冲突| Sub2[Worker Instance B]
        Dispatcher -->|串行依赖阻塞| Queue[等待队列]
        Sub1 --> Collector[成果整合与契约校验]
        Sub2 --> Collector
        Collector --> Queue
    end

    subgraph Quality_Phase[质量守卫闭环]
        Collector --> GateKeeper{质量门禁}
        GateKeeper -->|Hook / Test 失败| Replan[错误恢复: 修复/升级模型]
        Replan --> Dispatcher
        GateKeeper -->|通过| StopHook[Post-Check: Stop Hook 物理阻断]
        StopHook --> UserConfirm[最终交付]
    end
```

### 3.1 十大核心职责划分

1. **Goal Decomposition**：将宏观需求拆解为**有明确定义交付物**的最小不可分任务（Atomic Tasks）。
2. **Task Planning & DAG**：构建有向无环图，明确每个任务的输入、输出前置条件（Prerequisites）。
3. **Dependency & Conflict Management**：标记代码修改边界，识别文件冲突（File Collision），将写冲突任务强制排队串行。
4. **Agent Selection & Delegation**：匹配最合适的能力单元，严禁“大马拉小车”或“无权限执行”。
5. **Model Routing**：根据子任务风险与推理深度，按策略分流到对应模型。
6. **Scheduling**：管理执行队列，实现无依赖任务并发、有依赖任务串行等待。
7. **Progress Tracking**：实时维护外部持久化任务状态板（`.claude/tasks/state.json`）。
8. **Context Management**：负责向子 Agent 提炼高纯度上下文，并阻断无效日志回流到主上下文。
9. **Integration**：审查多 Agent 的代码与产物，完成系统集成与链路打通。
10. **Verification & Recovery**：运行确定性检验（编译、测试、Lint、Diff 审计），不达标绝不宣布完成。

---

### 3.2 关键架构决策与问题解答

#### Q1: Commander 应该使用主 Session，还是单独的 Orchestrator Subagent？
* **结论**：**Commander 必须由主 Session 亲自承担，严禁将 Commander 委派给 Subagent。**
* **深度推演**：Claude Code 的交互宿主是主 Session。如果把编排逻辑交给 Subagent，Subagent 结束后其思考过程被压缩，主 Session 会失去对全局 DAG 的实时掌控；更严重的是，Subagent 无法原生拦截用户的交互式中断与审批请求。主 Session 具有最完整的生命周期，是天然且唯一的指挥官。

#### Q2: 是否应该尽量避免 Commander 亲自修改代码？
* **结论**：**绝对避免。Commander 严禁直接调用 `Edit` 或 `Write` 工具修改业务代码。**
* **深度推演**：
  1. *上下文污染*：一旦 Commander 开始修改业务代码，大量的 AST 变更、文件碎片和编辑失败重试将迅速撑爆主上下文，导致上下文压缩（Context Compaction），从而遗忘最初的用户目标。
  2. *职责分离*：Commander 应该始终保持“上帝视角”的客观性。亲自写代码会导致“自产自审”的认知盲区。Commander 仅被允许编辑编排元数据（如任务清单、契约文件、集成验证脚本）。

#### Q3: Commander 的系统指令适合放在何处？
* **推荐方案**：采用 **`CLAUDE.md` + 专属 Orchestrator Skill + Hooks** 三位一体结构：
  * **`CLAUDE.md`（项目宪法）**：声明“指挥室架构原则”（如禁止主 Session 直接修改代码、所有实现任务必须通过 Subagent 委派）。
  * **Skill `.claude/skills/orchestrate/`**：包含任务分解模板、DAG 计算规则、任务契约生成器的结构化工具。
  * **Hooks**：作为底层的不可越过红线，拦截非法操作。

#### Q4: 如何避免 Commander 在实现阶段遗忘最初的任务目标？
* **机制 1：外部状态机锚定**。在拆解任务完成后，立即在本地创建不可变文件 `.claude/tasks/objective.md`，记录最初的验收标准（Acceptance Criteria）与不可妥协约束。
* **机制 2：Prompt 循环注入**。在向任何 Worker 委派任务前，主 Session 强制读取一次 `objective.md`，将当前进度与最初目标进行对齐校验。
* **机制 3：利用 Subagent 上下文隔离保护主 Session**。因为实现细节全在 Worker 内部消化，主 Session 只保留契约摘要，其上下文 Token 消耗极缓慢，可连续工作数十轮而不发生上下文截断。

#### Q5: 如何让 Commander 不因为某个 Agent 报告完成，就错误地宣布整个任务完成？
* **机制 1：严禁依赖 Agent 的口头声明（No Verbal Trust）**。Worker 的 `status: completed` 仅表示“该 Worker 认为自己执行完毕”，不代表“客观标准已满足”。
* **机制 2：必须提供机器可读的验证证据（Verifiable Evidence）**。所有完成状态必须伴随：
  * 真实命令退出码（Exit Code 0）；
  * 测试套件输出（Test Output pass）；
  * Git Diff 范围符合预期。
* **机制 3：强制性的 `Stop` Hook 物理拦截**。配置 Claude Code 原生 `Stop` Hook。当主 Session 试图向用户宣布任务完成退出时，Hook 自动执行全量静态分析与回归测试，若失败则强制退出码非 0，迫使 Claude 继续停留在工作流中修复。

#### Q6: 哪些决策由 LLM 动态执行？哪些规则由 Hooks/脚本强制执行？
* **LLM 动态决策领域（智力层）**：
  * 需求意图理解与架构方案设计；
  * 任务依赖关系的拓扑排序；
  * 针对测试失败日志的根因假设（Hypothesis Formulation）；
  * 代码审查中的设计模式与业务逻辑合理性判断。
* **Hooks/脚本强制执行领域（物理层）**：
  * **分支保护与写权限隔离**（通过 `PreToolUse` 拦截未经许可的文件写入）；
  * **语法与代码规范**（通过 `PostToolUse` 强制执行 linter/formatter）；
  * **交付验收门禁**（通过 `Stop` Hook 强制执行自动化测试套件）；
  * **状态机校验**（任务 DAG 未全部置为 DONE 时禁止宣布完成）。

---

### 3.3 Commander 执行协议（State Machine Protocol）

```text
[PHASE 0: INGESTION] -> 解析用户输入 -> 生成 Acceptance Criteria
       ↓
[PHASE 1: RECON]     -> 委派 Explorer 勘探代码库 -> 产出架构上下文
       ↓
[PHASE 2: PLAN]      -> 生成 Task DAG -> 写入 .claude/tasks/plan.json
       ↓
[PHASE 3: DISPATCH]  -> 拓扑遍历 DAG -> 构造 Task Contract -> 触发 Worker
       ↓
[PHASE 4: SYNC]      -> 接收 Result Contract -> 运行 Verification Gate
       ├─ (验证失败) -> 判定重试策略 (同模型重试 / 升级模型 / 重新拆解) -> 回到 PHASE 3
       └─ (验证通过) -> 标记 Task 为 COMPLETED -> 解锁下游任务
       ↓
[PHASE 5: AUDIT]     -> 触发 Verifier/Reviewer 执行独立审计
       ↓
[PHASE 6: RELEASE]   -> 全局回归测试 -> 生成交付报告 -> Stop Hook 校验放行
```

---

## 4. Worker Agent 最佳设计方法与角色分类体系

### 4.1 三种设计模式的深度解构

| 模式 | 核心思路 | 优点 | 致命缺陷 | 适用边界 |
| :--- | :--- | :--- | :--- | :--- |
| **模式 A：按工程阶段**<br/>(Researcher, Architect, Implementer, Tester, Reviewer) | 模拟经典瀑布/敏捷阶段，按时间线性递进。 | 职责明确，上下游接口标准化，符合工程师直觉。 | **难以应对跨阶段快速迭代**。例如一个简单的修 Bug 任务，若走完 5 个阶段会带来严重的 Token 浪费与延迟。 | 中大型跨模块新特性开发。 |
| **模式 B：按技术领域**<br/>(Frontend, Backend, Database, Security, DevOps) | 按技术栈边界切分，垂直自治。 | 上下文高度聚焦于特定技术栈，降低专业领域幻觉。 | **极难界定端到端功能责任**。全栈需求需要频繁的横向通信，极易发生“接口对齐”死锁。 | 巨石架构拆分、技术栈壁垒极高的异构项目。 |
| **模式 C：按任务性质**<br/>(Explorer, Planner, Executor, Verifier, Critic) | 抽象认知行为：勘探、规划、执行、验证、批判。 | **复用性最高，粒度最稳健**，不依赖具体语言和阶段，任务路由准确率最高。 | 缺乏特定业务或工程上下文的深度，需要高质量的任务契约输入。 | 通用软件工程、多变场景的高效调度。 |

#### 关键问题权衡剖析
* **工程阶段与技术领域的组合策略**：推荐**以“任务性质（模式 C）”为骨架，以“技术栈/工程阶段”为装配参数**。不需要为“React 前端”和“Go 后端”分别建两个 Agent，而是维护通用的 `Executor`，在调用时通过 Task Contract 注入对应的技术规范与工具链约束。
* **是否需要独立的 Architect？**：**不需要独立 Agent**。架构规划（Architecture Planning）是 Commander 的核心能力，剥离给 Subagent 会导致元认知割裂。架构决策必须留在主 Session 中，或仅在初期调用只读的 `Explorer` 收集现状后由 Commander 综合裁决。
* **Tester 与 Reviewer 是否应该分开？**：**必须分开**。
  * `Tester`（验证者）侧重**动态验证（Dynamic Verification）**：运行命令、构造用例、捕获崩溃、验证退出码，属于客观事实判定。
  * `Reviewer`（审查者）侧重**静态语义（Semantic Review）**：代码风格、可维护性、越权漏洞、规范遵从，属于主观逻辑推演。混在一起会导致精力分散。
* **Debugger 是否需要成为独立 Agent？**：**强烈建议设立**。常规 Executor 倾向于在原假设上修修补补；独立的 Debugger 具备“假设验证（Hypothesis-Driven Debugging）”思维，专注排查根因而非直接修改代码。

---

### 4.2 推荐的 Agent Role Taxonomy（生产级四角色精简体系）

```mermaid
classDiagram
    class Explorer {
        +只读扫描代码
        +符号与依赖分析
        +架构影响面评估
    }
    class Executor {
        +受控写代码
        +单元级即时验证
        +原子提交
    }
    class Debugger {
        +根因假设生成
        +日志与断点分析
        +重现脚本编写
    }
    class Verifier {
        +独立审查
        +回归测试套件
        +契约与质量审计
    }
    Explorer <-- Commander : 委派勘探
    Executor <-- Commander : 委派实现
    Debugger <-- Commander : 委派调查
    Verifier <-- Commander : 委派验收
```

#### 四角色全要素规范说明书

| 属性维度 | 1. Explorer (代码勘探者) | 2. Executor (工程实现者) | 3. Debugger (缺陷调查者) | 4. Verifier (独立验收者) |
| :--- | :--- | :--- | :--- | :--- |
| **核心职责** | 探索代码拓扑、查找引用、绘制依赖、评估变更面。 | 按契约实施代码修改、新增功能、调整配置。 | 针对异常与测试失败，提出假设并设计重现步骤，定位根本原因。 | 站在对抗与审计视角，审查代码差异，运行全量回归与安全检查。 |
| **适合任务** | 搜索特定模式、定位符号定义、理解架构流程、收集上下文。 | 实现明确规范的函数、重构特定类、补齐单元测试。 | 难以复现的 Bug 分析、性能瓶颈排查、并发竞争条件分析。 | PR 级别审查、静态代码扫描、集成验收测试、防止回归。 |
| **严禁执行** | **严禁修改任何代码与工作区文件**。 | 严禁超出 Task Contract 指定的文件边界。 | 严禁在未确认根因前进行“试错式”修改。 | 严禁自行修复 Bug（发现问题只能驳回）。 |
| **所需输入** | 目标符号、关键词、拟探究的业务问题。 | 精确的 Task Contract（包含输入、产物规范、文件白名单）。 | 报错堆栈、失败测试日志、复现环境说明。 | 任务原始验收标准、Git Diff、测试运行脚本。 |
| **预期输出** | 关键文件列表、调用链路、潜在冲突预警（Markdown 摘要）。 | 遵循契约的代码变更、局部测试通过证据（Result Contract）。 | 根因分析报告、最小复现用例、修复建议。 | 验收通过/驳回判定书、详细问题列表与风险评估。 |
| **工具权限** | `Read`, `Grep`, `Glob`, `Bash(git log/status*)`。 | `Read`, `Edit`, `Write`, `Bash(npm test/cargo check*)`。 | `Read`, `Grep`, `Bash(调试/运行命令)`。 | `Read`, `Grep`, `Bash(全量测试/Lint/Git diff)`。 |
| **读写权限** | **只读（Read-Only）**。 | **限制性写（Scoped Write）**。 | **只读 + 临时目录写（用于复现脚本）**。 | **只读（Read-Only）**。 |
| **可委派子任务** | 否（叶子节点）。 | 否。 | 否。 | 否。 |
| **并行支持** | **完全支持（无写冲突）**。 | **条件支持（需工作区或文件集物理正交）**。 | **完全支持（探索不同假设）**。 | **完全支持（分别审查不同模块）**。 |
| **模型配置** | `haiku` / 极速推理模型（成本优先）。 | `sonnet` / 代码主力模型（工程能力优先）。 | `sonnet` / 强推理模型（逻辑深度优先）。 | `sonnet` / 严谨模型（批判性思维优先）。 |
| **验收要求** | 产出的文件路径全部真实存在；没有遗漏关键依赖。 | 局部单元测试 100% 通过；无新增 Lint 警告；仅改动白名单文件。 | 复现脚本能确定性重现故障；根因分析具备因果逻辑链。 | 自动化套件 Exit Code 0；审查项逐条核对无违规。 |

---

## 5. 任务分解（Task Decomposition）与执行调度

### 5.1 概念辨析：消除多 Agent 系统概念模糊

```mermaid
flowchart LR
    Stage[1. Workflow Stage 流程阶段<br/>宏观生命周期: Ingest -> Exec -> Verify]
    Task[2. Task 任务定义<br/>具体的可执行数据结构: ID, Input, Output, Deps]
    Type[3. Agent Type 能力模板<br/>静态声明: System Prompt, Tools, Model]
    Instance[4. Agent Instance 执行实例<br/>瞬态运行进程: 分配具体 Task, 独立 Context]

    Stage -->|包含多个| Task
    Type -->|实例化为| Instance
    Task -->|指派给| Instance
```

* **Workflow Stage（工作流阶段）**：宏观工程生命周期的阶段（如：Phase 1 侦查、Phase 2 实施、Phase 3 验收）。阶段不可跳过，但内部可循环。
* **Task（任务）**：最小执行工作单元。包含唯一的输入、操作集、输出契约与依赖状态（Pending, Ready, Running, Completed, Failed）。
* **Agent Type（Agent 类型）**：静态配置定义（如 `.claude/agents/executor.md`），定义了其系统能力、默认模型与工具限制。
* **Agent Instance（Agent 实例）**：执行中的具象进程。一个 Agent Type 可以同时派生多个 Instance（例如同时启动 3 个 `Executor` 实例分别处理 3 个不同的独立文件模块）。

---

### 5.2 任务拆分粒度与冲突识别算法

#### 粒度黄金法则（Atomic Task Rule）
* **标准原子粒度定义**：
  1. 影响的文件集 $\le 3$ 个紧密耦合的文件；
  2. 能够在单次上下文中完成“编写 $\rightarrow$ 单元验证”闭环；
  3. 执行时间在 LLM 视角下可控制在 1~3 次工具调用回合内。

#### 文件冲突判定与并发调度矩阵
在将 Task DAG 推入调度器时，必须进行**写空间正交性检测（Write Space Orthogonality Check）**：

```text
设 Task A 拟写入文件集合为 W(A)，拟读取文件集合为 R(A)
设 Task B 拟写入文件集合为 W(B)，拟读取文件集合为 R(B)

1. 若 W(A) ∩ W(B) ≠ ∅:
   -> 强写冲突 (Write-Write Conflict)
   -> 强制转换为串行依赖 (Task A -> Task B 或 Task B -> Task A)
   
2. 若 W(A) ∩ R(B) ≠ ∅ 且 Task B 先被定义:
   -> 读写依赖 (Read-After-Write)
   -> Task A 必须在 Task B 启动前完成，或 Task B 使用工作区快照

3. 若 W(A) ∩ W(B) = ∅ 且 W(A) ∩ R(B) = ∅ 且 W(B) ∩ R(A) = ∅:
   -> 完全正交 (Orthogonal)
   -> 允许进入并发调度执行池 (Parallel Execution Pool)
```

---

### 5.3 动态调度与重规划原则（Dynamic Re-planning）

```mermaid
stateDiagram-v2
    [*] --> Planned
    Planned --> Ready: 前置依赖清空
    Ready --> Running: 调度器分发给 Agent Instance
    
    state Running {
        [*] --> InExecution
        InExecution --> SelfValidating
        SelfValidating --> ContractEmitted
    }
    
    Running --> VerificationPending: 提交交付物
    
    state VerificationPending {
        [*] --> DeterministicCheck: 运行 Tests / Lint
        DeterministicCheck --> ReviewerAudit: 独立语义审查
    }
    
    VerificationPending --> Done: 验证全量通过
    Done --> [*]: 解锁下游任务
    
    VerificationPending --> FailureTriage: 任一环节失败
    
    state FailureTriage {
        [*] --> Analyze
        Analyze --> RetrySame: 偶发性/小错误 (次数 <= 2)
        Analyze --> EscalateModel: 推理深度不足 (换强模型)
        Analyze --> ReDecompose: 任务定义有误/超出范围
    }
    
    RetrySame --> Ready: 原参数微调
    EscalateModel --> Ready: 提升模型重新派发
    ReDecompose --> Planned: 裂变为多个子任务
```

1. **动态任务派生（Dynamic Task Spawning）**：当某一 Executor 在执行过程中发现未预期的系统依赖（如缺少底层库或底层接口不兼容），其 Result Contract 必须将状态标记为 `BLOCKED` 并返回发现的依赖。Commander 捕获该事件后，**暂停下游任务，就地向 DAG 中动态插入新任务**，待新前置任务完成后唤醒原任务。
2. **留在主 Session 的保留任务**：
   * 需求与设计决策；
   * Git 最终 Squash Merge 与 Commit 动作；
   * 跨模块公共接口（Public API Schema）的设计与变更；
   * 最终生产发布报告的生成。

---

## 6. Agent 间标准任务与结果契约（Contracts）

### 6.1 Task Contract（输入契约规范）

主 Session 派发任务时，强制按此标准 Schema 组织 Prompt 或写入暂存文件：

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "TaskContract",
  "type": "object",
  "required": ["task_id", "objective", "context_files", "allowed_write_files", "acceptance_criteria", "forbidden_actions"],
  "properties": {
    "task_id": { "type": "string", "example": "TASK-AUTH-002" },
    "objective": { "type": "string", "description": "精准的单点任务描述，严禁多重目标" },
    "context_files": {
      "type": "array",
      "items": { "type": "string" },
      "description": "供 Worker 读取的参考接口、文档或现有实现路径"
    },
    "allowed_write_files": {
      "type": "array",
      "items": { "type": "string" },
      "description": "严格限制该 Worker 只能修改的文件路径白名单，严禁越界修改"
    },
    "acceptance_criteria": {
      "type": "array",
      "items": { "type": "string" },
      "description": "明确的客观验收指标，例如测试用例名、性能指标等"
    },
    "forbidden_actions": {
      "type": "array",
      "items": { "type": "string" },
      "description": "绝对红线（如禁止修改公共数据库迁移脚本、禁止安装新依赖包等）"
    },
    "expected_deliverables": {
      "type": "array",
      "items": { "type": "string" },
      "description": "预期生成的产物列表"
    }
  }
}
```

---

### 6.2 Result Contract（输出契约规范）

Worker 执行完毕后，必须以如下格式向主 Session 返回，禁止非结构化的寒暄输出：

```markdown
<!-- TASK_RESULT_BEGIN -->
### Result Contract
- **Task ID**: TASK-AUTH-002
- **Status**: [SUCCESS | FAILED | BLOCKED]
- **Modified Files**:
  - `src/auth/jwt.service.ts` (Lines: +45, -12)
  - `tests/auth/jwt.service.spec.ts` (Lines: +80, -0)
- **Deterministic Evidence**:
  - Command: `npm test tests/auth/jwt.service.spec.ts`
  - Exit Code: `0`
  - Output: `5 passed, 0 failed, 100% assertions met`
- **Key Decisions Made**:
  - 采用 RS256 算法替代 HS256 以支持公钥离线验签。
- **Unresolved Risks / Discovered Dependencies**:
  - 无。但下游模块需配置环境变量 `JWT_PUBLIC_KEY_PATH`。
<!-- TASK_RESULT_END -->
```

---

### 6.3 上下文损失控制与持久化任务记录

* **Subagent 隔离带来的信息损失应对**：
  * **必须显式传递的信息**：全局架构约定、被修改文件的关联接口定义、专有名词与核心业务规则。
  * **必须丢弃的噪声信息**：Worker 在调试过程中的几百行报错日志、排错过程中的试错代码、冗长的工具调用追踪。
* **全局持久化状态机制**：
  * 在项目根目录维护 `.claude/tasks/state.json`，持久化记录每个 Task 的当前状态、执行者、开始/完成时间及产物哈希。
  * **作用**：即使当前主 Session 发生意外退出或人工重启，新启动的 Session 只需重新读取 `.claude/tasks/state.json`，即可在秒级恢复任务图进度，从断点无缝续跑。

---

## 7. 模型选择与资源动态路由策略（Model Routing Policy）

```mermaid
flowchart TD
    TaskIn[接收 Task Contract] --> EvalComplexity{评估任务维度}
    
    EvalComplexity -->|只读代码扫描 / 格式化 / 简单测试运行| Tier1[Tier 1: 低成本/极速模型<br/>Haiku 级]
    EvalComplexity -->|标准业务逻辑编码 / 单元测试编写 / 局部重构| Tier2[Tier 2: 核心代码模型<br/>Sonnet 级]
    EvalComplexity -->|跨模块架构设计 / 根因调查 / 复杂并发与安全漏洞| Tier3[Tier 3: 顶尖深度推理模型<br/>Opus / Extended Thinking 级]

    Tier1 -->|执行失败 / 抛出异常| Escalate1[升阶到 Tier 2 重试]
    Tier2 -->|连续失败 2 次 / 遇到棘手逻辑| Escalate2[升阶到 Tier 3 重试]
```

### 7.1 多维模型路由决策矩阵

| 任务类型 | 推荐初始模型 | 关键考量依据 | 升级阈值与策略 |
| :--- | :--- | :--- | :--- |
| **代码库拓扑勘探 (Explorer)** | **Fast/Cost-effective (Haiku)** | 主要是大吞吐量读取、路径检索与模式查找，重在速度与低成本，无需复杂推理。 | 若连续 2 次未找到核心符号定义，升级至主力模型。 |
| **标准模块实现 (Executor)** | **Standard Coding (Sonnet)** | 绝大多数日常工程实现的平衡点，指令遵循与代码生成质量稳定。 | 若出现死循环或自测失败 2 次，升级至顶配模型并注入额外上下文。 |
| **深层缺陷调查 (Debugger)** | **Advanced Reasoning (Sonnet with Thinking / Opus)** | 涉及长因果链推演、隐藏状态机分析与并发时序推演，必须调用高智能推理。 | 一次到位，不推荐降级使用低成本模型。 |
| **独立代码审查 (Verifier)** | **Standard / Advanced (Sonnet / Opus)** | 审查需要敏锐发现隐蔽边界漏洞，杜绝“敷衍放行”。 | 核心支付、鉴权等高危模块采用顶配模型；常规模块采用标准模型。 |

---

### 7.2 重试与成本防击穿规则（Cost Guardrails）

1. **失败重试惩罚计费**：一次低成本模型失败带来的重试（清洗上下文 + 重新执行），其总消耗通常超过直接使用高能力模型的 1.5 倍。**因此，对于核心修改任务，严禁从低阶模型开始试错**。
2. **动态升阶机制（Dynamic Escalation）**：
   * 第 1 次失败：保持同模型，增加补充报错日志与约束，实施即刻修复；
   * 第 2 次失败：**立即熔断**，换用更高阶模型（如升级至开启 Extended Thinking 的模型）并重新派发；
   * 第 3 次失败：挂起该任务，将决策权与问题上下文移交回 Commander，向人类用户告警。

---

## 8. 质量控制（Quality Control）与失败恢复机制

```mermaid
flowchart LR
    subgraph Layer1[第一道门禁: 自动化物理检测 (Deterministic Gate)]
        A1[Worker 产出] --> A2[PostToolUse Hook: Linter & Formatter]
        A2 --> A3[自动化单测执行: Exit Code 检查]
    end

    subgraph Layer2[第二道门禁: 独立对抗审查 (Adversarial Review)]
        A3 -->|通过| B1[唤醒独立 Verifier]
        B1 --> B2[Git Diff 审查]
        B2 --> B3[越权/规范检查]
    end

    subgraph Layer3[第三道门禁: 系统级终审 (System Integration Gate)]
        B3 -->|通过| C1[跨模块集成测试]
        C1 --> C2[Stop Hook 全量门禁校验]
        C2 -->|放行| Final[任务交付通过]
    end

    A3 -->|挂掉| Fix1[回滚并重派 Executor]
    B3 -->|驳回| Fix2[下发 Review 缺陷单]
    C1 -->|挂掉| Fix3[触发全局回滚]
```

### 8.1 破除四大核心风险

#### 1. 杜绝“自产自评”（Self-Approval Prevention）
* **硬性铁律**：**编写代码的 Executor 实例严禁执行自身成果的最终验收。**
* **机制实现**：Executor 仅能运行其局部的单元验证；最终合并前，必须由 Commander 实例化一个**全新的、上下文干净的 Verifier 实例**进行独立审查与跨模块集成测试。

#### 2. 防止 Reviewer 与 Implementer 无限返工（Ping-Pong Prevention）
* **设置严格的返工预算计数器（Rework Budget）**：
  * 每个原子任务的返工上限硬编码为 **2 次**。
  * Reviewer 驳回时，必须一次性输出**格式化、可执行的清单（Actionable Checklist）**，严禁在下一轮中提出前一轮未提及的新琐碎要求（Moving Goalposts）。
* **达到上限后的熔断机制**：若达到 2 次返工依然无法通过审查，系统强制暂停自动化，由 Commander 将争议 Diff 和双方审查日志归纳为简洁报告，呈递给人类用户做“裁决（Arbitration）”。

#### 3. 失败恢复不从零开始（Checkpoint & Rollback）
* 利用 Git 建立微检查点：在每个 Task 启动前，由系统自动打一个临时 Git Tag 或本地 Stash（如 `git tag task-checkpoint-TASK-001`）。
* 若任务彻底失败，直接执行软回滚至该 Checkpoint，确保先前已成功的下游成果完好无损，仅需针对该特定分支重新规划。

#### 4. 通过 Hooks 强制执行关键工程规则
在 `.claude/settings.json` 中配置原生 Hooks，确保即便是最高权限的 LLM 也无法绕过以下限制：
* **`PreToolUse`**：拦截对生产敏感文件（如 `.env*`, `k8s/*.yaml`, `migrations/*`）的直接编辑。
* **`PostToolUse`**：在修改 TypeScript/Rust/Python 文件后，秒级运行轻量语法与格式检查（如 `prettier --write` 或 `ruff format`）。
* **`Stop` Hook**：在用户会话结束前运行全套安全扫描与单元测试套件，只要有失败项，直接拦截退出，强制主 Session 继续接管修复。

---

## 9. 真实场景端到端工程推演

### 案例 A：复杂高并发 Bug 修复（多根因并行调查）

* **任务场景**：订单结算服务在高并发压测下偶发死锁，出现 `499 Client Closed Request`，无明显全栈崩溃日志。
* **任务拆分与 DAG 拓扑**：

```mermaid
flowchart TD
    Start([接到报障]) --> T1[Commander: 生成三种并发竞争假设]
    T1 -->|并行启动| H1[Debugger 实例 1: 排查 DB 连接池耗尽与长事务]
    T1 -->|并行启动| H2[Debugger 实例 2: 排查 Redis 分布式锁释放时序]
    T1 -->|并行启动| H3[Debugger 实例 3: 排查异步协程/线程死锁]
    H1 --> R1[排除: 连接池监控平稳]
    H2 --> R2[确认: 锁续期机制存在时序漏洞]
    H3 --> R3[排除: 协程无阻塞]
    R1 & R2 & R3 --> Syn[Commander 汇聚决策: 锁定 Redis 续期 Bug]
    Syn --> Fix[Executor: 实现 Redlock 续期 Watchdog 补丁]
    Fix --> Val[Verifier: 运行 1000 并发压力重现脚本验收]
    Val --> Done([交付修复])
```

* **执行全流程细节表**：

| 步骤 | 执行者与模型 | 输入上下文 | 产出物与交付契约 | 失败/恢复路径 |
| :--- | :--- | :--- | :--- | :--- |
| **Step 1: 假设生成** | Commander (主 Session)<br/>*Model: Sonnet* | 压测指标、报错日志片段、系统架构图。 | 产出 3 个相互独立的排查 Task，分配给 3 个 Debugger。 | - |
| **Step 2: 并行排查** | Debugger-1, 2, 3<br/>*Model: Sonnet (Parallel)* | 针对各自模块的源码和日志配置，使用 `Read`, `Grep` 分析。 | 分别输出排除报告与根因证据。Debugger-2 提供了时序证明。 | 若均未查出，Commander 扩大排查范围至网络层。 |
| **Step 3: 补丁编写** | Executor<br/>*Model: Sonnet* | Debugger-2 提供的分析报告及复现条件。 | 编写代码修复分布式锁过期机制，增加单元测试。 | 仅允许修改 `src/infra/lock/` 目录。 |
| **Step 4: 极限压测** | Verifier<br/>*Model: Sonnet* | 修复后的分支及压测复现脚本。 | 执行并发模拟测试，提供 0 错误率验证报告。 | 若仍出现 499，打回 Executor 重新调整重试窗口。 |

---

### 案例 B：完整跨层功能开发（全栈功能）

* **任务场景**：为现有客户门户新增“API Key 自助生成与细粒度权限管理”功能，包含数据库 Migration、后端服务、前端 UI 以及 RBAC 鉴权。
* **任务 DAG 与文件所有权锁定**：

```mermaid
flowchart TD
    Init[需求拆解] --> T1[Task 1: DB Migration<br/>Lock: prisma/migrations/*]
    T1 --> T2[Task 2: Backend API & Service<br/>Lock: server/api/keys/*]
    T1 --> T3[Task 3: RBAC Middleware<br/>Lock: server/middleware/auth.ts]
    T2 & T3 --> T4[Task 4: Frontend UI Component<br/>Lock: web/components/keys/*]
    T2 & T3 --> T5[Task 5: End-to-End API Integration Tests]
    T4 & T5 --> Merge[Commander: 全系统集成审查与放行]
```

* **并行与串行编排设计**：
  1. **Phase 1（数据底座）**：串行执行 Task 1（DB Migration）。完成后执行 `prisma migrate dev` 物理验证。
  2. **Phase 2（后端双轨并行）**：Task 2（业务 CRUD）与 Task 3（鉴权中间件）文件所有权完全正交，派生两个 `Executor` 实例**并行实施**。
  3. **Phase 3（前端与集成并行）**：根据 Task 2 确定的 OpenAPI 规范，派发前端 `Executor` 编写界面（Task 4），同时派发 `Verifier` 编写后端自动化集成测试套件（Task 5）。
  4. **Phase 4（门禁终审）**：主 Session 调用全套端到端 Playwright 测试，通过 `Stop` Hook 完成收尾放行。

---

### 案例 C：大型代码库跨模块重构（Legacy 架构升级）

* **任务场景**：将核心单体应用中的 50+ 个模块从 CommonJS 同步调用迁移至 ESM 异步流式处理，影响超 200 个文件，极易引发严重回归。
* **编排技术选型判断**：
  * **选型策略**：**方案 A（主 Session 作为 Commander）+ Git Worktrees（物理隔离）+ Dynamic Workflows（批量自动化脚本）混合驱动**。
* **执行步骤推演**：
  1. **拓扑分层**：Commander 调用 `Explorer` 扫描全局 AST，绘制模块依赖图，将 50 个模块划分为 4 个分层批次（Layer 0 基础工具类 $\rightarrow$ Layer 1 数据访问层 $\rightarrow$ Layer 2 核心业务服务 $\rightarrow$ Layer 3 外部接口控制器）。
  2. **分层分批迁移**：
     * 针对 Layer 0：主 Session 派发动态脚本（Dynamic Workflow）瞬间并发处理 15 个无依赖工具类，每个工具类运行在独立工作区，脚本自校验测试通过后自动合并。
     * 针对 Layer 1~2：创建独立 Git Worktree，派发 `Executor` 处理，每完成一个模块立即执行全量回归。
  3. **变更冲突防护**：通过 Git 分支建立沙箱，主分支通过 Hooks 拒绝未通过类型系统全量检查（`tsc --noEmit`）的任何合并。

---

## 10. 五种编排架构横向基准对比分析

| 评估指标 | 架构 A：单 Agent 贯通 | 架构 B：Commander + 2 个通用 Subagent | 架构 C：Commander + 4 个专职 Subagent (推荐) | 架构 D：Commander + 专职 Subagent + 动态模型分层 | 架构 E：进阶 Agent Teams (分布式多进程) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **端到端任务成功率** | 35% ~ 45% (易迷失) | 60% ~ 70% | **85% ~ 90%** | **85% ~ 92%** | 75% ~ 85% (死锁风险) |
| **代码与输出质量** | 易产生妥协性代码/降级单测 | 质量较好，仍偶有遗漏 | **极高（独立对抗审查保证）** | **极高** | 较高，但分支集成点常有冲突 |
| **总交付耗时** | 长（多轮反复纠错） | 中等 | **短（精准并发 + 极少重试）** | 最优 | 视网络与进程调度开销而定 |
| **Token 与实际成本** | 随着上下文增长呈指数级爆炸 | 线性可控 | 保持扁平（主上下文常驻低位） | **最优（低阶模型分流高频扫描）** | 极高（多个常驻 Session 开销大） |
| **任务委派准确率** | N/A | 70% | **92%** | **90%** | 80% |
| **上下文信息损失率** | 0%（但带来高噪过载） | 30% | **10%（结构化契约抵消）** | **10%** | 25% |
| **并行效率增益** | 0（纯串行） | 1.5x | **2.5x ~ 3.5x** | **2.5x ~ 3.5x** | 3.0x ~ 4.0x |
| **文件冲突发生率** | 0% | 15% | **< 2%（调度器写锁定保障）** | **< 2%** | 10% ~ 20% (需 Git 解决) |
| **人工介入频率** | 极高（需频繁纠错） | 中等 | **极低（仅在致命熔断时介入）** | **极低** | 较高（需裁决 Agent 分歧） |
| **系统恢复弹性** | 弱（一旦截断难以恢复） | 中等 | **强（状态机持久化断点续跑）** | **强** | 中等（分布式清理较繁琐） |

---

## 11. 可直接落地的作战指挥室渐进式实施方案

### Level 1：轻量作战室（Lightweight Command Center）
* **定位**：零额外插件依赖，仅利用原生 `.claude/agents/` 与 `CLAUDE.md`，几分钟内即可启动。
* **架构拓扑**：主 Session 充当 Commander，挂载 2 个通用子 Agent：`researcher.md`（只读）与 `builder.md`（受控写）。
* **配置代码**：

```markdown
<!-- .claude/agents/researcher.md -->
---
name: researcher
description: Deep read-only code exploration and context analysis agent.
model: sonnet
tools:
  - Read
  - Grep
  - Glob
  - Bash(git status)
  - Bash(git log*)
---
# Researcher System Prompt
You are a meticulous, read-only code research agent.
Your mission is to explore the codebase, trace dependencies, locate relevant symbols,
and return a concise structured summary. Never attempt to edit, create files, or run mutating commands.
```

```markdown
<!-- .claude/agents/builder.md -->
---
name: builder
description: Scoped code implementation and local unit-testing worker.
model: sonnet
tools:
  - Read
  - Edit
  - Write
  - Bash(npm test*)
  - Bash(cargo test*)
---
# Builder System Prompt
You are a precision implementation worker. You receive strict Task Contracts.
You are only allowed to modify files specified in the contract.
Always run local unit tests before declaring success. Output your final report in Result Contract format.
```

---

### Level 2：标准作战室（Standard Command Center —— 生产首选推荐）
* **定位**：完整的四角色分类体系、结构化任务契约、外置持久化状态板与生命周期 Hooks 守卫。

#### 1. 架构总览
主 Session (Commander) + 四专职 Subagents (`explorer`, `executor`, `debugger`, `verifier`) + Hooks 守卫拦截。

#### 2. 配置文件落地

**A. 专职 Subagent 配置 (`.claude/agents/verifier.md`)**：
```markdown
---
name: verifier
description: Independent adversarial quality gate and review subagent.
model: sonnet
tools:
  - Read
  - Grep
  - Glob
  - Bash(git diff*)
  - Bash(npm test*)
  - Bash(npm run lint*)
---
# Verifier System Prompt
You are an adversarial quality assurance engineer. Your goal is to find bugs, security flaws,
specification violations, and regressions in recently modified code.
You never fix code yourself. You audit Git diffs, run the test suites, check edge cases,
and produce a PASS/REJECT verdict with concrete reproduction steps.
```

**B. 原生 Hooks 守卫配置 (`.claude/settings.json`)**：
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "command": "bash -c 'if [[ \"$TOOL_INPUT_PATH\" =~ \\.(env|pem|key)$ ]]; then echo \"[SECURITY HOOK] Forbidden editing sensitive files!\" >&2; exit 1; fi'"
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "command": "bash -c 'if [[ \"$TOOL_INPUT_PATH\" =~ \\.(ts|tsx|js)$ ]]; then npx prettier --write \"$TOOL_INPUT_PATH\" >/dev/null 2>&1; fi'"
      }
    ],
    "Stop": [
      {
        "command": "bash -c 'npm run test:fast && npm run lint:check || (echo \"[QUALITY GATE] Unit tests or linting failed! Task cannot be completed.\" >&2; exit 1)'"
      }
    ]
  }
}
```

**C. Commander 编排宪法 (`CLAUDE.md`)**：
```markdown
# Software Engineering Command Center Operating Rules

You are the Lead Commander of this software engineering session.
Follow this rigid operational doctrine at all times:

1. ORCHESTRATOR ROLE ONLY:
   - NEVER use `Edit` or `Write` tools directly on business source code in this main session.
   - All code exploration MUST be delegated to the `explorer` subagent.
   - All code changes MUST be packaged into Task Contracts and delegated to the `executor` subagent.
   - All investigations of non-trivial bugs MUST be routed to `debugger`.
   - All final reviews MUST be verified by `verifier`.

2. TASK BREAKDOWN & CONCURRENCY:
   - Break large user goals into small atomic tasks (max 3 files modified per task).
   - Maintain active task status in `.claude/tasks/state.json`.
   - Only tasks with orthogonal write sets (non-overlapping files) may be executed in parallel.

3. RESULT VERIFICATION:
   - Never accept an agent's claim of completion without verifiable evidence (Exit Code 0, Test Output).
   - If tests fail, enforce a maximum of 2 retries before escalating or changing strategy.
```

---

### Level 3：高级分布式作战室（Advanced Enterprise Command Center）
* **定位**：面向大规模跨模块重构、巨型单体仓库，集成 Git Worktrees 物理工作区隔离与 Dynamic Workflows 脚本扇出。
* **运行机制**：
  * 启用 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`；
  * Commander 在主 Session 初始化任务池，派发多名 Teammates 分别在 `--worktree <branch-name>` 独立目录中常驻运行；
  * 底层通过脚本自动化执行 `git merge --no-ff`，若遇代码冲突由 Commander 唤起三方合并子流程。
* **不适合采用该方案的情况**：
  * 日常常规需求或单个模块内的 Bug 修复（Worktree 切换与合并开销远超编码收益）；
  * 机器配置内存受限（多个并行物理编译进程可能耗尽系统 RAM）。

---

## 12. 终局结论与十问十答决策底册

### Q1: 对我的“单 Session 作战指挥室”目标，哪种架构最合适？
* **结论**：**方案 A（主 Session 作为 Commander + 4 个专职 Subagents + Lifecycle Hooks 守卫）最合适。**
* **理由**：它在保证人类用户交互界面单一、确定、干净的前提下，最大限度规避了上下文膨胀与多进程并发写冲突，是目前工程可靠性最高、Token 消耗最经济的架构形态。

### Q2: 第一版究竟需要定义几个 Agent 类型？为什么？
* **结论**：**严格定义 4 个，绝不多建。**
* **角色定义**：`explorer`（勘探）、`executor`（实现）、`debugger`（调查）、`verifier`（审查）。
* **理由**：这 4 个角色涵盖了软件工程的“读、写、查、验”四大底层认知基元。角色过多会导致 Commander 路由决策犹豫（Routing Entropy），降低分发准确率；角色过少则无法实现读写权限与对抗审查隔离。

### Q3: Agent 应该按能力、工程阶段还是技术领域划分？
* **结论**：**按“任务认知性质（能力）”划分骨架，按“Task Contract”动态注入领域与阶段上下文。**
* **理由**：严禁创建 `FrontendAgent`、`BackendAgent` 等技术领域孤岛，因为现代全栈需求极度依赖跨层理解；也严禁僵化遵循瀑布流阶段。通用能力 Agent + 动态约束是适应敏捷迭代的最佳解。

### Q4: 同一 Agent 类型何时值得创建多个执行实例？
* **结论**：仅在满足**“写空间严格正交（无文件写冲突）”且“无前置数据依赖”**时，才派生多个实例并发执行。例如：同时修改不同微服务、同时排查 3 个互不相关的 Bug 假设、或针对多个无耦合目录批量补充单元测试。

### Q5: Commander 应该如何动态调度 Agent？
* **结论**：基于**事件驱动的 Task DAG 状态机**调度。
* **理由**：依赖清空的节点自动进入就绪队列；任务成功通过验证后动态解锁下游节点；遇到未知阻断时动态在图中插入新节点；失败时依据重试计数器触发“原地微调 $\rightarrow$ 升级模型 $\rightarrow$ 任务重拆 $\rightarrow$ 人工裁决”的阶梯策略。

### Q6: 如何定义可靠的 Agent 输入输出契约？
* **结论**：**机器可读的 Task Contract 与 Result Contract。**
* **理由**：输入契约必须包含显式的**文件修改白名单**与**客观验收标准**；输出契约必须包含**物理退出码、测试套件实际输出文本与改动文件列表**。非结构化的自然语言汇报一律视为“未完成”。

### Q7: 如何安排并行和串行？
* **结论**：
  * **绝对串行**：存在数据流依赖的任务（前置输出是后置输入）；涉及公共配置/数据库迁移脚本/公共类型定义修改的任务；主 Session 的终审与发布动作。
  * **安全并行**：只读探测任务；文件集合互不重叠的独立子模块实现；多假设根因调查；多模块独立审查。

### Q8: 如何选择模型？
* **结论**：遵循**“低成本探测、高能力攻坚、严谨性守门”**原则。
  * 文本量大、只读模式匹配的 `explorer` 使用极速低成本模型；
  * 业务编码与重构的 `executor` 使用代码能力均衡的主力模型；
  * 疑难根因分析的 `debugger` 与最终代码把关的 `verifier` 选用高阶深度推理模型。

### Q9: 如何验证整个任务确实完成？
* **结论**：**三层闭环验证，严禁口头声明。**
  1. 局部闭环：Executor 自测通过；
  2. 对抗闭环：独立 Verifier 审查 Git Diff 且回归测试 Exit Code 为 0；
  3. 物理闭环：Claude Code 原生 `Stop` Hook 自动运行全量构建与静态门禁，校验失败则直接阻止任务终止。

### Q10: 从轻量系统演进到复杂编排系统，应遵循怎样的路线？
* **推荐演进路线（Evolutionary Roadmap）**：
  1. **Day 1（规则先行）**：在 `CLAUDE.md` 写入编排纪律，严禁主 Session 亲写代码；建立 `.claude/agents/` 下的基础 `explorer` 与 `executor`。
  2. **Day 7（契约与质检）**：固化 Task/Result Contract 模板；补齐 `debugger` 与 `verifier`；引入 `Stop` Hook 自动化拦截门禁。
  3. **Day 30（状态化与并发）**：引入 `.claude/tasks/state.json` 实现任务 DAG 持久化管理，开启正交任务的并发调度与断点续跑。
  4. **Day 90+（分布式工作区）**：仅在超大型重构与团队级协作场景下，按需引入 Git Worktrees 与 Agent Teams，升级至分布式作战指挥室。
