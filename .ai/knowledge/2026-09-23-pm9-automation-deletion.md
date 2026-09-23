# PM9 独立流程删除与配置快照清理

日期：2026-09-23。状态：confirmed（缺陷、已运行子范围）；本机完整回归已通过，三平台CI进行中。
来源：`docs/project-management/implementation/pm9/automation-deletion-follow-through.json`、实际 c165 ARM 已安装包 Electron/HTTP/worker、SQLAlchemy 删除契约反例。

已完成：复用现有桌面 smoke，在隔离项目创建 open→manual→End 工作流。真实人工等待阻断删除；停止任务后旧 impact 返回412并清空名称；新清单精确名称删除成功，独立文档 id/revision/nodes/edges 不变、可重新关联，原键重放保持同一 operation。完整旧包 smoke 同时通过真实业务、合成日志、万行写入、缩放、第二窗口和重启。此时未检查快照，因此不能用该成功结果掩盖后续发现。

追加 SQLite 契约证明：原影响清单按workflowId统计，误包含独立的准备内容；原清理查询要通过批次选快照，但先删批次，导致快照零命中。两个断言分别失败，根因修复只调整既有查询范围和同事务顺序。独立文档和无本自动化批次引用的快照保留。旧测试名“keeps_run_history”与实际断言矛盾，已改为准确名称。生产代码无新增接口/依赖/执行器。

实施验证顺序：
1. 已完成34项相关后端、6项删除对话框、Ruff/mypy407；直接断言RED→GREEN。
2. 重建ARM应用完整桌面通过（包内backend SHA256 bc7344d854babb0c3defbf342e9563dd4c74a99b32bba7e7b4913efd8821fd61），完整后端3479 passed/78 skipped/2依赖警告（793.08秒）通过；桌面 smoke新增只读SQLite检查，删除后批次/任务404且该独立workflow对应冻结快照为0。
3. 稳定候选推送同分支并跑一次三平台完整矩阵；后续只更新报告，不重复跑无关流水线。

AU-08未完成条件：项目所有权尚未持久化，deleteOwned返回WORKFLOW_OWNERSHIP_UNKNOWN，属于proposed所有权机制未实现；安全拒绝不等于实现。Studio并行编辑占用、重复关联去向、项目级解除关联完整联合证据仍缺。Windows/Intel物理UI、签名、公证、当前Google授权等外部条件保持pending。FR1–FR3/L1–L3/M1–M3/S4既有文件覆盖等提案不因本切片而获批准。releaseAccepted=false，不合并发布。

源码5346ceca已推送；三平台 Actions35871462256运行中。新包真实worker1004条/32035ms，五路10000行51959ms/0busy；固定1000条合成输入60021ms/最大滞后84ms独立记录。历史上已无批次引用的孤儿快照不自动扫除，不能猜测归属。删除后的运行产物目录清理不在本片断言范围。
