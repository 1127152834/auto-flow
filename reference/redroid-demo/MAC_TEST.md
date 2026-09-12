# Mac 真实 Android 验证

- 日期：2026-09-13，Asia/Shanghai。
- 状态：**confirmed**。来源：本机命令、真实 Docker/Android 返回值、HTTP API 和浏览器操作；用户本轮明确只测 Mac。
- 入口：**http://127.0.0.1:8081**。启动命令：在本目录执行 `bash scripts/start-mac.sh`。
- 结论：普通 Android 13 和 Magisk Android 13 已实际运行；基础管理、三实例任务、APK 和 shell root 对照可演示。**应用内 root 授权未验证。**

## 实际环境

| 层 | 实测配置 |
|---|---|
| Mac | macOS 26.4.1，Apple Silicon arm64，32 GiB 内存 |
| 虚拟化 | Lima 2.2.0，Apple VZ；VM `autoflow-redroid` |
| VM 配额 | 6 vCPU、8 GiB RAM、40 GiB 稀疏磁盘；未挂载 Mac 主目录 |
| Linux | Ubuntu 24.04.4 LTS arm64，内核 `6.8.0-134-generic`，页大小 4096 |
| 内核能力 | 安装匹配内核的 `linux-modules-extra`，加载 `binder_linux`；`/proc/filesystems` 实际包含 binder，Android 成功启动 |
| Docker | VM 内 Ubuntu 软件包的原生 Engine 29.1.3、Compose 2.40.3；通过本机 Unix socket 管理 |
| Android | 实际 `ro.build.version.release=13`、ABI `arm64-v8a`；软件渲染、memfd |
| 访问 | Mac 8081 → Lima guest 8080；脚本比对 guest/Mac API session ID，确认连到本 VM |

`/dev/binder` 等字符设备未出现不等于本机不支持：本次 binderfs 信号与实际启动均通过。Docker Desktop 的 LinuxKit 内核不作为运行路径，默认 context `desktop-linux` 保持不变。之前的 8080 页面仍是独立 Docker Desktop 管理服务的诊断页。

Lima 还会默认自动转发其他 guest 监听端口到 Mac 回环接口，因此这里不声称只映射了 8081。管理界面的 ADB 地址属于 **Docker 宿主（Linux VM）localhost**；本次 ADB 验证在 VM 内执行，没有依赖 Mac 端的动态 ADB 转发。

## 固定输入

| 输入 | 本次实际值 |
|---|---|
| Ubuntu 镜像 | `release-20260705/ubuntu-24.04-server-cloudimg-arm64.img`，SHA-256 `7df0201546f75b8bcc1044594c806c35749421ad3c9bc1be2a3ab806cfae39cc` |
| Android base | `redroid/redroid:13.0.0_64only-latest`，实际 image ID/digest `sha256:5a42a569ee1d7c71796c0385e906cbaa4c3e0a162a56d9f26b29bdb1befac13b` |
| redroid-script | `a4951b782fc8e06c845d9553bf07bb643fd8c158`，原参考仓库保持干净 |
| Magisk 下载 | 固定脚本引用的 ayasa520 fork：`v30.7/Magisk-v30.7.apk`，12,980,871 bytes；SHA-256 `a1292054b25c31f19f4cdc3f33b8b48020574fc237eabd7633e54193698ac396`；上游 MD5 校验匹配 |
| Magisk 产物 | `autoflow/redroid:13-magisk`，实际 image ID `sha256:0e8b779981d61a11ec1dd230b23dddc454fba2c75794abe8a7583037984e5f8b` |
| 运行版本 | `/sbin/magisk -v` 实际输出 **`30.6:MAGISK:R`**；不能由下载文件名推断为运行版本 30.7 |
| 测试 APK | Fossify Notes 1.7.0，`org.fossify.notes`，官方发布文件 `notes-13-foss-release.apk`，9,528,948 bytes，包含 arm64-v8a |
| APK SHA-256 | `5a56e0e39cc488e1f3b947d3801006d3b7450ec73c67f03195c64c5fd3b6bced`，与 GitHub release asset digest 一致 |

镜像 tag 会变化；上述摘要是此次结果边界。构建报告的 `built_not_boot_verified` 是构建结束时的正确状态；后续启动和 root 证据另存，未改写原始构建报告。

## 真实结果

| 场景 | 结果 |
|---|---|
| 创建与 Android 就绪 | 通过。普通版、Magisk 版实际 Android 13 就绪，返回真实镜像 ID、端口和状态 |
| 启停与数据 | 通过。写入标记后停止、启动、重启，标记保留 |
| 整台 VM 重启恢复 | 通过。`start-mac.sh stop` 后重新启动，Mac/guest API session 匹配；两台设备先为 exited，批量启动后 ready，原数据标记、Notes 包和 Magisk su 均保留 |
| 复制配置 | 通过。新实例拥有空数据卷，原设备数据标记未被复制 |
| 三实例隔离 | 通过。三个随机 ADB 端口不同；各自 `/data/local/tmp/autoflow-marker` 只包含自身 ID |
| Python 批量示例 | 通过。创建三台、逐台打开设置、保存三个 PNG、删除三台及专用数据卷；summary 为 passed，无 cleanup error |
| 失败隔离 | 通过。一台停止时批量安装，另两台成功，停止目标单独失败；冲突操作 HTTP 409/busy |
| APK 安装和启动 | 通过。普通和 Magisk 版安装 Notes、从包列表读取并启动；PNG 分别为 720×1280、540×960 |
| 无效 APK | 通过。带无效 Manifest 的测试 ZIP 进入真实包管理器后明确失败，返回 exit 255 / Corrupt XML binary file |
| 浏览器输入 | 通过。`AutoFlow Mac test 100%s` 在 Notes 正确显示；Home 返回桌面，Back 返回上层；720×1280 的 Notes 新建按钮、540×960 的 Settings/Apps 均正确命中；拖动使设置列表显示后续条目 |
| Magisk 重启 | 通过。真实构建产物可启动和重启，重启后 Magisk 版本与 `/sbin/su -c id` 仍可查询 |
| 清理 | 通过。公共批量示例三台、最初探针和配置副本已回收；有意保留普通/Magisk 两台演示实例及各自数据卷 |

