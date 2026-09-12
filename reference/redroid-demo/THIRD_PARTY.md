# 第三方来源与改动

- 日期：2026-09-13。
- 状态：实现来源已登记；运行验证以 `VERIFICATION.md` 为准。
- 原始参考仓库保留独立 Git 信息，本 Demo 不修改其源码。

## RedroidManager

- 来源：[JinHisAndy/RedroidManager](https://github.com/JinHisAndy/RedroidManager)。
- 固定 commit：`853b786b29430886ae8db58eb2d9e3432e0c8684`。
- 许可：MIT；原文保存在 [RedroidManager-LICENSE.txt](licenses/RedroidManager-LICENSE.txt)。
- 原作者版权声明保留在许可文件中；后端文件头标明来源版本和改编范围。管理镜像包含本说明和两份原始许可。

| 来源文件与职责 | Demo 目标 | 复用与修改 |
|---|---|---|
| `app.py`：Docker SDK 列表、创建/启停、command/volume、getprop | `backend/app.py` | 复制并改编核心操作；新增实例归属、输入校验、资源配额、就绪状态、动态宿主端口、失败处理；校验 Linux amd64/arm64 Engine 与所选镜像架构一致 |
| `app.py`：APK 的 tar/put_archive/pm install 流程 | `backend/app.py` | 默认保留 tar/put_archive 传输；唯一文件 ID、边界校验、真实退出状态、安装临时文件清理；对指定只读 pivot 错误增加 exec stdin 传输（细节见下文）；删除自写 AXML 包名推断 |
| `app.py`：screencap 与 input 调用 | `backend/app.py` | 保留 Android 命令路径；单帧 PNG、实际尺寸、有限执行、互斥与超时处理 |
| `app.py`：批量任务 ID/状态查询 | `backend/app.py` | 保留行为组织，重新实现有界任务执行与每设备占用 |
| `templates/index.html`：列表、创建、APK、屏幕交互 | `frontend/src/` | 作为功能和交互参考，重新编写 React 组件；未整页复制原 HTML/CSS/DOM 字符串实现；新增真实环境诊断、镜像架构筛选、Docker 宿主 localhost 文案与受限截图轮询 |

配置副本明确使用新数据卷，不复制原实例应用数据；截图作为单帧使用，不承诺视频帧率。

以下是 Demo 自行实现的适配，不是上游已经具备的能力：

- 环境接口返回镜像实际 `architecture`、`compatible`、image ID 和 digests；`compatible` 只表示 Linux 镜像与受支持 Engine 架构匹配，整体就绪仍取决于 binder 等检查。`REDROID_IMAGES` 第一项成为省略 `image` 时的 API 默认值；界面默认选择首个兼容且已缓存的镜像，并明确禁用不兼容镜像。
- 启动期间仅对固定只读 `getprop sys.boot_completed` 探针重试早期 init 错误或超时，限定在启动总期限内；只读列表恢复探针单独限频。截图、安装、输入等命令没有获得这个重试例外，不确定执行结果仍停止或保留设备占用。
- Magisk 可能使根文件系统只读，导致 Docker archive 建立 pivot 失败。只有 HTTP 500 且错误同时包含 `error setting up pivot dir` 与 `read-only file system` 才改用固定命令的 exec stdin，将 APK 写入 `/data/local/tmp/<内部ID>.apk`。其他传输错误照常失败；不重试不确定的部分发送。任务结果明确记录 `transport=archive` 或 `exec_stdin`，安装成功及临时文件清理仍分别检查。
- root 检查明确调用 `/sbin/magisk` 与 `/sbin/su`，避免 PATH 选中参数不同的 AOSP `/system/bin/su`。API 为缺失的可选工具保留实际退出码；宿主 ADB 脚本分别记录传输、shell UID 和 root 命令结果，不用 shell 成功推断应用授权。

## redroid-script

- 来源：[ayasa520/redroid-script](https://github.com/ayasa520/redroid-script)。
- 固定 commit：`a4951b782fc8e06c845d9553bf07bb643fd8c158`。
- 许可：MIT；原文保存在 [redroid-script-LICENSE.txt](licenses/redroid-script-LICENSE.txt)。
- 构建入口使用相邻参考仓库的固定版本，在临时副本中运行。脚本的生成文件、提取文件和缓存均放在构建临时区。
- 必要补丁限定在临时副本：构建退出码/产物校验、下载与执行边界、临时路径隔离、原生 `amd64`/`arm64` 别名到上游 Magisk ABI 分支的映射。构建入口要求 Linux 进程宿主、实际 Engine 与基础镜像同架构，设置对应 `DOCKER_DEFAULT_PLATFORM`；通过 `--base-image` 或 `REDROID_BASE_IMAGE` 指定已缓存 Android 13 基础镜像，并将生成 Dockerfile 的基础引用绑定至已检查镜像的 digest 或独立临时 tag。补丁实现和构建记录可在 `scripts/build_root.py` 及其输出中核查；构建完成状态仍是 `built_not_boot_verified`。
- 使用的 Magisk 下载地址来自该固定版本 `stuff/magisk.py`，为作者维护的 fork；不声称它就是官方 Magisk 的原封不动发行版。

## Docker 镜像与其他依赖

- 基础 Android 来自 `redroid/redroid`；记录实际运行或构建使用的 image ID/digest，浮动 tag 不作为精确版本证据。支持条件扩展至同架构 Linux amd64/arm64；没有加入跨架构 Android 转译。
- Apple Silicon 的 `scripts/lima-mac.yaml` 是本 Demo 的独立 Linux VM 配置，使用 Lima 与指定 Ubuntu arm64 cloud image，并在 VM 内配置 Docker Engine 和 binder；不是对 macOS 原生 Android 内核或 Docker Desktop 的支持声明。VM 镜像来源及 SHA-256 记录在配置文件中，部署和实测结论单独记录。
- 构建依赖 Node、Python、Flask、Docker SDK、Waitress、React、Vite 等，实际版本见各子工程锁定文件和镜像配置。
- 两份 MIT 许可只覆盖相应脚本/源码，不替代 Android 镜像、Magisk 或其他下载组件自己的许可。
- 本 Demo 不附带第三方测试 APK、Magisk APK、Google 服务或 ARM 转译二进制。
