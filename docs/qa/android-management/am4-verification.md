# AM4 数据与维护验收

早期增量基线：`a47bbb9d`，后端 `346 passed, 2 warnings`；最新[原生窗口、恢复归属与持久数据属性](2026-09-23-persistent-metadata-verification.md)记录真实新实例启动、UID/GID/mode、xattrs/ACL、根目录及链接实验。下表按后续真实链重新校准，整任务仍为 `partial`；未执行的失败演练不作为外部条件 blocked。

| 任务 | 状态 | 证据与限制 |
| --- | --- | --- |
| T17 停机备份 | `partial` | 运行中拒绝、摘要/路径安全 unit/contract 与 `test_android_backups.py` 自动化通过；真实停止后管理备份路由返回 `201 Created`、`state=available`、`bytes=18585260`，[发布一致性](2026-09-23-publication-verification.md)已补故障注入；[真实发布前 SIGKILL](2026-09-23-backup-hard-interruption-verification.md)证明无假成功、暂存可清且源卷读回不变。磁盘不足、取消、权限和归档传输中硬中断仍未完整验证。 |
| T18 安全恢复 | `partial` | 新卷恢复、损坏摘要、镜像不符、越界路径和特殊文件拒绝 unit 通过；`test_android_backup_restore.py` 自动化与真实源/目标标记一致；[持久属性](2026-09-23-persistent-metadata-verification.md)覆盖 xattrs/ACL、卷根属性、硬/软链接、部分失败隔离和正常恢复；[真实写入后发布前 SIGKILL](2026-09-23-restore-hard-interruption-verification.md)后待核实隔离、删除目标及新请求恢复通过。解包中断、磁盘不足仍未完成。 |
| T19 清理与诊断 | `partial` | 默认诊断白名单、runtime workspace 归属、预览摘要、409 变化提示与真实 HTTP 备份/暂存/未登记产物清理通过；受限本机保存 IPC 已实现；[应用命令标记](2026-09-23-command-marker-verification.md)修复后真实成功链不再新增客体残留。[新 APK 暂存回收](2026-09-23-guest-apk-cleanup-verification.md)及[完成标记跨重启隔离](2026-09-23-app-marker-restart-verification.md)经 RED→GREEN 与真实状态注入通过。[高级日志](2026-09-24-advanced-logs-and-capacity.md)单次同意、归属、限时限量及真实 ReDroid 元数据导出通过；无登记旧客体标记和真实 ADB 断连仍是软件/验收缺口。 |
| T20 AM4 最终演练 | `partial` | 数据写入→停机备份→新卷恢复→真实清理的基础链与自动化已有独立证据；另有[备份发布前硬中断](2026-09-23-backup-hard-interruption-verification.md)和[恢复写入后发布前硬中断](2026-09-23-restore-hard-interruption-verification.md)及安全清理读回。磁盘不足、损坏包、解包中断、镜像引用阻止、最终全分支审查和完整失败矩阵未形成同链真实证据。 |

## 自动验证命令摘要

```text
cd apps/backend && uv run pytest tests/contract/test_android_backups.py tests/unit/test_android_backup.py tests/unit/test_android_backup_storage.py tests/unit/test_android_cleanup_contract.py tests/unit/test_android_diagnostics_export.py -q
通过（包含在 Android 聚焦集合 235 passed 中）
```

上面的命令与 Docker `create`/`cp` 是早期快照；当前真实备份使用 Lima 客体侧 GNU tar。新证据见[持久数据属性增量](2026-09-23-persistent-metadata-verification.md)，不代表多实例恢复和人工清理确认已完成。

[全分支审查修复](2026-09-23-final-review-remediation.md)补齐自定义缓存镜像按固定 imageId 恢复、备份对镜像删除的引用保护，以及文件流备份/恢复。真实 Mac 在独立工作区使用 17,868,800 字节 tar 完成源实例写入→停机备份→HTTP 恢复新实例→启动读回，源/目标和备份均清理；旧整包字节方法在实验中被显式设为失败。磁盘不足与归档传输/解包中断仍未完成。

## 发布一致性增量

[2026-09-23 发布验收](2026-09-23-publication-verification.md)补齐文件/目录同步、事务原子性、故障注入及真实新实例恢复；硬中断孤立文件、恢复中断和完整阶段验收仍待完成。

## 清理目录增量

[2026-09-23 清理验收](2026-09-23-cleanup-verification.md)记录目录查询、显式选择、内容指纹、文件锁和真实HTTP证据；本次未声称完成APK遗留文件或恢复中断验收。
