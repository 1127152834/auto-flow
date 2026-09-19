# PM8 设计规格：完整生命周期与恢复收口

- 日期：2026-09-20
- 状态：confirmed（依据 `docs/superpowers/plans/2026-09-13-project-management-milestones.md` §PM8、`docs/project-management/design/functional-structure.md` PM-01…PM-05、`docs/project-management/implementation/api-contracts.md` §3.1/§3.5 冻结契约）
- 基线：`codex/architecture-baseline` @ `3a57aede`（含 PM0–PM7）
- 本规格不新增业务规则，只把已批准规则收敛成可实施、可验收的条目。

## 1. 目标

PM8 只做三件事：

1. **A**：把项目生命周期命令（归档、恢复、永久删除）和自动化删除/解绑做成真实可操作入口，含影响预检与阻断处置。
2. **B**：跨重启按持久事实核验（Run、文件发布、关联、发送、生命周期命令），已知可幂等收尾，未知不假释放，残留可见可处置。
3. **C**：退出应用、关闭 Studio、切换工作区与全局资源（Profile、内核、代理/池、模型）删除时，同时检查项目静态引用与活动占用，前后端共同保护。

**不做**：新增执行器、通用任务队列、PM9 的平台发行验收、Studio demo 联合测试、Sheets 远端写入语义变更。

## 2. 状态机与阻断规则（A）

### 2.1 生命周期状态

```
active --archive--> closing --(权威条件满足)--> archived --restore--> active
archived --delete(确认名+影响确认)--> deleting --(清理确认)--> deleted
```

- `closing`：禁止**新工作**——新批次、新领取、新导入/导出、新表/字段/状态/记录写、新自动化写、新 Sheets 连接/绑定/拉取/推送、新环境保存/维护。
- `closing` 必须**仍允许**已有工作的收尾：停止/强制停止批次、人工完成、已保存操作的核验、环境清理与已接受保存的发布、生命周期操作自身的进度查询。不能一开始锁死这些内部写回。
- `archived`：只读。所有写命令返回 `409 LIFECYCLE_CONFLICT`；读取、导出（写新文件到用户目标）仍可用。
- `deleting`：只允许删除操作自身推进与查询；对外读命令返回 `409 LIFECYCLE_CONFLICT`（对象正在消失，不得展示半删事实）。
- `deleted`：所有读命令返回 `404 PROJECT_NOT_FOUND`；只有 workspace 作用域的操作查询可按原幂等键找回删除结果。

### 2.2 归档条件（进入 archived 的权威判据）

同时满足才可从 `closing` 落到 `archived`：

| 条件 | 判据来源 |
|---|---|
| 无未终态批次/任务 | `project_batches`、`project_tasks` 状态集合为终态 |
| 无未决人工事项 | 人工事项不处于 `waiting` |
| 无进行中的环境现场 | 环境 instance 不处于 `reserved/starting/active/saving/cleaning` |
| 无进行中的导入/导出 | `project_operations` 中 `inspectExcel/importExcel/exportXlsx` 无 `accepted/running/reconciling` |
| 无进行中的生命周期命令 | 同一项目无其它 `archiveProject/deleteProject` 非终态 |

**不阻断归档**（必须保留并在归档后可见）：
- 未推送变化（`unsyncedCount > 0`）：归档保留未推送变化，不丢、不自动推送。
- 已关闭且归属确定的清理失败：按环境专项规则允许"警示归档"，并提供 ENV-09 维护入口。
- 历史失败批次/任务：保持历史事实，不因归档改写。

### 2.3 影响预检

`GET /projects/{projectId}/lifecycle-impact?action=archive|delete` 返回 `{impactRevision, blockers, impacts, unsyncedCount}`，
复用既有 `project_data_impacts` 确认存储（`action=archiveProject|deleteProject`），不新建迁移、不跨动作复用确认：

- 确认绑定 project、动作、项目 `managementRevision` 与影响事实摘要，有效期内（10 分钟，沿用既有实现）有效。
- 提交命令携带 `impactRevision` 与 `expectedManagementRevision`；任一不符、过期或事实变化 → `412 PRECONDITION_FAILED`。
- 归档预检出的 blockers 是**过程阻断**（列出真实对象与处理入口），不是拒绝；删除预检出的 blockers 是**拒绝**（必须先处置）。

### 2.4 删除归属

删除 A 项目时：

**删除**：A 的表/字段/状态/记录/槽/来源绑定与本地数据集、自动化与项目级运行默认、批次/任务/输入快照/事件/证据/产物、环境身份与工作副本目录、出站同步队列与意图、A 的项目级 Operation 与影响确认、项目记录本身。
**不删除**：外部 Excel 原文件、远端 Sheets（只解绑/断开本地关系）、全局资源（Profile、内核、代理/池、模型凭据）、其它项目对象、被其它项目引用的独立工作流文档。
**独立工作流**：`workflowDisposition='unlink'` 只解绑；`deleteOwned` 仅当该流程属于该项目且核心确认无占用时才允许。

**残留**：本地文件清理失败时，删除 Operation 保持非终态或 `failed` 且带 `CleanupSummary`，项目停留在 `deleting`，
用户可在归档目录看到"清理未完成"并重试；不得把残留报告成成功，也不得因为残留而让项目消失后不可查。

### 2.5 恢复

- 仅 `archived → active`；恢复后项目可编辑，项目资料与历史对象原样保留。
- **不自动**重跑历史任务、不重发同步队列、不重建已清理环境、不复活旧 Run。
- 恢复命令使用 `expectedManagementRevision`；归档期间不允许编辑项目资料，因此恢复时的修订冲突即代表并发客户端。

