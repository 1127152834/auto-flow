# 纯虚拟 Android：厂商系统可行性与验证方案

- 日期：2026-09-30，America/Los_Angeles。
- 状态：confirmed（公开资料与本机只读检查）；proposed（选型、产品设计与实验）；未进行镜像启动或应用验收。
- 任务类型：探路。输入为用户明确的纯虚拟化、真实厂商系统、Google 服务与外设要求；输出为路线筛选、产品边界与可执行验收方案。
- 范围：电脑或服务器运行虚拟 Android，不使用本地或托管实体手机。先成为独立模拟器管理工具，再接自动化。
- 基线：AutoFlow `bee55607`；不改变现有 ReDroid 设备、数据库、账号或业务代码。

## 结论

纯虚拟化运行厂商应用层存在公开实现，不能再笼统说“只能用真机”。但目前查到的证据没有证明一套可直接集成的工具能同时提供最新 One UI/HyperOS、完整厂商权限行为、Google 服务、全部外设和任意应用兼容。值得优先验证的是 QEMU/LineageOS 的 GSI 路线；Android Emulator 可作为 Google 服务与宿主外设的对照基线；Cuttlefish CHD 和 FMD Rehoster 是更深的系统适配候选。现有 ReDroid 管理资产继续保留。是否新增运行时要由实验决定，不先实现四套引擎。

置信度：路线存在为高；HyperOS 在当前 Mac 上完整可用为未知；One UI 完整纯虚拟化为未知；具体应用兼容性为未知。

## 1. 三条厂商系统路线

| 路线 | 本轮直接证据 | 缺口与判断 |
| --- | --- | --- |
| QEMU / LineageOS + GSI | LineageOS 文档包含 Apple Silicon UTM 与通用 QEMU 虚拟机目标；社区项目展示 HyperOS 3 GSI 启动 | 最接近可复现的桌面探索路线。不能将启动展示当成权限、商店、相机、后台服务全部通过。 |
| Cuttlefish Hybrid Device（CHD） | Google 文档提供 Android 15+ 的厂商 framework target-files 与 Cuttlefish vendor target-files 合并流程 | 需要构建产物；普通下载到的 OTA/刷机包不能直接视为合格输入。当前项目没有这些厂商产物，也没有 Linux/KVM 验收。 |
| FMD Rehoster | 开源工具抽取固件组件并集成 AOSP，研究有实测结果 | 适合厂商应用层移植研究，不能当作完整商业手机系统的现成替代。 |

