# PM4 V1 首条三表链核验记录

日期：2026-09-15
分支：`codex/project-management-pm4`
核验结论：**管理侧通过，真实执行核心接入待验收**
置信度：管理功能事实高；视觉匹配高；真实执行核心可用性未验证。

## 1. 本次通过范围

本轮证据来自真实 Electron、FastAPI、隔离 SQLite 和真实项目数据服务。项目、三张表、字段、状态、记录与自动化均通过界面创建；两个必要输入通过界面配置；批次与 Task 使用真实管理接口和持久化事实；邮箱状态修改与账号新增由隔离假执行器调用真实项目 capability 服务完成。

权威结果：

- [result.json](qa-runs/v1-mnj43N/result.json)
- [v1-facts.json](qa-runs/v1-mnj43N/v1-facts.json)
- 证据目录：`docs/project-management/implementation/pm4/qa-runs/v1-mnj43N`
- 运行源码版本：`60f4cc4feb97b1cab9583c4ae21aab7a9fd362cc`
- 源码内容摘要：`eb1529bafd7ee964dffc7fa63364c27d43d3f943709908c7092e9d0ffda87cee`
- 平台：macOS `darwin/arm64`
- 视口：1440×1024，DPR 1

`result.json` 状态为 `passed`，其 scope 原文为“管理侧通过，真实执行核心接入待验收”。本报告只继承该范围，不扩大结论。

## 2. 真实业务事实

| 事实 | 实际结果 | 证据 |
|---|---|---|
| UI 创建项目 | 已创建 `PM4 三表链验收`，只读项目查询找回同一项目 | `result.json.checkpoints[0]` |
| UI 创建数据资料 | 已创建人员、邮箱、账号三张表及字段；人员与邮箱各一条记录；邮箱有“待使用/已使用”状态；账号启动前为空 | `result.json.checkpoints[1]`、`01-three-tables.png` |
| UI 配置自动化 | 已创建自动化，两个数据输入分别为“人员输入”“邮箱输入”，均为 independent + required | `result.json.checkpoints[2]`、`02-two-required-inputs.png` |
| 原子输入快照 | Task 输入快照包含两项别名及记录的 typed identity、数据代次、内容/状态/关联修订和冻结字段值 | `v1-facts.json`、`03-input-preview.png`、`05-task-input-output.png` |
| 人员可保留 | 运行前后人员记录的值、业务状态和三个修订事实一致 | `result.json.facts.personBefore/personAfter` |
| 邮箱显式改状态 | 邮箱内容与 contentRevision 不变；状态从“待使用”变为“已使用”；statusRevision 从 2 推进到 3 | `result.json.facts.emailBefore/emailAfter` |
| 账号只新增一次 | 账号表最终记录数为 1 | `result.json.facts.accountCount` |
| 写入证据 | Task 展示 `statusChange` 和 `recordCreated` 两条成功写入 | `result.json.facts.dataWrites`、`05-task-input-output.png` |
| 运行事实 | 一个批次达到 completed，一个 Task 达到 succeeded，管理页面可打开批次及任务输入输出 | `04-batch-completed.png`、`05-task-input-output.png` |

这组事实验证了 V1 所需的管理闭环，以及最小范围内的事务、typed identity、版本校验、幂等恢复和旧执行代次保护实现。执行动作来源仍是 fake，不能解释为真实网页或生产工作流执行。

## 3. 执行器边界

| 项目 | 本轮状态 | 结论 |
|---|---|---|
| Electron 管理界面 | 已执行 | UI 创建与查看路径进入本轮证据 |
| FastAPI 管理接口 | 已执行 | 真实 handler；只读查询用于核对 UI 提交后的最终事实 |
| SQLite | 已执行 | 使用 marker 所有的隔离工作区数据库 |
| 数据领取与项目 capability | 已执行 | 真实事务、lease、状态写入与记录新增 |
| 执行器 | `fake` | 只由 PM4 QA 启动器注入，驱动确定性步骤 |
| 真实浏览器 | 未执行 | `browser=notExecuted` |
| Studio | 未执行 | `studio=notExecuted`；不做联合测试 |
| 真实生产执行核心 | 未执行 | 生产端 `project.data` 能力接入待单独验收 |

最终表述固定为：**管理侧通过，真实执行核心接入待验收**。

## 4. 截图证据与视觉状态

