# PM4-C 有限/不限调度管理链核验记录

日期：2026-09-16
分支：`codex/project-management-pm4`
运行提交：`64606a23de3a77d36c97f833151fed5b44903f33`
核验结论：**管理侧通过，真实执行核心接入待验收**
置信度：管理界面、FastAPI、SQLite、领取和项目数据写入事实为高；生产执行器、真实浏览器与 Studio 为未验证。

## 1. 权威证据与边界

本次权威成功结果仅引用：

- [result.json](qa-runs/c-m3SplP/result.json)
- [c-facts.json](qa-runs/c-m3SplP/c-facts.json)
- 证据目录：`docs/project-management/implementation/pm4/qa-runs/c-m3SplP`
- 生产源码内容摘要：`b6cddd53fc179bfed4b987140a18caa104b14a403bbb4051a626ee0f47e5952a`
- Electron 构建入口摘要：`8ef91fec4a6de03a0a58d1cdf157f1c933504ffbf68154353a344e3e3dcf8fb6`
- 视口：1440×1024，DPR 1
- 平台：macOS `darwin/arm64`

运行使用真实 Electron、FastAPI、隔离 SQLite、项目数据领取与 capability 服务。项目、人员/邮箱/账号三张表、字段、记录和自动化均通过界面创建。执行步骤由 PM4 QA 专用假执行器确定性触发；没有启动 CloakBrowser，没有调用 Studio，也没有验证生产工作流执行核心。

`result.json` 中的边界为 `executor=fake`、`browser=notExecuted`、`studio=notExecuted`。本报告不扩大该范围。

本轮成功退出后使用 QA 脚本相同算法复算生产源码摘要，与 `result.json` 一致。本结论严格绑定上述摘要；后续生产源码若继续变化，集成负责人仍须在最终候选版本上重跑 `node scripts/qa-project-management-pm4.mjs --c`。

## 2. 已验证的管理业务事实

| 业务事实 | 实际结果 | 证据 |
|---|---|---|
| 三张表和测试数据 | 人员表 1 条、邮箱表 5 条、账号表 0 条；邮箱业务状态初始为空 | `01-three-tables.png`、`result.json.checkpoints[1]` |
| 两个必要输入 | 人员输入、邮箱输入均为 `independent + required`；邮箱输入包含“业务状态为空”筛选 | `02-two-required-inputs.png`、`03-finite-three-preview.png` |
| 有限三次 | UI 启动 3 个任务；批次完成且 `selectionOutcome=limitReached`；3 个 Task 全部成功 | `04-finite-three-completed.png`、`c-facts.json` |
| 人员重复使用 | 5 次 Task 的人员输入均为同一个带类型 RecordRef；运行不修改人员状态 | `c-facts.json.reusablePersonRef`、`result.json.checkpoints[3:5]` |
| 邮箱逐条消费 | 5 次 Task 使用 5 个不同邮箱 RecordRef；每条由显式项目数据操作将状态改为“已使用” | `c-facts.json.emailRefs`、`c-facts.json.usedEmailCount` |
| 账号幂等新增 | 5 次 Task 最终恰好 5 条账号，引用互不重复；没有因重复轮询或结果恢复产生重复账号 | `c-facts.json.accountCount`、`result.json.checkpoints[3:5]` |
| 输入和写入事实可见 | Task 输入输出页显示人员、邮箱不可变原始输入，以及 `statusChange`、`recordCreated` 写入结果 | `05-finite-task-input-output.png` |
| 不限次数与主动停止 | UI 选择不限次数，假执行器完成 2 个 Task 后保持批次运行；UI 输入原因并确认停止，批次变为 stopped，任务数保持 2 | `07-unlimited-two-tasks-running.png`、`08-unlimited-stop-confirmation.png`、`09-unlimited-stopped.png` |

测试执行器的 `max_auto_tasks=5` 是 QA 屏障，用于在有限批次完成 3 次后，让不限批次稳定停在 2 次以便从界面执行停止。它不是生产批次上限，也不能证明生产执行器的无限调度吞吐。

## 3. 截图复审

截图均为同一 1440×1024 视口。逐页核对顶部导航、原 gallery 主体结构、统一细网格表格、小圆角、内容宽度和弹窗滚动。生成时 `result.json.visualReview` 仍为 `pending`；以下为生成后的人工复审，不回写原始证据。

