# 质量门禁修复记录

日期：2026-09-28。状态：in_progress。来源：历史审计 frontend-regression.md 与本轮源码/执行日志；已验证条目置信度高。

F-03：两个 inventory 脚本测试此前调用生成器覆盖历史验收清单、组件扫描与服务矩阵，且无法处理已经批准的原生节点。改为显式 `--output-dir <候选目录>`，测试使用本次 mkdtemp 创建的专属目录，结束删除自身目录。源码与已核销证据仍从仓库只读获取。无输出参数明确拒绝，避免检查或误调用静默改写历史证据。

节点清单分别验证 213 个冻结来源节点与 4 个原生节点（代理 3、项目数据 1）。原生节点保持原有 status、verifiedCases、remaining 和 deliveryBlock，禁止用旧节点共享验收记录将新节点升级为通过。现有冻结节点的独有字段与依赖断言保留。测试逐字节验证历史 capabilities/test-cases/component-tools/service-inventory/contract-matrix 不变，并独立检查候选生成确定性。

`inventory-readonly.log`：14 项通过，无 skip。未覆盖的门禁仍待处理，不代表完整根脚本或全前端回归已恢复。原生节点后续发生正式扩展时必须一起更新显式范围校验，不能从扫描结果自动放宽批准范围。
