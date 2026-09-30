# 恢复空间不足、取消与命令子进程回收

- 日期：2026-09-24；状态：confirmed（下列实际故障与 RED→GREEN），完整 AM1–AM4 仍 partial。
- 基线：`162fa380` 加本次进程回收修复。独立 worktree，三个 Studio 文档修改保持原哈希。
- 平台：Apple Silicon macOS、既有 Lima `autoflow-redroid`、真实 Docker/ReDroid。镜像 `sha256:5a42a569ee1d7c71796c0385e906cbaa4c3e0a162a56d9f26b29bdb1befac13b`。
- [可运行故障脚本](scripts/restore-failure-smoke.py)、[真实结果 JSON](2026-09-24-restore-faults-result.json)。

## 实际发现与根因

第一轮真实目标磁盘不足已正确留下 `needs_verification`；随后取消恢复请求任务，目标文件仍继续增长，稳定性断言失败，脚本 exit 1。该轮自建实例、备份和私有挂载均已清理。没有把第一轮记为完整通过。

根因在 `mac_runtime.run` / `run_file`：只对直接启动的 `limactl` 调用 `process.kill()`，其 SSH 子进程可能继续持有归档描述符并写入客体。结果未知隔离虽然仍在，但命令回收不完整。

先增加真实父进程→子进程连续写文件回归，分别执行两个 runner 的取消和超时。RED 四项均失败：停止返回后文件仍从 `1→13`、`1→14`、`162→174`、`160→173` 字节增长。最小修复让 POSIX 命令建立独立进程组，普通路径及 spawn 取消路径都调用同一组回收方法；非 POSIX 保持直接进程回收，未宣称 Windows 安卓运行时可用。

```text
uv run --project apps/backend pytest apps/backend/tests/unit/test_android_runtime.py -q -k command_cancellation_or_timeout_stops_descendant_writes
RED: 4 failed, 59 deselected in 5.44s

uv run --project apps/backend pytest apps/backend/tests/unit/test_android_runtime.py -q
GREEN: 63 passed in 6.03s
```

进程组来自本次 `create_subprocess_exec(start_new_session=True)` 返回的进程，不按资源名称搜索并杀死外部进程。没有修改持久 Operation、generation、归属、恢复意图或结果未知保护，也不引入迁移/契约变化。

## 真实故障重跑

```text
uv run --project apps/backend python docs/qa/android-management/scripts/restore-failure-smoke.py --allow-device-mutation
exit 0: status=passed
```

源实例通过认证 HTTP 创建，写入 256 MiB 随机合成探针并停机，HTTP 备份 `288563631` 字节。故障本身由进程内 ASGI 请求调用生产路由/SQLite/Mac runtime：空间不足通过边界钩子只在生产方法执行前挂载真实 16 MiB tmpfs；取消通过取消该 ASGI 请求任务注入。钩子没有替代解包、伪造响应或抛假 ENOSPC。它不是桌面点击取消，也不是 HTTP 客户端断线实验。故障后的重启、核实、恢复与删除再次使用独立真实 HTTP 后端。

| 场景 | 实际结果 |
| --- | --- |
| 目标空间不足 | 自建目标卷经生产标签校验后挂载独立 tmpfs，真实写探针先证明 `errno=28`；生产解包用满 `16777216` 字节，剩余 0，路由返回 503 `ANDROID_BACKUP_RESTORE_RESULT_UNKNOWN`。 |
| 解包中取消 | 文件实际写到 `1757184` 字节时取消；最后稳定于 `6189056` 字节，小于完整 `268435456` 字节，连续两次读取不再增长。 |
| 持久结果与锁 | 两种 Operation 均 `needs_verification`，目标 `restoreState=pending/control=recovery_required`；本次命令树结束，运行时锁释放；原请求重放均 409。 |
| 重启后 | 两种状态保留；普通 `recover` 后尝试启动仍 409 `ANDROID_RESTORE_INCOMPLETE`；不完整目标可通过公开删除流程移除。 |
| 新请求与源保护 | 同一备份由新请求恢复、启动读回，源/目标 SHA-256 一致；源备份中各文件摘要前后不变。 |
| 清理 | 四台自建源/目标实例及卷、备份文件与记录、私有 tmpfs 挂载全部清理；结果 JSON 三个清理字段均 true。 |

源 deviceId `f08df172-6691-4ae6-9af5-ab5ea6d7d3d9`；backupId `280ff34a-eb80-491d-b038-d8e9fb81aa97`；两个失败目标和请求 ID 见结果 JSON。只挂载本轮新建且归属匹配的目标卷，没有填满 Lima 公共文件系统。