**QEMU/GSI 证据链。** [LineageOS 的 Mac 文档](https://lineageos.github.io/lineage_wiki/utm-vm-on-apple-silicon-mac.html)明确说明这些目标由个别维护者维护、没有官方构建服务器镜像和 OTA；Apple Silicon 推荐 ARM64-only，特定图形后端选择会影响显示。[通用 QEMU 文档](https://lineageos.github.io/lineage_wiki/libvirt-qemu.html)还列有视频播放等已知问题。因此“有上游构建说明”不等于“可直接交付普通用户”。

[jqssun/android-lineage-qemu](https://github.com/jqssun/android-lineage-qemu)提供预构建包、Mac HVF 启动示例和 GSI 挂载说明，可用于小规模复现。其 Mac 示例使用 `hda-output`；这不是麦克风输入已实现的证据。不能把此项目的 GApps 安装说明外推为每个厂商 GSI 都兼容。

[SamuraiArtem/android-lineage-emulator](https://github.com/SamuraiArtem/android-lineage-emulator)宣称 HyperOS 3 GSI 可启动，README 有截图和步骤，要求 permissive SELinux。其最新公开 release 元数据为 `LineageOS23.1`（2026-03-16），附件是 Linux/Windows 的 LineageOS 包，不是已核实的 HyperOS 完整镜像交付；HyperOS 下载入口指向外部 Telegram。尚未核实该 GSI 的构建来源、内容、摘要或厂商服务完整性。该证据支持“值得实验”，不支持“已经支持 HyperOS”。

**CHD 证据链。** [Google CHD 文档](https://source.android.com/docs/devices/cuttlefish/create-chd)的输入包括 framework/vendor target-files 和 OTA tools。物理设备的构建目标不意味着运行时需要实体手机，但不代表任意零售固件都能直接用。底层 [Cuttlefish](https://source.android.com/docs/devices/cuttlefish)面向 Linux x86/ARM64；Mac 上再包一层虚拟机的可用加速、图形、输入链都须另验，不能宣称现有 Lima 已解决。

**研究结果不能包装成完成率。** [Relocate and Emulate](https://arxiv.org/html/2606.09528v1)使用 184 个 SDK 31–33 固件样本，表 I 报告约 97% 可构建/启动，但核心服务和桌面初始化各约 35%；其启动定义仅要求 ADB 可用。表 II 明确不覆盖原厂内核模块、环境检测规避和设备证明，SELinux 仅 permissive。它证明部分厂商应用层可移植，未证明最新完整 ROM 可用。代码见 [FMD-AECS](https://github.com/FirmwareDroid/FMD-AECS)，仓库提供构建、容器管理、串流等模块，标注 GPL-3.0；本轮只研究，没有复制代码。

**One UI 仍无合格候选。** 本轮定向搜索没有找到具备可核对构建流程及完整运行证据的纯虚拟 One UI 项目。这不是不存在的证明。一个搜索命中的 [emulator-android 项目](https://github.com/code-root/emulator-android)虽有 Samsung 固件相关配置，其自身 README 明确真实 One UI 路线依赖 physical 模式，Google AVD 仍为 Google 系统；不符合本任务范围，不纳入候选。

## 2. 相机、麦克风、定位与号码分别怎么落地

| 能力 | 已有依据 | 对 AutoFlow 的具体验收 |
| --- | --- | --- |
| 摄像头 | Android Emulator 支持宿主 webcam 输入；Cuttlefish 有浏览器帧传入虚拟设备的源码 | 应用内相机实际预览、拍照、保存、上传；测试前后镜头、旋转、拒绝权限与重连。宿主预览成功不能代替应用内成功。 |
| 麦克风 | Android Emulator 可启用宿主音频作为虚拟麦克风 | Android 录音保存可回放，目标应用语音消息有声；检查权限拒绝、设备断开、多实例争用。系统声音输出与麦克风输入分开验收。 |
| 定位 | Android Emulator 支持点位、路线及 GPX/KML | 应用取得并更新位置；明确手动测试位置或宿主位置来源、时间和精度。宿主定位转发是待开发能力，不能凭官方模拟器支持点位就称已完成。 |
| 虚拟号码/短信/来电 | 官方模拟器提供模拟事件与实例间测试通信 | 可测系统短信/拨号流程；不把测试事件显示成运营商真实接收。 |
| 真实可达号码 | 外部通信服务可提供号码、消息回调、VoIP SDK | 单独验证号码能力、入站消息、出站与语音链。写入 Android 短信系统或接入系统拨号器需要额外适配，不会自动获得 SIM/eSIM/基带或运营商身份。 |

来源：[Android Emulator 命令参数](https://developer.android.com/studio/run/emulator-commandline)、[扩展控制](https://developer.android.com/studio/run/emulator-extended-controls)、[模拟实例间通信](https://developer.android.com/studio/run/emulator-networking-voice)。真实号码候选机制参考 [Twilio 号码](https://www.twilio.com/docs/phone-numbers)、[消息 Webhook](https://www.twilio.com/docs/messaging/guides/webhook-request)、[Android Voice SDK](https://www.twilio.com/docs/voice/sdks/android)，尚未选供应商、购买号码或验证目标应用接受情况。

Cuttlefish 不只是“理论上 WebRTC 可以传视频”：已读取上游提交 `483d070eff39b4ad0de5cb5fec7fd44135506ce4` 的 [app.js](https://github.com/google/android-cuttlefish/blob/483d070eff39b4ad0de5cb5fec7fd44135506ce4/base/cvd/cuttlefish/host/frontend/webrtc/html_client/js/app.js) 和 [camera_streamer.cpp](https://github.com/google/android-cuttlefish/blob/483d070eff39b4ad0de5cb5fec7fd44135506ce4/base/cvd/cuttlefish/host/frontend/webrtc/libdevice/camera_streamer.cpp)：前者按 `camera_passthrough` 能力显示入口，后者将客户端视频帧发给虚拟设备。此为源码证据，尚未验收选定镜像/HAL。概览见 [WebRTC 文档](https://source.android.com/docs/devices/cuttlefish/webrtc)。

## 3. Google 默认体验、版本与自定义内核

建议提供三个明确的系统配置：Google Play 日常使用、厂商系统实验、自定义系统。默认推荐第一种，另两种保留用户要求，但各自展示真实验证结果；不能让“Google 默认可用”掩盖厂商系统仍未通过。

[官方 AVD 文档](https://developer.android.com/studio/run/managing-avds)区分 Google APIs、带 Play Store 的镜像和 AOSP；带商店的镜像是 release 签名，常规 `adb root` 不可用。因此 Google 日常镜像和自定义内核实验应分开管理。自定义内核还须匹配虚拟板卡、驱动和启动接口，不能直接把任意三星手机内核文件当作虚拟机内核。

当前 [ReDroid](https://github.com/remote-android/redroid-doc)以 Linux 容器运行并依赖宿主内核模块。在 AutoFlow 的 Lima 部署中，该宿主是 Linux 客体；更换容器镜像不会为每个实例更换独立内核。若“自己的内核”要求每个实例单独启动不同内核，应该验证独立虚拟机路线，不能在现有镜像选择器里加一个文件字段就称支持。

“最新”设计为目录的可用更新信息，实例则锁定实际版本、架构、构建号和镜像摘要。Android 版本、OEM 版本、地区版本、Google 组件版本分别记录。未验证的新版本标为待验证，不因有下载链接就提升为推荐；更新先建测试副本，通过后再提供迁移路径，不覆盖正在使用的实例。

“应用不发现模拟器”拆成具体应用版本与操作的兼容结果，不提供全局隐身开关或泛化成功标记。[Play Integrity](https://developer.android.com/google/play/integrity/verdicts)明确 Android 13+ 的设备完整性判断涉及硬件支持的锁定启动链与认证厂商镜像；Google Play Games for PC 的虚拟完整性标签另有适用范围。安装 Google 组件、修改型号文字、运行厂商桌面，都不能据此推出认证通过。

## 4. 用户应该看到的管理工具

以下是结合前轮截图的产品提案，未实施，也未覆盖旧 UI 批准记录。

| 页面 | 主体内容 | 操作组织 |
| --- | --- | --- |
| 我的设备 | 设备列表/缩略图、系统与版本、运行状态、当前控制状态 | 常驻主操作为新建设备；每台设备随状态显示启动或打开。选中后才出现批量栏，删除/重置收进菜单。 |
| 系统库 | Google、厂商、自定义系统；安装状态、验证状态、版本与更新 | 普通用户选择可用系统并安装；仓库地址、摘要和构建信息进详情。尚不可用的 OEM 项明确显示实验条件。 |
| 设备工作台 | 中央安卓屏幕、简短常用工具栏、按需展开的能力面板 | 相机来源、麦克风来源、定位、文件与应用分面板，不把全部按钮并排铺开。 |
| 运行环境 | 安装、启动、依赖状态和恢复动作 | 失败摘要给出可行动下一步；详细日志折叠。绿色状态只用于实际可用条件。 |

先复用 AutoFlow 现有 tokens、Button/Input/Select、Dialog 和表单模式，移除安卓独立视觉偏差。保留原有设备归属、独占控制、操作幂等和结果未知保护。引擎选择与启动参数放高级设置，普通路径围绕用户要用的系统和能力组织。

不把不同实验组合包装成同一完整设备：相机在官方 AVD 通过，只能标记该 AVD 组合通过；不能给尚未实测的 HyperOS 配置自动勾选。

## 5. 最小验证顺序与停止条件

以下为实验设计，尚未执行。先在独立临时设备验证底座；通过后才决定 AutoFlow 接入设计、规格和实施计划。不开四套运行时的产品化工程。

| 阶段 | 输入与动作 | 通过条件/产物 | 不通过时 |
| --- | --- | --- | --- |
| A：Google 基线 | 实际 SDK 目录中可用的 Mac ARM64 Play 镜像，固定版本与摘要 | 冷启动、重启保留数据、商店打开/登录/安装、相机/录音/定位、触控键盘；每项保留日志和画面 | 先解决官方基线，不把问题混入 OEM 移植。账号相关项无测试账号时单列待验。 |
| B：虚拟机基线 | 固定 QEMU/LineageOS ARM64 构建与启动参数 | UI、ADB、联网、应用安装、数据持久化，连续三次冷启动并记录耗时/RAM；这是初筛而非长期稳定性证明 | 定位图形、指令集或启动问题；不直接换入 OEM GSI 掩盖底座故障。 |
| C：一个 OEM 样本 | 优先核实 HyperOS GSI 的来源、构建说明和内容摘要，再使用全新数据盘 | 厂商设置、权限授予与撤销、后台策略、系统应用、通知、重启持久化；记录与原厂公开行为基线的差异 | 无可信输入则停止下载/接入；只能亮屏或持续服务崩溃则保留实验状态。 |
| D：能力组合与应用 | 在 C 的同一镜像上测试 Google、相机、麦克风、定位及用户目标应用 | 同一组合跑通实际用户动作；标明失败和无法判定项 | 不使用 A 的成绩替代 C；评估 CHD/FMD 是否有可解决该失败的输入与机制。 |
| E：产品接入 | 只接入通过实验且覆盖需求的候选 | 一个垂直切片：系统安装→创建设备→启动操控→关闭恢复→错误处理 | 按批准规格实现，不提前扩展通用引擎框架。 |

OEM 权限验收须检查实际行为：例如关闭相机权限后应用访问是否被阻止、重新授予后能否恢复、设置是否跨重启保留。只有菜单截图不能证明权限机制一致。不使用实体手机做对照的情况下，无法从本轮测试证明全部行为与真机等价；只能报告公开基线与已测试行为。

## 6. 本轮验证记录与证据强弱

- 网络检索恢复，成功读取上述官方文档、论文正文、上游 README/脚本、GitHub release 元数据及 Cuttlefish 两个源码文件。上一轮网络失败记录仅描述上一轮，不再代表当前状态。
- 本机只读检查：Darwin ARM64；PATH 中有 `adb` 与 `limactl`，未发现 `emulator`、`sdkmanager`、`qemu-system-aarch64`；`~/Library/Android/sdk` 不存在。这只是已查路径，不证明电脑所有位置都没有相关程序。
- 再次核实 AutoFlow：`stream.py` 仍为 `audio=false`、`clipboard_autosync=false`；`mac_runtime.py` 平台门禁仍为 Darwin ARM64。未重跑旧截图或声称控制台验收通过。
- LineageOS wiki 原域名本轮 403；使用 LineageOS 项目 GitHub Pages 文档读取。社区相机故障议题正文不可充分读取，未用搜索摘要判断当前缺陷或发生率。
- 来源优先级：官方机制/源码 > 有方法与结果的研究 > 社区启动说明。没有遥测或代表性用户样本，不能给出“多数用户受影响”的频率结论。
- 验证：文档差异检查和本地链接检查；无业务代码变化，不运行无关全量测试。未安装依赖、下载系统镜像、运行上游脚本、启动虚拟机、访问相机麦克风、购买服务或操作账号。
- 尚待用户补充：优先验证的 2–3 个应用及具体动作；该信息不阻塞本轮路线研究。
