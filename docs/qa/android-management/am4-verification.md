# AM4 数据与维护验收

审计基线：`432d1cdc`；当前聚焦后端 `175 passed, 1 warning`、前端 Android `13 files, 47 passed`；完整端到端演练尚未完成。

| 任务 | 状态 | 证据与限制 |
| --- | --- | --- |
| T17 停机备份 | `blocked` | 运行中拒绝、摘要/路径安全 unit/contract 与 `test_android_backups.py` 自动化通过；本轮真实停止后管理备份路由返回 `201 Created`、`state=available`、`bytes=18585260`；磁盘不足/取消/权限/中断未完整验证。 |
| T18 安全恢复 | `blocked` | 新卷恢复、损坏摘要、镜像不符、越界路径和特殊文件拒绝 unit 通过；`test_android_backup_restore.py` 自动化与真实源/目标标记一致；链接属性和恢复中断隔离未完成。 |
| T19 清理与诊断 | `blocked` | 递归脱敏、环境/设备/操作快照、预览摘要、409 变化提示、cleanup contract 与 Android 前端 `13 files, 47 passed` 自动化通过；本轮真实备份预览/确认清理返回 `200/state=succeeded`，设备删除后容器/卷均为 0；临时文件、高级日志 IPC 和全量引用选择仍缺，保持 blocked。 |
| T20 AM4 最终演练 | `blocked` | 数据写入→停机备份→新卷恢复的基础链与自动化通过；清理确认、磁盘不足、损坏包、恢复中断、镜像引用阻止和完整发布门槛未形成逐项真实证据。 |

## 自动验证命令摘要

```text
cd apps/backend && uv run pytest tests/contract/test_android_backups.py tests/unit/test_android_backup.py tests/unit/test_android_backup_storage.py tests/unit/test_android_cleanup_contract.py tests/unit/test_android_diagnostics_export.py -q
通过（包含在 Android 聚焦集合 175 passed 中）
```

真实卷 copy 使用 Docker `create`/`cp` 适配，不代表已完成多实例恢复和人工清理确认。
