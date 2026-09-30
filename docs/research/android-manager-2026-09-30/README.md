# 安卓模块：独立模拟器管理工具研究

- 日期：2026-09-30（Asia/Shanghai）。
- 状态：现状观察 confirmed；产品方向、运行时选择及阶段安排 proposed，等待讨论，不是实施规格或交付验收。
- 范围：AutoFlow 安卓模块；面向需要日常操作、多实例管理、随后接入自动化的桌面用户。研究当前产品与公开资料，优先近一年问题，旧问题只作历史背景。
- 输入：用户本轮需求、当前 Electron 界面、仓库源码与相关架构记录、官方文档、公开仓库和问题记录。
- 输出：五张本轮截图、问题排序、竞品与技术边界、建议的信息架构和验证路线。
- 验证：源码基线 `codex/architecture-baseline@d099c042`；直接观察运行中的 AutoFlow Electron（开发入口 `localhost:5174/#/android`），使用 CUA 截图并重新打开五张保存图片核对。不是打包应用验收。
- 本轮没有修改业务代码、安装运行时、启动模拟器、操作 Google 账号或创建/删除设备。已有未提交内容保留。

## 用户澄清：真实厂商行为与硬件能力（2026-09-30 追加）

状态：confirmed（用户需求）；proposed（以下路线）；未知（具体应用兼容性与硬件桥接效果）。来源：用户在初版研究后明确要求真实厂商设置、权限和系统应用，尽可能接近真机，期望应用不能识别为模拟器，并支持定位、电话号码、摄像头及录音。

这已经排除“仅品牌桌面/主题即可”的解释。下文初版把真实 OEM 是否必需列为待确认的问题已 superseded；Google 原生 + Play 的方案仍可作为一个设备类型，但不足以独立覆盖全部目标。用户尚未选择实体手机、云端物理手机或纯虚拟化，因此不将真机接入写成已批准架构。

| 能力 | 模拟器/虚拟化边界 | 物理手机路线及仍需核实项 |
| --- | --- | --- |
| 真实 One UI/HyperOS | 需要实际系统框架与厂商组件适配；skin/Launcher 不足 | 对应机型原厂系统直接提供；版本和 Google 服务随机型、地区、固件而异。 |
| 定位 | 官方模拟器支持位置/路线输入；Android 标准 mock location 可以被 `isMock()` 识别 | 使用手机实际所在地的定位；电脑位置、手机位置、指定测试位置必须分开。 |
| 电话号码、短信、通话 | 模拟来电/短信仅是测试事件；填写号码不建立运营商服务 | 真实蜂窝业务需要有效通信服务以及对应 SIM/eSIM、基带链路；是否要求真实收短信/打电话待细化。 |
| 摄像头、麦克风 | 官方模拟器可接宿主 webcam/mic；当前 ReDroid provider 是否具备同等桥接未验 | 应用可使用手机传感器；把电脑摄像头/麦克风送进远端手机又是独立的输入桥接能力。 |
| 不被应用识别为模拟器 | 不能承诺任意应用不可识别；完整性检查不只读取品牌/型号 | 原厂系统物理设备更贴近目标，但应用仍可能限制调试、录屏、远程控制或设备状态，需要目标应用测试。 |

