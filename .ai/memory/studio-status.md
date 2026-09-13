# Studio 当前状态

- 日期：2026-09-13；状态：confirmed；来源：用户“先把现有代码都清除，然后再思考 WebRPA 迁入”及对应源码清理。
- 旧 Studio 前后端已清除，仅保留总览菜单和正式独立空窗口；不再有编辑、保存、执行、Debug、录制或拾取功能。
- 本轮不实施此前提出的 WebRPA 迁入架构，也不预置新的模型/API/执行器。下一步先重新讨论迁入。
- 主应用和其他领域保留；通用浏览器管理、进程清理和工作区继续可用。
- 旧代码归档 `codex/studio-before-removal-20260913@4eda207`，M6 未完成试验归档 `codex/m6-unfinished-checkpoint-20260913@59ae8d4`。
- 0005–0008 历史 Alembic 迁移及旧数据库/产物数据保留；没有旧业务兼容执行器。
- 本文优先于历史 project-context 中有关 WebRPA 重写方式、M1–M6 能力和实施状态的描述。迁入目标仍为原 UI/交互/业务逻辑复刻，具体实施尚未启动。
- [清除记录](../../docs/migration/studio-removal.md)包含验证与平台边界。
