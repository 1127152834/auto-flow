# 内置 Android 环境候选调研

- 日期：2026-09-12
- 状态：confirmed（所引官方文档与仓库描述）；proposed（AutoFlow 选型建议，未批准实施）
- 分类：探路调研；输入为用户要求自行创建和管理 Android 环境、无需 MuMu/雷电。
- 验证方式：阅读 GitHub 上游 README、Android Developers 和 AOSP 文档，并核对本项目架构。未安装运行时、下载系统镜像或执行性能测试。
- 项目约束：Electron + React + Python FastAPI；Windows x64、macOS Intel/Apple Silicon。来源：docs/architecture/README.md。
- 输出：候选、平台边界、集成建议与待验证项；不包含业务实现、依赖变更或已批准的新架构。

## 候选和来源

| 候选 | 已确认事实 | 对 AutoFlow 的判断（proposed） |
| --- | --- | --- |
| Android Emulator / AVD | 官方提供独立命令行启动、系统镜像和虚拟设备管理；Windows 使用 WHPX，macOS 使用 Hypervisor.Framework | 本地跨平台首选验证对象 |
| google/android-emulator-webrtc | React 组件、WebRTC 音视频及输入转发，通过网关连接模拟器 | 内嵌屏幕优先参考；本身不创建 Android |
| google/android-emulator-container-scripts | 容器脚本及 Python 网关，网关把 REST/WebSocket 转成模拟器 gRPC；README 包含 macOS discovery 文件示例 | 借鉴网关，不把 Docker 作为本地桌面的必要前提 |
| remote-android/redroid-doc | Linux Android 容器，多实例，arm64/amd64，GPU；依赖宿主内核能力；该仓库主要是文档与构建入口 | Linux 远程批量环境候选；桌面本地部署需额外 Linux 层 |
| google/android-cuttlefish | Linux x86/arm64 虚拟 Android 的宿主工具，镜像另行取得；支持多实例和 WebRTC | 自建远程虚拟设备候选 |
| budtmo/docker-android | 容器化模拟器、noVNC、ADB、测试集成；快速启动需要 KVM | CI 或 Linux 服务部署参考 |
| waydroid/waydroid | GNU/Linux 上运行完整 Android 的容器方案 | 不优先用于 Windows/macOS 内置模块 |
| Genymobile/scrcpy、yume-chan/ya-webadb | 屏幕控制与 ADB；Tango 支持 Electron，提供 Scrcpy TypeScript 客户端但不提供 UI 组件 | 显示/控制备选，不能代替 Android 运行时 |
| anbox/anbox | GitHub 标示 2024-02-13 归档 | 不建议作为新模块基础 |

主要来源：

