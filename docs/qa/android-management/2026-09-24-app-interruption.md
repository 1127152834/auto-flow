# APK 执行中断、重启核实与应用数据保留

- 日期：2026-09-24；状态：confirmed（本文场景）；整体目标active/partial。
- 基线：隔离分支`codex/android-management-complete@8520a655`；本轮仅增加真实QA脚本和证据，无生产、契约、迁移或前端修改。唯一迁移head仍为`am01_management_operations`。三份既有Studio文档不属于本次提交。
- 环境：Apple Silicon macOS、实际Lima ARM64/Docker/ReDroid，固定imageId `sha256:5a42a569ee1d7c71796c0385e906cbaa4c3e0a162a56d9f26b29bdb1befac13b`。
- 输入：本地Shizuku APK，包`moe.shizuku.privileged.api`、versionCode1086、2571773bytes、SHA256 `6e273ab0e991c4e79bc8b1bbb9b9dd739ccac1a8712a541a214078886b7b790f`。不提交APK或账号，不作为GApps商店链证据。

## 方法与观测边界

[脚本](scripts/app-interruption-smoke.py)复用现有认证HTTP sidecar启动/关闭、生命周期和进程树故障助手。每轮使用新临时工作区和新设备，操作通过真实HTTP、SQLite与生产Mac适配器运行。

脚本从客体实际`ps`捕获`cmd package install -r`，核实APK已完整上传、真实安装命令存活、完成标记尚不存在，再用SIGSTOP短暂停住该命令客户端以固定故障时点；没有暂停PackageManager服务，也没有伪造完成标记或数据库回执。随后只终止身份匹配的实例SSH tunnel，或SIGKILL本轮HTTP服务的全部自有进程组，再按客体PID/birth恢复该客户端（若仍存活）。这是安装命令执行中的真实链路/进程中断；不声称已测量PackageManager正在写入的具体文件偏移。

最终轮先正常安装，再按实际应用目录UID/GID写入唯一测试探针，随后中断覆盖安装。重启完整HTTP服务后，以原session/generation/requestId重放和显式核实；读取应用包版本及原应用数据。

## 实际结果

| 故障 | ADB链路断开 | HTTP服务进程树强杀 |
| --- | --- | --- |
| 设备 | `170808fa-51d9-41de-b9dd-5128d68689ee` | `f0271721-cdef-48ee-a215-b65b5288a161` |
| 安装命令PID | 2366 | 2312 |
| 已上传APK | 2571773bytes | 2571773bytes |
| 故障前完成标记 | 不存在 | 不存在 |
| 注入 | 实例SSH PID53727、birth匹配后SIGTERM | 2个已核实自有进程组SIGKILL |
| HTTP结果 | 502 | RemoteProtocolError |
| 故障后回执 | needs_verification | running |
| 重启后原请求重放 | 410，旧会话失效 | 410，旧会话失效 |
| 显式核实 | 503、needs_verification | 503、needs_verification |
| 再次取得控制权 | 409拒绝 | 409拒绝 |
| 原包/应用数据 | versionCode1086；探针不变 | versionCode1086；探针不变 |

[最终原始结果](2026-09-24-app-interruption/reinstall.json)。关键保护是：即使相同包版本已存在，也不能证明这次覆盖安装成功；缺少完成标记时继续保持未知，没有自动重放、释放占用或显示成功。恢复到可核实的安全状态不等于恢复为idle，本次两项均有意保持隔离。

前一轮新安装也完成两种故障，见[新安装结果](2026-09-24-app-interruption/fresh-install.json)，同样核实503并拒绝控制。首次观察器逐个读取/proc，未捕获安装命令，等待90秒超时；实际安装已成功，该轮不计中断通过。读取实际镜像`/system/bin/pm`确认`cmd package "$@"`后改为单次ps快照，未修改生产代码或放宽故障断言。[首次结果](2026-09-24-app-interruption/observer-miss.json)保留status=started。

三轮5台自建设备已清理，生产`verify_deleted`逐台返回missing，见[跨轮清理审计](2026-09-24-app-interruption/cleanup-audit.json)。未知场景的最终清理属于QA夹具销毁：先关闭自建服务，再按生产workspace/device标签和卷挂载归属校验，对本轮精确容器ID/卷名删除。未绕过产品保护去释放回执，不将夹具销毁冒充产品“恢复成功”或“删除流程通过”；临时数据库保留原回执供审计。

## 验证命令

| 命令 | 实际输出 |
| --- | --- |
| `apps/backend/.venv/bin/python docs/qa/android-management/scripts/app-interruption-smoke.py --allow-device-mutation --apk /Users/zhangtiancheng/Downloads/shizuku-v13.6.0.r1086.2650830c-release.apk` | 最终exit0、status=passed；两种覆盖安装中断、数据与版本核对、归属清理通过。 |
| `cd apps/backend && .venv/bin/pytest tests/contract/test_android_apps.py tests/unit/test_android_apk.py tests/unit/test_android_console_lifecycle.py -q` | exit0；32passed、2warnings in0.27s。警告为既有anyio弃用及重复manifest负向测试。 |
| `apps/backend/.venv/bin/ruff check docs/qa/android-management/scripts/app-interruption-smoke.py` | exit0，All checks passed。初次仅脚本import/BLE001问题已修正。 |
| 脚本`--help`；缺少`--allow-device-mutation`且APK路径不存在 | help exit0；缺授权exit2，在读取APK/设备变更前拒绝。 |
| 三轮生产`runtime.verify_deleted`审计 | 5台均missing。 |

本轮没有生产修改，沿用8520a655已验证的后端4041passed/26skipped、前端5631passed及类型/lint/OpenAPI/build，不将其标为本轮重新执行。

## 状态映射与剩余项

T07.3的基础链、输入/切端/数据/删除隔离由既有[AM1真实链](2026-09-23-am1-real-control-retention.md)及[桌面控制](2026-09-24-desktop-control.md)证明，本轮补真实安装执行中断及完整HTTP重启后的安全核实；这些是分轮真实场景，设备ID分别归档，不宣称在一个连续桌面录制中完成。T07任务仍有历史RED输出缺证。T15/AC18仍partial，桌面停止/清数据/卸载确认流尚待真实界面验收。

精确窗口/缩放、镜像桌面删除与拉取断线、回退演练、前台/隐藏页探测指标仍未全部完成；十实例内存预算和专用GApps条件仍blocked。原操作缺少客体终态证明时保持未知是本轮确认的边界，不可通过清除数据库标记绕过。
