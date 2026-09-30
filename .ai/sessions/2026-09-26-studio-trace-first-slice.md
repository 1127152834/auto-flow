# Studio Trace 第一切片

日期 2026-09-26；confirmed 的范围限于验收记录。来源：用户选择时间线方案后要求继续，基线 2cc06c63。

复用 existing worker/session、产物索引、鉴权项目过滤、LangGraph client_action 和底部面板，不增加执行器/数据库迁移。主仓库与运行中用户应用未改。独立 codex/studio-trace 工作树。

已实现与未完成边界统一见 docs/migration/evidence/studio-trace/acceptance.md 及设计第 8 节。真实内核 Console/Runtime 行为不一致，因此以真实受控页面测试作为依据；不声称捕获所有 JS。

后续优先：显式追踪设置及多会话/项目运行一致性，然后三类诊断节点及增强资源读取；无需重做已通过的原型或另建执行框架。当前未经合并，不修改其他工作树。

同轮继续完成三个诊断扩展及只读 DOM/助手分段读取。第一切片提交 23bf1ec3；后续提交独立。优先剩余改为多会话/项目路径、显式模式设置、增强脚本采集和完整新节点 UI 主链；不再把已实现三个节点登记为缺实现，但未完成场景继续保持待验收。


2026-09-26 后续增强（confirmed仅限acceptance所列证据）：补齐traceMode保存/撤销/运行快照，增强实际JS源文件归档、只读面板和助手分段读取，多浏览器manifest聚合与会话筛选。真实测试发现Cloak Debugger需要同时skipAllPauses与setBreakpointsActive=false才能防止网页debugger语句阻塞，保留真实回归。正式构建HTML通过模式设置、保存、CmdW重开验证。下一块为项目运行的诊断产物与ACK/End关闭顺序，不可把Standalone验收迁移为项目通过；真实模型仍缺测试配置。权威状态见规格11.2与acceptance新增段。
