# 旧 Studio 清除完成

- 日期：2026-09-13；状态：confirmed。
- 用户最新范围：先清除现有代码，再思考 WebRPA 迁入；没有继续执行此前迁入计划。
- 基线 `826b7b3`；归档旧完整源码及两个未提交原型至 `codex/studio-before-removal-20260913@4eda20742ae39339b49d37c47e01d64ec12c2663`；M6 试验另有 `codex/m6-unfinished-checkpoint-20260913@59ae8d4`。
- 删除 112 个 tracked Studio 源码/测试/fixture/脚本文件及 2 个原型文件。原型删除前逐字节核验归档。保留空目录骨架、主应用、独立空窗口、其他领域及通用浏览器进程管理。
- 移除 workflow/inspection HTTP/SSE、执行/Debug/变量/定位模型与 worker、ORM/仓储、导出IPC/离开握手/Studio服务权限、前端编辑器和 hooks；更新 OpenAPI，卸载仅旧画布使用的 React Flow 依赖。
- 保留 0005–0008 历史迁移，逐文件核验 diff 为零。临时数据库验证旧五表及产物启动/关闭后保持原值；未操作用户实际数据。清理前记录的 173 个无关文件 SHA-256 全部一致，不把用户模型/UI改动放入本次提交。
- 后端 399 pytest、Ruff、mypy（124源码）通过；桌面 308测试（50文件）、TypeScript、ESLint通过；脚本/目录12项通过；OpenAPI/diff检查通过。
- renderer/main/preload、PyInstaller、Electron macOS arm64 目录包构建通过。检查冻结 PYZ 模块表无旧 workflow/inspection 业务模块。
- 真实 Electron 开发 URL、构建 HTML、目录包各5组：启动/旧API移除、空窗/复用/最小化恢复、关闭重开、只关主窗、正常退出清理通过。新脚本先修正异步关窗断言与退出前断开Node inspector，再完成三个入口通过。
- 独立复审未发现共享浏览器/模型/代理误删或旧业务依赖残留。旧功能测试被删除，对仍有消费者的通用进程监管保留8项回归。
- macOS Intel/Windows 未实测；目录包未作分发签名，无安装器验收。本轮没有启动 WebRPA 迁入。
- 正文/证据：[清除记录](../../docs/migration/studio-removal.md)；当前状态：[studio-status](../memory/studio-status.md)。
