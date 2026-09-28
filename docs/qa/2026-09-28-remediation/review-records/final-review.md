# 最终独立广度审查：faf8fc21..e49144f2

日期：2026-09-28。状态：confirmed（历史初审结论）。置信度：高，限已读源码及逐项核对的证据。

审查范围：`faf8fc21..e49144f2458a5024ef2ef06d5f8bba75f67c0557`，生产 End、进程归属清理、交互恢复、Studio 配置一致性及相应测试、契约、可执行 QA。按 requesting-code-review/code-reviewer.md 执行。完整分段阅读 90 文件代码包，并追踪相关共享调用方。没有修改源码、提交、派生子代理或重跑已通过套件。范围不含此前被自动审查阻止的独立安全修复。

本文件在后续限定复审时落盘，保存初审当时的结论与证据时点。后来的修复结论独立见 `final-rereview.md`，不能倒改为初审已通过。

## Strengths

- End 接纳绑定冻结节点、访问身份、执行代次和写租约；发布及关联事务再次校验权限。清理未知时保留恢复责任，没有发现新增绕过关闭确认的问题。
- End 状态跨嵌套运行上下文传播；部分保存成功保留完整错误、保存身份及修复入口，历史失败事实未被修复结果覆盖。
- 交互恢复继续查询原命令，claim 等待不再阻塞其他轮询；同实例重连与 workspace/instance remount 已分开处理。
- 进程清理改动仅跳过已由 birth 确认归属 PID 的重复参数检查，未取消新候选归属检查或发信号前的 birth 复验。

## Issues

### Critical

0。

### Important

1. **非空静态 End 目标被显示为空，界面与实际关联行为不一致。**

   位置：`apps/desktop/src/renderer/domains/workflows/components/config-panels/ProjectEndConfig.tsx:30`（e49144f2 行号）。

   触发：打开合法非空静态 `recordTargets` 数组的工作流，启用环境保留。领域验证和 End 宿主接受静态数组；该处却只有字符串才能显示，其余一律显示空字符串。

   影响：用户看见“留空不追加记录”，实际执行仍关联隐藏数组中的记录；开启替换授权时还可能替换这些记录已有的关联。显示已经为空也无法直接通过清空操作删除原目标。初审时组件测试没有覆盖静态数组。

   最小修复：对静态数组提供准确可见的展示及明确清空入口，或提供支持数组读取/编辑的控件。不能仅 JSON.stringify 后作为字符串存回，因为后端字符串分支只接受完整变量引用。补非空数组回显、保留与清空后的存储形状回归。

2. **“调用子流程”选择器遗漏有效 nested 分组，并继续读取陈旧外层名称。**

   位置：`apps/desktop/src/renderer/domains/workflows/components/config-panels/ControlModuleConfigs.tsx:478`，以及第 487、509 行（e49144f2 行号）。

   触发：分组采用 `data.config = {isSubflow: true, subflowName: 'x'}`，外层没有 isSubflow；这是 Task6 支持并保持原形状的配置。新的分组编辑入口能识别它，但 SubflowConfig 仍用原始 n.data.isSubflow 过滤。

   影响：有效子流程从调用下拉框消失，用户无法选择；存在冲突外层旧值时则可能列出运行时并非子流程的分组，并显示或写入陈旧名称。这是共享配置一致性修复遗漏的直接消费者，虽然该文件在初审范围内本身未改。

   最小修复：过滤、选项名称、选择后写入的名称统一读取 getNodeConfigData(n.data)；继续保留外层 label 身份和原始文档形状。补 nested-only、外层旧值冲突、实际选择写入回归。

### Minor

新增 0。既有 Node localStorage ExperimentalWarning 按账本 deferred Minor 保留，没有重复计数。

## 验证证据及限制

- 已核对最终后端摘要：4326 passed、0 failed、50 skipped；`d6f9cb0f..e49144f2` 后端生产源码无变化。
- 已核对最终前端原始日志及 manifest：433 文件、5683 测试通过；根脚本 102 通过；lint/typecheck/build/package 全部 exit 0，源码前后摘要一致。
- 已核对 packaged-end-v3：e49144f2 同版包 exit 0，首次保存登录、完整应用重启、第二 Run 复用 Cookie，两会话结束后记录的 owned 进程为空。该脚本通过 API 建立流程，不能替代原生编辑验收。
- 初审报告形成时，旧 SQLite 工作区的原生修改→保存→重开→完整重启→真实 End 闭环尚未取得完整结果，因此当时未计通过。随后 root 完成的 e49144f2 证据在 `../native-session-LCCIyR/README.md`，仅作为后续证据追加，不覆盖以上两个遗漏。
- claim 窄窗口物理断线、物理清理未知、真实磁盘满/提交中断仍缺实证；确定性边界测试和内部回执注入不能替代。
- AOCI 首次传输因 snapshot unavailable 中止；压缩后的刷新发生宿主截断，已停止，没有维护或接管资产。审查结论绑定源码和具体证据，不声明完整系统认知或治理对齐。

## Declined to judge

- 人工跨应用重启续接语义：Task2 等待用户裁定，未实现，不属于本次完成切片。
- 基线之前被自动审查阻止的安全修复：明确排除，不重试、不给通过结论。
- Windows、macOS Intel、外部账号/付费模型/消息发送、Android 与原生硬件能力：本次无对应实证，不扩大本机结果。
- 历史未带版本标记的环境摘要升级：保留路径/大小摘要兼容上限；不把本次 v2 内容摘要实现解释为历史目录已迁移。
- AOCI 初始化与治理对齐：另一任务拥有，不在本审查中裁定完成。

## Assessment

**初审 scope verdict：With fixes。Critical 0、Important 2、新增 Minor 0。** 当时不能将 Studio 配置一致性切片判为完成。需修复两个 Important 后做限定复审，并补齐原生配置验收。End、交互恢复和进程归属清理在已读范围没有发现新的阻断缺陷；这不是完整生产验收通过的结论。

勘误（落盘时明确追加）：初审聊天中第 1 项曾以 `{projectId, tableId, recordId}` 简写合法静态目标，该示例字段错误。实际 worker End 入参是直接 `{projectId, tableId, datasetGeneration, recordKey}`，见 `apps/backend/src/autoflow/application/project_runs/end.py:222-223`，不能包在 recordRef 中。这不改变“所有非空数组被显示为空”的源码事实及修复要求。
