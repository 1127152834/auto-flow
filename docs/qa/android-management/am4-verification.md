# AM4 数据与维护验收

早期增量基线：`a47bbb9d`，后端 `346 passed, 2 warnings`；最新[原生窗口、恢复归属与持久数据属性](2026-09-23-persistent-metadata-verification.md)记录真实新实例启动、UID/GID/mode、xattrs/ACL、根目录及链接实验。下表按后续真实链重新校准，整任务仍为 `partial`；未执行的失败演练不作为外部条件 blocked。

| 任务 | 状态 | 证据与限制 |
| --- | --- | --- |
| T17 停机备份 | `passed`（AC19 功能） | 运行/控制拒绝、归档安全、权限、原子发布及真实停机备份通过；[真实 ENOSPC 与传输中取消](2026-09-24-backup-failure-verification.md)证明不发布成功备份、原请求不重放、源数据保留。UI 已 RED→GREEN 补本机未加密与私密数据说明。[传输中进程树 SIGKILL](2026-09-24-restore-cancel-and-disk-full.md)已补；[真实权限拒绝](2026-09-24-backup-permission.md)扩展故障已passed。 |
| T18 安全恢复 | `passed`（已列功能） | 新 ID/新卷/源保护、摘要/镜像/路径/链接/属性回归通过；真实1792项属性读回、恢复发布前硬中断隔离及新请求恢复已验。UI 已说明应用数据恢复不保证登录/DRM/私钥；[真实解包在途中 SIGKILL](2026-09-24-restore-transfer-interruption.md)后隔离及新请求恢复通过；[真实目标 ENOSPC 与取消恢复](2026-09-24-restore-cancel-and-disk-full.md)已通过，并修复命令取消后的 SSH 子进程遗留写入。 |
| T19 清理与诊断 | `passed`（已列功能） | 冻结预览、引用/归属变化409、真实备份/暂存清理和受限保存通过；[高级日志](2026-09-24-advanced-logs-and-capacity.md)单次确认及真实196条仅元数据通过。[多对象清理硬中断](2026-09-24-cleanup-interruption.md)已验，首项成功不掩盖未执行项；无来源旧客体文件按归属边界保持排除。 |
| T20 AM4 最终演练 | `partial` | 真实写入/停机备份/新卷恢复/读回/清理、备份和恢复发布点 SIGKILL、真实 ENOSPC/传输取消、最终分支审查及软件门禁均有记录；恢复解包在途中硬中断已补；目标磁盘不足、取消恢复和多对象清理硬中断已补；完整真实负向矩阵尚未结束。 |

## 自动验证命令摘要

```text
cd apps/backend && uv run pytest tests/contract/test_android_backups.py tests/unit/test_android_backup.py tests/unit/test_android_backup_storage.py tests/unit/test_android_cleanup_contract.py tests/unit/test_android_diagnostics_export.py -q
通过（包含在 Android 聚焦集合 235 passed 中）
```

上面的命令与 Docker `create`/`cp` 是早期快照；当前真实备份使用 Lima 客体侧 GNU tar。新证据见[持久数据属性增量](2026-09-23-persistent-metadata-verification.md)，不代表多实例恢复和人工清理确认已完成。

[全分支审查修复](2026-09-23-final-review-remediation.md)补齐自定义缓存镜像按固定 imageId 恢复、备份对镜像删除的引用保护，以及文件流备份/恢复。真实 Mac 在独立工作区使用 17,868,800 字节 tar 完成源实例写入→停机备份→HTTP 恢复新实例→启动读回，源/目标和备份均清理；旧整包字节方法在实验中被显式设为失败。真实备份磁盘不足与在途任务取消已由 2026-09-24 故障记录补足；恢复解包中 SIGKILL 已由 2026-09-24 记录补足；恢复目标磁盘不足与取消已补；备份传输中进程树硬中断亦由命令树回归补足。

## 发布一致性增量

[2026-09-23 发布验收](2026-09-23-publication-verification.md)补齐文件/目录同步、事务原子性、故障注入及真实新实例恢复；硬中断孤立文件、恢复中断和完整阶段验收仍待完成。

## 清理目录增量

[2026-09-23 清理验收](2026-09-23-cleanup-verification.md)记录目录查询、显式选择、内容指纹、文件锁和真实HTTP证据；本次未声称完成APK遗留文件或恢复中断验收。

- 2026-09-24 最快验收（confirmed，整体不通过/partial）：当前Android后端477项、前端177项、迁移6项及工程门禁通过；真实备份磁盘预检零写入拒绝、释放后估计=实际18595840字节、传输取消及自有资源清理通过。最终限时审查新增备份跨动作未知编号覆盖已RED→GREEN关闭；创建/拉取磁盘准入和宿主/VM数值展示仍Important。Mac已解锁，最终构建首页/无效拉取恢复输入实机通过，其余完整UI改记not_run；十台/GApps仍blocked。最后候选全仓全量未重跑，旧数字不代替；见[完整验收命令及输出](2026-09-24-final-acceptance.md)。
