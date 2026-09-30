# 恢复清单与目标身份增量验证

- 日期：2026-09-23；状态：confirmed（本增量），AM1–AM4 完整目标仍 `partial`。
- 基线：隔离工作区 `codex/android-management-complete@eb1f83fb` 加本次增量。需求来源为安卓管理规格 T18/T20 和真实恢复隔离验收。
- 原始真实结果：[restore-manifest-result.json](2026-09-23-restore-manifest-result.json)；[实验脚本](2026-09-23-restore-manifest-smoke.txt)。

## 行为与证据

恢复时先核对备份属于当前工作区、已登记版本是整数 1，归档恰好包含 `data.tar` 与 `manifest.json`，清单版本、源设备、镜像和配置与目录记录逐项一致。即使改写清单并重算摘要，也不能改变源身份或配置。写目标卷前再次核对目标是新的 `pending` 恢复实例，请求 ID、备份 ID、generation、禁用自动启动及运行时工作区均匹配。

按 RED → GREEN 运行：伪造清单 4 项先失败；布尔版本及跨工作区 2 项先失败；直接调用服务写入非恢复目标 2 项先失败。修复后：

```text
cd apps/backend && uv run pytest tests/unit/test_android_backup.py tests/integration/test_android_backup_restore.py tests/integration/test_android_cleanup_files.py -q
# 44 passed, 1 warning in 5.72s
```

真实 macOS/Lima/ReDroid 命令：

```text
uv run --project apps/backend python /tmp/autoflow-restore-manifest-20260923.py > /tmp/android-goal-manifest-real.log 2>&1
# exit 0; JSON status=passed
```

该脚本在独立工作区经真实 FastAPI 路由和 Docker 数据卷注入部分写入/连接超时；恢复操作进入 `needs_verification`。普通 recover 后目标保持 `pending`，start/restart/restore/control/backup 拒绝；原请求重放为 409。正常 HTTP 恢复与同请求重放为 202；目标启动后 ADB 读回 `restore-isolation-proof`，UID 10001、GID 2000、mode 0640，源测试文件内容不变。原始结果中的 `sourceUnchanged=true` 仅指脚本比较的 `restore-proof` 文件，不代表源卷全量校验。仓库脚本与当时执行的 `/tmp/autoflow-restore-manifest-20260923.py` 的 SHA-256 均为 `e9045e83c4590fe347be03df5118f64e3109c9ed44c0d2522a76334e0aa4a5b3`。三台自建实例最终均 `deleted=true`、容器 0、卷 0；Lima 已停止。受控连接超时并非 `kill -9` 或断电实验。

## 仍未完成

源卷 xattrs 的可信探测、真正进程硬中断、APK 临时文件清理、高级脱敏日志、AM1 原生窗口/重启、AM2 Google 组件及 AM3 压力和应用动作、T20 完整演练与最终全分支审查均未据此标记完成。网络/账号条件缺失记 `blocked`；可实施但未验证的软件项记 `not_run`。
