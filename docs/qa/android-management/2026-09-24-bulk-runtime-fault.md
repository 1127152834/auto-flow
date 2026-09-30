# 批次真实运行时失败、重试与未知结果核实

- 日期：2026-09-24；状态：confirmed（下列真实故障与定向回归），完整目标仍 partial。
- 基线：隔离分支 `codex/android-management-complete@0c67bffc`。本增量只新增 QA 脚本和证据，未修改生产代码、测试、迁移或契约。
- 平台：Apple Silicon macOS、Lima ARM64、真实 Docker/ReDroid。固定 imageId `sha256:5a42a569ee1d7c71796c0385e906cbaa4c3e0a162a56d9f26b29bdb1befac13b`。
- [可运行脚本](scripts/bulk-runtime-fault-smoke.py)、[实际结果](2026-09-24-bulk-runtime-fault-result.json)。

## 实际场景

在独立临时工作区通过认证 HTTP 创建两台 1 CPU / 1536 MiB 实例，分别写入不同合成探针，记录摘要。故障由独立 Python 子进程中的生产 ASGI 路由、真实持久批次队列、SQLite 和 Mac runtime 执行。钩子只选择故障时点，不伪造命令结果、操作状态或设备观察；后续重启、恢复、重试、核实与删除通过完整认证 HTTP 后端。

1. **真实 Docker 失败。** 第一台按批次停止成功；第二台在生产运行时完成归属核验、发出 stop 之前，再次核实 workspace/device 标签并移除其自有容器，保留数据卷。生产 stop 对已消失的确切容器 ID 返回非零，Operation 为 `failed/ANDROID_COMMAND_FAILED`，批次为 `[succeeded, failed]`。未经恢复的 retryFailed 不产生新副作用。公开 recover 确认保留卷，再显式 restore 重建运行环境；retryFailed 使用新 attempt 并保留 retryOf，最终两项 succeeded。两台重启后探针摘要匹配。
2. **完成回执前 SIGKILL。** 新批次停止两台，第二台真实停止并经运行时 inspect 确认为 stopped，但 Operation 仍 running 时，子进程对自身发送 SIGKILL，exit -9。重新启动完整 HTTP 后端后为 `[succeeded, needs_verification]`。重放原批次保持同一批次 ID，retryFailed 不替换未知项 Operation，也不推进 generation；显式 verify 经实际运行时核实后两项 succeeded，核实不推进 generation。再次启动两台读回原探针，摘要一致。
3. **清理。** 最终两台自建实例和卷经生产删除流程移除，`verify_deleted` 均 missing。失败轮的两台也已清理；最终另行只读复核两轮共四台，输出 `verifiedDeletedDevices=4/allStates=missing`。

这覆盖容器在执行期间消失造成的真实运行时失败，以及停止实际成功但持久回执未知的进程级故障。不是实际网络断开、ADB 断连、桌面点击或 APK 安装进程中断验收。

## 命令及实际输出

| 命令（仓库根） | 实际结果 |
| --- | --- |
| `limactl list` | 首次为 Stopped；未创建测试设备。 |
| `limactl start --tty=false autoflow-redroid` | exit 0，READY；启动现有 VM，未改变预算或删除其他资源。 |
| `uv run --project apps/backend python docs/qa/android-management/scripts/bulk-runtime-fault-smoke.py --allow-device-mutation` | 最终 exit 0，status=passed；runtimeFailure.finalState=succeeded；hardKill.exitCode=-9；verificationState=succeeded；bothDataProbesPreserved=true；ownedResourcesDeleted=true。 |
| `uv run --project apps/backend pytest apps/backend/tests/unit/test_android_bulk.py apps/backend/tests/unit/test_android_batch_safety.py apps/backend/tests/integration/test_android_capacity_reservations.py -q` | exit 0，43 passed in 5.76s。 |
| `uv run --project apps/backend ruff check docs/qa/android-management/scripts` | exit 0，All checks passed。 |
| 新脚本 `--help` / 不带授权开关 | exit 0 / exit 2；后者明确要求 --allow-device-mutation。 |
| `git diff --check` | exit 0。 |

首轮因 VM 已停止而结束，无设备创建。第二轮真实故障已如预期失败，但 QA 错把 recover 当作恢复运行环境，随后重试 stop 被 `ANDROID_DATA_RETAINED` 拒绝；该轮资源已清理。修正脚本为 recover → 显式 restore → retryFailed 后完整重跑通过，没有修改生产保护或放宽断言。这不是产品修复的 RED→GREEN；既有软件通过真实负向验收，新增产物是可重复运行的验收脚本。

全后端、前端和工程完整门槛沿用各自受测代码未变的已记录结果，见[命令树修复门槛](2026-09-24-restore-cancel-and-disk-full.md)。本增量没有重复执行全量门槛，不将历史输出称作本轮新运行。

T13 与 AM-AC15 的既有批次部分失败、取消、重试及未知项核实缺口已补。T14/T16 前台与后台指标、T05/T06/T07 桌面同链、AM2 候选镜像和 GApps/十台条件仍不能由本报告替代。
