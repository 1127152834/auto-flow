# 安卓工作流与原生交接：Mac 验证记录

2026-09-13 · confirmed：正式模块已实现，Mac 本地验证通过。置信度：高（下表已测项）；未测边界单列。

## 交付与入口

实现位于 `codex/android-workflow-handoff` 独立工作树，基于正式 M3。主工作区的另一项 M4 正在修改运行契约、执行器和数据库迁移，本次不覆盖或提交它的工作。

已准备工作区：`/Users/zhangtiancheng/Documents/projects/autoflow-android-handoff/.local/android-handoff-workspace`。
已构建应用：`apps/desktop/dist/mac-arm64/AutoFlow.app`。本地开发包，未签名/公证。

在该工作树运行，或双击启动脚本：

```sh
./scripts/open-android-demo.command
```

1. 主窗口选择“安卓设备”，确认“安卓工作流测试”可用。
2. 从总览进入“工作流工作台”，点击“打开”，选择“安卓人工接管示例”。
3. 顶栏选择“安卓工作流测试”，运行当前草稿。
4. 到“人工处理”节点后点击“打开操作窗口”，在独立 Mac 窗口操作 Android。
5. 回工作台点击“完成并继续”。关闭窗口本身不会继续；可重开，倒计时不会重置。
6. 自动 BACK 和第二张截图完成后，在“只读结果”查看截图。Android 和数据卷保留。

运行页使用真实 API；截图是工作流产物，手动输入由独立 scrcpy 窗口处理。设备页首版提供状态查看，创建仍用准备命令。没有引入新的批量调度器。

## 环境与保留资源

| 项目 | 实际值 |
| --- | --- |
| Mac | Apple Silicon / arm64；macOS 26.4.1（25E253） |
| Python | 正式服务 Python 3.11；冻结 sidecar 单独实测 |
| Linux | Lima 2.2.0，VM `autoflow-redroid`；Ubuntu 24.04 ARM64；6.8.0-134-generic |
| binder | `/proc/filesystems` 包含 binder；Android 实际启动成功。宿主不需要预置 `/dev/binderfs` 目录 |
| ADB / scrcpy | ADB 36.0.2-14143358；固定官方 scrcpy 3.3.4 |
| Android | `redroid/redroid:13.0.0_64only-latest`，Linux arm64，软件渲染 |
| 镜像 image ID | `sha256:5a42a569ee1d7c71796c0385e906cbaa4c3e0a162a56d9f26b29bdb1befac13b`（image ID，不冒充 registry digest） |
| 设备 ID | `f4b86f69-bf45-4adf-853d-b9c687ab3985` |
| 新容器 / 卷 | `autoflow-android-f4b86f69-bf45-4adf-853d-b9c687ab3985` / 同名加 `-data` |
| 配置 | 1 CPU，1536 MiB，720 × 1280，dpi 320 |

旧 Demo 的 `afd-5a7beadf6de2468d`、`afd-635e8a215e194178`、`afd-ef3857a550924052` 均仍在运行。本次没有导入、删除、重建这些设备或改动它们的数据卷。正式设备使用 `io.autoflow.android.*` 标签，与 Demo 筛选隔离。

## 已验证结果

| 场景 | 证据 / 结果 |
| --- | --- |
| 源码 HTTP 完整流程 | 5 节点完成、2 PNG、重复打开无新会话、重复继续只发一次 resumed、最终 idle 无 owner；[source/result.json](android-workflow-handoff-qa/source/result.json) |
| 真实失败处理 | 不存在应用 → `ANDROID_APP_UNAVAILABLE`；旋转坐标基准 → `ANDROID_SCREEN_CHANGED`；正常 tap、停止等待、30 秒人工超时均返回真实结果并释放占用；[source/faults.json](android-workflow-handoff-qa/source/faults.json) |
| 冻结 sidecar | 重跑同组流程与故障测试；额外在原生窗口打开时 SIGKILL 本测试 sidecar，重启为 interrupted，不重放，设备恢复 idle；[frozen/faults.json](android-workflow-handoff-qa/frozen/faults.json) |
| 正式桌面源码 | 页面运行、原生键盘进入 Connected devices；关窗仍 waiting_manual；显式继续后 BACK/截图成功；[关窗等待](android-workflow-handoff-qa/desktop/04-closed-still-waiting.jpg) |
| Mac 打包应用 | 从 app.asar 界面启动冻结服务，原生键盘进入 Connected devices，显式继续并完成；[原生页](android-workflow-handoff-qa/desktop/06-packaged-native.jpg)、[完成页](android-workflow-handoff-qa/desktop/07-packaged-completed.jpg) |
| 画布状态变化 | 修复节点重新派生时 measured 尺寸丢失；组件测试和打包真实运行均验证节点保持可见 |
| 并发 / 恢复替身测试 | 数据库双占用仅一个成功；跨工作区同 VM 锁；人工输入门控；过期 handoff 与 requestId 冲突；两个连续人工节点旧回执持久化；启动取消；继续中停止；数据库失败不派发；清理失败隔离；PID 复用不误杀；未知身份隔离；worker EOF 不进入下一节点 |
| 浏览器回归 | 原有六节点真实执行、提取、PNG、弹窗、停止、记录恢复 8 组通过；M3 实际 worker 启动/取消/崩溃回收 5 组通过；[回归记录](android-workflow-handoff-qa/regression/) |

