# Studio 当前状态

- 日期：2026-09-13；状态：源码清除及用户迁入方向 confirmed，具体迁入安排 proposed。
- 旧 Studio 前后端已在 `25273d5` 清除，仅保留总览菜单和正式独立空窗口；当前没有编辑、保存、执行、Debug、录制或拾取功能。
- 用户要求 WebRPA 迁入贴合 AutoFlow，并进一步要求“详细里程碑、方便测试、稳步前行”。当前计划细化为 R0–R8，含 60 组编号验收和统一台账，全部尚未实施/验收；没有新增业务源码、API、依赖或数据库迁移。
- 产品以冻结 WebRPA 原 UI/交互/执行语义为准，按 AutoFlow 领域目录、分层、共享 API/OpenAPI、工作区存储、Profile 和进程监管落位。具体设计见[规格](../../docs/superpowers/specs/2026-09-13-studio-webrpa-source-migration-design.md)与[实施安排](../../docs/superpowers/plans/2026-09-13-studio-webrpa-source-migration-implementation.md)。
- 原“整块 webrpa 目录 + 默认 Socket.IO”建议已 superseded；新方案保留原编辑算法/专用控件，使用领域 Store 和 HTTP/SSE 适配。原组几何存在执行语义，不能当作纯显示字段删除。
- 主应用和其他领域保留；通用浏览器管理、进程清理和工作区继续可用。旧 Studio 的草稿离开握手和连接权限已删除，迁入时需要重新接入。
- 旧代码归档 `codex/studio-before-removal-20260913@4eda207`，M6 未完成试验归档 `codex/m6-unfinished-checkpoint-20260913@59ae8d4`。
- 0005–0008 历史 Alembic 迁移及旧数据库/产物数据保留；没有旧业务兼容执行器。
- 本文优先于历史 project-context 中有关 WebRPA 重写方式、M1–M6 能力和实施状态的描述。迁入尚未开始；架构判断高置信，受管共享会话中置信，必须早期真实验证。
- [迁入验收台账](../../docs/migration/studio-webrpa-migration-validation.md)单独记录原版证据和各平台状态，不用旧 M1–M6 测试勾选。R1即交付原编辑/真实保存/原引擎执行/断点单步停止，并验证事件、离开、清理、迁移和实际包入口；后续细分编辑、网页、控制流/通用核心、拾取、录制、Debug及全量对照。
- [清除记录](../../docs/migration/studio-removal.md)包含已完成清除的验证与平台边界，不是新迁入的验收结果。
