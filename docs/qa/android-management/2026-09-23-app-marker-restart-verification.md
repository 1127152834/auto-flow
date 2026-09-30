# AM3/T15 与 AM4/T19：应用完成标记跨重启隔离

- 日期：2026-09-23；状态：`confirmed`（有持久 `pendingCommand` 的新旧应用操作）；T15/T19 整体仍为 `partial`。
- 来源：`AndroidDeviceService.cleanup/recover`、`MacAndroidRuntime.recover`，自建 Mac/Lima/ReDroid 实例及对应 RED→GREEN 测试。

原实现中，自动启动恢复和会话结束都会读取客体完成标记后清除设备的 `pendingCommand`，并将设备放回 `idle`。重启后旧控制会话不能再读取，尚未持久核实的应用结果可能因此失去唯一证据。先写启动恢复、会话收尾、运行时保留三项失败测试，实际 `3 failed`；再写 `v2:124` 与旧格式 `0` 两项失败测试，实际 `2 failed`。二者分别验证“自动路径不可释放结果未知”和“显式核实也不可把不确定退出码当作完成”。

修复让自动启动恢复和会话收尾仍回收进程，但保留合法 `pendingCommand`，将设备置为 `recovery_required`；普通设备操作和新控制会话因此不能越过栅栏。显式设备 `recover` 操作读取客体标记；仅当结果为已确认的 v2 退出码或旧格式非零失败码时删除客体标记并释放设备。`v2:124`、旧格式零码、缺失/异常标记和删除失败均继续保持隔离。相关集合 `102 passed, 1 warning in 3.00s`，Ruff 与 compileall 通过。

真实状态注入仅用隔离工作区 `/tmp/autoflow-android-control-rAHSP7` 的自建实例 `ae1ea169-9b7c-4751-96a0-c896fffd5c13`：经公开接口启动并核实容器/卷归属，在客体写入 `v2:0` 完成标记且在设备记录登记路径，模拟命令已完成但服务退出前未提交终态回执。重启认证 HTTP sidecar 后，设备持久状态为 `recovery_required`，标记仍可读，普通 `start` 返回 `409 ANDROID_RECOVERY_REQUIRED`。经公开设备 `recover` 后，持久操作 `succeeded`、标记文件不存在、设备回到 `idle`；再经公开接口停机，容器与卷仍各一份。一次性脚本输出 `status=passed`、`markerPreservedAfterRestart=true`、`normalStartDenied=true`、`explicitRecoverySucceeded=true`、`guestMarkerRemoved=true`、`volumeIntact=true`。这是真实客体文件及服务重启的受控状态注入，不是一次实际 ADB 响应丢失。

限制：实验当时，该自建卷内有 5 个早期遗留、但设备记录中已无 `pendingCommand` 的客体文件，没有可证明的单文件归属，不能自动逐个清理。后续用认证公开 API 删除了本轮自建实例及卷，这 5 个文件随自建卷移除；对仍在使用的旧卷，安全清理无登记标记的能力仍缺失。真实 ADB 断连、桌面核实交互和对不确定码的人工后续处理还缺验收证据。不得通过遍历文件名前缀直接删除无登记文件。
