# Studio 当前状态

- 日期：2026-09-13；状态：前端优先迁入方向 confirmed，前端源码与 Mock 基线 implemented。
- 用户已授权先迁 WebRPA 的 UI、交互、Store、请求、事件/SSE，接口允许 Mock。此前“仅空窗口、迁入未开始”和“全量前端必须后于 R1 真运行”的描述 superseded。
- `renderer/domains/workflows` 迁入冻结版 `WebRPA@5ccb900e8dcf1530aae66f676d87593c416c7ebb` 的编辑器调用闭包；原布局/算法、流程图/模块条、配置面板、记录/Debug/日志组件保留。主题为 AutoFlow 暖灰米白黏土棕。
- 正式 Electron 单窗口复用，独立 studio.html 同 renderer 构建；主窗口 CSS 隔离。普通关闭有未保存内容确认；退出先处理 Studio，再关闭 sidecar。
- API 通过 workflows/api/transport.ts，事件通过 HTTP 命令 + SSE，复用共享 SSE parser；原事件名/payload 投影保留。没有恢复旧 M1–M6 执行器、没有新增真实工作流 API 或数据库迁移。
- Mock 文档/配置/资源使用浏览器本地存储；事件/运行/录制会话为内存协议夹具。虚拟目录不是后端工作区。不得宣称真实浏览器、AI、系统工具或全平台验收完成。
- 来源清单、旧代码类型债务和适配边界在 workflows/SOURCE.md；实测和未验收项见[前端迁入验收](../../docs/migration/studio-frontend-mock-validation.md)。
- 企业协作、发布/版本、Windows 桌面控制入口排除；其余外部系统能力的配置表单保留，服务调用尚待后端逐项接入。
- 原详细 R0–R8 路线仍用于真实迁入验收，不能以 Mock 通过勾选真实执行、清理或工作区隔离。
- 旧源码归档 `codex/studio-before-removal-20260913@4eda207`；M6 试验归档 `codex/m6-unfinished-checkpoint-20260913@59ae8d4`。0005–0008 历史迁移/数据保留。用户其他领域的未提交改动未覆盖。