| 截图 | 页面/状态 | 对照基准 | 当前视觉结论 |
|---|---|---|---|
| `00-isolated-ready.png` | 隔离应用就绪 | `00-projects/100-projects-prototype-5238b4.png` | 92/100，通过 |
| `01-three-tables.png` | 三张表目录 | `05-data/001-data-v1-approved-ca940d.png` | 87/100，通过 |
| `02-two-required-inputs.png` | 自动化两个必要输入 | `docs/prototype/project-management-pm3/automation-detail-inputs.png` | 89/100，通过 |
| `03-input-preview.png` | 启动前输入预检 | `docs/prototype/project-management-pm3/batch-start-dialog.png` | 88/100，通过 |
| `04-batch-completed.png` | 批次完成 | `03-runs/004-batch-detail-approved-459f25.png` | 91/100，通过 |
| `05-task-input-output.png` | 原始输入与写入结果 | `03-runs/006-task-input-output-approved-7af0aa.png` | 91/100，通过 |

独立视觉复审结论：**PASS**。六个画面均满足单页 85 分门槛；顶部导航、统一细网格表格和小圆角符合已批准调整，页面没有因长内容或浮层发生应用级横向撑宽。`result.json` 中的 `visualReview: pending` 是截图生成时的现场值，本节记录截图生成后的独立复审事实，不回写生成证据。

## 5. 异常与保护验证边界

已实现并存在专项自动反例的能力包括：

- 两个必要输入中任一领取失败时，Task、输入快照、全部 lease 和 queued CoreRun 不产生半提交；
- 数据操作身份绑定 project/task/run/executionGeneration，旧执行代次不能继续写入或提交终态；
- 邮箱状态写入和账号新增使用稳定 operationId，提交后 ACK 丢失先查原操作，账号不会重复新增；
- 缺少账号 create grant、邮箱 status grant 或目标时，启动在持久运行事实产生前被拒绝；
- 普通停止先于第一步取得权时不执行数据写入；终态确认后才释放可安全释放的 lease。

这些反例位于：

- `apps/backend/tests/integration/test_project_run_data_start.py`
- `apps/backend/tests/integration/test_project_node_writes.py`
- `apps/backend/tests/integration/test_pm4_qa_runner.py`
- `apps/backend/tests/unit/test_project_data_capabilities.py`
- `apps/backend/tests/unit/test_pm4_fake_executor.py`

本文件不把测试文件存在本身当作通过证据，也不以测试数量代替功能完成度。相应命令与用户可执行边界见 [manual-test.md](manual-test.md)。V1 最新 E2E 结果只证明正常三表链；ACK 丢失、缺 grant、停止竞争与旧代次属于专项自动反例，尚未作为 Electron 人工故障场景执行。

## 6. 历史运行处理

`docs/project-management/implementation/pm4/qa-runs` 中存在早期 `v1-*` 成功和失败目录，它们用于记录开发期间的失败、修复和重跑过程。当前通过结论只引用 `v1-mnj43N/result.json`；不使用早期失败目录证明通过，也不覆盖或删除历史失败事实。

## 7. 尚未完成或未执行

| 项目 | 状态 | 说明 |
|---|---|---|
| 独立视觉复审 | 通过 | 六个画面均达到单页 85 分门槛，无视觉阻断 |
| 用户手动验收 | 未执行 | 手册中的所有用户结果保持“未执行” |
| 真实工作流执行核心接入 | 未执行 | 当前 V1 使用隔离 fake executor |
| 真实 CloakBrowser 网页执行 | 未执行 | 本轮只复用安装内核通过资源校验 |
| Studio 联合测试 | 未执行 | 用户明确排除 Studio demo 联合测试 |
| Windows | 未执行 | 无本机运行证据 |
| 其他 CPU 架构 | 未执行 | 无运行证据 |
| 打包应用 | 未执行 | 本轮为开发构建和隔离 Electron |
| PM4 A/B/C/F 全范围 | 未完成 | V1 是首个垂直切片，不能替代完整 PM4 验收 |

## 8. V1 退出门槛状态

| 门槛 | 状态 |
|---|---|
| 真实 UI 创建项目、三表、资料和自动化 | 通过 |
| 两个必要输入共同领取并创建一个 Task | 通过 |
| 邮箱显式状态写入、账号新增和人员不变 | 通过 |
| 管理页面查看不可变原始输入与写入结果 | 通过 |
| 假执行器边界准确记录 | 通过 |
| 事务、身份、版本、幂等和旧代次专项反例 | 已有自动验证；用户手测未执行 |
| 截图产出 | 通过 |
| 独立视觉复审达到既定门槛 | 通过 |
| 用户手动验收 | 未执行 |

因此 V1 已达到首条三表链退出门槛，可以进入 PM4-A；它不能替代完整 PM4 验收，也不能进入“生产工作流可用”结论。
