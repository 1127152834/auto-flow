# PM9 Follow-through Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. 用户已授权当前可完成的验证与根因修复；仅超出既有 R1–R4 的架构扩展另行确认。

**Goal:** 核对全部 251 条规格，补齐优先真实场景，交付有证据的修复与可审查的架构扩展方案。

**Architecture:** 保留现有项目 Run/Task、HTTP、受控 worker、共享 WorkflowRuntime、数据和环境账本。覆盖映射写回唯一 coverage.json，验收扩展复用现有生产 smoke；没有第二执行器。新增能力先确定协议、所有权和安全边界。

**Tech Stack:** Python 3.11 / FastAPI / SQLite / pytest；Node 22 / Electron / React / Vitest；现有 GitHub Actions 三平台。

**Spec:** 用户本轮四部分实施指令；docs/project-management/design/{functional-structure,data-and-state-rules,data-flow-and-contracts,execution-and-environment}.md；docs/superpowers/plans/2026-09-13-project-management-milestones.md；已批准 2026-09-20-pm9-production-runtime-integration.md。

## Global Constraints

- 仅 /Users/zhangtiancheng/.codex/worktrees/pm9-runtime/autoflow / codex/project-management-pm9-runtime；不修改 Studio 并行目录、不归并历史分支、不合并或发布。
- 不能仅凭文件名/测试数量判断覆盖；未覆盖的子条件独立记录，禁止批量升级 verified。
- 区分 implementation_missing、test_missing、production_evidence_missing、external_acceptance_pending；允许同一规格同时有多类缺口。
- 不扩大跨进程人工恢复或全部 Studio 节点接入；不移除安全检查冒充支持。
- 同一写命令恢复必须保持身份，End 修复不重跑、不重复保存；未知结果和清理失败保持可见。
- 历史 Sheets 服务账号证据保留；缺授权/签名/实机不阻断本地可完成工作；releaseAccepted=false。

## Review Focus

1. 映射存在但断言只验证规格子集：保留 covers 与 gaps，不自动提升状态。
2. 故障注入绕开真实 worker：只在传输/提交响应边界注入，运行仍走正式调度和浏览器。
3. End 保存成功/关联失败：保存代次、关联组、Run 终态与重试副作用必须分别断言。
4. 人工继续/到期：同一持久检查点竞争，不用睡眠顺序假装测试竞争。
5. 新候选报告与旧产物混用：记录提交、执行命令、平台和真实场景清单；代码稳定后才启动一次必要全量 CI。

### Task 1: 全部规格与实际断言映射

**Files:** coverage.json；pm9/coverage-audit.json；scripts/verify-pm9-coverage.mjs 与对应 test；pm9/test-mapping-review.md。
**Interfaces:** 每条现有 id 保持；新增 testMapping 保存具体 file/test/assertion 范围和分类缺口，保留原 planned_test_file 为历史意图。

- [ ] 逐条读取 source 需求及实际测试函数断言，先处理 73 条失效预定路径，再检查其余 178 条。
- [ ] 验证器只检验映射完整性和引用真实性，不把静态检查称为业务验收：251 个唯一 id；每项有对应检查或明确 test_missing；引用文件和函数真实存在；分类枚举合法；未闭合 gap 不得新晋 verified。
- [ ] 使用缺少映射/不存在函数的输入运行失败，再补最小实现与逐项数据；运行 `node --test scripts/verify-pm9-coverage.test.mjs` 和 `node scripts/verify-pm9-coverage.mjs`，预期结构检查通过，业务未关闭项如实输出。
- [ ] 提交映射与分类证据，记录没有证明的子条件。

### Task 2: 生产数据与环境故障场景

**Files:** scripts/project-runtime-smoke.mjs 及复用的领域验收辅助文件；apps/backend/tests/integration/test_project_batch_real_cloakbrowser.py；现有数据/环境测试与涉及的真实缺陷实现。
**Interfaces:** 保持 `checkProjectRuntime(baseUrl, token, browserVersion)` 既有调用边界；返回新增逐场景断言结果，源码与打包调用相同断言。

