# 安卓模拟器管理验收证据（2026-09-22）

- 状态：`partial`；代码、契约和真实基础 ReDroid 链路已验证，Google 组件、测试 APK、批量压力和手动原生窗口仍 `blocked`。
- worktree：`codex/android-management-complete`，起点 `a92f0688f206d4339ff4468c1871f3ccdd6816dc`。
- 代码交付提交：`432d1cdc`；OpenAPI 生成类型与本提交一致。
- 主工作区既有 Studio 未提交改动未复制、未修改。

## 已执行

| 类别 | 命令 | 实际结果 |
| --- | --- | --- |
| 后端 Android/迁移/契约 | `cd apps/backend && uv run pytest tests/contract/test_android*.py tests/unit/test_android*.py tests/integration/test_android*.py -q` | `175 passed, 1 warning` |
| 前端 Android（历史基线） | `cd apps/desktop && npm exec vitest run src/renderer/domains/android/tests` | 旧记录已由本轮 13 files/47 passed 覆盖 |
| 前端类型 | `cd apps/desktop && npm run typecheck` | 通过 |
| 前端 Android 最终聚焦回归 | `cd apps/desktop && npm exec vitest run src/renderer/domains/android/tests` | `13 files, 47 passed`（含批量失败项 retryFailed 幂等请求、镜像删除未知结果核实、服务端镜像验证入口） |
| 前端 lint | `cd apps/desktop && npm run lint` | 通过 |
| OpenAPI | `npm run openapi:generate`、`npm run openapi:check` | 通过 |
| 前端 build | `npm run build` | 完成并有依赖注释 warning；本轮未重复构建 |
| smoke 参数保护 | `cd apps/backend && uv run pytest tests/unit/test_android_management_smoke_args.py -q` | `2 passed`；带授权参数时明确输出 blocked |
| 新增契约集合 | `cd apps/backend && uv run pytest tests/contract/test_android_{apps,backups,images,templates}.py -q` | `4 passed, 1 warning` |
| 本轮增量契约/单元 | `cd apps/backend && uv run pytest tests/contract/test_android_images.py tests/contract/test_android_management_diagnostics.py tests/unit/test_android_images.py tests/unit/test_android_diagnostics_export.py tests/contract/test_android_management_operations.py -q` | `32 passed, 1 warning` |
| 迁移 | Alembic 临时 SQLite 升级及旧 Android 历史回归 | head=`am01_management_operations`，通过 |
| 结构检查 | `npm run test:structure` | `4 passed` |
| 全脚本基线 | `npm run test:scripts` | `95 tests: 92 passed, 3 pre-existing Studio inventory/reference failures` |
| Lima/Docker/binderfs 环境 | `limactl start autoflow-redroid`；`limactl shell autoflow-redroid sudo sh -lc 'mkdir -p /dev/binderfs && mountpoint -q /dev/binderfs || mount -t binder binder /dev/binderfs'`；`limactl shell autoflow-redroid sudo docker info --format '{{.Architecture}} {{.OperatingSystem}} {{.NCPU}} {{.MemTotal}}'` | Lima `Running`，Linux arm64，6 CPU，约 7.9 GiB；`/dev/binderfs/{binder,hwbinder,vndbinder}` 存在；`MacAndroidRuntime.environment()` 返回 `available: true` |
| 真实基础实例准备 | `cd apps/backend && uv run python -m autoflow.bootstrap.android_prepare --data-dir /tmp/autoflow-android-real-20260922b --scrcpy-archive /Users/zhangtiancheng/.autoflow/android-runtime/scrcpy-macos-aarch64-v3.3.4.tar.gz` | 创建并连接真实 ReDroid Android 13 ARM64 实例；`androidStatus=ready`；固定 digest `sha256:5a42a569ee1d7c71796c0385e906cbaa4c3e0a162a56d9f26b29bdb1befac13b` |
| 真实生命周期/画面/应用 | 临时实例上执行 `connect`、`app_info`、`android_screenshot`、HOME、stop、再次 connect | 应用清单 `102` 项；截图尺寸 `720x1280`；当前包 `com.android.launcher3`；停止后状态 `exited`，再次连接恢复 `ready` |
| 真实备份恢复 | 临时实例通过 ADB 写入 `real-backup-check`，停机后 `backup_volume`、`restore_volume`，再读取目标卷 | `backup_bytes=25472000`；源/恢复标记均为 `real-backup-check`；归档字节数一致；容器/卷标签核验后已清理 |
| 真实双实例隔离 | 两个独立临时 workspace 同时创建，分别 `for_device`、连接、发送 HOME、截图和读取应用 | ADB serial `127.0.0.1:58272` 与 `127.0.0.1:58287` 不同；两台均 `720x1280`、`102` 应用；按各自 workspace/device 标签清理 |
| 本轮管理 API 复核 | `android_prepare` + sidecar `environment/capabilities/management/devices`；真实 stop、backup、cleanup、delete | workspace/device 归属一致；环境 `available=true`、6 CPU/7921 MiB；stop operation `succeeded`；backup `201 Created`、`state=available`、`18585260 bytes`；cleanup `200/state=succeeded`；删除后标签过滤容器/卷均为 `0`；Lima 最终 `Stopped` |
| 最终运行时静态复查 | `limactl start/stop autoflow-redroid`；binderfs 检查；`docker info`；固定 digest `docker image inspect` | Lima 真实启动时 `Running/aarch64`；`aarch64 Ubuntu 24.04.4 LTS 6 8306663424`；输出 `binderfs-ok`；固定镜像实际返回 `arm64 linux`；随后已停止 |

