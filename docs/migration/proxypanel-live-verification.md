# ProxyPanel 真实代理链路验收

- 日期：2026-09-12
- 状态：confirmed；列表、凭据和 SOCKS5 实网链路通过。HTTP 实网未通过，远程管理写操作未实现。
- 来源：用户要求补齐真实代理能力；[官方 Developers](https://proxypanel.io/developers)、[连接说明](https://proxypanel.io/docs)、授权只读响应与本机隔离测试。
- 工作区：`../autoflow-proxy-live`，分支 `codex/proxy-live`，起点 `c7c3021`。使用隔离 SQLite；未改动原应用的代理、浏览器配置或账号凭据。

## 根因与修复

旧 Provider 在 Key 验证通过后仍无条件抛出 `PROXYPANEL_SCHEMA_UNSUPPORTED`，列表和数据面凭据没有真正接通；失败连接的刷新按钮又被禁用，形成无法恢复的界面。

现在解析实际 `GET /proxies` 返回的 `{proxies:[...]}`，完整校验后一次性投影；重复 ID、非法字段或未知分页包装拒绝导入，保留本地数据。本地别名和资源引用继续保留。连接失败后可以重试刷新，成功后清除旧错误。

复制或健康检测时调用 `GET /proxies/{id}/credentials`，校验端点和连接版本后在内存中使用用户名/密码。API Key 继续保存在系统凭据库；数据面密码不进入 renderer/SQLite，也不额外缓存到凭据库。主进程取密通道维持独立 token、禁止 Origin 和 no-store；复制仍由 Electron main 写剪贴板。

检测支持显式 HTTP 或 SOCKS5，双协议时 UI 默认 SOCKS5；显式 HTTP 失败不会悄悄回退。健康状态只代表最近一次检测，不承诺两个协议均可用。过期/缺失/stale 投影不会作为可用浏览器固定代理选项，也不能继续获取凭据。详情显示实际 expires_at，不推算续费或即将到期数量。

## 真实检查结果

| 检查 | 结果 |
| --- | --- |
| 官方列表与账户网页数量 | 6 条一致，4 active、2 expired；未观察到分页 |
| 列表映射 | 名称、状态、运营商、城市、出口 IP、分协议端点和到期时间正确显示 |
| 凭据读取 | HTTP 200；独立字段与返回 URL 的协议/端点/认证值一致；没有保留原始 URL |
| SOCKS5 → 固定 HTTPS 出口检测 | 服务用例实网通过；CUA 界面再次通过，显示健康、约 5512 ms |
| HTTP → 固定 HTTPS 出口检测 | 两条 active 代理超时；其中独立 trace 确认 TCP 已连接，CONNECT 已发送，等待响应头超时。无法仅据此区分供应商端与当前网络原因 |
| CUA 隔离预览 | 原失败连接可刷新，成功显示已连接和 6 条记录，旧错误消失；两条 expired 的检测按钮禁用；详情协议默认 SOCKS5，真实检测成功 |
| 凭据复制 | 后端 host-only 契约和主进程 IPC 自动测试通过；浏览器预览无 Electron IPC，未进行真实密码剪贴板操作 |

未做实际换 IP、切地点、重置密码、修改轮换/白名单、购买或续费。只读观察的地点/轮换/白名单/余额接口不能据此启用相关写操作。位置与轮换、用量等现有占位能力仍返回明确不可用，不声称完整远程控制已接入。

本次打通代理管理、凭据、检测及浏览器配置可选项；尚未实现的浏览器启动/自动化执行链路不属于已验收范围。

## 自动验证

接上 baseline 的语言/时区修复 f37a5e1 后，在隔离分支最终实现上执行：

| 命令 | 结果 |
| --- | --- |
| uv run --directory apps/backend pytest -q | 334 passed；2 条既有 Starlette/httpx 弃用提示 |
| uv run --directory apps/backend ruff check src tests | 通过 |
| uv run --directory apps/backend mypy src | 108 个源码文件通过 |
| npm test | 268 passed / 44 files |
| npm run test:scripts | 9 passed |
| npm run typecheck / npm run lint / npm run build | 通过 |
| npm run openapi:generate / npm run openapi:check | 通过，内部取密路由未进入公开契约 |

脱敏 fixture 来源见 `apps/backend/tests/fixtures/proxypanel/README.md`。回归额外覆盖连接替换期间凭据晚返回、端点漂移、过期代理、协议选择、完整同步保留本地名称、失败重试恢复。没有数据库迁移或新依赖；Windows/macOS Intel 本轮未运行，真实凭据与网络验证在 macOS 本机完成。
