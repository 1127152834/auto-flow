# 真实磁盘不足、传输取消与备份说明

- 日期：2026-09-24；状态：`confirmed`（下列真实演练与 RED→GREEN）；完整 AM1–AM4 仍 `partial`。
- 基线：`codex/android-management-complete@30eb0926` 加本次 UI 说明及 QA 增量。后端生产代码没有改动。
- 平台：Apple Silicon macOS，现有 Lima `autoflow-redroid`、Docker-in-Lima、ARM64 ReDroid。镜像固定 `sha256:5a42a569ee1d7c71796c0385e906cbaa4c3e0a162a56d9f26b29bdb1befac13b`。
- [可运行脚本](scripts/disk-full-smoke.py)、[实际结果 JSON](2026-09-24-backup-failure-result.json)。本实验直接使用生产服务、SQLAlchemy 操作仓储及 Mac runtime，不是 HTTP 或桌面端到端，也没有替换运行时或注入假文件系统错误。

```text
uv run --project apps/backend python docs/qa/android-management/scripts/disk-full-smoke.py --allow-device-mutation --scrcpy-archive /Users/zhangtiancheng/.autoflow/android-runtime/scrcpy-macos-aarch64-v3.3.4.tar.gz
```

exit 0，`status=passed`。自建独立 workspace、设备 ID `30a8fff3-8664-4d5a-ae4b-856ee974fcbc`；备份根目录挂载独立 64 MiB HFS+ 可写磁盘映像，`st_dev` 与宿主目录不同。先写合成探针并停机，再将该私有磁盘的空闲空间限制为 `2097152` 字节。额外探针写入真实触发 `errno=28 (ENOSPC)`，确认不是模拟异常；只填充自建小映像，没有填满系统盘或 Lima 公共卷。

| 场景 | 实际结果 |
| --- | --- |
| 真实小磁盘上的卷归档 | `ANDROID_BACKUP_UNAVAILABLE`；持久 Operation `failed`；无目录记录、无已发布备份、无 staging 残留。 |
| 释放容量后重放原请求 | `ANDROID_BACKUP_REQUEST_REPLAYED`，旧请求不再次执行。 |
| 新 requestId 再备份 | `available`，`19353772` 字节，备份 ID `37dfb62d-a88d-4e26-bb43-b8f6c262ee86`。随后通过服务删除本轮备份。 |
| 真正归档传输过程中取消任务 | 观察到实际 staging 文件已写 `133120` 字节、尚未达到完整归档大小时取消；进程等待被取消并回收；Operation `needs_verification`，无备份记录、无最终文件和 staging。原请求仍禁止重放。 |
| 失败与取消后的源实例 | 再次启动，实际 Docker 读取合成数据探针与写入前完全一致。 |
| 清理 | 仅删除自建实例；生产归属核实结果 `missing`。独立磁盘 detach 成功并删除本轮磁盘映像。JSON 中 `ownedResourcesDeleted=true/privateDiskDetached=true`。 |

首轮命令因 QA 脚本误用 `hdiutil create -format UDRW` 失败；本机帮助明确空白映像需 `-type UDIF`。当轮自建设备已清理，该失败没有记为产品失败或验收通过。修正命令后磁盘不足演练通过；再加入实际在途取消并完整重跑，结果如上。取消是 Python 任务取消和生产 subprocess 回收，不冒充宿主进程 `SIGKILL`；随后[真实恢复解包中 SIGKILL](2026-09-24-restore-transfer-interruption.md)另行通过；恢复目标磁盘不足与取消恢复仍未验证。

逐项审计还发现 T17/T18 的面板说明缺失：创建备份前没有显示本机未加密及账号/私密数据边界，恢复前没有说明登录状态、DRM、私钥不保证可用。新增 `describes private local storage and restore limits before either action`，直接渲染真实 BackupPanel，要求操作按钮具有对应可访问说明。

```text
npm exec --offline --yes --package=node@22.23.2 -c 'npm --workspace @autoflow/desktop test -- src/renderer/domains/android/tests/ManagementTools.test.tsx -t "describes private local storage"'
RED: 1 failed, 25 skipped；创建按钮 Received accessible description 为空。

npm exec --offline --yes --package=node@22.23.2 -c 'npm --workspace @autoflow/desktop test -- src/renderer/domains/android/tests/ManagementTools.test.tsx'
GREEN: 1 file, 26 passed in 1.66s。
```

最小修复只加两段可见说明，并通过 React `useId`/`aria-describedby` 绑定各自按钮；不增加确认步骤、不改变备份或恢复调用。

```text
npm exec --offline --yes --package=node@22.23.2 -c 'npm test -w @autoflow/desktop -- --maxWorkers=1 --testTimeout=15000'
exit 0: 424 files, 5626 passed in 894.27s。

npm exec --offline --yes --package=node@22.23.2 -c 'npm run typecheck && npm run lint && npm run openapi:check && npm run build'
exit 0: tsc / ESLint / OpenAPI 差异检查通过；renderer 11751 modules，built in 54.79s。

uv run --project apps/backend ruff check docs/qa/android-management/scripts/disk-full-smoke.py
exit 0: All checks passed!
```

构建仍提示既有 zod PURE 注释与 Studio 静态/动态混合导入；未将这些非失败提示改写成零警告。后端生产代码与测试未改，本轮 Android 聚焦再次执行，全量沿用相同后端树的 4031 passed / 26 skipped。

本轮另执行目标中的原 Android 聚焦命令：在 `apps/backend` 执行 `uv run pytest tests/contract/test_android*.py tests/unit/test_android*.py tests/integration/test_android*.py -q`，exit 0，`447 passed, 2 warnings in 29.43s`。UI 修改前全部 Android 前端为 `14 files/135 passed in 27.61s`；此旧局部数字不冒充说明增量后的全量结果。Alembic 仍唯一 head `am01_management_operations`。
