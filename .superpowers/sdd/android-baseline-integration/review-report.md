# Android / PM9 合并独立审查

- 日期：2026-09-24；状态：confirmed，有限范围审查完成。
- 输入：`c6e02427`、`746c9c5b`；真实共同祖先 `31bfbb514bb2dc56cf9a4213448c06bc0ef74400`。
- 审查方式：分别对双方 parent 比较当前合并树，核查原冲突文件和直接交叉调用；仅此报告写入，未修改生产代码、测试或提交。

## 结论

**当前未发现未解决的 Critical / Important；置信度：高（本次冲突与直接交叉范围）。** 合并期间发现一项 Important，已立即回报主代理并确认实现代理修复。Minor：无需要单列的问题。最终全量门禁、原生打包与本地分支推进由主代理完成；本报告不将未执行的平台验收表述为通过。

## 已闭环 Important

**P1：结构化并行分支深拷贝新的任务局部循环栈会直接崩溃。**

- 位置：`apps/backend/src/autoflow/application/workflows/runtime.py:484`；相关类型 `apps/backend/src/autoflow/domain/workflows/execution.py:15`。
- 触发：任意 PM9 structured parallel fork。Android 分支将 `ExecutionContext.loop_stack` 包装为含 `ContextVar` 的 `_TaskLocalStack`，PM9 仍调用 `copy.deepcopy(self.context.loop_stack)`，首个 child 创建前即抛 `TypeError: cannot pickle '_contextvars.ContextVar' object`，手动队列、分支取消与显式输出均无法执行。
- 独立 RED：在合并工作区以 `PYTHONPATH=src .venv/bin/python -c 'import copy; from autoflow.domain.workflows.execution import ExecutionContext; print(copy.deepcopy(ExecutionContext().loop_stack))'` 复现该异常。实现代理的已有真实图回归同时出现九个相关失败，见 `backend-runtime-green.log`（保留原失败文件名）。
- 当前修复：在唯一 fork 复制点先 `list(self.context.loop_stack)` 取当前分支可见帧，再深拷贝；保留双方隔离机制。
- 独立 GREEN：`PYTHONPATH=src .venv/bin/python -m pytest -q tests/unit/test_project_graph_executor.py -k 'structured_parallel_loops or parallel_local_break or sensitive_values_keep_taint' tests/integration/test_migration_heads.py`：**4 passed / 26 deselected，0.81s**。此处 `-k` 未选择迁移用例，迁移另行运行如下。

## 核查结果与证据

1. **运行时与装配**：保留 PM9 节点边界、manual 串行门禁、stop 抑制、结构化分支取消等待、敏感值 finally 传播，以及 Android 调试入口、变量事件与循环变量恢复。`configure_project_workflow_runtime` 仍装配 `ProjectWorkerCapabilities`、environment 服务、capacity=2、fenced/manual 清理与共享 browser 资源门禁；Studio 新服务、metadata 路由与静态路由优先顺序均保留。canvas subflow 对 PM9 无 command bus 的调用仍可用，有 bus 时继续绑定 Studio 交互 gateway。
2. **worker / Android 身份与未知结果**：ready 消息仍从 browser session 读取真实 `browser_pid`；平台进程存在性检查保留 PM9 Windows 实现；Android 无 birth 的存活进程继续隔离，未改回信号探测。`pendingCommand`、v2 完成标记、124/旧零结果未知、持久 receipt 后 acknowledge 与 `preserve_command` 路径保持 Android 侧实现。未发现因冲突解决而移除代次/取消/归属门禁。
3. **PyInstaller**：同时保留 PM9 required-fields JSON、macOS cryptography OpenSSL ABI pair 与 Android 分支引入的 Studio ML 动态库/模型资源；不把 spec 静态正确等同实际打包成功。
4. **迁移**：新 `0020_merge_android_pm9` 仅汇合 `am01_management_operations` 和 `pm10_shared_sheet_cursors`。独立逐文件字节核对：baseline 的 **38** 个、Android 的 **43** 个既有迁移均无修改（两组包含共同历史，不能据此称 81 个不同迁移）。独立运行 `PYTHONPATH=src .venv/bin/python -m pytest -q tests/integration/test_migration_heads.py`：**4 passed，0.77s**，覆盖从两个发布 head 真实 SQLite 升级、重复迁移、记录保留和外键检查。其他迁移冲突保持原断言，仅将预期 head 更新为合并 revision。
5. **前端与清单**：现有 source 目录维持 213 节点，另有 `project_data` / `project_manual` / `project_end` 三个 PM 节点；配色审计总数 216，source 教学审计仍只检查 213。独立解析 capabilities：恰 **213** 条，ID 集合与 Android parent 完全相同，通知仅 `notify_telegram` / `notify_webhook`。六个 smoke 冲突保留扩展场景并使用不依赖目录总数的 Studio 就绪条件，未回填退役通知节点。
6. **实现代理证据已阅读**：`backend-report.md` 的 52 项 runtime/migration、559 项 Android/migration、24 项 worker 协议及 Ruff；`frontend-report.md` 的 11 项目录/配色、889 项生成契约/文档、docs test 和六脚本语法检查。明确区分这些代理结果与本报告独立运行的 8 项检查。

## 验证边界

未执行完整历史功能再审计、真实 Android 设备变更、Windows/Intel/ARM 全平台运行或正式包 smoke。生成 OpenAPI、全量前后端测试、类型/lint/build 的最终结果以主代理本轮整合门禁为准；读取代理报告不替代这些门禁。

## 补充复审：默认变量解析基线

2026-09-24；状态：confirmed；仅复核 `addNodeParserBaseline.json`、`addNodeDefaults.test.ts` 及双方对应 `editor-store.ts` 增量，没有扩大产品审查范围。

- 真实共同祖先 `fieldDistribution.variableName=14`。PM9 parent 新增 `project_data` 的 `variableName: 'task_inputs'`，独立增加 1；Android parent 把 `ocr_captcha` 的 `resultVariable: 'captcha_text'` 改成 `variableName: 'captcha_text'`，再增加 1。Git 将相同的文本 `14→15` 合并一次，不反映两个语义增量；整合后正确值为 **16**，同时 `resultVariable` 应为 **114**。
- 当前 JSON 修正正确，并保留 PM9 三节点的 branch/module/field 总数增量及全部严格分布断言。当前样例测试分别断言 `project_data/task_inputs`、`ocr_captcha/captcha_text`，与双方生产源码一致；无需产品修改。
- 已阅读定向原始日志 `frontend-parser-baseline-green.log`：**15 passed / 1 file，932ms**。这是实现代理执行结果；本轮复审没有重复运行同一检查。完整前端重跑结果仍由主代理收口。
- 首轮全量结果由主代理观察并保存为 `docs/qa/android-management/2026-09-24-baseline-integration/frontend-first-failure-summary.txt`：**5724 passed / 1 failed，429 files**，唯一失败即预期 15 / 实际 16。该文件明确是工具输出摘要；原 raw 因归档路径错误而被重跑覆盖，不能引用旧 `frontend-full.log` 或旧行号作为完整首轮证据。已通知主代理修正 frontend 报告中的陈旧 raw 引用。
- 本补丁无新增 Critical / Important / Minor；原审查通过结论保持，置信度高。