- [Android Emulator 命令行](https://developer.android.com/studio/run/emulator-commandline)
- [硬件加速平台条件](https://developer.android.com/studio/run/emulator-acceleration)
- [AOSP 模拟器源码开发入口](https://android.googlesource.com/platform/external/qemu/+/emu-master-dev/android/docs/DEVELOPMENT.md)；[GitHub 镜像，非权威上游](https://github.com/mirror/qemu-android)
- [React WebRTC](https://github.com/google/android-emulator-webrtc)
- [容器与 Python 网关](https://github.com/google/android-emulator-container-scripts)
- [redroid](https://github.com/remote-android/redroid-doc)
- [Cuttlefish](https://github.com/google/android-cuttlefish)、[多实例](https://source.android.com/docs/devices/cuttlefish/multi-tenancy)、[WebRTC](https://source.android.com/docs/devices/cuttlefish/webrtc)
- [docker-android](https://github.com/budtmo/docker-android)
- [Waydroid](https://github.com/waydroid/waydroid)
- [scrcpy](https://github.com/Genymobile/scrcpy)、[Tango](https://github.com/yume-chan/ya-webadb)、[Tango Scrcpy 开发文档](https://tangoadb.dev/scrcpy/)
- [Anbox 归档状态](https://github.com/anbox/anbox)

## 当前工具链变化

2026-09-12 读取的官方 [avdmanager](https://developer.android.com/tools/avdmanager) 与 [sdkmanager](https://developer.android.com/tools/sdkmanager) 文档均已将其标为 deprecated，推荐 Android CLI。
但 [Android CLI 文档](https://developer.android.com/tools/agents/android-cli) 的 Known issues 同时标明 Windows 的 `android emulator` 命令当前被禁用。
这不代表底层 Android Emulator 不支持 Windows。实施前必须固定可工作的工具版本，对旧命令行工具和新 CLI 分别做平台验证，不能直接假定新 CLI 已覆盖所有桌面平台。

## 最小验证方向（尚未执行）

本地 Emulator 子进程运行 Android，AutoFlow 后端管理镜像、实例目录和生命周期；React 通过本地网关显示画面并发送输入。实例持久化、端口分配和异常退出回收由模块管理。运行时按需安装的产品方向待规格确定。

先验证一个实例的创建、启动、ADB 就绪、APK 安装、嵌入显示与触控、关闭后数据保留。再验证两个独立实例的数据/端口隔离和资源占用；分别覆盖 Windows x64、macOS Intel、macOS ARM64。具体应用的 ABI、GMS 依赖和可用性必须用目标 APK 验证，当前没有兼容率或性能结论。

置信度：项目定位与宿主平台限制高；本地集成路线中；具体 APK 兼容性、帧率、延迟、多开数量未知。

## 补充：Root、摄像头和 Docker

- 日期：2026-09-12；用户需求状态 confirmed：要求可 root、可接入宿主摄像头等扩展能力，接受 Docker 部署。接受 Docker 不等于已经选择远程 Linux 宿主或批准部署。
- 以下为文档验证，未进行设备实测；集成建议仍为 proposed。

1. [官方 AVD 文档](https://developer.android.com/studio/run/managing-avds)明确 AOSP 镜像支持 `adb root` / `adb unroot`；原版 Google Play Store 镜像不提供这一 root 能力。ADB root shell 与应用通过 su 获权应分别验收。[Magisk](https://github.com/topjohnwu/Magisk)提供 MagiskSU 和模块能力，但兼容性需要绑定镜像/ABI/版本验证。
2. [模拟器命令行文档](https://developer.android.com/studio/run/emulator-commandline)提供 `-webcam-list`、`-camera-front webcamN`、`-camera-back webcamN`；还列出图片/视频输入源。摄像头映射本身不要求 root。`-writable-system` 是会话临时系统副本，不能作为永久系统修改方案。
3. [rootAVD GitHub](https://github.com/newbit1/rootAVD)说明项目迁往 [GitLab](https://gitlab.com/newbit/rootAVD)。可参考其 Magisk 镜像修补流程，不据历史示例承诺当前 Android 全版本兼容。
4. redroid README 明确 `ro.secure=0` 可提供默认 root ADB shell；摄像头需额外核实 HAL/provider 和视频格式。[上游 issue 178](https://github.com/remote-android/redroid-doc/issues/178)记录 V4L2 HAL/摄像头实验，不能作为最新官方镜像开箱可用的证明。容器可见设备节点不等于 Android 应用可通过 Camera API 使用。
5. Cuttlefish 的 [AOSP 提交](https://android.googlesource.com/device/google/cuttlefish/+/963a5d897aedbd00a9a75a38ddc4f16cf3edf911)有 V4L2 摄像头仿真实现和相应测试步骤；[WebRTC 文档](https://source.android.com/docs/devices/cuttlefish/webrtc)涵盖摄像头/麦克风扩展能力。userdebug 的 root 能力来源：[AOSP 构建变体](https://source.android.com/docs/setup/create/new-device)。这支持继续验证摄像头流注入方案，不代表已验证所有镜像的 Camera2 兼容性。
6. [Docker Desktop FAQ](https://docs.docker.com/desktop/troubleshoot-and-support/faqs/general/)明确不支持直接 USB 透传，可走 [USB/IP](https://docs.docker.com/desktop/features/usbip/)，但不保证全部设备兼容。Windows/macOS 的摄像头接入不能直接套用 Linux `/dev/video*` 映射命令。

建议顺序：本机摄像头和桌面可玩性优先验证 Android Emulator AOSP；Docker/Linux 完整虚拟设备与定制优先验证 Cuttlefish；批量 Android 容器优先验证 redroid。远程运行时需区分服务器摄像头与 AutoFlow 客户端摄像头，后者需客户端采集并传入虚拟摄像头链路。

新增验收项：ADB root、应用 su 授权（如需要）、系统改动跨重启保存、前后摄像头枚举/预览/拍照/录像、宿主摄像头权限与多实例占用。上述结果目前未知。

## 补充：批量工作流与风险控制测试环境

- 日期：2026-09-12；需求状态 confirmed：批量任务可能各占用一个 Android 实例；要求地理位置、网络、厂商和设备指纹等测试环境可配置，提出反检测需求。
- 来源：用户本轮补充、下列官方文档；未执行实例压测或检测对抗实验。
- 选型建议状态 proposed：在批量和环境控制成为主要需求后，优先验证 Cuttlefish，redroid 为批量容器对照，AVD 为本机摄像头和开发调试候选。此前“本地优先”的建议只适用于原始桌面需求，不再作为完整新需求下的唯一排序。尚未批准架构或实施。

### 已确认的能力边界

- [Cuttlefish 多实例](https://source.android.com/docs/devices/cuttlefish/multi-tenancy)：每台虚拟机有独立磁盘 overlay 和实例资源；不能将磁盘隔离直接等同网络隔离或业务身份隔离。
- [Cuttlefish 环境控制](https://source.android.com/docs/devices/cuttlefish/control-environment)：提供 GNSS、OpenWrt、Wmediumd 等服务的 CLI/REST 控制；具体镜像需探测服务可用性。
- [AVD Console](https://developer.android.com/studio/run/emulator-console)：位置、网络延迟/速率、传感器等控制；网络命令有 Ethernet/Cellular 范围，不能假定覆盖新版所有 Wi-Fi 数据路径。
- [redroid](https://github.com/remote-android/redroid-doc)：多实例、DNS/代理及调试用 ro.xxx 覆盖；这不能证明全套设备特征可任意伪装或通过检测。
- [Docker 网络](https://docs.docker.com/engine/network/)默认 bridge 使用 masquerading，多个容器不自动获得不同公网出口。独立出口和 DNS/IPv6/UDP 路径需单独设计与观测验证。
- [Build API](https://developer.android.com/reference/android/os/Build)中的 FINGERPRINT 标识软件构建，不是每台设备的唯一标识；更改品牌字符串不能复现厂商 ROM、驱动、HAL 和真实硬件。
- [ANDROID_ID](https://developer.android.com/reference/android/provider/Settings.Secure#ANDROID_ID)在 Android 8+ 按应用签名密钥、用户和设备组合确定，不能当成一个全局可替换字段。模板克隆需检查业务存储、安装标识和密钥状态，不能承诺天然产生新身份。
- [Play Integrity](https://developer.android.com/google/play/integrity/overview)使用硬件支持的信号；root、模拟器或系统修改会影响判定。没有验证依据承诺上述开源方案普遍通过真实设备/强完整性检测。
- 对自有应用的风控决策分支，可用 [Play 官方测试响应](https://developer.android.com/google/play/integrity/additional-tools)构造 verdict/error 测试；响应有 testingDetails 标记，不代表环境通过了实际证明。

### 建议验证模型（尚未实施）

工作流申请独占实例，绑定固定版本的镜像和测试环境档案，检查就绪及实际观测值后执行，最后收集结果并按状态保留或清理。任务总数与同时运行数量分开，按实测资源设置上限；长登录态任务绑定持久设备，全新环境任务重建经验证的干净数据层。清理失败的实例不回池。

环境档案区分配置目标与实测结果，保存镜像摘要、地域/网络配置、属性模板、root 模式、状态保留策略及检测版本。测试包含正常匹配环境、刻意矛盾环境、root/虚拟化负样本，并用真机取得硬件相关正样本。检测结果必须按应用/SDK/规则版本报告，不使用“万能反检测”或未实测通过率。

性能验收使用目标 APK 和真实工作流逐步增加并发，测启动、成功率、内存/CPU/GPU/磁盘、摄像头链路、取消和回收；无硬件与负载数据，不估算可多开数量。
