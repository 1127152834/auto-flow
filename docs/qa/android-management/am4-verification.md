# AM4 数据与维护验收

当前增量基线：`233c09dd`，后端 `314 passed, 2 warnings`；[归档安全与属性](2026-09-23-archive-verification.md)记录真实新实例启动、UID/GID/mode 及链接保真。下表早期证据保留，整任务仍需重审；未执行的失败演练不作为外部条件 blocked。

| 任务 | 状态 | 证据与限制 |
| --- | --- | --- |
| T17 停机备份 | `not_run`（整任务） | 运行中拒绝、摘要/路径安全 unit/contract 与 `test_android_backups.py` 自动化通过；本轮真实停止后管理备份路由返回 `201 Created`、`state=available`、`bytes=18585260`；磁盘不足/取消/权限/中断未完整验证。 |
| T18 安全恢复 | `not_run`（整任务） | 新卷恢复、损坏摘要、镜像不符、越界路径和特殊文件拒绝 unit 通过；`test_android_backup_restore.py` 自动化与真实源/目标标记一致；安全内部链接及 UID/GID/mode 已真实验证；xattrs、发布耐久性和恢复中断隔离未完成。 |
| T19 清理与诊断 | `not_run`（整任务） | 递归脱敏、环境/设备/操作快照（9 月 23 日进一步加入默认字段白名单和 runtime workspace 归属校验）、预览摘要、409 变化提示、cleanup contract 与 Android 前端 `13 files, 81 passed` 自动化通过；本轮真实备份预览/确认清理返回 `200/state=succeeded`，设备删除后容器/卷均为 0；受限本机保存 IPC 已实现；高级日志采集、时间窗口/体积限制、临时文件和全量引用选择仍是软件缺口，不能归为外部条件阻塞。 |
| T20 AM4 最终演练 | `not_run`（整任务） | 数据写入→停机备份→新卷恢复的基础链与自动化通过；清理确认、磁盘不足、损坏包、恢复中断、镜像引用阻止和完整发布门槛未形成逐项真实证据。 |

## 自动验证命令摘要

```text
cd apps/backend && uv run pytest tests/contract/test_android_backups.py tests/unit/test_android_backup.py tests/unit/test_android_backup_storage.py tests/unit/test_android_cleanup_contract.py tests/unit/test_android_diagnostics_export.py -q
通过（包含在 Android 聚焦集合 235 passed 中）
```

真实卷 copy 使用 Docker `create`/`cp` 适配，不代表已完成多实例恢复和人工清理确认。
