# 浏览器配置管理验收记录

- 日期：2026-09-12
- 状态：in progress（后端打包与 sidecar smoke 已确认；桌面页面验收等待任务 11）
- 范围：浏览器配置 CRUD、默认/已安装内核、冻结 worker、跨平台打包资源与已有真实公开内核证据。

## 当前结论

macOS arm64 上的源码 sidecar 和 PyInstaller sidecar 均通过隔离 smoke。冻结进程在 `PYTHONTZPATH=''` 时成功创建并重载 `timezone=Asia/Shanghai` 的配置，修复前同一输入返回 `422 VALIDATION_ERROR`，因此 `tzdata` 缺失问题已经由真实 frozen 运行验证闭环。smoke 的数据目录、数据库、内核扫描 fixture 和 worker cache 都位于系统临时目录，结束后删除，不读取或写入 AutoFlow 用户数据。

PyInstaller 产物已确认包含：Alembic 配置、迁移脚本、SQLAlchemy SQLite dialect、`tzdata/zoneinfo/Asia/Shanghai`、CloakBrowser 运行时子模块、CloakBrowser/keyring/tzdata metadata、macOS 与 Windows keyring 系统后端，以及冻结进程的 kernel worker 入口。

## 自动 smoke 覆盖

`scripts/smoke-browser-management.mjs` 支持源码模式和 `--executable <path>` 冻结模式，执行以下闭环：

1. 在临时 worker cache 中提供本地 `CLOAKBROWSER_BINARY_PATH`，调用真实 `--kernel-worker` download 协议，验证 CloakBrowser 动态导入、进度消息和完成结果；不访问网络、不下载内核。
2. 在临时 `data/kernels` 中创建当前平台目录结构，启动真实随机端口 sidecar，并使用实例 token 调用 HTTP API。
3. 验证已安装公开内核扫描、默认内核 revision 设置与清除。
4. 创建包含 locale、IANA timezone、viewport、humanize 和高级参数的公开版配置；复制后验证新 fingerprint seed；更新后重新 GET 验证持久化；最后删除两个配置。

此 smoke 使用 `proxyMode=none`，没有注入生产 fixture endpoint。代理与代理池选择仍由独立 API/领域测试覆盖；最终 Electron 流程如需代理资源，只允许测试进程写入临时数据库。

## 本机证据

| 环境 | 验证 | 结果 | 证据 |
| --- | --- | --- | --- |
| macOS 26.4.1 arm64，Python 3.11.13 | 源码 browser-management smoke | 通过 | `node scripts/smoke-browser-management.mjs` |
| macOS 26.4.1 arm64，PyInstaller 6.22.2 | frozen backend 构建 | 通过 | `npm run backend:build` |
| macOS 26.4.1 arm64，frozen sidecar | `PYTHONTZPATH=''`、worker、installed/default、profile CRUD | 通过 | `node scripts/smoke-browser-management.mjs --executable apps/backend/dist/autoflow-backend/autoflow-backend` |
| macOS 26.4.1 arm64，frozen sidecar | 真实公开内核下载和安装 | 通过 | CloakBrowser wrapper 0.5.9；public `145.0.7632.109.2`；archive 147,384,149 bytes；安装目录 367,270,152 bytes；operation `63e1732c-8b4e-4797-90e6-a9f1979c92dc` completed |
| macOS 26.4.1 arm64，frozen sidecar | 真实下载取消和进程清理 | 通过 | public `142.0.7444.175`；operation `4c1f49ce-eaca-44aa-9890-e8176e3df6b7` cancelled；观察到 1 个 worker；PID 已退出、staging 已删除、health 仍为 ok |

真实下载证据来自隔离目录 `/var/folders/8g/sq3srr71063c083rpkd32k380000gn/T/autoflow-real-kernel-9lctnbha` 中的 `validation-evidence.json`、`cancellation-evidence.json` 和 `timezone-before-evidence.json`。没有重复下载公开内核。

## 平台与能力矩阵

| 项目 | macOS arm64 本机 | macOS Intel CI | Windows 2022 CI |
| --- | --- | --- | --- |
| 源码 sidecar smoke | 通过 | 待 CI | 待 CI |
| frozen backend build | 通过 | 待 CI | 待 CI |
| frozen worker + browser-management smoke | 通过 | 待 CI | 待 CI |
| packaged Electron 生命周期 | 等待任务 11 | 待 CI | 待 CI |
| 浏览器管理 UI 截图/视觉对比 | 等待任务 11 | 不适用 | 不适用 |

CI 保留 `windows-2022`、`macos-15-intel` 和 `macos-15` 三个平台，并新增源码与 packaged browser-management smoke。CI 的 worker smoke 使用本地 binary override，不依赖远端 provider 响应；不能在 CI 实际完成前把 macOS Intel 或 Windows 标为通过。

## 未完成与限制

- CloakBrowser License 未提供；授权版 License 校验、下载和安装为未验证，不能从 catalog 元数据推断商业下载成功。
- Electron 页面接入、未保存确认、reveal、服务重连、退出清理、截图对比、`npm run package:dir` 及最终全量命令等待任务 11 合入后执行。
- 本机没有 Windows 实机结果；Windows 结论只接受对应 CI runner 或真实 Windows 环境的证据。
