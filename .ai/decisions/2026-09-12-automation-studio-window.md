# Automation Studio 独立窗口入口

- 日期：2026-09-12
- 状态：confirmed
- 来源：用户明确要求先在总览添加“工作流工作台”按钮，点击打开独立空窗口，随后再设计编排工作台。
- 实现：复用总览的“工作入口”卡片样式；renderer 经 `shared/automation-studio.ts`、preload 的固定 `openAutomationStudio()` IPC 调用主进程，窗口管理在 `main/ipc/automation-studio.ts`。
- 行为：首次打开独立非模态窗口，标题“工作流工作台 · AutoFlow”，内容为 `about:blank`。重复点击聚焦同一窗口，最小化时恢复；关闭后重新创建。主窗口关闭不会连带关闭工作台；macOS 激活应用时仍可重新打开主窗口。
- 边界：只允许主窗口的主 frame 发起开窗。空白工作台不加载主应用 preload，也不获得本地后端或凭据能力。未接入旧 automation 原型、编排器、工作流数据模型或后端。
- 验证：窗口/IPC 与总览交互 9 项测试通过，覆盖单窗口复用、最小化恢复、关闭重开、来源校验、加载失败回收、离线时入口可用与错误重试。类型检查、lint 和桌面构建通过。
- 实机验收：macOS arm64 启动正式工程的 Electron 构建，主应用连接真实 sidecar；通过 CUA 点击总览中的“工作流工作台”，确认出现独立标题窗口，并通过截图确认内容为空白。已保持窗口打开供用户查看。Windows 本轮未运行。
