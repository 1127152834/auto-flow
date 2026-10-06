# 安卓设备平台：开源参考项目（执行与自动化侧补充）

日期：2026-10-01；状态：research（供执行环境扩展 E3–E5 细化时引用）
关系：`README.md` 第 122 行起的"参考产品"表已覆盖 scrcpy、QtScrcpy、ya-webadb、ws-scrcpy、STF、docker-android、ReDroid、Genymotion 等**模拟器管理与投屏**一侧；本文补充**群控、自动化驱动、录制、AI 操作、设备内 Chrome、每设备代理**一侧。

## 使用规则

- 只借鉴设计与流程。源码复用前先固定上游版本、核实许可证并记录来源（沿用 README 的规则）。
- 许可证列写"未核实"的，在复用任何代码前必须先核实；copyleft（AGPL / GPL）项目只看思路。
- 本文没有安装或实测任何项目；能力描述来自官方文档或项目主页。

## 对照表

| 项目 | 对应需求 | 已核实的信息 | 最值得借鉴 | 注意 |
| --- | --- | --- | --- | --- |
| [escrcpy](https://gitee.com/viarotel-org/escrcpy)（Electron + Vue + scrcpy + adbkit） | R3-06 操控、R5-01 群控 | 同一窗口控制多台设备并广播输入；批量截图、批量装 APK；局域网自动发现；gnirehtet 反向共享网络；按截图识别编排步骤并批量执行；跨 Mac / Windows / Linux | 多设备窗口编排、批量操作的交互；"步骤编排 + 图像识别"的节点形态 | README 未写许可证（未核实）；高级功能在付费的 EscrcpyX，不可拷代码 |
| [QtScrcpy](https://github.com/barry-ran/QtScrcpy)（Apache-2.0，C++/Qt） | R5-01 群控 | 群控、脚本化按键映射、文件传输、APK 安装、剪贴板同步、录屏；Windows / macOS / Linux | 群控的同步语义（坐标按比例换算）、按键映射配置格式 | C++/Qt，与 Electron 栈不同，不复制代码 |
| [uiautomator2](https://github.com/openatx/uiautomator2) + weditor | R4-03 元素定位、R4-05 录制 | Python 驱动的安卓元素树自动化；weditor 是配套的元素查看器（许可证未核实） | 定位方式（文字 / 资源 ID / 描述 / 类名 / XPath）与元素选取界面；与后端 Python 栈一致 | E4 Task 2 的 ADR 里与 Appium 并列比较 |
| [Maestro](https://github.com/mobile-dev-inc/maestro-docs) | R4-02 节点设计、R4-05 录制 | 用 YAML 描述移动端流程；带 Maestro Studio 可视化录制 / 检查（许可证未核实） | 命令粒度（启动应用、点击、输入、滑动、等待、断言）与录制体验 | 以 Java / Kotlin 实现，只借鉴设计 |
| [Airtest / Poco](https://github.com/AirtestProject/Airtest)（网易） | R4-02 找图点击 | 基于图像识别的移动端自动化；AirtestIDE 提供录制（具体许可证未核实） | "按图找图点击"节点的匹配参数（阈值、区域、多尺度） | — |
| [droidrun](https://landscape.jimmysong.io/projects/droidrun/)（MIT） | R4-02 "按描述操作" | 用自然语言驱动安卓，模型可替换，提供命令行与集成接口 | 动作空间与提示词设计；与模型管理中的视觉模型对接的方式 | 项目更名 / 实现细节（元素树还是截图）本次未核实 |
| Midscene.js、AppAgent（腾讯）、Mobile-Agent（阿里）、UI-TARS（字节） | R4-02 "按描述操作" | 视觉模型驱动的移动端操作研究 / 框架（本次未逐一核实许可证与现状） | 动作空间定义、失败恢复提示词 | 偏研究；不作为依赖 |
| [GADS](https://gittrend.io/repo/shamanec/GADS)（Go，AGPL-3.0） | R3-04 生命周期、设备占用 | 同时管理 Android / iOS 的设备农场，集成 Appium；2026-08 仍有更新 | 设备占用 / 归还、状态展示 | **AGPL-3.0，只看思路，不拷代码** |
| Zebrunner mcloud、DeviceFarmer STF | 同上 | README 已覆盖 STF；mcloud 本次未展开 | 占用模型、使用者状态 | 面向多用户设备农场 |
| [Playwright Android（实验）](https://playwright.dev/docs/api/class-android) | R4-04 设备内 Chrome | 官方标注为实验功能；支持 Chrome for Android 与 WebView；要求设备或模拟器、已认证的 adb、设备上 Chrome 87+、chrome://flags 开启命令行模式；不支持裸 USB；截图时设备必须唤醒 | 通过 adb 驱动设备 Chrome 的能力边界与限制清单 | 官方文档页面描述的是该接口本身；**Python 版是否提供该接口本次未核实**（执行进程是 Python），E4 Task 4 的调研必须先确认；备选是 adb 转发 `chrome_devtools_remote` + `connect_over_cdp` |
| [gnirehtet](https://github.com/Genymobile/gnirehtet)（Genymobile） | R3-05 每设备独立代理 | 反向共享：设备流量经电脑转发（本次依据项目所属与已知用途，未逐条核实当前版本与许可证） | 在宿主侧给每台设备接身份绑定的代理，代理断开则设备断网而非直连 | 与模拟器自带的 HTTP 代理参数对比后再选；写入 E3 Task 5 的设计 |
| [bundletool](https://github.com/google/bundletool)（Google） | R3-06 分包安装 | 处理 AAB / APKS | APKS 分包安装路径 | XAPK 是第三方打包格式，需单独解析 |
| [ARTEMIS](https://github.com/google/artemis)（Google，Apache-2.0） | S1 AI 测试 | 固定提交 `351ca8422f7b5b54e80a9c1ce03a222e02415b6b`（2026-10-06 已集成）；按用户模型驱动安卓设备完成自然语言测试任务，输出步骤与截图 | 已作为 S1「AI 测试」工具集成：AutoFlow 按固定提交安装到应用数据目录，经桥接进程（`artemis_bridge`）以 JSON 行协议驱动并回收步骤、截图与 logcat | 步骤事件通道（IPC）尚未在真实设备上验证（真机验收 blocked）；仅支持 openai / openai-compatible / gemini / anthropic 四类模型；升级固定提交前须重跑桥接测试 |

## 对计划的影响

1. **E3 Task 5（设备代理）**：先在设计里并列比较"模拟器自带代理参数"与"宿主侧 gnirehtet 式反向共享 + 代理中转"，以"代理断开设备不得直连"为判据。
2. **E4 Task 2（驱动 ADR）**：候选为 uiautomator2、Appium；weditor 与 Maestro Studio 作为元素选取与录制界面的参考。
3. **E4 Task 4（设备内 Chrome）**：调研第一步是确认 Python 侧可用的接入方式（Playwright Android 接口是否可用，或 CDP 转发）。
4. **E5 Task 1（群控）**：同步语义以 QtScrcpy 为参考，交互以 escrcpy 为参考。
5. **E4 Task 3（"按描述操作"节点）**：从 droidrun 与视觉模型研究项目中借鉴动作空间，不引入为依赖。

## 待核实清单（细化 E3 / E4 前完成）

- escrcpy、weditor、Maestro、Airtest、gnirehtet 的当前许可证与维护状态。
- Python 版 Playwright 是否提供 Android 接口。
- droidrun 当前实现方式（元素树 / 截图）与是否更名。