随后在同一脚本加入真实损坏归档路径并完整重跑，exit 0：[三场景最终结果](2026-09-24-restore-corrupt-faults-result.json)。通过 HTTP 额外创建第二份本轮备份，QA 主动向它追加损坏字节；正常备份保持不变。生产恢复返回 409 `ANDROID_BACKUP_CORRUPT`、Operation failed，新目标真实卷仍空，重放被拒；重启后 failed 保留，普通 recover 仍不能启动该不完整目标。两种故障再次得到 ENOSPC/needs_verification 及取消后稳定部分文件（`1527808→5787648` 字节）。最后正常备份 `289280431` 字节恢复读回成功、源与正常备份摘要不变；五台自建设备/卷、两份备份及私有挂载均清理。损坏是 QA 对独立故障样本的有意操作，不是产品修改源备份。

## 最终软件验证

| 命令 | 实际输出 |
| --- | --- |
| 在 `apps/backend`：`uv run pytest -x -q` | exit 0；`4035 passed, 26 skipped, 2 warnings in 842.30s`。 |
| 在 `apps/backend`：`uv run pytest tests/contract/test_android*.py tests/unit/test_android*.py tests/integration/test_android*.py -q` | exit 0；`451 passed, 2 warnings in 30.99s`。 |
| 在 `apps/backend`：`uv run ruff check src tests && uv run python -m compileall -q src/autoflow` | exit 0；All checks passed，编译无输出。 |
| `npm exec --offline --yes --package=node@22.23.2 -c 'npm run openapi:check'` | exit 0，无契约差异。 |
| 在 `apps/backend`：`uv run alembic -c src/autoflow/infrastructure/database/alembic.ini heads` | `am01_management_operations (head)`，仍为唯一 head。 |
| `uv run --project apps/backend ruff check docs/qa/android-management/scripts` | exit 0；All checks passed。 |
| 三份本轮修改/新增 QA 脚本的 `--help` / 无授权开关运行 | 分别 exit 0 / exit 2，后者明确要求 `--allow-device-mutation`，无设备副作用。 |
| `git diff --check` | exit 0。 |

全量与聚焦两个警告为既有 Starlette anyio 别名弃用和故意构造重复 APK Manifest 的 ZIP 提示。26 skipped 保留真实跳过状态，没有当作通过。另对最终三组真实运行的 SQLite 设备记录逐个调用生产 `verify_deleted`，实际输出 `{"ownedDeletedDevicesVerified":9,"allStates":"missing"}`，证明本轮已删除实例和卷确实不存在。

## 验证范围

命令树修复影响共享运行时命令，因此重新执行真实备份磁盘/取消、整进程树硬中断和全后端测试，最终输出如上。前端源码未改，前一提交 Node 22 的 424 文件/5626 项以及类型/lint/build 结果仍对应相同前端树；OpenAPI 本轮再次检查通过。结构/全脚本的受测代码未改，沿用此前 4/4 与 95/95 结果，不把它们写成本轮重新执行。

- `uv run --project apps/backend python docs/qa/android-management/scripts/restore-interruption-smoke.py --allow-device-mutation` exit 0：[实际输出](2026-09-24-process-group-restore-result.json)。实验依据父子关系枚举本次后端的命令组，检查组长均属于自身进程树且排除 QA 父组后，终止两个自有进程组。备份 `289270187` 字节，观察到 `1288192` 字节时强制退出，稳定部分文件 `12492800` 字节；重启隔离、新请求恢复和源/备份保护全部通过，资源已清理。旧脚本只杀后端组的方式不再覆盖新隔离的命令组，因此相应调整故障注入范围，未放宽部分写入断言。
- `uv run --project apps/backend python docs/qa/android-management/scripts/disk-full-smoke.py --allow-device-mutation --scrcpy-archive /Users/zhangtiancheng/.autoflow/android-runtime/scrcpy-macos-aarch64-v3.3.4.tar.gz` exit 0：[实际输出](2026-09-24-process-group-backup-result.json)。真实 ENOSPC，备份 failed；新请求备份 `19364012` 字节；在 `112640` 字节时取消传输，needs_verification，无目录/staging，源探针保留，实例/卷和私有磁盘挂载均清理。
- `uv run --project apps/backend python docs/qa/android-management/scripts/restore-interruption-smoke.py --allow-device-mutation --interrupt-backup-first` exit 0：[实际输出](2026-09-24-transfer-hard-kill-result.json)。备份归档真正传输到 `1302528` 字节时终止两个自有进程组；重启无成功备份，原 Operation needs_verification，原请求重放被拒，经公开预览清理暂存。之后同源的新请求备份 `289280427` 字节，再在恢复写入 `1134592` 字节时硬中断，稳定部分文件 `12914688` 字节；同样隔离、新请求恢复成功、源和源备份摘要不变。所有自建设备/卷/备份已清理。这补足传输过程硬中断，不冒称只是发布点中断。

另补[真实多对象清理硬中断](2026-09-24-cleanup-interruption.md)。仍未完成：完整桌面断线/控制链、批次未知结果与完整真实负向矩阵；GApps 与十台容量仍有明确外部不足。本项通过不代表完整 AM4 或全目标完成。
