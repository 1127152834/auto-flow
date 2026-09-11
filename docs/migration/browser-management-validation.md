# 浏览器配置管理验收记录

- 日期：2026-09-12
- 状态：confirmed（本机自动与人工验收完成；macOS Intel / Windows 结果等待 CI）
- 范围：浏览器配置 CRUD、默认/已安装内核、冻结 worker、跨平台打包资源与已有真实公开内核证据。

## 当前结论

macOS arm64 上的源码 sidecar、PyInstaller sidecar、开发态 Electron 和 packaged Electron 均通过隔离 smoke。冻结进程在 `PYTHONTZPATH=''` 时成功创建并重载 `timezone=Asia/Shanghai` 的配置，修复前同一输入返回 `422 VALIDATION_ERROR`，因此 `tzdata` 缺失问题已经由真实 frozen 运行验证闭环。smoke 的 userData、数据库、内核扫描 fixture 和 worker cache 都位于系统临时目录，结束后删除，不读取或写入 AutoFlow 用户数据。

PyInstaller 产物已确认包含：Alembic 配置、迁移脚本、SQLAlchemy SQLite dialect、`tzdata/zoneinfo/Asia/Shanghai`、CloakBrowser 运行时子模块、CloakBrowser/keyring/tzdata metadata、macOS 与 Windows keyring 系统后端，以及冻结进程的 kernel worker 入口。

## 自动 smoke 覆盖

`scripts/smoke-browser-management.mjs` 支持源码模式和 `--executable <path>` 冻结模式，执行以下闭环：

1. 在临时 worker cache 中提供本地 `CLOAKBROWSER_BINARY_PATH`，调用真实 `--kernel-worker` download 协议，验证 CloakBrowser 动态导入、进度消息和完成结果；不访问网络、不下载内核。
2. 在临时 `data/kernels` 中创建当前平台目录结构，启动真实随机端口 sidecar，并使用实例 token 调用 HTTP API。
3. 验证已安装公开内核扫描、默认内核 revision 设置与清除。
4. 创建包含 locale、IANA timezone、viewport、humanize 和高级参数的公开版配置；复制后验证新 fingerprint seed；更新后重新 GET 验证持久化；最后删除两个配置。

此 smoke 使用 `proxyMode=none`，没有注入生产 fixture endpoint。代理与代理池选择仍由独立 API/领域测试覆盖；最终 Electron 流程如需代理资源，只允许测试进程写入临时数据库。

`scripts/smoke-browser-management-desktop.mjs` 同样支持开发态和 `--executable <desktop-path>` packaged 模式。它通过真实 Electron renderer 和 sidecar 完成列表进入、新建、内核管理打开/关闭、创建、完整页面 reload、编辑、重新生成指纹、复制和删除；每一步再用实例 token 读取 API，核对持久化值与 fingerprint seed。列表、配置表单和内核管理的 document、容器与可见控件分别在 1280px 和 1024px viewport 下检查横向边界。

## 本机证据

