# 安卓管理最终分支审查与边界回归

- 日期：2026-09-24；状态：`confirmed`（下列 RED→GREEN 和只读复审）；AM1–AM4 总验收仍为 `partial`。
- 来源：隔离分支 `codex/android-management-complete` 的全分支只读复审、对应失败回归和 Mac/Lima/ReDroid 实验。复审覆盖运行时、持久操作、镜像、批次、备份恢复、清理、诊断及页面；复审者未独立运行全量测试或真实设备。

| 高优先级边界 | RED 可观察失败 | GREEN 行为 |
| --- | --- | --- |
| 新设备 `generation=0` 与 `generation=1` 的公开 revision 别名 | 旧批次/备份可用 `revision=1` 越过版本栅栏 | 统一公开 `generation+1`；列表、备份和批次一致；旧版本拒绝。 |
| 镜像目录与拉取回执分两次发布 | 回执写失败后目录半发布 | 生产目录与回执使用同一 SQL 事务；旧记录核实后补回执。 |
| 拉取/登记、未知拉取核实与内容删除并发 | 核实后删除可插在 Operation 成功提交前；拉取后目录可指向已删镜像 | 全程使用相同运行时独占锁；`verify_pull` 在锁内完成精确镜像核实及 Operation 终态提交。 |
| 备份文件发布后释放锁、目录记录随后写入 | 镜像内容可在未登记的备份窗口删除 | 归档发布和备份目录/Operation 提交同处运行时锁内，镜像引用保护可见。 |
| APK 安装跨重启失去 ADB tunnel | 客体成功标记存在但包版本核实永远返回断连 | 重建核实上下文按归属验证容器，直接读取容器内 `pm` 包清单；核实持久终态后释放标记。 |
| 删除容器后崩溃且数据库仍为旧快照 | `inspect` 因旧 `dataRetained=false` 无法确认已删容器/卷 | 删除专用只读归属核实分别判 `retained` / `missing`，设备和 Operation 同事务收敛；未知/外部对象仍拒绝。 |
| 容量探测中的异步间隙推进设备版本 | 旧批次随后仍发起操作 | 容量返回后复读设备，且生命周期控制器在全局运行时锁内核对 `expectedRevision`。 |
| 真实运行时失败后批次 `retryFailed` 仍持旧版本 | 自身上一尝试已推进 generation，重试总是冲突 | 显式重试只对空闲、无未核实命令设备冻结新的 `retryExpectedRevision`；原批次幂等输入保持不变。 |
| 恢复预检的 `AndroidError` 遗留父 Operation `running` | Docker 镜像枚举失败后相同请求永远不能收敛 | 目标创建前的只读预检异常记 `failed`；不会假装已写入目标。 |
| 异步设备清理后父 Operation 不收敛 | 子删除成功而页面查询原请求始终看到 `running` | 查询/核实原请求时按子操作持久终态重算父记录和 Operation。 |
| 多对象清理仅首项落盘后崩溃 | 只看已存 `items`，可把未执行的第二项误判为全完成 | 只有持久条目 ID 多重集与冻结候选完全一致才可标 `succeeded`；缺项保持待核实/运行中。 |

上述每条均先有可观察失败回归；最后一组清理/恢复定向命令：

```text
uv run --project apps/backend pytest -q apps/backend/tests/contract/test_android_management_operations.py apps/backend/tests/unit/test_android_cleanup_contract.py apps/backend/tests/integration/test_android_backup_restore.py::test_restore_environment_failure_records_terminal_preflight_state
```

实际输出：`51 passed, 1 warning in 6.50s`。镜像、备份、控制会话定向集合 `157 passed, 1 warning in 6.50s`；批次/管理/容量/投影集合 `53 passed, 1 warning in 5.48s`。警告是 Starlette 的 anyio 别名弃用。最终全量门槛单独记录，不将这些局部计数相加。

最新真实 AM3 命令 `uv run --project apps/backend python /tmp/autoflow-am3-bulk-failure-cancel-real-20260924.py` exit 0：`{"status":"passed","partial":["succeeded","failed"],"cancelled":"cancelled","capacityItem":"cancelled"}`。这是在公开修订号与批次透传修复后的重跑。真实重试、真实删除后硬中断、恢复预检 Docker 错误与多项清理硬中断仍只有故障回归，未冒充真实环境验收。

对该脚本隔离工作区已永久删除的三台设备，使用生产 `MacAndroidRuntime.verify_deleted` 按原设备 ID、容器 ID、卷 ID 和工作区执行只读 Docker 枚举，exit 0，输出 `{"realDeletedDevices":3,"states":["missing","missing","missing"]}`。这证明永久删除结果可由真实运行时核实；保留卷删除后崩溃的真实场景仍需另验。

AM1 APK 跨重建核实另用真实 ReDroid 和 Shizuku `versionCode=1086` 执行 `uv run --project apps/backend python /tmp/autoflow-am1-restart-install-real-20260924.py`，exit 0，输出 `{"status":"passed","verifiedAfterReconstruction":true,"packageName":"moe.shizuku.privileged.api","versionCode":1086,"recoveredAfterReceipt":true}`。原会话与请求回执在控制台重建后核实为成功，客体完成标记清除，再恢复设备控制；脚本仅删除本次自建实例，并确认容器/卷消失。真实 HTTP 进程级 `SIGKILL`、ADB 实际断线仍未作为这条证据验收。
