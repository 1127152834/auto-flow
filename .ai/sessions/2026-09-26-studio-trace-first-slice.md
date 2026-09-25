# Studio Trace 第一切片

日期 2026-09-26；confirmed 的范围限于验收记录。来源：用户选择时间线方案后要求继续，基线 2cc06c63。

复用 existing worker/session、产物索引、鉴权项目过滤、LangGraph client_action 和底部面板，不增加执行器/数据库迁移。主仓库与运行中用户应用未改。独立 codex/studio-trace 工作树。

已实现与未完成边界统一见 docs/migration/evidence/studio-trace/acceptance.md 及设计第 8 节。真实内核 Console/Runtime 行为不一致，因此以真实受控页面测试作为依据；不声称捕获所有 JS。

后续优先：显式追踪设置及多会话/项目运行一致性，然后三类诊断节点及增强资源读取；无需重做已通过的原型或另建执行框架。当前未经合并，不修改其他工作树。
