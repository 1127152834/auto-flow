# M2A Task 1 实施记录（主处理输入、完整身份与台账仓储）

日期：2026-10-02。分支：codex/architecture-baseline（本机提交，未推送）。状态：Task 1 本机完成；M2A 未退出。
来源：用户 2026-10-02 指示"本机端到端测试，暂不推送，测试完成后继续实施后续里程碑"。步骤级计划见 docs/superpowers/plans/2026-10-02-remediation-m2a-task1-ledger.md。

## 已做（每项先失败测试后实现）
- 领域 `domain/project_runs/ledger.py`：完整作用域（键类型、数据代次、Sheets 命名空间；本地表命名空间为空串以保证唯一约束）、reset/skip/resolve 转换；needs_review 只能 resolve，保留原未知事实。
- `inputPlan.processingInputId`（可选，须指向必填输入）；`processing_input()`：显式优先，唯一必填时自动取，多必填未选为歧义，不按顺序猜。HTTP 契约与前端生成类型同步。
- 迁移 `rm2_record_ledger`：建 automation_record_ledger、project_batch_units；回填单必填输入的主处理输入；结果不明（interrupted + WORKFLOW_RESULT_UNKNOWN）的历史任务转 needs_review。可重入。迁移 head 固定值测试同步更新。
- 仓储 `infrastructure/database/record_ledger.py`：只接受完整作用域，修订号比较写入，按 id 键集分页，批次处理单位登记；`processing_input_report()` 列出需要选择的自动化（HTTP 暴露留 Task 3）。
- 批次启动门禁：歧义拒绝 `PROCESSING_INPUT_REQUIRED`（409）且不留运行事实；确定时冻结进批次请求。
- 前端输入编辑器：多必填时显示"逐行处理的数据"选择，编辑时只保留仍有效的选择。

## 验证（本机 Windows）
- 新增/受影响：台账规则 15、自动化规则 22、仓储与迁移 5、数据启动 14、自动化前端 123 全过；元数据门禁（迁移与模型一致）通过。
- 项目范围回归（unit + contract + test_project_* + test_pm*，含真实浏览器）：3700 过；失败均为本机环境（符号链接权限、人脸/OCR、冻结参考源）或原有问题，已逐个用未改动代码复核。
- 原有问题（未改）：`test_project_full_scenarios.py::test_browser_result_updates_claimed_record_and_status` 在配置真实浏览器时 422（请求体多带 workflowId），CI 全量回归未设真实浏览器变量所以没暴露。
- ruff/mypy（除本机缺 face_recognition）/严格类型债务（除同因 4 项）/前端 typecheck、lint 通过。

## 影响与风险
- 行为变化：已有"多份必填数据且未选择"的自动化，升级后新批次（含失败后续）被拒，需用户在输入编辑器里选择。迁移报告函数已就绪，界面提示依赖启动报错文案。
- 台账尚未接入领取与终态（Task 3/4）；当前只建档与门禁，不改变领取行为。

## 下一步
M2A Task 2（失败分类与整 Task 重放边界）→ Task 3（终态同事务投影、resolve 接口）→ Task 4（三种领取模式）。

## 2026-10-03 续：Task 2a 与 Task 3（本机提交，未推送）
- Task 2a（569aeab1，计划 docs/superpowers/plans/2026-10-02-remediation-m2a-task2a-side-effects.md）：节点副作用声明（默认"可能"，白名单只读），随已确认的 started 事件持久化；失败分类 infrastructure/page/unknown/cancelled，任务详情 failureCategory。真实浏览器写冲突用例分类为 unknown。
- Task 2b（统一 errorPolicy、旧配置候选迁移、节点级重试与前端控件）顺延到 Task 4 之后。
- Task 3（98b1139a，计划 docs/superpowers/plans/2026-10-03-remediation-m2a-task3-projection.md）：终态在释放主处理输入租约的事务内投影到处理记录（恰好一次）；业务失败来自 End；processing-units HTTP 与人工 reset/skip/resolve；自动化详情页"处理记录"面板（组件测试覆盖，未在真实 Electron 中截图核对）。
- 验证：项目范围回归 3772 过；失败为已知本机环境项，另 `test_real_project_batch_http[manual-stop]` 一次失败、重跑通过（时序偶发，未定位）。
- 仍未接入领取：处理记录目前只记录与人工处理，领取行为不变（Task 4）。
