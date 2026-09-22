# AM4 数据与维护验收

审计基线：`edf3906b`；当前聚焦后端 `126 passed, 1 warning`、前端 Android `13 files, 39 passed`；完整端到端演练尚未完成。

| 任务 | 状态 | 证据与限制 |
| --- | --- | --- |
| T17 停机备份 | `blocked` | 运行中拒绝、摘要/路径安全 unit/contract 与 `test_android_backups.py` 自动化通过；真实停机卷 copy `25,472,000 bytes` 和标记恢复通过；磁盘不足/取消/权限/中断未完整验证。 |
| T18 安全恢复 | `blocked` | 新卷恢复、损坏摘要、镜像不符、越界路径和特殊文件拒绝 unit 通过；`test_android_backup_restore.py` 自动化与真实源/目标标记一致；链接属性和恢复中断隔离未完成。 |
| T19 清理与诊断 | `blocked` | 脱敏、预览摘要、409 变化提示、cleanup contract 与 Android 前端 `13 files, 39 passed` 自动化通过；生产页面已覆盖设备与已登记备份，诊断范围单独限制为设备；临时文件、全量引用选择和专用 IPC 流程仍缺，真实维护入口条件不足，保持 blocked。 |
| T20 AM4 最终演练 | `blocked` | 数据写入→停机备份→新卷恢复的基础链与自动化通过；清理确认、磁盘不足、损坏包、恢复中断、镜像引用阻止和完整发布门槛未形成逐项真实证据。 |

## 自动验证命令摘要

```text
cd apps/backend && uv run pytest tests/contract/test_android_backups.py tests/unit/test_android_backup.py tests/unit/test_android_backup_storage.py tests/unit/test_android_cleanup_contract.py tests/unit/test_android_diagnostics_export.py -q
通过（包含在 Android 聚焦集合 126 passed 中）
```

真实卷 copy 使用 Docker `create`/`cp` 适配，不代表已完成多实例恢复和人工清理确认。