### root 结果必须分层读取

| 检查 | 普通版 | Magisk 版 |
|---|---|---|
| 容器 exec `id` | UID 0 | UID 0 |
| VM 宿主 `adb root` | already running as root | already running as root |
| ADB shell `id` | UID 0 | UID 0 |
| `/sbin/magisk -v` | 不存在，exit 127 | exit 0，`30.6:MAGISK:R` |
| `/sbin/su -c id` | 不存在，exit 127 | exit 0，UID 0 |
| 独立 App 申请 root | **未验证** | **未验证** |

普通镜像本身已有 ADB root；Magisk 对照不能被描述为“普通镜像没 root”。Notes 只用于安装和交互，不申请 `su`。本轮没有独立 APK 的授权弹窗、授权拒绝/允许、应用 UID 提权证据，因此不宣称应用 root 已通过。

## 实测发现并修复的问题

1. **启动时过早失败**：Android init 还未挂载 `/system` 时，首次 `getprop` 返回路径不存在。现在仅固定只读启动探针在总期限内重试；写操作超时仍停止/隔离实例，不能误报成功。
2. **Magisk 重启后的 APK 传输**：Docker archive API 返回 `Error setting up pivot dir` 和 `read-only file system`。仅此明确 HTTP 500 情况改用固定 exec stdin 写入可写的 `/data/local/tmp`，随后正常 `pm install`、检查退出码并清理。实测 `transport=exec_stdin`，安装成功、临时文件不存在；普通实例使用 archive 路径通过。
3. **`su` 路径误判**：系统 PATH 原先先找到 AOSP `/system/bin/su`，其 `-c` 语义不同。诊断现在显式检查固定脚本生成的 `/sbin/su` 和 `/sbin/magisk`，新实例 PATH 也优先 `/sbin`。
4. **ARM 镜像适配**：环境和创建均比对实际 Engine/镜像架构；Mac 默认64位 ARM镜像，Windows默认x86_64镜像，错误架构不能进入创建。

5. **预览与交互竞争**：自动截图可能先占设备锁。前端用户操作仅对后端明确拒绝执行的 HTTP 409/busy 每200ms有限重试，重试窗口2秒、最多10次；网络/其他错误不重试。自动列表与截图轮询不接入此重试。短暂暂停保留上一帧并标注冻结，避免清屏。

自动检查共 **68 项**（Python 后端34、React交互26、Python脚本8）通过；React类型检查与生产构建、Python致命错误lint、Shell语法、Compose配置、Lima配置验证通过。最终管理镜像在实际ARM64 VM内重新构建并达到healthy。

## 证据与复测

提交的紧凑证据位于 [verification/mac-2026-09-13](verification/mac-2026-09-13/)，包括三实例示例结果、安装及 API root 结果、两份 ADB 对照、构建摘要、VM 重启后核验与实际输入截图。原始 APK、构建和调试日志在本机 `.data/mac-test/`（Git 忽略），不作为源码提交；测试期间使用的大型中间镜像归档不要求保留。API root 和 ADB root 是两组独立记录；前者不会自动导入后者的实测结果。

```sh
# 在 reference/redroid-demo 内；已有两台演示设备时不要直接运行需三台空闲容量的批量示例
bash scripts/start-mac.sh check
bash scripts/start-mac.sh stop
bash scripts/start-mac.sh

# 清理自己不再需要的演示设备后，可重跑三台生命周期示例
python3 examples/batch_demo.py --api http://127.0.0.1:8081 --output .data/batch-runs
```

尚未验证：Windows/WSL、Intel Mac、其他 Android/Magisk 组合、应用内 root 授权、摄像头、环境伪装、视频投屏、GPU 性能及大规模并发。启动超时和清理异常的关键分支有自动测试，本轮没有人为破坏内核或磁盘来制造真实启动超时/卷删除失败。

来源：[redroid 官方说明](https://github.com/remote-android/redroid-doc)、[Ubuntu 部署说明](https://github.com/remote-android/redroid-doc/blob/master/deploy/ubuntu.md)、[Lima VZ](https://lima-vm.io/docs/config/vmtype/vz/)、[Lima 端口转发](https://lima-vm.io/docs/config/port/)、[binderfs 文档](https://docs.kernel.org/admin-guide/binderfs.html)、[Ubuntu 镜像校验](https://cloud-images.ubuntu.com/releases/noble/release-20260705/SHA256SUMS)、[Notes 1.7.0](https://github.com/FossifyOrg/Notes/releases/tag/1.7.0)。