`tap.png` 是紧接 input 命令后的单帧，可能处于动画或焦点变化；命令完成不等于页面视觉稳定。本次未引入 UI 元素等待节点。

前序 Demo 的真实鼠标首开/重开/移动/缩放已由用户确认正常。本轮正式应用的键盘输入和原生交接已实测；CUA 合成鼠标事件仍存在此前偏移，未将它记作修复或再次人工验收。

## 自动检查

- 完整 Python 测试最终结果见 `android-workflow-handoff-qa/checks.txt`；包含 API、迁移、并发和错误分支。
- React 415 项测试通过；类型检查、ESLint、Ruff、mypy（169 源文件）、OpenAPI 一致性通过。
- 脚本测试 12 项、结构测试 3 项；前端构建、PyInstaller 构建、Mac `package:dir` 通过。
- 浏览器真实执行与 M3 worker 回归日志保存于本记录的 `regression/`。

## 准备另一专用工作区

前提是本机已有 `autoflow-redroid` Lima VM、可用 Docker/binder、缓存的上述 arm64 Android 13 镜像，以及 PATH 中的 adb/limactl/ssh。准备命令不自动更换内核或搭建虚拟机。

```sh
uv run --directory apps/backend python -m autoflow.bootstrap.android_prepare \
  --data-dir /absolute/path/to/android-test-workspace
```

scrcpy 由固定官方地址下载，SHA-256 校验后解压；也可传 `--scrcpy-archive /absolute/path/to/verified.tar.gz`。源码/许可与实际依赖版本见 [NOTICE](../references/android-runtime/NOTICE.md)。运行时不需要 `reference` Demo 服务。

该命令创建独立容器、数据卷和数据库记录，先写准备日志；失败时保留已创建资源的名称，不能把部分失败当作完成。已有设备时返回登记记录，不复制或重新创建。工作区路径是归属身份的一部分，不能直接搬目录并冒充新归属。

通过应用“设置”选择此目录可创建标准工作区标记；当前交付目录已完成这一步。`open-android-demo.command /absolute/path` 可打开指定的已初始化工作区。

## 恢复方式

运行中优先点击“停止运行”；清理未确认时保留 owner 和恢复状态，可重试停止。关闭连接只关闭本次 scrcpy/SSH 与专用 ADB serial，不执行 `adb kill-server`，不停止 Android。

sidecar 崩溃后，启动时核验持久化 PID/创建时间和 Android 命令完成标记；无法确认则隔离，不接收新运行。旧命令确认已完成时才能释放占用。退出应用后可针对同一工作区执行：

```sh
uv run --directory apps/backend python -m autoflow.bootstrap.android_prepare \
  --data-dir /absolute/path/to/android-test-workspace --recover
```

若输出仍报恢复失败，保留记录和资源进行诊断；本轮没有提供强制抢占或强制清空按钮。未确认的 spawn 或 Android 命令会继续阻塞，不能伪装已清理。

## 边界与后续接入

本轮仅 Mac ARM64、单设备、纯安卓顺序图；Windows/Intel Mac、摄像头、root 变化、环境伪装、批量/混合图不在本切片。未进行宿主断电、内核崩溃或长时间稳定性测试。

代码交付在独立分支。与正在开发的 M4 合并时需重新检查节点目录、运行记录/产物字段和迁移头；M4 的 `0007_workflow_artifacts` 与本分支 `0007_android_devices` 各自从 0006 分叉，应增加显式 merge revision，不能改写已应用的迁移或覆盖 M4。当前可运行包和专用数据库不受主工作区未完成改动影响。

## 验证过程中的波动

一次并行构建时，原有 browser worker 的 50 毫秒清理预算测试出现清理未确认；单独复跑其三种状态通过，最终全量结果见 checks.txt。未放宽运行时清理确认或把失败伪装成功。

Profile 表单原有测试在错误文案出现后立即断言焦点，但组件通过 requestAnimationFrame 延后聚焦；将该断言改为 waitFor，保留必须聚焦的行为验证。迁到正式 M3 基线后去掉了临时基线的一项旧草稿测试，前端正式计数为 415。
