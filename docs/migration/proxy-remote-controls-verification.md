# ProxyPanel 位置与轮换验收

- 日期：2026-09-12
- 状态：confirmed（实现、自动测试和实网只读验收）；真实写入验收 pending。
- 来源：用户批准的设计/实施计划、官方 Developers/Documentation、当前账号授权只读请求、隔离数据库测试和 CUA。
- 实施分支：`codex/proxy-remote-controls`，从 `codex/architecture-baseline@17e0870` 开始。

## 交付行为

现有详情「位置与轮换」已接入真实状态、地点目录和轮换计划读取；提供即时换 IP、地点切换、计划保存/关闭四种命令。目录以 location_id 合并城市别名，显示容量和覆盖范围；只在确认后提交。轮换支持官方三种 mode，以分钟为单位，采用当前官网显示的 5/10/30/60 分钟；编辑不触发远程写入，离开未保存表单会提示。

SQLite `0004_proxy_remote_controls` 在原有 operation 表增补幂等与快照字段，唯一约束实现同键去重和同代理排他。受监管 asyncio 任务只发送一次写请求，然后通过实际 GET 结果确认。远程写入被受理与结果已确认分开呈现，120 秒预算后未知结果不自动重发。重启把未发送 queued 结束为 failed、可能已发送 running 转为 unknown；重新核实只读。用户必须明确处理 unknown 才能再次变更。

完成后只合并远程字段，保留别名和本地启用状态、失效旧健康结果，刷新详情/列表和浏览器代理选项缓存。连接替换后的旧结果不能回写。HTTP 和任务记录不暴露 API Key 或数据面密码，前端只获得安全摘要。

## 自动验证

在 macOS arm64 的隔离 worktree 执行：

| 验证 | 结果 |
| --- | --- |
| `pytest -q` | 365 passed，2 条既有 Starlette/httpx 弃用提示 |
| `ruff check src tests` | 通过 |
| `mypy src` | 114 源文件通过 |
| `npm test` | 46 文件 / 274 tests 通过 |
| 最后 hook 调整后的代理组件/页面复验 | 2 文件 / 16 tests 通过 |
| `npm run typecheck`、`npm run lint`、`npm run build` | 通过 |
| `npm run openapi:check` | 通过；类型由实际路由生成 |
| `npm run test:scripts` | 9 tests 通过 |
| `npm run backend:build` | 通过 |
| `npm run smoke:sidecar` | 源码服务启动/健康/退出通过 |
| `npm run smoke:sidecar -- --executable apps/backend/dist/autoflow-backend/autoflow-backend` | 冻结服务实际启动/迁移/健康/退出通过 |
| `git diff --check` | 通过 |

新增 24 项后端检查，包括官方模式/单位、地点别名去重、四种固定路径和方法、真实临时 SQLite 生命周期、同键重放/不同请求冲突、并发登记、实际条件禁止写入、容量复核、429、网络未知结果、受理后读取失败、只读核实、连接替换和关机恢复。非空计划、写入结果使用明确标识的合成 Provider；这些测试不是实网成功证据。迁移验证覆盖新库、浏览器 0001、代理/模型两个 0002 起点，并检查旧记录及外键保留。

## 实网只读与 UI

本轮未向真实代理发送 POST rotate/relocate、PUT/DELETE schedule。

- 当前账号先前读取的 4 条 active 代理均为 bound=false / rotation_available=false / not_bound；最终 CUA 抽样仍显示该原因。实现没有调用 start、购买、续费或修改凭据。
- 真实 GET 目录观察到 243 条城市记录、125 个不同目标 ID。数量不写死；共享目标容量不累加。CUA 搜索城市别名只显示合并后的目标，能显示运营商、容量及完整覆盖城市。
- GET 空计划 `schedule=null` 实读成功，UI 显示尚未设置。非空计划尚未实采，未知响应形状会显示错误而非伪造关闭状态。
- CUA 查看地点切换确认（未提交），默认焦点是取消；选择周期后离开，会显示未保存确认；放弃草稿后返回列表。检查了实际截图，未发现截断或额外侧栏。
- 实网即时 rotate 因 not_bound 仍不能使用。地点和计划实现依据各自条件开放，是否被此账号接受需写入验收，不从 rotation_available=false 泛化结论。

## 剩余验收

按已批准计划，需要用户指定允许短暂中断的真实代理，再测试地点切换、计划保存/关闭，并在 rotate 条件允许时测试换 IP；逐项核对真实读回，不能只依据 HTTP 2xx 宣布成功。不承诺切换到城市别名或恢复到同一个出口 IP。

Windows、macOS Intel 本轮未运行实机或 CI，不标记为通过；实现未新增业务层平台分支或外部调度依赖。

## baseline 接入与运行状态

基于 baseline 新增的 `a0fde8a` 模型目录调整无冲突 rebase 后，再次通过前端全量 274 tests、TypeScript、ESLint 与 OpenAPI 检查；后端未受该模型 UI 提交影响。其他任务的自动化草稿、模型设计记录和未提交文件不纳入本次提交。

实现提交 `54e9729` 已 fast-forward 接入 baseline。主应用初次检查时有未保存的「新建浏览器配置」表单，暂缓重启；随后确认用户已保存配置、表单关闭，再通过设置中的「重启服务」加载新实现。重启后本地服务正常，实际用户库已迁移至 `0004_proxy_remote_controls`，已保存的浏览器配置保留。主应用已打开代理详情的新「位置与轮换」页签。最终真实写入仍待指定测试目标。
