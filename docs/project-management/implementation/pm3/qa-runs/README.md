# PM3 项目运行 QA

状态：proposed（2026-09-15）。执行证据以每次 `run-*` 目录中的 `result.json`、截图哈希和真实 HTTP/SQLite 事实为准；本文件不表示场景已经通过。

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

普通停止在真实运行中及时完成，未稳定进入 `stopping`/`reconciling` 的强制停止准入窗口；因此强制停止没有执行，也没有记录为通过。

`force-stop` 使用真实 CloakBrowser 慢导航工作流再次验证：普通停止后批次从 0–1400ms 保持 `stopping` revision 3，在 1600ms 已成为 `stopped` revision 4，远早于 30 秒宽限。没有使用 SIGSTOP、数据库改写或调度器替身，因此无法合法显示并提交强停确认框；精确时间线与截图见 `run-dTjriF`，该场景未记为通过。

Failure 场景已在重建当前 renderer 后通过：真实任务以 `WORKFLOW_NODE_TIMEOUT` 失败，后端返回 `available image/png`，UI 打开了失败截图预览。`run-hB8hGK` 等较早目录使用旧 renderer，只作为 stale-build 失败证据，不代表当前源码结论；当前通过证据见 `run-aLealp`。

尚未接入真实 UI 动作的场景会明确失败，不会写入伪造的通过结果。