## 3. 跨重启核验与残留（B）

启动顺序（`bootstrap/app.py` 既有钩子顺序上追加）：

1. 撤权旧 Worker（既有 `workflow_services.runs.recover_interrupted()`）——迟到 Worker 不能写记录。
2. **Run 核验**：非终态批次/任务按持久事实查询核心；已知终态落库；未知保持 `reconciling` 并列出可处置入口，不释放不安全的占用、不重放网页。
3. **文件核验**：Excel 导入/导出按既有 `startup()/reconcile()` 检查发布事实；发布成功但结果未落库的按原目标+摘要恢复结果；目标不匹配报冲突，不覆盖、不另存。
4. **发送核验**：Sheets 出站 `unknown` 保持未知，只允许按原操作身份核验，不盲重发。
5. **生命周期续跑**：`closing`/`deleting` 项目重新评估条件并继续收尾或停在明确阻断上。
6. **残留可见**：任务详情的 `cleanup: CleanupSummary`、项目归档目录的清理失败条目、环境 `cleanup_failed` 都要有真实入口。

**重试不复活旧 Task**：同一 Task 的重试沿用 Run 身份与执行代次；旧代次的写被撤权拒绝。

## 4. 工作区与资源保护（C）

- **关闭 Studio 不取消任务**：关闭窗口/画布不是停止命令，批次与任务状态不变。
- **退出应用 / 切换工作区**：`SettingsRuntimeService.blockers()` 汇总项目侧阻断（活动批次、closing/deleting 生命周期命令、未决人工、未知发送）；有阻断时前端展示可去处理的对象，而不是静默退出。
- **全局资源删除**：Profile、内核、代理/池、模型的删除/卸载在**同一个事务**内检查：
  - 项目静态引用（`projects.default_resources`、自动化资源绑定）；
  - 活动占用（既有 lease/运行中操作）。
  存在任一引用 → `409`，返回引用对象清单与处理入口；前端展示阻断项，不提供"强制删除"。

## 5. 接口与持久事实

- 路由、请求/响应 DTO、错误码、Operation kind 结果形状全部沿用 `api-contracts.md` 冻结契约；**不新增**未列入契约的路由。
- 新增 Operation kind 只有 `archiveProject`、`restoreProject`、`deleteProject`、`deleteAutomation`；`cleanup` 由内部协调器使用。
- 迁移：原则上零新增。生命周期影响确认复用 `project_data_impacts`；生命周期进度与残留由 `project_operations` 承载。若实施中发现必须新增持久事实，先在本文件登记该事实与理由，再独立迁移。

## 6. 验收条件

### 6.1 自动验收（后端）

`apps/backend/tests/integration/test_project_lifecycle.py`：

1. 归档预检列出真实阻断（活动批次/人工/环境/导入导出）与 `unsyncedCount`；预检不改变任何状态。
2. closing 期间：新批次/新导入/新记录写被拒；停止、人工完成、已接受保存仍可提交。
3. 条件满足后自动落入 archived；`unsyncedCount>0` 与清理失败不阻止归档且保持可见。
4. archived 只读：写命令 409；读取与导出可用。
5. restore 后不重跑、不重发：历史任务状态与出站队列逐条不变。
6. delete 需要归档态 + 确认名 + 有效影响确认；名称不符 422、状态不符 409、影响过期 412。
7. delete 后：A 的对象与本地文件消失，B 与全局资源保留，外部 Excel 原文件字节不变。
8. 清理失败时项目停留 `deleting`，Operation 携带残留清单且可重查。
9. 幂等：同 key 重发不产生第二条删除/归档事实；响应丢失后按原操作身份找回。

`apps/backend/tests/integration/test_project_crash_recovery.py`：

10. 重启后非终态批次按核心事实收尾，未知保持未知且不释放占用。
11. 发布成功但结果未落库的导出/导入按原目标+摘要恢复；目标不匹配报冲突。
12. 未知发送不被重发；按原身份核验后才改变状态。
13. 撤权后的迟到 Worker 写入被拒；重试不复活旧 Task。

`apps/backend/tests/contract/test_project_resource_references.py`：

14. Profile/内核/代理/池/模型删除时，静态引用与活动占用分别产生 409，且不产生部分删除。

`apps/backend/tests/contract/test_settings_dashboard.py`（扩展）：

15. 退出/切换工作区阻断包含项目侧真实阻断项（活动批次、closing/deleting）。

### 6.2 自动验收（前端）

- `domains/projects/tests/ProjectLifecycleDialog.test.tsx`：影响展示、阻断清单、确认名、只读归档态、清理残留、失败保留。
- 归档目录与只读态：`ProjectDirectory`/`ProjectHeader` 扩展用例。
- 自动化删除/解绑：`AutomationDetailPage`/目录用例。
- 设置页与全局资源删除阻断展示。

### 6.3 真实应用端到端

Electron + FastAPI + 隔离 SQLite（隔离测试执行器，不调用真实 Studio）：

活动任务退出/切换工作区 → 处理阻断 → 重启核验 → 归档 → 只读导出 → 恢复 → 删除，逐个核对本地文件、外部原文件和全局资源。
每步保存截图；对照原型对应画板逐画面评分 ≥85；未执行项如实登记。

## 7. 已知边界

- 真实生产执行核心接入仍是既定边界，PM8 用隔离测试执行器验证管理侧，交付声明保持"管理侧通过，真实执行核心接入待验收"。
- Windows / 其他架构 / 打包应用未运行时明确标"未执行"。
