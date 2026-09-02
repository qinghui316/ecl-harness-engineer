<p align="center">
  <img src="assets/readme/hero.png" alt="ECL Harness Engineer" />
</p>

<div align="center">

# ECL Harness Engineer

**让 Codex、Claude Code 和多个 worktree 共享项目知识、Change 证据与可靠交付流程。**

一个面向长期软件项目的 Agent Skill：分析真实项目，创建项目专属 Harness，并让开发经验持续回流为更可靠的知识、规则与验证。

[![License: MIT](https://img.shields.io/badge/License-MIT-cc785c)](LICENSE)
[![Agent Skill](https://img.shields.io/badge/Agent%20Skill-ecl--harness--engineer-181715)](https://skills.sh)
[![Runtime](https://img.shields.io/badge/runtime-Codex%20%2B%20Claude-5db8a6)](#快速开始)
[![Awesome Skills](https://img.shields.io/badge/awesome--skills-accepted-2ea44f)](https://github.com/sickn33/antigravity-awesome-skills/pull/678)

GitHub repo：[qinghui316/ecl-harness-engineer](https://github.com/qinghui316/ecl-harness-engineer)

已被 40k+ stars 的 [sickn33/antigravity-awesome-skills](https://github.com/sickn33/antigravity-awesome-skills)
收录：[PR #678](https://github.com/sickn33/antigravity-awesome-skills/pull/678)。

```bash
npx skills add qinghui316/ecl-harness-engineer
```

</div>

---

## 为什么做这个

AI Agent 可以快速写代码，但长期项目真正困难的是保持连续性：

- 新会话需要重新理解项目目的、模块边界和验证命令。
- 需求、计划、实现与测试散落在对话中，难以交接和复盘。
- 多个 Worker 并行开发时，路径和 contract 冲突往往到合并阶段才暴露。
- 代码完成后缺少一致的验收、review 和集成证据。
- 同类问题重复发生，却没有回流为项目知识、规则或机械检查。

ECL Harness Engineer 为项目创建一套专属 **project Harness**。它把项目地图、开发流程、Change
历史、协作事实和验证规则组织成 Agent 可以渐进读取、持续使用和可靠演进的工作环境。

## ECL 是什么

ECL 是 **Evolution Constraint Language**，即演进约束语言。

它不是新的编程语言，而是一套把开发意图变成可执行约束的工作方式：

- **Evolution**：每次开发都为后续工作留下可复用证据。
- **Constraint**：实现前明确目标、边界、风险、验收标准和验证方式。
- **Language**：用统一的 Change 结构连接需求、计划、实现、测试和 review。

简单说，ECL 让 Agent 不只“完成这次修改”，还知道为什么改、不能破坏什么、怎样证明完成，
以及哪些经验值得留给下一次开发。

## 核心循环

![从项目证据到可靠交付](assets/readme/core-loop.png)

ECL Harness Engineer 使用一条统一路径：

1. **分析**：从源码、manifest、接口、配置和测试理解真实项目。
2. **创建 Harness**：生成项目知识、工作流、规则和确定性辅助能力。
3. **Structured Change**：把非平凡需求收敛为 spec、plan 和可验证任务。
4. **验证**：运行与当前项目和 scope 对应的 build、test、lint 与检查。
5. **Integration**：聚合多个 Change，通过独立 review 和 I2 后进入 canonical branch。
6. **Evolution**：从真实 Change 历史中提炼经验，只发布通过独立验证的改进。

Agent 负责理解项目、判断语义和制定方案；Harness runtime 负责需要机械一致性的索引、身份、
Registry、锁和发布事务。

## Project Harness 提供什么

![Project Harness 能力结构](assets/readme/directory-map.png)

| 能力 | 带来的结果 |
| --- | --- |
| **Project Knowledge** | L1 项目总览、L2 模块与系统、L3 语义桥和 Architecture Map |
| **Change System** | spec、plan、tasks、validation、review、archive 和可检索 INDEX |
| **Environment** | build、test、lint、start、service、readiness、cleanup 和变量契约 |
| **Reference Maps** | 参考项目的机制、接口、调用流、测试、可借鉴点和适配边界 |
| **Coordination** | Lane、Registry、affected paths、contracts 和并行冲突预检 |
| **Integration** | 精确 Change 边界、候选集成、独立 review 和 CHECKPOINT I2 |
| **Evolution** | 五 Change 窗口、经验生命周期、独立 Judge 和 CHECKPOINT E1 |
| **Greenfield** | Go、TypeScript、Python 的 CLI/Web API 六种成熟项目起点 |

Project Harness 中的 L1/L2/L3 会完整表达经过项目证据验证的知识，不要求项目预先拥有完善的
架构文档。参考源码也会形成可导航的 source map，让 Agent 知道当前模块借鉴了什么、应该查看
哪里，以及哪些设计不能直接照搬。

Project Harness 使用稳定项目身份和相对寻址，使项目知识与开发历史不依赖创建时的本机绝对路径。

## Change 如何工作

局部低风险工作可以直接作为 Small Change 处理。跨模块、contract、数据、权限、架构或多阶段
验证的任务进入 Structured Change：

```text
需求假设
-> spec：WHAT / WHY / acceptance
-> plan：HOW / impact / validation
-> tasks：可执行任务与验收映射
-> implementation
-> validation
-> review
-> close
```

高影响问题会在实现前澄清；计划经过 review 后才进入任务；验收标准必须能够追踪到实现与验证。
完成的 Change 会留下可检索历史，供后续 Agent、Integration 和 Evolution 使用。

## 多 Worktree 与 Integration

同一项目的多个本地 worktree 可以共享一套 project Harness。每个 Lane 保持自己的 active Change，
共享 Registry 提前暴露路径、contract 和 baseline 冲突。

Integration 以 Change 的精确完成边界为单位组合候选，而不是笼统合并整个长期分支。聚合验证和
独立 review 通过后，由用户在 **CHECKPOINT I2** 确认进入 canonical branch。

## 五 Change Evolution

![五 Change Evolution](assets/readme/auto-evolve.png)

每积累五个证据和验证完整的 Change，project Harness 会形成一个 Evolution 窗口：

1. 从 Change、审计和知识 findings 中发现重复问题与有效经验。
2. 将经验分类为 Promote、Retain、Merge、Retire 或 Archive-only。
3. 在 **CHECKPOINT E1** 确认本轮 Evolution。
4. 由唯一 Owner 形成候选，并交给独立 Judge 评估。
5. 只有分数、hard issue 和验证门禁全部通过的候选才会发布。

这是一条只吸收项目真实经验的演进棘轮：项目知识会持续更新，但不会把一次性建议或未经验证的
经验直接提升为长期规则。

## 快速开始

### 安装

```bash
npx skills add qinghui316/ecl-harness-engineer
```

### 初始化现有项目

```text
Use $ecl-harness-engineer to initialize a project-bound local Harness for this project.
```

### 审计 Project Harness

```text
Use $ecl-harness-engineer to audit this project's Harness and report the highest-impact gaps without modifying it.
```

### 迁移或刷新

```text
Use $ecl-harness-engineer to migrate this project Harness from a fresh evidence-backed analysis while preserving its development history.
```

### 创建 Greenfield 项目

```text
Use $ecl-harness-engineer to initialize an honest Harness for this empty project. Ask me to confirm the purpose, language, and CLI or Web API type before planning the first Structured Change.
```

初始化完成后，日常业务开发直接使用项目入口指向的 project Harness：

```text
Use this project's Harness to implement the requested feature and follow its Change and validation workflow.
```

## 推荐全局提示词

<details>
<summary><strong>展开推荐提示词</strong></summary>

```markdown
# 全局开发原则：演进约束驱动

## 优先级

1. 优先读取当前项目的 `AGENTS.md` 和 `CLAUDE.md`，遵守它们指向的项目规则、正式文档、lint、测试、CI 和本地命令。
2. 如果项目入口指向 project Harness，加载对应 `<project-id>-harness/SKILL.md`，并按其中的项目知识、Change 和 workflow 执行。
3. 如果当前 worktree 缺少 project Harness 链接，按项目入口运行 connector 后重新加载。
4. 如果项目没有 project Harness，使用本提示中的简化开发闭环。
5. 只有在用户要求创建、审计或迁移 project Harness 时才使用 `ecl-harness-engineer`。

## 核心原则

用户需求是待验证假设。实现前根据项目证据明确目标、边界、依赖、风险和验收标准。

`需求假设 -> 方案探索 -> 约束收敛 -> 实现 -> 测试验证 -> 问题回流`

实现应能够追踪到：

`需求 -> 功能 -> 模块 -> 实现 -> 测试`

## 执行纪律

1. 优先从代码和项目证据发现事实；只有无法发现且会影响结果时才询问用户。
2. 不修改无关文件，不回滚用户已有改动。
3. 局部低风险任务可以直接处理；跨模块、contract、数据、权限、架构或多阶段验证的任务使用 Structured Change。
4. 不绕过项目测试、lint、CI 或 project Harness 门禁。
5. 修复会使受影响的旧验证失效，必须针对当前工作区重新验证。

## 编码与文件安全

1. 所有源码使用 UTF-8。
2. Windows PowerShell 读写源码时显式指定 `-Encoding UTF8`。
3. 禁止把终端显示乱码写回源码。
4. 批量修改后扫描乱码特征：`锅|锛|銆|馃|脳|瑙|褰|闆|鍥|鍙|鍦|鏈`。
5. 只修复确认损坏的文本，不盲目重编码整个文件。
```

</details>

## 适合什么项目

- 需要 Codex、Claude Code 或多个 Agent 长期协作的项目。
- 使用多个 worktree 并行开发，需要提前发现 scope 与 contract 冲突的项目。
- 希望把需求、计划、实现、验证和 review 串成可靠证据链的项目。
- 希望新会话能够快速理解项目，而不是每次重新扫描整个仓库的项目。
- 希望项目知识和规则能从真实开发历史中持续演进的项目。
- 从空仓库启动，希望获得成熟 CLI 或 Web API 架构起点的项目。

## 设计灵感与致谢

- [darwin-skill](https://github.com/alchaincyf/darwin-skill)：独立评分、验证门禁与演进棘轮思路。
- [Harness Skill / HiClaw](https://market.hiclaw.io/skills/product-69e7187be4b0d28be543a809)：Harness Engineering 与 Agent 协作基础设施方向参考。

ECL Harness Engineer 在这些思路上加入项目知识分层、Structured Change、多 worktree Registry、
本地 PR 式 Integration、参考源码地图和项目级 Evolution，形成一套面向持续软件开发的 project Harness。

---

<div align="center">

**让项目知识可继承，让每次 Change 可验证，让有效经验持续留下。**

MIT License

</div>