新事实的官方来源：[模拟器扩展控制](https://developer.android.com/studio/run/emulator-extended-controls)、[摄像头输入参数](https://developer.android.com/studio/run/emulator-commandline)、[Android Location.isMock](https://developer.android.com/reference/android/location/Location)、[Play Integrity verdicts](https://developer.android.com/google/play/integrity/verdicts)。Android 13+ 的 MEETS_DEVICE_INTEGRITY 包括硬件支持的锁定 bootloader 与厂商认证系统证明；因此“任意自定义内核/ROM”和“原厂设备完整性”存在实际取舍，不能承诺随意组合。

[scrcpy 摄像头文档](https://github.com/Genymobile/scrcpy/blob/master/doc/camera.md)和[音频文档](https://github.com/Genymobile/scrcpy/blob/master/doc/audio.md)说明的是从设备采集/传出。不能据此声称已实现电脑向手机内任意应用注入相机、麦克风，或双向运营商通话。受保护画面与通话音频也要按设备/应用验证。

调整后的建议是研究统一 Android 设备工作台：物理设备承担原厂系统和真实通信/传感器；虚拟设备承担版本测试、可恢复环境和可扩展实例。所谓云手机要核实是物理设备托管还是 Android 容器，不能只凭 ARM 或云手机名称判定等同真机。此建议未实施。

下一项架构决策：用户是否接受实际接入三星/小米/Pixel 物理手机（本地或托管），还是要求全部运行在电脑/服务器上且不使用实体手机。后续验收应按具体应用与实际动作定义，不使用“任何应用都无法识别”这种不可穷尽的验收承诺。

## 核心判断

安卓模块已有管理和控制基础，用户感受到的简陋主要来自使用路径和界面组织，而不是所有底层能力都不存在。当前创建流程围绕环境配置、镜像摘要和运行时诊断展开，用户却希望得到一台能直接使用的安卓手机。安卓页面还使用独立的样式和控件，与产品共享设计系统产生偏差。最值得借鉴的组合是 Genymotion 的设备与镜像组织、MuMu/BlueStacks 的日常多开管理、scrcpy 的直接操控。默认 Google 原生风格、Google Play、最新或指定 Android 版本可作为主路径，但真实 One UI/HyperOS 和任意自定义内核不能被当成普通主题选项。建议先确定独立工具的完整使用闭环，再通过小规模验证评估官方 Android Emulator，保留已实现的 ReDroid 管理能力。

置信度：现状问题与运行时边界高；推荐路线中；最新镜像在本机的实际兼容性未知。

## 本轮界面证据

捕获顺序从用户当前打开的创建页开始。只做导航和只读观察，没有提交表单。

| 步骤 | 画面 | 健康度与观察 |
| --- | --- | --- |
| 1 | 创建安卓实例 | 有清楚的三段表单和提交区，但当前只见 Android 13 配置；没有按系统版本/Google 服务选择的主路径。未连接使用绿色状态点，“请检查运行环境”旁边显示勾形图标，状态表达冲突。 |
| 2 | 安卓资源看板 | 当前零设备，三列高空面板、重复计数、筛选和禁用批量区占据主视图；没有把第一步引导集中呈现。“启动与停止”混合相反状态，难形成稳定分类。 |
| 3 | 运行环境 | 能看到各项状态，但原始命令错误直接铺开；画面显示 Lima 实例已停止，只提供重新检查，没有本页可见的启动/修复入口。不能把本地服务正常等同于安卓可用。 |
| 4 | 镜像管理 | 技术人员可登记/拉取，但普通用户需理解 sha256、仓库引用、登记与本机内容差别；标签与窄输入排列拥挤，正常安装路径不突出。 |
| 5 | 浏览器配置对照 | 同产品已有共享控件、统一筛选、主次操作和清楚的信息分组；可作为安卓统一视觉的直接参照。本轮没有对浏览器模块作完整可用性评价。 |
| 6 | 在线设备控制 | blocked：当前没有设备，且界面报告运行环境停止。本轮未验证触控、音频、剪贴板、重连或持续运行。 |

### 1. 创建页

![本轮创建页截图](/Users/zhangtiancheng/Documents/projects/autoflow/docs/research/android-manager-2026-09-30/01-create.jpg)

### 2. 管理首页

![本轮管理首页截图](/Users/zhangtiancheng/Documents/projects/autoflow/docs/research/android-manager-2026-09-30/02-board.jpg)

### 3. 运行环境

![本轮运行环境截图](/Users/zhangtiancheng/Documents/projects/autoflow/docs/research/android-manager-2026-09-30/03-environment.jpg)

### 4. 镜像管理

![本轮镜像管理截图](/Users/zhangtiancheng/Documents/projects/autoflow/docs/research/android-manager-2026-09-30/04-images.jpg)

### 5. 产品内部对照

![本轮浏览器配置截图](/Users/zhangtiancheng/Documents/projects/autoflow/docs/research/android-manager-2026-09-30/05-browser-reference.jpg)

无障碍观察：界面存在可读标签和文字状态，不能说完全依赖颜色；但创建页颜色/图标与文字语义冲突。镜像页较小的确认区域、弱化文本和控件排列值得进一步测试。本轮没有测量对比度、完整键盘顺序、读屏表现或 200% 缩放，不能作 WCAG 合规判断。

## 源码核对：保留什么，缺什么

| 发现 | 直接证据 | 含义 |
| --- | --- | --- |
| 安卓有自己的视觉层 | `apps/desktop/src/renderer/domains/android/android.css`、`management-board.css`、`components/PrototypeControls.tsx` | 独立字体、字号、硬编码颜色和按钮；与 `renderer/styles/tokens.css`、共享 Button/Input/Select 不一致。统一应复用现有组件。 |
| 已有管理基础 | `AndroidPage.tsx` 接入生命周期、批量、镜像、模板、备份和清理组件 | 不能描述成全部缺失；需要重组入口，并逐项区分已实现与已验收。 |
| 当前 provider 是 Mac/Lima/ReDroid | `apps/backend/src/autoflow/bootstrap/android.py`、`providers/android/mac_runtime.py:155` | 平台门禁限定 Darwin + arm64；不能把 AutoFlow 总体跨平台目标写成安卓现已跨平台。 |
| 镜像并非任意导入 | `providers/android/image_catalog.py` | 拉取白名单是 redroid/redroid；检查 Linux ARM64 与固定摘要；登记已有镜像不等于能启动任意手机 ROM。 |
| 现有准备流程使用 Android 13 | `bootstrap/android_prepare.py:81` | 与本轮界面吻合，但不能据此推断 ReDroid 上游只能运行 13。 |
| 已实现直接控制链 | `components/AndroidVideo.tsx`、`DeviceConsole.tsx`、`providers/android/stream.py` | scrcpy 视频、触控、键盘和 Unicode 文本路径可保留，本轮没有真实在线复验。 |
| 音频和自动剪贴板尚非完整消费体验 | `providers/android/stream.py` 固定 `audio=false`、`clipboard_autosync=false` | Unicode 文本注入已经使用剪贴板消息；不能误报为完全没有剪贴板能力，也不能称已有双向同步。 |
| GApps 有验收模型，不代表默认可用 | `domain/android/image_verification.py` 要求 boot/store/login/download/restart/isolation | 当前镜像目录为零；历史 GApps 验收记录 blocked。本轮未完成登录/商店下载。 |
| 自动化接口有明确缺口 | `bootstrap/android.py` 的 CurrentAndroidRunBoundary | 当前安卓工作流启动/接管返回不可用；管理闭环可独立推进，之后要制定正式自动化契约。 |

上述路径均相对仓库根目录。历史 `.ai` 中 R1/R2/R3 为旧视觉基线，本研究提出重新设计供用户讨论，不将新建议伪装成已批准决策。

## 按影响排序的问题

频率列是本轮证据信号，不是客户发生率。没有访问分析、支持工单统计或多用户访谈，因此不能声称问题影响了某个比例的用户。

| 顺序 | 类型与用户目标 | 表面及断点 | 证据/频率信号 | 严重度 | 置信度 | 产品动作与收益 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 安装/引导：第一次就能启动手机 | 创建页不可启动；诊断展示依赖错误却没有操作闭环 | 本机当前 1 次直接观察，步骤 1/3 | 阻断当前主任务 | 高 | 集中呈现缺什么、安装或启动什么、进度与失败恢复；首先让首次使用完成。 |
| 2 | 功能/信息架构：选系统和 Google 服务 | 用户从环境配置跳到摘要登记，无法按目标组合选择 | 用户明确反馈 + 步骤 1/4 + 源码 | 高 | 高 | 系统库提供经过验证的预设；手工仓库/摘要仅高级入口。 |
| 3 | UI 一致性：可预期的面板与操作 | 独立控件、字号、间距和多层面板 | 安卓 4 个画面与 1 个内部对照；两套样式实现 | 高 | 高 | 使用共享 tokens/控件；统一标题、工具栏、表单、主次操作。 |
| 4 | 工作流：迅速找到并打开设备 | 三列空看板、重复状态、无选择仍展示批量表单 | 步骤 2；当前仅零设备样本 | 中至高 | 高（空态）；中（规模推断） | 默认设备库，列表/缩略图切换；选中后出现批量栏。运行状态与控制者分开。 |
| 5 | 可靠性：新系统升级后仍可控制 | Android 与串流工具版本不匹配可能断连 | 上游 scrcpy #6370/#6691 与本地固定 3.3.4；多个案例，无频率分母 | 高 | 高（存在此类风险）；本机影响未知 | 固定镜像与控制协议版本，兼容性矩阵验证后更新，保留旧实例。 |
| 6 | 功能：运行真实厂商系统 | Samsung skin/型号预设容易被误解为 One UI ROM | 官方 skin/RTL 与用户品牌需求；未发现可直接集成的通用方案 | 高（若为硬要求） | 高（区别）；未知（具体 ROM 移植） | 分开桌面外观与真实系统；真实 OEM 优先评估真机接入。 |
| 7 | 文档/帮助：知道 Google 应用是否可用 | “组件声明/验收”无法直接回答能否登录、下载应用 | 本地验收模型；Genymotion 官方安装/兼容文档；ReDroid 历史 #240 | 高 | 高（状态需要拆分）；未知（目标应用结果） | 展示预装、登录、商店下载、目标应用验证结果与日期，失败给下一步。 |

公开问题的解释边界：scrcpy [#6370](https://github.com/Genymobile/scrcpy/issues/6370) 是 Android 16 QPR2 Beta 与旧版工具的具体断连报告，已关闭，不能说当前版本仍普遍失效；[#6691](https://github.com/Genymobile/scrcpy/issues/6691) 提醒嵌入旧 scrcpy-server 的产品需要跟进兼容。ReDroid [#240](https://github.com/remote-android/redroid-doc/issues/240) 是旧版 GApps 可用性案例，只作历史机制信号。Genymotion 的[官方性能说明](https://support.genymotion.com/hc/en-us/articles/22372747242397-Android-15-and-16-are-very-slow-in-Genymotion-Desktop)针对特定宿主/虚拟化组合，不证明 AutoFlow 的性能。

## 参考产品：借鉴具体流程，不整体搬另一套产品

| 产品/项目 | 已核实的定位或能力 | 最值得借鉴 | 不宜直接照搬的原因 |
| --- | --- | --- | --- |
| [Genymotion Desktop](https://docs.genymotion.com/usage/desktop/overview/) | 独立启动器；设备、Android 镜像、硬件配置、设置与诊断分开 | 主信息架构；从镜像创建设备；设备菜单与控制窗口 | 商业模拟器产品；并非自带完整 Google Play 的万能底座。 |
| [Android Device Manager](https://developer.android.com/studio/run/managing-avds) | 硬件配置 + 系统镜像构成 AVD；区分 Google APIs、Google Play、AOSP | 系统版本选择、下载、配置和设备生命周期 | 开发工具操作密度不适合整套搬进日常使用界面。 |
| [MuMu for Mac](https://www.mumuplayer.com/help/mac/multi-instance.html) | 新建设备和多实例运行 | 面向普通用户的创建、启动、多开路径 | 官方帮助可作体验参考，不等于其内核可集成或任意 ROM 可用。 |
| [BlueStacks 多开管理器](https://support.bluestacks.com/hc/en-us/articles/360052834092-How-to-create-and-manage-instances-using-the-Multi-instance-Manager-on-BlueStacks-5) | 创建、管理多个实例和可用 Android 版本 | 新建/复制的区别、批量管理和实例状态 | 可选版本受产品限制；不能承担“永远最新”的承诺。 |
| [scrcpy](https://github.com/Genymobile/scrcpy) | 桌面镜像与控制、音频、录制、剪贴板等；Apache-2.0 | 继续作为控制能力来源；本项目已接入固定版本 | 不是模拟器引擎，不提供系统镜像和实例生命周期。 |
| [QtScrcpy](https://github.com/barry-ran/QtScrcpy) | 跨平台 USB/网络投屏控制；Apache-2.0 | 设备连接、键鼠控制与常用操作 | Qt/C++ 与现有 Electron/React 不同，整体复制会引入第二套桌面栈。 |
| [Tango / ya-webadb](https://github.com/yume-chan/ya-webadb) | TypeScript ADB 客户端，支持 Chromium/Node/Electron；MIT | Web 操控与文件/设备交互的后续参考 | 不能因技术栈匹配就重写当前已工作的 Python/ADB 控制链；需先定位实际缺口。 |
| [ws-scrcpy](https://github.com/NetrisTV/ws-scrcpy) | Web scrcpy 客户端原型；MIT；使用修改版服务端 | 浏览器内设备视图与串流结构 | 不是模拟器管理产品；修改版协议和新版 Android 兼容性需要另验。 |
| [DeviceFarmer STF](https://github.com/DeviceFarmer/stf) | 浏览器远程设备管理，设备清单、应用/日志等；公开入口本轮导向 jamf/devicefarmer-stf | 真机设备库、使用者状态与控制工作台 | 面向设备农场；依赖和多用户管理超出本地单用户主路径。README 的版本表不能替代新版 Android 验收。 |
| [docker-android](https://github.com/budtmo/docker-android) | Docker + Android Emulator + noVNC | CI/远程运行和网页操控参考 | 官方快速开始依赖 Linux/KVM；Mac 下不是直接替换现有 provider 的捷径，Galaxy 型号也不证明运行 One UI。 |
| [ReDroid](https://github.com/remote-android/redroid-doc) | Linux 上运行多实例 Android 容器，arm64/amd64；上游列出 8.1–16 | 保留现有批量、卷数据和生命周期投资 | Google 服务需额外组合与验证；宿主内核模型不等同于每实例虚拟机内核。 |

“直接复刻”的建议：可以按成熟产品复刻明确的创建流程、设备操作层级和控制布局；AutoFlow 外层仍使用已有设计系统。源码复用发生时固定上游版本并记录来源/许可证。此次没有复制任何外部业务代码，也没有安装上述产品作性能对比；竞品体验依据官方公开资料，而非登录后实测。

## 需求边界：内核、系统、桌面与 Google 服务

| 层 | 用户看到的选项 | 可实现边界 |
| --- | --- | --- |
| 模拟器引擎 | Android Emulator、ReDroid 等 | 决定宿主支持、虚拟化、性能和生命周期，不能靠换主题替代。 |
| Android 系统镜像 | Android 版本、架构、构建版本 | 决定框架与 API；必须与引擎兼容。 |
| 内核 | 自定义 Linux kernel/启动配置 | 是高级系统开发能力。Android Emulator 有 `-kernel`；需要兼容的内核和系统，不支持把任意手机内核直接换进去。 |
| 厂商系统 | Samsung One UI、Xiaomi HyperOS/旧 MIUI | 包含厂商框架、系统服务与应用；不只是桌面样式。 |
| 桌面与主题 | Launcher、壁纸、图标 | 可单独定制一部分视觉和交互；安装某个 Launcher 不等于获得完整厂商系统。 |
| Google 服务 | Google Play 服务、商店、相关框架 | 默认预装是一条可选镜像路线；存在组件、可登录、可下载、特定应用兼容分别验收。 |

官方依据：Android Emulator 支持[指定内核文件](https://developer.android.com/studio/run/emulator-commandline)。[Samsung Galaxy Emulator Skin](https://developer.samsung.com/galaxy-emulator-skin)提供模拟设备外观，[Remote Test Lab](https://developer.samsung.com/remote-test-lab)提供真实 Galaxy 设备测试。小米当前系统品牌是 [HyperOS](https://www.mi.com/uk/hyperos)，需求不能继续只写 MIUI。

真实 OEM 虚拟化不能绝对说“不可能”：AOSP 的 [Cuttlefish Hybrid Device](https://source.android.com/docs/devices/cuttlefish/create-chd)能组合设备 framework target files 与虚拟设备 vendor target files，但需要匹配的构建产物及工程适配。该路线不等于下载一个手机刷机包就能在 Mac 跑；本轮未验证任何 One UI/HyperOS 镜像。

关于 Google：官方 AVD 文档明确，Google APIs 与带 Play Store 的镜像不同，后者的发行签名镜像不提供正常的 `adb root` 路径。应提供“Google Play 日常使用”和“可定制/调试”两类明确预设，而不是默认承诺一个镜像同时满足所有条件。Genymotion [官方文档](https://docs.genymotion.com/usage/desktop/install_apps/)也说明商店与服务默认未装，另有 Open GApps 安装流程；直接换成 Genymotion 不会自动满足本轮全部需求。microG 是替代实现，不能作为已内置官方 Google 三件套的证据。

## “最新版本”应如何落到产品

本轮核实到 Google 已于 2026-06-16 [发布 Android 17](https://android-developers.googleblog.com/2026/06/Android-17.html)，并提供[模拟器配置说明](https://developer.android.com/about/versions/17/get)。ReDroid 当前公开支持列表最高列到 Android 16，AutoFlow 当前画面配置为 Android 13。这三种事实应分开展示，不把上游发布、引擎支持和本产品已验证混为一谈。

建议系统库区分：最新正式版、其他正式版、预览版；每项展示引擎、架构、具体修订、Google 服务类型、下载大小/磁盘估计、验证状态和验证日期。默认推荐当前宿主上最新且通过产品验收的正式组合；如落后上游，明确显示差距，仍可让用户显式选择未验证版本，而非假称最新。

创建时将版本解析为固定构建身份。已有实例不随 `latest` 静默变化；更新先建立独立测试实例或可恢复备份，验证通过再迁移。快照、备份、克隆是三种不同操作，不应复用模糊的“保存”按钮。不同 provider 的数据格式不可假设可互相恢复。

本轮没有枚举本机 SDK 仓库包，也没有验证 Android 17 的具体 ABI + Google Play 组合。官方版本介绍中的安装示例可能落后于发布状态，实施时以实际 SDK package ID/revision、签名来源和运行结果确认；不在本研究中承诺一个尚未验证的下载组合。

## 建议的产品结构（proposed）

定位：一个无需先创建项目或工作流即可使用的 Android 设备管理工具。先在 AutoFlow 内形成独立完整入口；“可独立使用”不自动等于本期拆出另一款安装包。

| 区域 | 默认内容 | 主要动作 |
| --- | --- | --- |
| 我的设备 | 统一设备清单；名称、系统版本、Google 状态、运行状态、控制者；列表/缩略图切换 | 创建、打开/启动；选中后才出现批量动作；复制/备份/删除在更多菜单。 |
| 系统库 | 推荐、已安装、所有可用版本；清楚标识 Play Store/AOSP/自定义 | 下载并创建；高级导入；查看兼容性。 |
| 设备工作台 | 设备画面为主体，旁边窄工具条；工具面板按需展开 | 返回/主页/最近任务、旋转、音量、截图、录屏、安装 APK、文件传输。 |
| 备份与模板 | 可复用环境配置、已有备份和恢复目标 | 创建模板、复制、恢复；保留独立语义。 |
| 设置与诊断 | 引擎安装/更新、资源容量、网络、详细日志 | 检查、启动/修复环境、导出诊断。 |

“操作记录/下载任务”作为贯穿各页的任务区域，无需又加一整层大型控制面板。现有未知结果的核实、原 requestId、数据归属、独占控制与容量保护全部保留，正常操作时减少技术字段暴露，异常时再展开对应处理。

创建主路径建议：选择系统预设 → 填设备名称和数量、选择性能规格 → 下载/准备 → 启动成功后打开设备。推荐项优先为 Google 原生风格 + Google Play；高级入口提供 CPU/内存、分辨率、语言/时区、网络及自定义镜像。原生风格不承诺完整 Pixel 专有功能。

视觉建议：复用 AutoFlow 的颜色、字体、圆角和控件，不再造安卓专属设计语言；一个区域突出一个主要动作，维护和危险操作收进菜单；少设备优先清晰卡片，多设备提供紧凑列表和预览墙。三列状态看板可作为后续自动化调度视图，是否保留为默认需由下一轮设计选择确定。

## 引擎路线取舍（proposed）

| 路线 | 适合点 | 代价/未知 | 当前建议 |
| --- | --- | --- | --- |
| 继续只用 ReDroid | 现有管理/数据保护可最大复用，多实例容器路线已有基础 | 最新版与 GApps 需自己维护；本实现仅 Mac ARM；每实例独立内核不适合现模型 | 保留，不把它包装成覆盖全部需求。 |
| 官方 Android Emulator + 现有控制能力 | Google 系统镜像、版本选择、桌面单实例操作较贴近当前目标 | 新增 provider；Mac/Windows/ABI 性能和 Play 验收待测；现有 ReDroid 数据不能直接移植 | 最值得先作技术验证，再决定是否成为默认。 |
| Genymotion 作为运行时 | 成熟独立工具，有平台支持和控制工具 | 产品依赖、分发条件、Google 服务和目标应用仍需处理 | 优先作为体验参照，暂不决定强依赖。 |
| 真机 ADB + scrcpy | 获得真实 One UI/HyperOS 与厂商行为 | 需要真实设备；供电/USB/网络、授权与设备管理 | 如果真实品牌系统是硬要求，优先验证该路线。 |
| Cuttlefish/ROM 移植 | 更深入的系统和 framework 定制 | Linux 宿主/构建产物/厂商适配成本，Mac 本地路径未验证 | 独立研究项，不放在首版普通创建流程。 |

不要预先实现通用插件市场或一次接入所有引擎。先验证一个新增引擎是否解决当前默认体验，再复用已经存在的领域端口。

## 机会与推进顺序

以下是优先级分组，不是未经估算的交期承诺。

**本周优先处理的设计事项：** 定义统一组件/操作层级；改造空态和状态语义；区分运行环境与设备配置；让镜像库从“登记摘要”转为“选择系统”；完成设备库、创建、控制台三处视觉方案。本轮没有开始设计稿生成或实现。

**本季度能力方向：** 独立启动及依赖管理；镜像版本目录；Google Play 默认使用闭环；完整日常控制（含中文输入、剪贴板、音频、文件、录屏）；多开资源观测；备份恢复与应用数据保持。原有已实现功能逐项复用和补验，不全部重写。

**需要深入验证：** Android Emulator 在 Mac ARM/Intel、Windows 的具体镜像与性能；真实 OEM 系统是否为硬要求；自定义内核的具体改动目标；目标应用的架构、Google 服务和设备完整性要求；独立安装包是否另立产品任务。

进入架构实施前，先完成一个可审查验证报告：

1. 在目标宿主发现并固定一个最新正式版 Google Play 镜像，另固定一个自定义/AOSP 组合，记录实际包版本和 ABI。
2. 验证创建、启动、停止、重启后数据保留；首启/再次启动耗时、空闲资源、交互延迟用实测记录，不引用宣传值。
3. 验证 Google 登录、下载一个用户指定应用、重启后账号保持；组件已安装不代替这些验证。
4. 验证中文输入、点击/拖动、旋转后的坐标、剪贴板、音频、断连恢复；再测两台并行，不直接宣称十台稳定。
5. 验证备份恢复、旧版本保留和失败恢复；既有未知操作不自动重放。
6. 根据证据确定默认 provider，并提交设计、规格、垂直切片计划供确认；工作流接入排在独立管理闭环之后。

## 来源地图与信号强弱

| 来源 | 本轮贡献 | 局限 |
| --- | --- | --- |
| 当前 AutoFlow 源码与 5 张 Electron 截图 | 直接确认界面、入口、provider、已有能力与断点 | 单机、当前数据为空、运行时停止；不是完整在线设备测试。 |
| Android Developers / AOSP | AVD、Google Play/root、Android 17、内核、Cuttlefish 边界 | 文档不是本机兼容或性能结果。 |
| Samsung / Xiaomi 官方 | 品牌系统、skin 与真机测试边界 | 未取得厂商可用虚拟 ROM 或固件构建产物。 |
| Genymotion / MuMu / BlueStacks 官方帮助 | 独立管理器和多实例使用路径 | 未登录、安装、购买或实测竞品；营销性能不作结论。 |
| scrcpy / ReDroid / QtScrcpy / Tango / ws-scrcpy / DeviceFarmer / docker-android 仓库 | 定位、技术栈、功能与许可标识，复用候选 | 没有完成依赖审计或供应链验收。 |
| GitHub issues | Android 升级与串流兼容、GApps 使用断点 | 单个报告不代表发生率；关闭问题不当成当前缺陷。 |
| Reddit 搜索 | [自定义镜像困惑](https://www.reddit.com/r/AndroidQuestions/comments/1igdkpu/)、[Mac 上版本选择困惑](https://www.reddit.com/r/BlueStacks/comments/1qxfzyx/bluestacks_for_older_android_emulation/)、scrcpy GUI 使用动机 | 自述/样本偏差，只用于发现问题，不用于证明技术能力。 |
| Stack Overflow 搜索 | [真实 Samsung 系统而非 skin 的需求](https://stackoverflow.com/questions/52577939/samsung-system-image-for-android-emulator/52579001) | 2018 年旧问题，仅证明历史需求，不采用旧费用或当前支持结论。 |
| Hacker News / X 定向检索 | 本轮未获得足以影响结论的相关证据 | 不编造社区共识；没有使用内部客户工单或访谈数据。 |

本研究足以支持产品范围讨论，尚不足以选择最终引擎、保证任意品牌 ROM、宣称 Google 应用兼容或承诺并发容量。
