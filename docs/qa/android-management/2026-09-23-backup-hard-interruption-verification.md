# AM4 真实备份发布前硬中断与受控清理

- 日期：2026-09-23；状态：`confirmed`（发布前硬中断这一场景）；AM4/T20 整体仍为 `partial`。
- 环境：Apple Silicon Mac、Lima `autoflow-redroid`、ReDroid；隔离目录 `/tmp/autoflow-android-control-rAHSP7`，唯一自建活跃实例 `ae1ea169-9b7c-4751-96a0-c896fffd5c13`。运行前核实工作区哈希、实例停机状态及容器/卷双标签；未触碰其他实例或卷。

先经生产 HTTP 将自建实例停机，持久操作确认为 `succeeded`、设备为 `stopped`。停机脚本在打印结果时误读取 HTTP 投影不包含的 `volumeId`，出现 `KeyError`；随后独立读取持久库证实停机成功。此错误是一次性脚本字段假设，不是产品停机失败。

测试子进程调用生产 `AndroidBackupService.create_with_runtime` 与真实 `MacAndroidRuntime.backup_volume`，完整读取自建 Docker 卷并写入受控暂存目录的 `data.tar` 和 `manifest.json`。仅在 `BackupStorage.finalize` 的入口用一次性测试钩子发送 OS `SIGKILL`，不改生产代码、不用 mock 卷。父进程确认退出信号为 `SIGKILL`，新暂存归档 `41,748,480` bytes，`final` 目录未新增备份，也没有该请求的可用备份记录；崩溃瞬间持久操作为 `running`。

重新启动认证的本机 HTTP sidecar 后，按原请求读取操作为 `needs_verification`。`GET /management/cleanup/resources` 找到且仅选择本轮 `backup-staging` 对象；通过公开预览与确认清理接口删除该暂存目录，返回 `state=succeeded`。已有 final 目录集合不变，原容器与卷仍各一份且归属不变。

最后通过公开设备操作重新启动原实例，ADB 从同一卷读取此前写入的探针，SHA-256 仍为 `ec71875896933e03b3f433e118ae483b5bb63088f44b37fd8e09d7ebebde331f`。一次性脚本结果 `/tmp/android-am4-backup-hard-kill-result.json` 和 `/tmp/android-am4-hard-kill-source-readback.json` 均为 `status=passed`；脚本、原始归档与设备数据均未提交。

此实验准确覆盖“真实卷归档已暂存、发布前进程硬退出”的结果未知保护和孤立暂存清理；尚未覆盖归档传输中硬退出、磁盘耗尽、权限拒绝、恢复目标写入中硬退出或 5/10 台性能。
