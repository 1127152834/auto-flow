# AM4 真实恢复写入后、发布前硬中断

- 日期：2026-09-23；状态：`confirmed`（目标卷写入完成、恢复状态发布前 `SIGKILL` 这一窗口）；T18/T20 整体仍为 `partial`。
- 环境：Apple Silicon Mac、Lima `autoflow-redroid`、ReDroid；隔离工作区 `/tmp/autoflow-android-control-rAHSP7`，运行前逐一核实工作区哈希与自建源/目标容器和数据卷标签。未对其他工作区的设备或卷执行操作。

早期自建实例 `ae1ea169-9b7c-4751-96a0-c896fffd5c13` 缺少 `creationConfig`；从它生成的备份虽然可用，恢复路由按契约返回 `409 ANDROID_BACKUP_INCOMPATIBLE`（缺少配置快照）。这不是恢复中断测试的有效源。随后通过公开 HTTP 新建带完整配置的源实例 `53b3c90a-c19f-4fb0-95e9-29f22970a9c0`，启动后写入 `/data/local/tmp/am4-restore-probe`，停机并通过公开备份路由生成 `7f711b1c-2a2b-43dd-acf6-7f89a50446ca`；响应 `201/state=available/bytes=18719146`。

测试子进程使用生产恢复 HTTP 路由与真实 `MacAndroidRuntime.restore_volume`，确认目标卷真实解包完成后，仅在返回调用者之前用一次性钩子向子进程发送 OS `SIGKILL`。进程退出码为 `137`。崩溃瞬间持久恢复操作 `1a5dd460-a309-4a70-b51b-506d204b72a0` 为 `running`；新目标 `630e942c-8e98-5d41-a12f-3baee4fcbf6f` 为 `restoreState=pending`、`androidStatus=stopped`，其受控新卷里可读取探针。目标卷与源卷 ID 不同。

重新启动认证的本机 HTTP sidecar 后，按原请求查询得到 `needs_verification`；管理列表仍报告 `restoreState=pending` 且未允许启动。对新目标的启动、备份和手动控制会话均返回 `409 ANDROID_RESTORE_INCOMPLETE`。随后通过公开设备删除操作并选择删除数据，持久操作 `succeeded`，目标容器与卷均不存在，源容器/卷仍各一份。一次性脚本输出 `status=passed`，目标卷探针 SHA-256 为 `312feabd0449fe6ceff079573263f8afa84a6201a9f4b9b89d1cc08ee4e79886`。

再用同一备份、不同请求恢复至新目标 `fd307d4c-8796-515f-a72e-021a18d77fd7`，得到 `202/state=restored`；启动后从客体读取相同探针，随后通过公开接口删除目标。独立持久库及归属核验显示目标已删除、容器和卷不存在，源探针哈希相同、源卷仍在、备份仍为 `available`。一次性脚本在读取 HTTP 设备投影中不存在的 `containerId` 字段，以及等待已删除设备继续出现在设备列表时分别失败；经受控持久记录核验后确认都是演练脚本假设错误，未作为产品通过或失败证据。

此实验覆盖真实目标卷**写入完成后、成功状态提交前**的硬退出与重启隔离；不覆盖 tar 解包中断、磁盘不足、权限拒绝或损坏包实机演练。脚本和原始卷数据保存在隔离 `/tmp`，未提交仓库。

配套自动回归：在 `apps/backend` 运行 `./.venv/bin/python -m pytest -q tests/integration/test_android_backup_restore.py tests/integration/test_android_restore_isolation.py tests/unit/test_android_backup.py`，实际结果 `51 passed, 1 warning in 11.56s`。本次未修改生产代码；最新全量门槛仍以先前[记录](2026-09-23-command-marker-verification.md)为准。
