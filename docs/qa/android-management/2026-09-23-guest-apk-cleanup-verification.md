# AM3/T15 与 AM4/T19：客体 APK 暂存回收

- 日期：2026-09-23；状态：`confirmed`（新上传的受控临时文件）；T15/T19 整体仍为 `partial`。
- 来源：`MacAndroidRuntime.install_apk`、`acknowledge_pending_command`、`recover`、设备启动恢复及真实自建 Mac/Lima/ReDroid 实例。

此前本机 APK 文件由 `TemporaryDirectory` 自动回收，但客体 `/data/local/tmp/autoflow-apk-<UUID>.apk` 仅在安装 shell 正常结束时删除。若 `adb push` 在传输后丢响应，路径尚未写入设备记录，进程重启后无法定位该文件。这是软件缺口，不能归为设备条件阻塞。

先写三项失败测试：上传调用前必须持久登记客体路径；重启恢复只删除登记且格式合法的 APK 路径；持久成功回执后的确认必须先清理 APK 再移除操作完成标记。实际 RED 为 `3 failed in 0.60s`。最小修复将 `pendingApk` 写入设备记录后才执行 push；确认和恢复使用既有容器归属检查，且仅接受 `/data/local/tmp/autoflow-apk-[0-9a-f]{32}.apk`。清理失败保留待恢复状态，下一次可重试；手动输入在待清理时拒绝。GREEN 聚焦 `5 passed in 0.65s`，相关后端集合 `74 passed, 1 warning in 2.29s`；Ruff 与 compileall 通过。

真实验证只使用隔离工作区 `/tmp/autoflow-android-control-rAHSP7` 的自建实例 `ae1ea169-9b7c-4751-96a0-c896fffd5c13`。经公开接口启动并核实容器/卷标签后，在客体受控路径写一字节测试文件，模拟 push 完成但响应丢失时的持久 `pendingApk` 状态。重启认证 HTTP sidecar，启动恢复移除该客体文件及字段，设备回到 `idle`；随后经公开接口停机，容器和卷归属仍各一份。一次性脚本输出 `status=passed`、`persistedBeforeRestart=true`、`recoveredAfterRestart=true`、`guestTempRemoved=true`、`sourceVolumeIntact=true`。这是**状态注入和真实客体清理**，不是一次真实网络传输中断；原始 APK 数据和脚本未提交。

限制：验证当时，旧版本在该自建卷内留下 5 个没有持久路径的 `autoflow-operation-*` 标记，不能按文件名前缀猜测归属并逐个删除。2026-09-23 后续收尾用认证公开 API 永久删除本轮两台自建实例及其卷，随后用清理预览/确认删除本轮两份备份；脚本输出 `status=passed`，两台 deviceId 的 Docker 卷查询无结果。因此这 5 个标记随本轮自建卷移除，不代表已实现对仍在使用的旧卷进行无归属标记清理。上传时恰好断连的真实 ADB 链路、旧会话回执的重启核实和高级日志仍待单独验收。
