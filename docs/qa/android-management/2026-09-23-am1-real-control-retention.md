# AM1 真实控制、应用与保留卷验收

- 日期：2026-09-23；状态：`confirmed`（下列真实链），AM1 整体验收仍为 `partial`。
- 环境：macOS arm64；现有 Lima `autoflow-redroid` 从 `Stopped` 启动；本轮在 `/tmp/autoflow-android-control-rAHSP7` 隔离数据目录创建 `ae1ea169-9b7c-4751-96a0-c896fffd5c13`。容器、卷均按工作区和设备标签限定，未修改已有用户设备或卷。
- 镜像 ID：`sha256:5a42a569ee1d7c71796c0385e906cbaa4c3e0a162a56d9f26b29bdb1befac13b`；卷：`autoflow-android-ae1ea169-9b7c-4751-96a0-c896fffd5c13-data`。本轮实例在记录时仍为 `ready`，用于后续受控验收；完成后须按标签删除本轮资源。

使用生产 `AndroidConsole`/`AndroidStream`、认证的本机 HTTP sidecar 和一次性守护脚本执行。脚本以 `--workspace` 与 `--allow-device-mutation` 限定目标，并要求隔离库恰有一台且工作区哈希一致。原始截图、UI XML、APK 字节和输入文本仅留在本机临时目录，不入仓库。

| 实验 | 实际输出与核验 |
| --- | --- |
| `limactl start autoflow-redroid`；`uv run python -m autoflow.bootstrap.android_prepare --data-dir <隔离目录> --scrcpy-archive <本机固定包>` | VM 返回 `READY`；新实例 `androidStatus=ready`，ADB 实例由新工作区容器与卷提供。 |
| 一次性控制脚本 `PYTHONPATH=src uv run python /tmp/android-am1-control-real-smoke.py --workspace <隔离目录> --allow-device-mutation` | `status=passed`；嵌入式画面、HOME 按键、原生窗口打开、返回嵌入式、显式结束、重进、无心跳超过 30 秒后回收、再次重进/结束均通过；截图 `653948` bytes；实例保持 `ready`。 |
| 一次性输入脚本 `/tmp/android-am1-chinese-input-smoke.py`，同样使用隔离目录与授权旗标 | `inputTransport=completed` 且 `unicodeVisibleInUiXml=true`；本机截图人工核实文字显示在设备输入框。仓库不保留原图或输入值。 |
| 一次性 HTTP 脚本 `/tmp/android-am1-http-restart-smoke.py` | `status=passed`；第一进程会话重启后 `GET` 为 410，第二进程仍能读取同一设备并创建/结束新会话。首次探测误沿用宿主代理返回 502；脚本对回环 HTTP 设 `trust_env=False` 后重跑通过，此 502 不计为产品错误。 |
| 一次性应用脚本 `/tmp/android-am1-real-apk-smoke.py` | 本地 APK 的包 `moe.shizuku.privileged.api`、versionCode `1086`；安装前清单不存在，HTTP 安装后包/版本读回一致，启动、停止、清数据、卸载均成功，最终清单不存在。无账号或商店下载参与。 |
| 一次性保留卷脚本 `/tmp/android-am1-retained-real-smoke.py` | `status=passed`；固定测试探针 SHA-256 为 `ec71875896933e03b3f433e118ae483b5bb63088f44b37fd8e09d7ebebde331f`。写入→停机→启动读回→再停机→移除容器但保留卷→普通 `start` 返回 409→管理快照提供 `restore`→重建后原卷、探针摘要一致。 |
| 一次性双实例隔离脚本 `/tmp/android-am1-two-device-isolation.py` | 在同一隔离工作区创建第二台停机实例 `c45be10c-dbde-4d90-ad76-ca4960117e58`，核实各自容器和卷的归属标签及不同 ID；通过公开 HTTP `deleteData=true` 删除第二台后，其容器、卷均不存在，第一台仍 `ready` 且容器/卷身份不变。JSON `status=passed`，独立数据库后验 `post-check passed: first ready; second deleted/missing`。 |

保留卷脚本第一次把客户端 `requestId` 误当设备投影的 `operation.id`，导致等待超时；持久记录证实停止操作早已 `succeeded`。修正游标后，第二次在观察器刷新前读取了旧快照；等待快照收敛后，连续完整链通过。失败的两次脚本结果不冒充产品失败或通过。

双实例脚本本体完成后，外层 shell 包装误把结果变量命名为 zsh 只读的 `status`，因此外层退出 1；JSON 已完整写出且后验重新打开数据库确认第一台可用、第二台已删除。此包装错误不计作产品通过或失败，也没有重新执行破坏性步骤。

新增 `restore` 公开动作前的 RED：`/tmp/android-am1-retained-restore-backend-red.log` 为 `2 failed`（契约拒绝动作、保留实例 `start` 未被拦截）；`/tmp/android-am1-retained-restore-frontend-red.log` 为 `2 failed, 45 passed`（缺按钮和确认入口）。GREEN：后端 `16 passed, 1 warning`，前端 `2 files, 47 passed`；缺卷拒绝回归另有 `1 passed`，确认没有创建空白替代卷。生成的 OpenAPI 类型同步了 `restore` 枚举。首次完整后端回归 `3971 passed, 1 failed, 26 skipped`，失败为既有“未发布恢复意图优先拒绝”的集成断言；调整共享校验顺序后，相关 29 项通过，第二次完整后端回归 `3972 passed, 26 skipped, 2 warnings in 855.84s`。完整前端回归 `424` 文件、`5621` 项通过。

| 本切片门槛 | 实际结果 |
| --- | --- |
| `cd apps/backend && uv run pytest -q` | exit 0；`3972 passed, 26 skipped, 2 warnings in 855.84s`。两条 warning 为 Starlette/AnyIO 废弃别名和故意重复 Manifest 的 ZIP 夹具。 |
| `cd apps/backend && uv run ruff check src tests`、`uv run python -m compileall -q src tests` | 均 exit 0；Ruff `All checks passed!`，编译无错误输出。 |
| `cd apps/backend && uv run alembic -c src/autoflow/infrastructure/database/alembic.ini heads` | exit 0；唯一 head `am01_management_operations`。 |
| `npm --workspace @autoflow/desktop test -- --maxWorkers=1 --testTimeout=15000` | exit 0；`424 Test Files passed, 5621 Tests passed in 805.73s`。单 worker 避免并行主机负载导致的无关 5 秒测试超时。 |
| `npm run openapi:check`、`npm run typecheck`、`npm run lint` | 均 exit 0；无类型、生成漂移或 lint 错误。 |
| `npm run test:structure`、`npm run build` | 均 exit 0；结构检查 `4 pass`，Electron/Vite `built in 40.15s`。 |
| `npm run test:scripts` | exit 0；`95 pass, 0 fail`。重写的三份原有 Studio 改动已恢复并与原 SHA-256 一致；额外被脚本重写的、原本干净的 `capabilities.json` 已还原至 HEAD。 |
| `git diff --check` | exit 0；无空白错误。 |

实机安装后的客体 `/data/local/tmp` 检出 5 个 `autoflow-operation-*` 完成标记；成功安装未留下 `autoflow-apk-*`，但命令标记没有在持久回执落盘后清理。这是 T19 的软件缺口，不能把应用链通过等同临时文件生命周期完成。

剩余：桌面 UI 的长名称、200% 缩放、真实网络断开后旧数据只读、受控硬中断及当前隔离实例最终清理尚未执行。专用 Google 镜像/账号/下载链继续 `blocked`。
