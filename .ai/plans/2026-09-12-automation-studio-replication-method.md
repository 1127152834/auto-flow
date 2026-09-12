# Automation Studio 渐进复刻路线索引

- 日期：2026-09-12
- 状态：proposed
- 来源：用户要求先提供 WebRPA 复刻方法论、可复用代码分类和实施路线，再套用方法进入后续开发。
- 正文：[方法与实施路线](../../docs/superpowers/plans/2026-09-12-automation-studio-replication-method.md)。只维护一份正文。
- 验证：只读核对参考提交 `5ccb900e8dcf1530aae66f676d87593c416c7ebb` 的前端/执行器与 AutoFlow 正式窗口、浏览器 worker；未运行 WebRPA，本轮不修改业务代码。
- 核心建议：以行为为基线按用户场景迁移；先完成真实编辑保存，紧接少量节点真实执行，再扩展控制流、网页能力和录制。
- 当前关键依赖：Profile 测试浏览器端口只有 start/stop/statuses，首个执行链前须验证受控 page 的操作通道和资源生命周期。
- 后续状态：首批节点行为规格、运行对照、领域命名和旧计划冲突归一尚未完成；本路线未自动 supersede 既有决定。
- 下一步：R0 首批来源对应、最小契约和验收样例；实施依据用户后续对方案的反馈。
