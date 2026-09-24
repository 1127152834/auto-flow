# 真实备份目录权限拒绝验收

2026-09-24；confirmed；产品候选78bf8c92；结果passed。使用生产HTTP、SQLite、Mac/Lima/ReDroid，新建隔离workspace；没有mock运行时或修改外部设备。

命令：`uv run --project apps/backend python docs/qa/android-management/scripts/backup-permission-smoke.py --allow-device-mutation --output /private/tmp/android-backup-permission.json`，exit0。完整[JSON](2026-09-24-backup-permission/real-mac.json)和[输出](2026-09-24-backup-permission/real-mac.log)。

在本轮新建备份目录设置macOS UF_IMMUTABLE，真实mkdir返回EPERM(errno1)。生产备份返回503/ANDROID_BACKUP_RESULT_UNKNOWN，持久操作needs_verification/BACKUP_RESULT_UNKNOWN，没有发布备份或遗留staging。移除标志后同requestId返回409/ANDROID_BACKUP_REQUEST_REPLAYED，防止未知结果自动重试；新requestId备份成功，18616779字节。源实例启动后探针内容未变。最终权限限制移除，自有容器/卷0、备份0。

镜像sha256:5a42a569ee1d7c71796c0385e906cbaa4c3e0a162a56d9f26b29bdb1befac13b；deviceId fa461538-12c0-4461-a994-33955c940cbd；backupId 97386572-a9cf-44fc-a1f2-5a31289cbf32。

这是T17扩展故障的真实权限拒绝证据，不改变102个原计划步骤计数，也不代替真实桌面、GApps、十实例或下载途中断网验收。脚本Ruff通过；未对生产代码作修改。
