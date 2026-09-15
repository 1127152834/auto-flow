# PM3 项目运行 QA

状态：confirmed（2026-09-15）。执行证据以每次 `run-*` 目录中的 `result.json`、截图哈希和真实 HTTP/SQLite 事实为准；历史失败仍保留，但不覆盖后续当前版本的通过结论。

脚本仅使用临时目录下带 `.pm3-project-management-qa.json` 标记的工具 workspace。已安装的公开版 CloakBrowser 内核以只读来源复制到该 workspace。工作流文档和浏览器配置分别通过 `WorkflowService` 与 `ProfileService` 准备，并在结果中明确标记为 fixture；项目和自动化必须通过 Electron UI 创建。

场景分开运行，先执行成功链：

```sh
node scripts/qa-project-management-pm3.mjs --scenario success
node scripts/qa-project-management-pm3.mjs --prepare-only --scenario success
node scripts/qa-project-management-pm3.mjs --manual --scenario success
```

- `success`：UI 创建项目和自动化，启动两个真实浏览器任务，检查批次、任务、日志、输入与输出。
- `failure`：UI 创建点击目标不存在且节点超时为 1 秒的自动化，检查失败事实、真实 PNG 附件与预览。
- `stop`：使用受控慢响应页面，UI 普通停止批次，检查全部任务取消与临时浏览器目录清理。
- `recovery`：仅在服务已接受启动后丢弃响应及首次原键查询，检查 UI 使用原 Idempotency-Key 恢复且只有一个批次。
- `restart`：完成批次后关闭并重启 Electron/后端，通过重启后的真实服务读取持久批次，并确认终态网页动作没有重放。
- `isolation`：启动两个独立且各自带标记的 workspace，分别通过 UI 创建项目、自动化和批次，检查 workspace、项目与批次身份互不相同。

普通停止的直接证据为 `run-35V8u7`。自然慢导航会在约 1.6 秒内完成清理，无法稳定进入 30 秒强停准入；`run-sjkcAl` 保留为该夹具限制的失败证据。

强制停止的当前 HEAD 证据为 `uuid-runs-1789458500247`。专项工具只在当前隔离 Electron 的后代树中选择唯一、命令匹配的真实 `workflow_worker`，记录 PID 与进程开始时间后发送 `SIGSTOP`，再由 UI 提交普通停止、等待 31 秒、输入固定短语并提交真实强停。结果同时确认旧 worker 的同一 PID/开始时间已退出、旧执行代次不再提交、资源完成清理，并能继续启动后续真实失败批次。该故障注入明确标记为 `synthetic-os-process-pause`；Electron、FastAPI、SQLite、CloakBrowser、停止接口和终态均为真实路径。

可重复执行当前强停链：

```sh
npm run build
node scripts/qa-project-uuid-flow.mjs --scenario runs
```

Failure 场景已在重建当前 renderer 后通过：真实任务以 `WORKFLOW_NODE_TIMEOUT` 失败，后端返回 `available image/png`，UI 打开了失败截图预览。`run-hB8hGK` 等较早目录使用旧 renderer，只作为 stale-build 失败证据，不代表当前源码结论；当前通过证据见 `run-aLealp`。

尚未接入真实 UI 动作的场景会明确失败，不会写入伪造的通过结果。