| 截图 | 页面/状态 | 复审结果 |
|---|---|---|
| `00-isolated-ready.png` | 隔离应用就绪 | 92/100，通过 |
| `01-three-tables.png` | 三张数据表目录 | 88/100，通过 |
| `02-two-required-inputs.png` | 自动化两个必要输入 | 89/100，通过 |
| `03-finite-three-preview.png` | 有限 3 次启动预检 | 88/100，通过 |
| `04-finite-three-completed.png` | 有限批次完成与 3 个任务 | 91/100，通过 |
| `05-finite-task-input-output.png` | 原始输入与写入结果 | 92/100，通过 |
| `06-unlimited-preview.png` | 不限次数启动预检 | 88/100，通过 |
| `07-unlimited-two-tasks-running.png` | 不限批次运行中 | 90/100，通过 |
| `08-unlimited-stop-confirmation.png` | 停止确认 | 90/100，通过 |
| `09-unlimited-stopped.png` | 不限批次已停止 | 91/100，通过 |

每张截图单独达到 85 分门槛。应用没有发生横向撑宽；批次与任务表保持紧凑密度。`06-unlimited-preview.png` 中可见两条历史“批次已创建”通知同时存在，属于通知视觉噪声，不影响本次调度事实；本轮按 QA 独占边界未修改前端。

## 4. 失败资料与问题闭合

开发期间的 `c-*` 失败目录保留，不用于证明通过：

- 早期失败集中在内联记录状态编辑的 CDP 指针时序。数据库与失败截图表明这是 QA 操作路径不稳定，不是状态持久化缺陷。C 场景改为在自动化输入中使用真实“业务状态为空”条件，随后由假执行器显式改为“已使用”，仍覆盖状态条件与状态变更语义。
- `c-EuWBN5` 暴露保存后路由漂移，QA 脚本改为从真实页面重新打开自动化。
- `c-QHvjW5` 暴露原生 radio 没有自身文本内容，QA 改用 `value="unlimited"` 选择器。
- `c-XZV9Zv` 暴露桌面会话启动后才写入工作流夹具时，资源查询可能保留夹具写入前的空目录。QA 在所有夹具完成后刷新一次真实渲染页，使资源通过公开查询重新加载；没有绕过 UI 选择或修改生产缓存逻辑。

这些调整只修改 QA 路径与假执行器编排，没有修改生产数据服务或前端。

构建入口摘要由 `out/main/index.js`、`out/preload/index.js`、`out/renderer/index.html` 以及该 HTML 实际引用的主 JS/CSS 文件路径和内容摘要聚合得到；不把 `out` 中历史哈希文件计入本次运行构建身份。

## 5. 验证覆盖与未覆盖项

本次真实 Electron C 链验证：有限 3 次、人员重复使用、邮箱显式状态变更、账号一次新增、不限次数启动、UI 主动停止和管理页面事实展示。

以下行为有生产集成测试或领域反例，但本次没有作为 Electron C 端到端执行：暂时占用后等待、真实耗尽自动结束、失败后默认停止/显式继续、进程重启恢复、旧执行代次撤权。它们不得写成用户界面验收通过。

在上述权威源码上定向执行 `test_project_data_scheduler.py` 与 `test_project_run_data_start.py`，结果为 **44 passed**；覆盖有限/不限次数、人员重复使用、暂时占用、真实耗尽、失败策略、停止门闩、终态 lease 释放、重启恢复、旧执行代次撤权、双工作区隔离，以及输入选择错误分类。另执行 `test_pm4_qa_runner.py`，结果为 **12 passed**；QA 脚本单元测试 **4 passed**，C 模式自检通过，QA Python 文件 Ruff 通过。它们属于生产服务、临时 SQLite 与 QA 编排的自动证据，不替代 Electron 人工故障路径。

以下项目明确未执行：

- 真实生产工作流执行核心接入；
- CloakBrowser 网页执行；
- Studio 联合运行；
- Windows、其他 CPU 架构与打包应用；
- 用户手动验收。

因此本轮结论固定为：**PM4-C 管理侧有限/不限链通过；真实执行核心接入待验收。**
