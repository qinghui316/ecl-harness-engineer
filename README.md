# ECL Harness Engineer

![ECL Harness Engineer](assets/readme/hero.png)

为长期项目建立可验证、可移植的 AI 开发工作环境。

`ecl-harness-engineer` 是一个面向 Codex 和 Claude Code 的 Agent Skill。它分析真实项目，
创建一套项目绑定的本地 project Harness，让不同会话、不同 Agent 和多个本地 worktree
共享同一份项目知识、Change 证据、协作事实和演进规则。

![License: MIT](https://img.shields.io/badge/License-MIT-cc785c)
![Agent Skill](https://img.shields.io/badge/Agent%20Skill-ecl--harness--engineer-181715)
![Runtime](https://img.shields.io/badge/runtime-Codex%20%2B%20Claude-5db8a6)
![Awesome Skills](https://img.shields.io/badge/awesome--skills-accepted-2ea44f)

```bash
npx skills add qinghui316/ecl-harness-engineer
```

项目已被 [Antigravity Awesome Skills](https://github.com/sickn33/antigravity-awesome-skills)
收录：[PR #678](https://github.com/sickn33/antigravity-awesome-skills/pull/678)。

## ECL 是什么

ECL 是 **Evolution Constraint Language**，即演进约束语言。

它不是一种编程语言，而是一套让 AI 开发持续保持可解释、可验证和可交接的工作方式：

- **Evolution**：项目会持续演进，每次修改都应为后续工作留下可靠证据。
- **Constraint**：实现前明确目标、边界、验收标准、风险和验证方式。
- **Language**：用统一的 Change 结构表达 WHAT、WHY、HOW、任务和 review 结果。

一次 Structured Change 通常沿着以下证据链推进：

```text
需求假设 -> spec -> plan -> tasks -> implementation -> validation -> review -> close
```

代码完成不是结束。有效的经验还会进入项目知识、规则、检查或下一轮 Evolution。

## 为什么需要 Project Harness

普通项目交给 AI Agent 时，经常遇到这些问题：

- 新会话不知道项目目的、模块边界、入口和验证命令。
- 任务记录停留在对话中，换 Agent 或换 worktree 后无法可靠接续。
- 多个 Worker 同时修改相同路径或 contract，直到合并时才发现冲突。
- 代码写完便被视为完成，但验收标准、review 和完成提交没有绑定。
- 文档、规则和检查长期漂移，同一问题反复出现。

Project Harness 把这些问题转换为可导航的项目知识、结构化 Change、共享 Registry、
精确 Integration 和有证据的 Evolution。业务仓库仍然保存业务代码和正式文档；
project Harness 独立保存 Agent 工作所需的完整知识与开发历史。

## 工作模型

![从项目证据到可靠交付](assets/readme/core-loop.png)

职责边界保持简单：

| Owner | 负责什么 |
| --- | --- |
| Agent + Skill 文档 | 理解 purpose、流程、模块、架构、参考关系，制定方案并判断内容质量 |
| Harness runtime | 校验 schema、路径、ID、索引、Registry、Git 身份、锁和原子事务 |

脚本提供机械证据，不替代 Agent 对项目语义和实现方案的判断。

## 它会创建什么

![Project Harness 能力结构](assets/readme/directory-map.png)

Project Harness 默认位于：

```text
<primary-worktree>/.agents/skills/<project-id>-harness/
```

它不会作为业务源码提交，但由稳定 project ID 与仓库中的精简 marker 定位。持久状态使用
项目相对路径或 Skill 相对路径；项目绝对位置、Git common dir、worktree 地址、解释器和链接
只在当前进程中发现。

| 能力 | 产物与作用 |
| --- | --- |
| Project knowledge | L1 总览、L2 模块与系统、L3 语义桥、Architecture Map |
| Reference-source maps | 记录参考项目的 commit、机制、接口、调用流、测试和适配边界 |
| Environment | build、test、lint、start、service、readiness、cleanup 和变量契约 |
| ECL Change | `summary.md`、`spec.md`、`plan.md`、`tasks.md`、review、archive 和 INDEX |
| Coordination | Lane、Registry、affected paths、contracts、baseline 和冲突 preflight |
| Integration | 精确 completion commit、候选 worktree、独立 review 和 I2 |
| Evolution | 每五个合格 Change 形成一个 E1 窗口，经独立 Judge 后原子发布或保持不变 |
| Greenfield | Go、TypeScript、Python 的 CLI/Web API 六种成熟起点 |
| Checks | dependency、quality、template、encoding、Change integrity、知识引用和漂移 |

L1/L2/L3 完整表达经过源码、manifest、接口、配置或测试验证的项目事实。仓库 README、ADR
或其他 prose 文档可以帮助 Analyzer 发现线索，但不会成为 project Harness 工作知识的持久依赖。

## 快速开始

### 初始化成熟项目

```text
Use $ecl-harness-engineer to initialize a project-bound local Harness for this project.
```

Skill 会先只读分析项目，形成由 Agent 复核的 analysis bundle，并在发布前展示项目身份、
写入范围、可执行产物和验证计划。

完整 analysis bundle 由 `project-profile.json`、`architecture.json`、`audit.json` 和
`creation-delta.json` 组成；证据提取器只能生成 draft，不能代替 Agent 完成语义判断。

### 审计现有 Project Harness

```text
Use $ecl-harness-engineer to audit this project's Harness and report semantic, structural, runtime, and workflow gaps without modifying it.
```

### 迁移或刷新

```text
Use $ecl-harness-engineer to migrate this project Harness from a fresh evidence-backed analysis bundle while preserving Change and Registry history.
```

### 空项目 Greenfield

空项目第一次初始化只创建诚实的 bootstrap project Harness，不猜语言和业务。确认 purpose、
语言和 CLI/Web API 类型后，再在 project Harness 中创建 Structured Change：

```text
Use this project's Harness to plan and implement a Structured Change that bootstraps a TypeScript Web API from the approved greenfield reference.
```

Go、TypeScript 和 Python 模板只会选择当前技术栈的一种，不会把六套源码复制进项目。

> 日常业务开发只使用项目入口指向的 project Harness，不需要再次调用
> `ecl-harness-engineer`。本 Skill 只负责创建、审计和迁移 project Harness。

## 日常开发

Agent 从 `AGENTS.md` 或 `CLAUDE.md` 进入 project Harness，再按当前任务自然读取：

```text
SKILL.md -> L1 -> 当前模块 L2 -> 相关 L3 -> reference map -> reference source
```

普通解释、项目导航和源码研究不需要运行 preflight。准备修改仓库时，在 scope 初步明确后运行
一次；paths、contracts 或 baseline 发生实质变化，以及 publish、close、Integration 前再重跑。

局部低风险工作可以作为 Small Change 直接完成。跨模块、contract、数据、权限、架构或多阶段
验证的工作进入 Structured Change：

```text
intake -> spec -> plan review -> tasks -> implementation -> validation -> review -> close
```

高影响 clarification 未解决、plan review 未通过、验收标准没有映射到 task/validation、仍有
未完成任务或 review 证据不完整时，Change 不能关闭。Git Change 的关闭结果会绑定精确的
`completion_commit`，而不是模糊的分支 tip。

## 多 Worktree 与 Integration

同一台机器上的多个 Git worktree 共享一个物理 project Harness。每个长期 worktree 是一个
Lane，可以顺序完成多个 Change；共享 Registry 会提前检查 affected paths、contract 和 baseline
冲突。

新 worktree 按项目入口运行 connector，建立 Codex 与 Claude Code 的本地链接。删除 secondary
worktree 前必须先使用同一 connector 的 detach 参数解除链接；Integration 的临时 worktree 会在
complete 或 abort 时执行相同的安全拆链。

Integration 不合并整个长期分支，而是只选择每个 Change 的
`base_commit..completion_commit`。聚合验证和独立 review 通过后，只有用户确认
`CHECKPOINT I2` 才能落到 canonical branch。

## 五 Change Evolution

全项目累计五个唯一、completed、validation-passed、evidence-complete 的 Change 后，生成一个
Evolution 窗口。Integration 记录、Evolution 自身工作和没有正式 Change 的小任务不计数。

![五 Change Evolution](assets/readme/auto-evolve.png)

候选必须重新分析项目并消费 Change、知识漂移和审计 findings。Judge 不可用、分数不足、出现
hard issue、验证失败或候选被篡改时，project Harness 保持不变。没有第二个人工发布检查点。

## 跨机器复用

Project Harness 不持久保存本机绝对路径。将项目仓库和对应 project Harness 一起提供到新机器后，
稳定 project ID、项目知识、Change archive、INDEX、contracts、Integration 结果和 Evolution 经验
可以继续使用；当前 worktree、Git common dir、链接和解释器会重新发现。

这不是远程同步产品。不同机器不会自动交换未共享的 Harness 状态，项目仓库和 project Harness
需要由用户通过自己的交付方式一起提供。

## 推荐全局提示词

下面这段提示词只负责全局路由和通用开发纪律。详细项目知识、Change gate 和 workflow 由每个
project Harness 提供，不需要在全局提示词中重复。

```markdown
# 全局开发原则：演进约束驱动

## 优先级

1. 优先读取当前项目的 `AGENTS.md` 和 `CLAUDE.md`，遵守它们指向的项目规则、正式文档、lint、测试、CI 和本地命令。
2. 如果项目入口指向 project Harness，加载对应 `<project-id>-harness/SKILL.md`，并按其中的项目知识、Change 和 workflow 执行。
3. 如果当前 worktree 缺少 project Harness 链接，按项目入口运行 connector 后重新加载；connector 失败时报告缺失，不隐式初始化或迁移 Harness。
4. 如果项目没有 project Harness，使用本提示中的简化闭环。
5. 只有在用户要求创建、审计或迁移 project Harness 时才使用 `ecl-harness-engineer`。

## 核心原则

用户需求是待验证假设，不是未经审查的事实。实现前根据项目证据明确目标、边界、依赖、风险和验收标准。

非平凡任务遵循：

`需求假设 -> 方案探索 -> 约束收敛 -> 实现 -> 测试验证 -> 问题回流`

实现应能够追踪到：

`需求 -> 功能 -> 模块 -> 实现 -> 测试`

发现问题时，先判断是本次引入、既有问题、环境问题还是阻塞项；确有长期价值时，再沉淀为规则、测试、检查或正式文档。

## 执行纪律

1. 不把第一个方案直接当作最终方案。
2. 优先从代码和项目证据发现事实；只有无法发现且会影响结果时才询问用户。
3. 编码前确认当前约束足以支撑实现和验证。
4. 不修改无关文件，不回滚用户已有改动。
5. 不绕过项目测试、lint、CI 或 project Harness 门禁。
6. 局部低风险任务可以直接处理；跨模块、contract、数据、权限、架构或多阶段验证的任务按 project Harness 创建 Structured Change。
7. 修复会使受影响的旧验证失效，必须针对当前工作区重新验证。

## 编码与文件安全

1. 所有源码使用 UTF-8。
2. Windows PowerShell 读写源码时显式指定 `-Encoding UTF8`。
3. 禁止把终端显示乱码写回源码。
4. 批量修改后扫描乱码特征：

   `锅|锛|銆|馃|脳|瑙|褰|闆|鍥|鍙|鍦|鏈`

5. 只修复确认损坏的文本，不盲目重编码整个文件。
6. 中文内容修改后运行乱码扫描和项目编译检查。
```

## 适合什么项目

适合：

- 需要多个 Agent、多个 worktree 或多轮会话协作的长期项目。
- 经常因为上下文缺失导致误改、漏测或重复踩坑的项目。
- 需要把需求、实现、验证、review 和完成提交精确关联的项目。
- 希望项目知识和开发历史能够随项目迁移，而不绑定创建时电脑的项目。
- 希望 Harness 从真实 Change 经验中进化，同时保持独立评估和原子发布门禁的项目。

不适合：

- 一次性脚本或没有长期维护价值的 demo。
- 只需要 Agent 立即完成一个普通功能、没有 Harness 建设需求的任务。
- 需要跨机器、跨团队实时同步或远程锁服务的场景。

## 明确边界

- 不自动执行普通业务开发；日常开发属于 project Harness。
- 不自动初始化 Git，不自动合并业务代码，不绕过测试或用户检查点。
- 不启动 daemon、scheduler、远程 Registry 或远程锁服务。
- 不把本机绝对路径写入 project Harness 持久状态。
- 不把仓库 prose 文档当作项目知识的长期依赖或替代源码验证。
- 不自动拉取、更新或移动参考项目源码。
- 不把 archive 全量加载进当前上下文；历史通过 INDEX、search 和 context 选择性读取。
- README 是安装与产品说明，不参与 Skill 的运行时渐进式读取。

## 本仓库验证

```powershell
python -m py_compile scripts/harness_cli.py
python -m unittest discover -s tests -v
python <skill-creator>/scripts/quick_validate.py .
```

GitHub: [qinghui316/ecl-harness-engineer](https://github.com/qinghui316/ecl-harness-engineer)

## License

MIT