- [ ] 复用已有 HTTP 创建项目/多表/自动化/正式 Studio 文档；配置人员可重复、邮箱显式改态和多任务，断言实际 Task 的 typed 输入与业务状态，不直接构造 Task/Run 事实。
- [ ] 同一真实任务依次写入并在人工等待窗口修改记录，继续后断言本任务版本推进成功而人工新值不被覆盖；后续节点失败仍保留此前写入。
- [ ] 在已有 capability 响应边界注入一次已提交响应丢失，用同一 commandId 查询/重发，断言只有一条新增记录与一个操作结果；不注入替身执行器。
- [ ] 在实际 End 保存/关联边界制造 linkRevision 冲突，断言 saved_unlinked、Run failed、环境只保存一次；修复只改关联且历史 Run 不变。另断言旧候选不覆盖新代次、混合关联与未经授权替换被拒绝。
- [ ] 复用现有人工命令并发测试核对继续/到期唯一转换；增加缺失的真实 worker 情形。每个暴露缺陷先保留 RED，再根因修复并取得 GREEN。
- [ ] 运行受影响 pytest/ruff/mypy、脚本回归与本机真实源码 smoke；构建新包后运行同一场景。将实际断言映射回 Task 1，不对未覆盖分支升级。

### Task 3: 架构扩展设计与审批边界

**Files:** docs/superpowers/specs/2026-09-21-pm9-runtime-capability-completion.md；对应实施计划；相关 .ai 决策。
**Interfaces:** 先核对当前 shared Runtime、frozen prepared content、capability 与人工 DTO；设计不得假定新的端点或第二执行器已经存在。

- [ ] 子流程：明确冻结依赖图、调用栈/访问身份、输入输出拷贝、取消与能力传播、依赖环和深度拒绝、旧内容兼容与测试。
- [ ] 人工：明确声明输入 schema、合法后继/可验证目标、缺项响应、版本/代次/CAS 与 TTL，组件先于页面；不支持跨进程恢复。
- [ ] 并行：明确分支状态所有权、循环栈/取消/人工额度、join 与唯一 End、副作用次数和故障回收；证明安全后再开放准入。
- [ ] Windows：核对原生安全文件句柄、原子发布与重解析点拒绝、进程 birth/handle 所有权、未知归属保持隔离；每项用原生 CI 验证。
- [ ] 对超出已批准 R1–R4 的变更提交完整规格、接口、垂直切片与验证方案后请求一次确认；等待期间完成 Task 1/2/4 中独立工作。确认前不实现新的架构协议。

### Task 4: 稳定候选与交付

**Files:** CI 仅在新场景需要入口时调整；pm9/verification.json 与新候选报告；.ai/sessions。
**Interfaces:** 保留之前 d59607f3 三平台证据，新增候选单独标识，禁止沿用旧产物宣称新代码通过。

- [ ] 定向检查完成后，运行必要完整回归、typecheck/lint/OpenAPI/build；候选稳定再推送触发一次三平台验证，取消重复事件流水线。
- [ ] 收集各平台真实结论和场景报告；未具备外部条件的事项写明所需授权/机器/签名身份，不虚构通过。
- [ ] 完成本轮一次独立审查，修复实质问题后验证；提交推送、更新既有草稿 PR，不合并发布。

## 执行账本

- 2026-09-21 confirmed：起点 30c4a768，工作区干净，PR #1 OPEN/DRAFT，base codex/architecture-baseline；已有代码候选 d59607f3 三平台 success。本轮不得把旧成功视为新场景证据。
- Ruling：用户已明确授权计划后立即完成可执行工作，覆盖映射、现有能力验证和根因修复不再请求重复审批；仅 Task 3 的新增架构规格等待确认。

## 本轮执行结果（2026-09-21）

Task 1 完成：251 条、73 个预定路径相关条目均有映射/分类，静态引用与反例检查通过；22 个旧 verified 因实际缺口回退，未升级整项验收。Task 2 已交付基础真实链、两个人工竞争根因修复、环境账本 500 契约修复、原命令恢复和关联提交竞争；完整 FX 业务组合仍按 coverage 的细项保留，详见 completion-gaps §5。Task 3 的四片规格/契约/验证方案已提交确认，未获答复前维持 proposed。Task 4 本机验证及一次独立审查已通过，新三平台 CI 待运行。没有合并或发布。
