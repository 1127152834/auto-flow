# 真实 HTTP 恢复解包中 SIGKILL

- 日期：2026-09-24；状态：`confirmed`（本项实际执行），AM4 总验收仍 `partial`。
- 基线：`codex/android-management-complete@30eb0926` 加 UI/QA 文档增量；后端生产树未修改。
- 平台：Apple Silicon macOS、Lima `autoflow-redroid`、真实 Docker/ReDroid；固定镜像 `sha256:5a42a569ee1d7c71796c0385e906cbaa4c3e0a162a56d9f26b29bdb1befac13b`。
- [自包含可运行脚本](scripts/restore-interruption-smoke.py)。本实验使用真正的认证 HTTP、生产数据库与文件流适配器，不替换方法或返回值。只对脚本 `start_new_session=True` 启动的独立后端进程组发送 SIGKILL。

```text
uv run --project apps/backend ruff check docs/qa/android-management/scripts
uv run --project apps/backend python docs/qa/android-management/scripts/restore-interruption-smoke.py --allow-device-mutation
```

先检查宿主和客体均至少剩余 2 GiB，再从缓存镜像通过 HTTP 登记/创建独立实例。写入 256 MiB 随机合成探针、计算 SHA-256，停机后由 HTTP 创建备份。恢复使用新 requestId、新设备和空卷；只读客体监视器观察该新卷中的真实探针文件大小。在文件仍远小于 256 MiB 时，杀死本次后端进程组，确认退出码 `-9`，并确认部分文件大小稳定且仍小于完整文件。

重启同工作区的生产后端后，实际断言：

- 原 Operation 为 `needs_verification`，设备 `restoreState=pending`。
- 相同请求得到 409 `ANDROID_RESTORE_REQUEST_REPLAYED`。
- 启动、创建备份、进入控制会话均得到 409 `ANDROID_RESTORE_INCOMPLETE`。
- 原不完整目标经 HTTP 永久删除，并由生产归属核实返回 `missing`。
- 同一备份的新请求恢复成功；启动后目标探针 SHA-256 与源一致。
- 源实例重新启动后探针不变；原备份内文件的 SHA-256 前后不变。
- 清理仅涉及本轮自建实例/卷及本轮备份；目录与文件实际为空。

首次实际中断链 exit 0：备份 `288635307` 字节；文件写到 `1150976` 字节触发杀进程，最终稳定于 `4067840` 字节；结果未知/拦截/新请求恢复/源保护均为 true。该轮三台自建实例已删除；备份随后由生产服务另行删除，目录和最终文件为空。

随后把备份文件摘要前后比对与备份清理纳入脚本并完整重跑，exit 0，`status=passed`；[最终实际结果 JSON](2026-09-24-restore-transfer-result.json)记录：

| 字段 | 实际值 |
| --- | --- |
| 源 deviceId | `b4f42146-30e1-4a73-8d9d-5cf8d3aa8821` |
| 不完整目标 deviceId | `2bbf5cf6-8d1e-558a-bcaf-dd9b8de30494` |
| backupId | `a559f8e8-e993-4d27-9aaa-18a6c04b7549` |
| 备份字节数 | `289382827` |
| 发送 SIGKILL 时文件大小 | `1691648` 字节 |
| SIGKILL 后稳定部分文件大小 | `4124672` 字节，显著小于完整的 `268435456` 字节 |
| 进程退出与重启结果 | `-9`、`needs_verification` |
| 幂等拦截、启动/备份/控制拦截 | `true` |
| 新请求恢复、源/目标探针一致、源备份文件不变 | `true` |
| 自建设备/卷、备份清理 | `ownedResourcesDeleted=true`、`ownedBackupsDeleted=true` |

最终运行前客体剩余 `33593249792` 字节；未填满公共客体文件系统。宿主保留的临时目录只有 QA 数据库、日志与结果等证据，源/目标数据卷与备份归档均已删除。

前置失败如实记录：第一轮脚本未登记镜像，源创建被生产准入拒绝“镜像未在当前工作区登记”；尚未进入恢复。补 HTTP 登记后重跑。该失败记录通过生产 recover→delete 核实为 `missing`，没有降低镜像准入。Ruff 曾指出 QA 脚本 import 排列，修正后通过。

本证据补足“解包过程中断”，不同于之前“解包完成、成功发布前中断”。恢复目标磁盘不足、取消恢复、传输中的备份进程 SIGKILL 和完整桌面确认链仍未验收，不能因本次通过改为通过。
