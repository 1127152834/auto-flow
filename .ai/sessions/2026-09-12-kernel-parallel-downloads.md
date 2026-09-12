# 内核并行下载与双列卡片实施记录

- 日期：2026-09-12
- 状态：confirmed（本机验证完成；Windows 实机待验证）
- 来源：用户要求、旧项目源码、当前改动及下列验证命令。
- 范围：浏览器配置中的 CloakBrowser 管理弹窗、下载 worker 和相关测试；不新增 API、独立页面、依赖或数据迁移。

## 结果

- 对照旧项目 `autoflow-desktop/src/renderer/pages/KernelPage.tsx` 的按版本 pending 集合，以及 `backend/src/autoflow/kernel_manager.py` 的按 edition/version 任务管理。不同安装目标可并行下载；同一 edition/version 跨 Stable/Preview 共用目录，因此仍禁止重复任务。
- 前端每个目标有独立提交中/启动错误状态，每个 operation 有独立取消状态；乱序响应不会清除其他任务的状态。筛选或目录离线后保留活动任务的取消入口。
- 后端沿用独立工作进程和 staging：任务持有目标锁及 owner lock；发布使用短维护锁。恢复获得 owner 后重读数据库，避免误清理仍活跃或已完成的任务。实际版本碰撞复用完整安装，关闭时并行回收任务。
- 内核列表使用双列卡片，窄窗口单列；平台名称使用后端返回值，平台路径判断留在适配器。
- 更新原型交互说明和历史实施计划，旧“全局单安装 worker”约束标为 superseded；决策见 `.ai/decisions/2026-09-12-kernel-parallel-downloads.md`。

## 验证

| 命令/检查 | 结果 |
| --- | --- |
| `uv run --project apps/backend pytest -q apps/backend/tests` | 374 passed；两条既有依赖弃用警告 |
| worker integration + kernel service unit 测试 | 42 passed |
| `uv run --project apps/backend mypy apps/backend/src` | 114 source files 通过 |
| 本次 6 个后端文件 `ruff check` | 通过 |
| 内核前端组件测试 | 6 files / 29 tests 通过 |
| `npm test` | 47 files / 278 tests 通过 |
| `npm run typecheck` / `npm run lint` / `npm run build` | 通过；构建仍有第三方 zod 注释提示 |
| `npm run test:scripts` | 9 tests 通过 |
| `node scripts/smoke-browser-management.mjs` | source / macOS arm64 通过 |
| `node scripts/smoke-browser-management-desktop.mjs` | Electron + 真实 sidecar 通过 |
| `npm run backend:build` | PyInstaller macOS arm64 构建通过 |
| `node scripts/smoke-browser-management.mjs --executable apps/backend/dist/autoflow-backend/autoflow-backend` | frozen sidecar / macOS arm64 通过 |

并发测试覆盖两个真实受控 worker 同时活跃、单独取消、跨 manager/channel 防重复、恢复二次读取、实际版本碰撞、三个忽略 TERM 的 worker 并行关闭及关闭后拒绝接单。平台参数测试覆盖 Windows x64 和 macOS Intel/arm64 的可执行产物路径；不访问外部下载服务。

桌面 smoke 使用独立临时 userData 和两个测试内核文件，保留原有用户工作区。新增几何断言验证 1280/1024 宽度双列、640 宽度单列及无横向溢出；实际截图也已检查。测试文件不被当作真实可启动浏览器。

## 独立复查

由独立 gpt-5.6-sol 审查并发、平台路径和 UI 状态。发现取消错误共用提示的问题后，改为按 operation ID 记录并展示在对应卡片，包括筛选后保留的活动卡；重试只清除自己的错误，终态清理且忽略晚到失败。新增 A 取消失败、B 取消成功、筛选、重试 A 的回归测试已通过。

最终复查无剩余阻塞性或重要正确性问题，置信度高。审查者独立复跑后端定向 42 项、前端相关组件 20 项及 diff-check 均通过。后端提交为 `236a677`。

## 限制与现有问题

- 当前机器为 macOS arm64；Windows x64/macOS Intel 未做实机验证，本次没有重新执行外网大文件下载。
- 全 backend Ruff 仍有 45 个既有 import-order 问题；本次不修改其他模块。
- 主动退出时 Uvicorn 对存活 SSE 执行 drain timeout，仍打印既有 CancelledError；source/frozen smoke 均验证清理成功并以 0 退出。
- 当前用户正在使用的桌面窗口未被强制重启；已启动的 Python 服务需重启后加载本次后端修改。验收使用新启动的隔离实例。
- 保留模型、代理及 automation 的其他工作区改动，没有纳入本次提交。
