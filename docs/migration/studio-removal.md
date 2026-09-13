# 旧 Studio 清除记录

日期：2026-09-13。用户指令：先清除现有代码，再思考 WebRPA 迁入。**本轮只清除旧 Studio，不实施迁入方案。**

## 清除边界

- 移除旧编排编辑器、动作表单、文档/变量/控制图模型、Store/hooks、运行/日志/结果、Debug、拾取和对应测试、fixture、烟测脚本。
- 移除后端工作流文档/运行/拾取 HTTP 与 SSE、错误处理、启动装配、worker CLI、执行器、仓储、文件适配器和 ORM。旧 API 返回 404，不保留空成功响应。
- 移除 Studio 专用的导出 IPC、未保存草稿离开握手、窗口转场状态及向 Studio 传送服务令牌的能力。主窗口的服务和设置接口继续使用来源校验。
- 移除只由旧画布使用的 `@xyflow/react` 及无其他依赖者的传递依赖。前端 OpenAPI 重新生成，不保留旧工作流 DTO。
- 早期 `renderer/domains/automation/studio` 未提交原型一并归档移除；不保留另一个旧原型入口。

保留主应用、浏览器 Profile/内核/代理/模型/设置/总览、鉴权、工作区管理、通用进程监管及 WebRPA 参考源码。保留“总览 → 工作流工作台”入口和独立空窗口，窗口复用、最小化恢复、关闭重开照常工作。窗口内不显示旧编排控件，不调用工作流服务。

保留 `domain/workflows`、`application/workflows` 和前端 `domains/workflows` 的空目录骨架。新模型、API、Store、执行器与迁入方式均不在本轮预置。

## 代码和数据保全

| 内容 | 保留位置与核验 |
| --- | --- |
| 旧完整 Studio、主工程及两个未提交原型文件 | `codex/studio-before-removal-20260913`，提交 `4eda20742ae39339b49d37c47e01d64ec12c2663`；原型字节和归档 blob 比对一致 |
| 上轮未完成 M6 试验 | `codex/m6-unfinished-checkpoint-20260913`，提交 `59ae8d4462b3384b321ba8c7ca8e913cbbb5774b`；不视为可用实现 |
| 数据库 schema 历史 | `0005_workflow_documents` 至 `0008_workflow_debug` 原文件保留且 diff 为零，head 仍为 `0008_workflow_debug` |
| 用户流程、运行、事件、产物与诊断 | 不连接用户数据库执行清除，不执行 downgrade/drop；保留原表及文件。临时数据库测试验证旧五表及产物在应用启动/关闭后逐值不变 |
| 无关工作树改动 | 清理前记录 173 个文件 SHA-256；清理后全部比对一致。模型管理和 UI 草稿不归入本次提交 |

保留历史迁移是为了让已有工作区继续打开，不意味着业务代码仍在运行。没有为旧流程建立兼容执行器或转换层。恢复旧代码应从上述 Git 检查点提取，不能覆盖当前用户工作树。

## 验证

| 检查 | 实际结果 |
| --- | --- |
| 后端 pytest | 399 passed；2 个依赖弃用警告 |
| Ruff / mypy | 通过；mypy 检查 124 个源码文件 |
| 前端 renderer 测试 | 39 个文件、243 项通过 |
| 完整桌面测试 / TypeScript / ESLint | 50 个文件、308 项测试通过；TypeScript、ESLint 通过 |
| OpenAPI / 脚本 / 目录检查 | OpenAPI 一致性通过；脚本及目录共 12 项通过；diff 检查通过 |
| renderer / main / preload 构建 | 通过；依赖 Zod 的已有注释提示不影响构建 |
| 真实 Electron 开发 URL / 构建 HTML | macOS arm64 两个入口各 5 组检查通过 |
| 冻结后端 / 正式 Electron 目录包 | PyInstaller 构建与冻结 sidecar smoke 通过；归档模块表不包含旧 workflow/inspection 模块；正式目录包构建及 5 组窗口检查通过 |

真实窗口检查使用独立临时 userData，并核验主应用/后端启动、旧 API 缺失、菜单打开空窗口、重复打开/最小化恢复、关闭重开、仅关主窗仍保持 Studio、正常退出回收 sidecar。证据位于 `studio-removal-qa/`。

可重复执行的窗口命令：`npm run smoke:studio`、`npm run smoke:studio -- --dev`、`npm run smoke:studio -- --executable apps/desktop/dist/mac-arm64/AutoFlow.app/Contents/MacOS/AutoFlow`。三个入口的 [构建 HTML](studio-removal-qa/built-html.json)、[开发 URL](studio-removal-qa/development-url.json)、[目录包](studio-removal-qa/packaged.json) 结果与截图均已保存。

验证脚本两次初测分别暴露原生窗口关闭异步、Node inspector 阻止退出的问题；已改为等待关闭完成、退出前断开测试调试连接，随后三个入口全部通过。没有通过修改应用退出行为来掩盖验证问题。

此轮移除 112 个已跟踪文件及 2 个已归档原型文件，另精简共享装配/契约并补数据保全和通用进程回归。删除模块的遗留 Python 字节码缓存一并清理，冻结产物已重建。目录包为本机内部验收产物，未做发布签名；未生成或验收分发安装器。

平台分别记录：本机 macOS arm64；macOS Intel 和 Windows 本轮未实测，不将模拟平台分支算作实机验收。旧 M1–M6 规格与验收是历史记录，不再描述当前应用能力。
