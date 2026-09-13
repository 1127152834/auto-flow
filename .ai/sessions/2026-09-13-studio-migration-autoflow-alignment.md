# WebRPA 迁入与 AutoFlow 工程对齐

- 日期：2026-09-13；状态：用户产品方向和工程约束 confirmed，具体实施 proposed。
- 用户本轮要求：说明如何迁入，架构、技术栈、开发习惯贴合 AutoFlow。本次只交付文档，未迁入代码。
- 基线：`25273d5`，旧 Studio 已清除，仅剩独立空窗口；新实现未开始，历史迁移 head `0008_workflow_debug`。
- 核查：当前领域目录、共享 ApiClient/Query/SSE、组件/样式、窗口权限、Profile/worker，以及冻结 WebRPA 的编辑器/Store/文档转换/执行器/录制/Debug。前后端分别委托独立只读复核。
- 修订：取消平行 webrpa 应用树和默认 Socket.IO；领域 Zustand 保留原编辑算法，Query 管服务数据；同构建独立 studio.html 隔离原 CSS；原专用控件与即时表单保留。后端仅在 IO/宿主边界调整，保留原解析和执行语义。
- 关键事实：原分组/子流程由几何识别成员，部分按位置排序；原运行 Toolbar 有 create/update，不能沿用旧草稿不保存限制；原共享浏览器不能强制变成每次独立会话。KernelEventBroker 覆盖快照不能作为工作流日志队列。旧草稿离开握手需重新接入。
- 交付顺序：来源/行为基准 → 原编辑器及真实保存，同时提前做原引擎真实运行/单步/停止探路 → 全部核心执行 → 拾取/录制/Debug → 完整对照与正式包验收。
- 正文只维护既有[规格](../../docs/superpowers/specs/2026-09-13-studio-webrpa-source-migration-design.md)和[计划](../../docs/superpowers/plans/2026-09-13-studio-webrpa-source-migration-implementation.md)，更新决策/状态和入口索引；旧自定义 IR 取舍在架构索引标注替代。
- 独立复核后修正：globalConfigStore 必须保留自动保存/副本/快捷键/autoCloseBrowser等行为配置；工作区不接受两次运行不等于禁止原图内部并行；revision/去重事务放在用例与仓储，不能下放 HTTP。
- 验证：本轮范围为文档，git diff --check 通过，8 份文档的 24 个本地链接全部可解析，核对当前空窗口和 proposed 状态一致；未运行业务测试，也未把清除基线测试记为迁入通过。
- 未验证：新共享会话 worker 实际兼容、原 UI 对照、录制/调试竞态及各平台正式运行。工程分层高置信，共享会话适配中置信；S1 必须有真实探路证据。