| 环境 | 验证 | 结果 | 证据 |
| --- | --- | --- | --- |
| macOS 26.4.1 arm64，Python 3.11.13 | 源码 browser-management smoke | 通过 | `node scripts/smoke-browser-management.mjs` |
| macOS 26.4.1 arm64，PyInstaller 6.22.2 | frozen backend 构建 | 通过 | `npm run backend:build` |
| macOS 26.4.1 arm64，frozen sidecar | `PYTHONTZPATH=''`、worker、installed/default、profile CRUD | 通过 | `node scripts/smoke-browser-management.mjs --executable apps/backend/dist/autoflow-backend/autoflow-backend` |
| macOS 26.4.1 arm64，Electron 41.10.3 | 开发态真实页面 CRUD、reload、fingerprint、嵌套内核弹窗、1280/1024 边界 | 通过 | `node scripts/smoke-browser-management-desktop.mjs` |
| macOS 26.4.1 arm64，packaged Electron | 包内 frozen sidecar 与同一桌面闭环 | 通过 | `node scripts/smoke-browser-management-desktop.mjs --executable apps/desktop/dist/mac-arm64/AutoFlow.app/Contents/MacOS/AutoFlow` |
| macOS 26.4.1 arm64，electron-builder 26.15.3 | unpacked 应用目录 | 通过 | `npm run package:dir` |
| macOS 26.4.1 arm64，frozen sidecar | 真实公开内核下载和安装 | 通过 | CloakBrowser wrapper 0.5.9；public `145.0.7632.109.2`；archive 147,384,149 bytes；安装目录 367,270,152 bytes；operation `63e1732c-8b4e-4797-90e6-a9f1979c92dc` completed |
| macOS 26.4.1 arm64，frozen sidecar | 真实下载取消和进程清理 | 通过 | public `142.0.7444.175`；operation `4c1f49ce-eaca-44aa-9890-e8176e3df6b7` cancelled；观察到 1 个 worker；PID 已退出、staging 已删除、health 仍为 ok |
| macOS 26.4.1 arm64，真实 Electron + CUA | 页面、四标签表单、嵌套焦点/草稿、真实内核选择、reload、Finder reveal、License nowrap | 通过 | [人工验收记录](../../.ai/sessions/2026-09-12-browser-management-ui-validation.md)；[列表](browser-management-screenshots/profiles.png)、[环境表单](browser-management-screenshots/profile-environment.png)、[内核管理](browser-management-screenshots/kernel-manager.png) |

真实下载证据来自隔离目录 `/var/folders/8g/sq3srr71063c083rpkd32k380000gn/T/autoflow-real-kernel-9lctnbha` 中的 `validation-evidence.json`、`cancellation-evidence.json` 和 `timezone-before-evidence.json`。没有重复下载公开内核。

## 平台与能力矩阵

| 项目 | macOS arm64 本机 | macOS Intel CI | Windows 2022 CI |
| --- | --- | --- | --- |
| 源码 sidecar smoke | 通过 | 待 CI | 待 CI |
| frozen backend build | 通过 | 待 CI | 待 CI |
| frozen worker + browser-management smoke | 通过 | 待 CI | 待 CI |
| packaged Electron 生命周期与 CRUD | 通过 | 待 CI | 待 CI |
| 浏览器管理 UI 人工验收与截图 | 通过 | 不适用 | 不适用 |

CI 保留 `windows-2022`、`macos-15-intel` 和 `macos-15` 三个平台，并新增源码与 packaged browser-management sidecar/Electron smoke。CI 的 worker smoke 使用本地 binary override，不依赖远端 provider 响应；不能在 CI 实际完成前把 macOS Intel 或 Windows 标为通过。

## 最终本机回归

- Backend：ruff、mypy 通过；pytest `311 passed`，另有 2 个来自 Starlette/httpx 和 anyio 兼容别名的上游弃用提示。
- Desktop：Vitest `45 files / 259 tests passed`；typecheck、lint、build 通过。build 仅报告第三方 zod 注释位置提示。
- Repository：OpenAPI check、script tests `9 passed`、development desktop smoke、source browser sidecar smoke、development browser Electron smoke 全部通过。
- Package：backend build、`package:dir`、包内 sidecar health/lifecycle、包内 browser sidecar smoke、packaged Electron browser smoke 全部通过。目录包使用默认图标且本机没有有效 Developer ID，因此没有代码签名；本轮没有把未签名目录包宣称为可发布安装器。

## 未完成与限制

- CloakBrowser License 未提供；授权版 License 校验、下载和安装为未验证，不能从 catalog 元数据推断商业下载成功。
- macOS Intel 和 Windows 的新 CI 步骤尚未在当前本机会话运行，状态保持“待 CI”。
- 本机没有 Windows 实机结果；Windows 结论只接受对应 CI runner 或真实 Windows 环境的证据。
