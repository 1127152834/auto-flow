# P2 持久计划任务验收索引

状态：macOS arm64 开发入口与目录包通过；macOS Intel、Windows 未实测。

- SQLite/Alembic `0018_scheduled_tasks` 保存任务、触发实例、运行关联、队列状态、统计和日志。
- 时间触发按 `Asia/Shanghai` 计算，错过的间隔不补放；一次触发使用稳定 occurrence key 去重。
- 不同任务持久排队，同一任务拒绝并发；重复执行、响应丢失查询、停写准入和重启恢复由专项测试覆盖。
- Studio 只绑定主应用 CloakBrowser Profile；工作流和 Profile 删除保护已接入。
- 正式 UI 已完成创建、自动到点、停用、日志查看；真实 CloakBrowser 五节点执行并持久化提取值和 PNG，终态无受管浏览器残留。
- Electron 主进程注册热键并对 sidecar 实例做回调隔离；Webhook 沿用 AutoFlow 令牌鉴权，界面示例明确携带 `x-autoflow-token`。
- 通知秘密只接受系统凭据引用；外部邮件和第三方通知供应商仍按 B6 外部环境分别验收，不由本证据核销。

证据：

- 开发入口：[result.json](formal-schedules-electron-UjDMys/result.json)
- 冻结后端与正式目录包：[result.json](formal-schedules-electron-58AJO9/result.json)
- 运行成功界面：[scheduled-run-success.png](formal-schedules-electron-58AJO9/scheduled-run-success.png)
- 重启恢复界面：[scheduled-task-restored.png](formal-schedules-electron-58AJO9/scheduled-task-restored.png)

正式脚本：`scripts/smoke-studio-backend-p2-schedules.mjs`。脚本使用临时工作区和临时 Profile，不读取或修改真实用户数据库。
