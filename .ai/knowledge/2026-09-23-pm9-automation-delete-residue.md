# 自动化删除后的人工事项和产物残留

日期：2026-09-23。状态：confirmed（真实反例、人工事项修复）；AD1–AD3为proposed。
来源：`pm9/automation-deletion-follow-through.json` 的 manualAndArtifactFollowThrough 及实际5346ceca打包HTTP/worker/浏览器/UI失败报告。

停止真实等待人工任务后，UI完成删除但cancelled人工事项仍指向已删除Task。另一流程人工继续后在click_element缺失选择器处失败，产生可用PNG；删除前HTTP登记字节数和摘要已确认，真实workspace/runs/<runId>/generation-1非空，删除后resolved人工项和相同PNG均保留。最初探针误查userData/runs，不能作为文件结论；修正到AppPaths.workspace路径并确认删除前文件存在后才获得有效反例。显式screenshot节点探针被既有准入拒绝，不扩大白名单，也不把它计作清理证据。

有界修复：影响与提交复用同一_facts，在事务内按目标Task检查waiting/resume_requested；终态批次不能掩盖未处理人工命令。_purge_automation在Task前删除该项目这些Task的终态人工事项；不删其他Task事项。最初直接测试使用resumed非合同状态，已改为resolved，后者另由真实worker反例证明。38相关后端、最终11删除契约、6前端、101脚本、Ruff/mypy407通过。新包复测resolved人工项消失而PNG仍残留，失败报告没有改成passed。

文件目录清理需要先持久接受原删除操作、冻结有归属Run、失败保留恢复事实和重启续清，不能在数据库删除后做一次不记账的rmtree冒充完成。AD1–AD3规格和实施计划已按AGENTS架构要求提交确认；未新增执行器、未跨进程恢复人工、未删除外部输出或旧孤儿。项目工作流所有权仍未实现，FR/L1/M1/S4附录授权状态不受本修复改变。

旧5346矩阵35871462256因该新实际缺陷取消；新的最终源码与全量/打包/三平台结果继续追加到专项报告。releaseAccepted=false，草稿PR不合并发布。