## 已覆盖

只读环境诊断、逐项 `unknown`、workflow=false；独立 Android operation 表、workspace/request 幂等、摘要冲突 409、状态栅栏、needs_verification、全量计数分页和迁移；管理首页不请求 workflows/allocations/runs 或旧 `/api/v1/android/devices`；现有 provider 归属校验、生命周期锁、generation/sequence；控制会话 clientSessionId/generation heartbeat；镜像登记、引用保护、来源校验、拉取引用安全校验、服务端镜像元数据验证和精确 imageId 删除核实、模板 revision 归档；persistent 默认创建并以稳定错误拒绝 temporary；停机备份前置条件、受限目录/权限、归档摘要/字节数/镜像一致性和路径安全校验；诊断导出采集环境/设备/操作快照并递归脱敏；容量未知和预留阻止准入；观察器活跃 3 秒刷新、失败指数退避和 10/45 秒陈旧规则；应用操作 requestId/保护包边界、真实 Android 平台包名解析；清理预览摘要冻结并执行受控删除；批量操作 UI 冻结设备 revision、失败项 retryOf lineage 和稳定请求号；smoke 授权保护；前端诊断面板、管理快照、批量操作、备份入口、镜像/模板和会话控制器。备份适配使用 Docker volume copy，不依赖 Android 镜像提供独立 `/bin/sh`。

## 阻塞项与风险

- 主机的 Lima/Docker-in-Lima 和基础 ReDroid 已完成真实核验；宿主 Docker socket 仍不作为本模块运行时入口。测试实例使用独立临时 workspace，完成后按 workspace/device 标签删除。
- Google 组件镜像、专用测试账号、可分发测试 APK 和人工原生 scrcpy 窗口未具备，因此 GApps 登录、免费测试应用安装/启动、中文输入、窗口交互仍 `blocked`；没有用 mock 结果代替。
- `npm run test:scripts` 的三个 Studio inventory/reference 失败与本模块无关，未扩大范围修复；依赖安装/Node 版本会影响其复现。
- 全量 `cd apps/backend && uv run --group build pytest -x -q` 完成 `262 passed, 1 warning` 后，在既有 `tests/contract/test_proxy_runtime.py::test_runtime_mounts_proxies_but_never_publishes_host_contract` 失败；该 proxy compatibility 断言不在 Android 范围，安卓聚焦集合不受此阻塞。
- 镜像拉取和内容删除已接入 Mac runtime 的受限 Docker pull/inspect/rm 适配和兼容性门禁；服务端验证忽略客户端结果并核对精确 digest、架构和 OS，未知删除可按原 requestId 核实。本轮真实使用了缓存基础镜像并核对固定 digest，网络拉取、内容删除实机和 GApps 候选仍未验收。观察器规则已接入后台启动/关闭调度；应用列表已接入版本/系统应用标识、搜索、停止、卸载、清除数据、确认和结果未知复核。
- 备份已接入受限数据卷 copy 归档、摘要、路径/特殊文件校验，并真实完成数据标记写入、停机归档和新卷恢复；缺失适配器、缺失精确镜像、旧 manifest 或损坏归档会明确失败，不发布“恢复成功”。清理按实际 workspace identity 汇总保留数据和备份，预览包含不可逆影响与引用指纹，执行前重检并分别走设备删除操作或受控备份目录删除。
- AM3 的批量压力和人工窗口验收仍未执行；应用停止/卸载/清除的真实破坏性动作未执行，保持保护边界。诊断导出当前只采集管理快照和只读环境检查，未接入高级日志 IPC/时间窗口，仍不宣称完整日志导出。
