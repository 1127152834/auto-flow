# vphone-aio / vphone-cli 平台支持核查

- 日期：2026-09-13
- 状态：confirmed（官方文档及源码静态核查）；未安装、编译或启动虚拟机。
- 范围：确认帖子所指仓库、Windows/macOS 本地运行条件及远程控制边界；本次属于探路，不涉及 AutoFlow 实现或架构变更。
- 输入：[用户指定帖子](https://x.com/lksmlabc/status/2098684287226941689)。X 直读返回 403，通过 FxTwitter 公共接口解析出两个仓库，再以仓库本身验证技术结论。
- 代码快照：vphone-aio `1db79dccd95391d6247c41f3cc4eac523567f295`；vphone-cli `9c23c8adcd4b362120988ab9d228b959bcc23ae3`（GitHub API 查询所得）。

## 结论

1. 两者均不是 Windows/macOS 双平台本地 iOS 运行时。vphone-cli 官方要求 Apple Silicon、macOS 15+、Xcode/iOS SDK 和 SIP/AMFI 相关配置。Intel Mac 和 Windows（包括 ARM Windows）均不在支持范围。
2. vphone-aio 是预配置 vphone-cli 环境的分卷归档及启动脚本，README 标称 iOS 26.1、已越狱并装有 bootstrap；作者明确推荐转向 vphone-cli。启动脚本明确要求 macOS 与 Xcode，未提供独立 Windows 引擎。未下载大体积归档，因此不把当前 cli 的精确最低系统版本当作 aio 归档内版本的独立实测结果。
3. vphone-cli 的 Package.swift 声明 `.macOS(.v15)`，链接 Virtualization、AppKit、SwiftUI 等框架；虚拟机代码使用 VZVirtualMachine、VZMacPlatformConfiguration 和私有 PV=3 能力。Windows 障碍在底层运行时，不能靠改写 shell 脚本、WSL 或 Docker 解决。
4. 官方 FAQ 明确当前 PV=3 guest boot 不支持嵌套。因此 Windows 内先开 macOS 虚拟机再启动 vphone，不是项目支持的可用路径。
5. Windows 作为远程控制端有技术可行性：cli 文档提供 VNC/SSH 连接方式，但仍需符合条件的 Mac 承载虚拟机；跨机网络及自动化接入尚未实测。
6. cli 的测试环境表包含 iOS 27 条目；这说明 guest 版本覆盖，不代表 Windows 支持。反虚拟机检测补丁被标记为研究用途，不能据此认定所有 App 的设备指纹或验证均已解决。

## 对 AutoFlow 的含义

- 若要求 Windows/macOS 用户均在本机启动 iOS 环境，两者不满足选型要求（高置信）。
- 若允许共用 Apple Silicon Mac 执行节点，可继续研究 Windows/macOS 控制端连接 Mac 的方式；此为候选方向，尚未批准或实施。
- 后续价值验证应关注目标 App 安装/登录、截图与触控自动化、多实例资源成本及稳定性；本次不宣称已验证这些能力。

## 补充：Windows 运行 iOS 的其他路线

- 日期：2026-09-13；状态：confirmed（官方网页及维护者答复核查，未实机运行）。用户追问 Windows 是否存在其他办法。
- 上述 Windows 不支持结论仅针对两个 vphone 项目，不能推广为 Windows 无任何 iOS 本地仿真方案。
- **ChefKiss Inferno**：QEMU 衍生项目，维护者在 [Discussion #212](https://github.com/ChefKissInc/Inferno/discussions/212) 明确表示支持 Windows，但团队不使用 Windows，相关说明不完善；同帖维护者提到 Linux/WSL 2 可采用实验性 APFS 驱动。此为支持声明，不等于本次验证成功。
- [Inferno 官方能力页](https://chefkiss.dev/applehax/inferno/)（页面标注 2026-09-12 更新；web 读取 403，curl 成功取得 HTML 并提取 main 文本）列出：iPhone 11 可进入 SpringBoard，iPhone 6s Plus 为 WIP 且无 UI；当前 iOS 14.x，13/15/16/17/18/26 属未来支持；iCloud/App Store、生物识别和锁屏密码不工作。不能沿用第三方旧介绍将当前范围锁为仅 iOS 14 beta 5。
- [Inferno 安装指南](https://chefkiss.dev/guides/inferno/)明确要求 companion VM 处理恢复与网络，需要文件系统补丁开启软件渲染，目前无 GPU 仿真。官方列出最低 6GB RAM、约 32GB 空闲磁盘，但本次未测量实际总开销、速度或多实例表现。适合有界可行性实验，不能直接承诺现代 App 自动化兼容性。
- **devos50/qemu-ios**：[iPod Touch 2G 分支说明](https://github.com/devos50/qemu-ios/blob/ipod_touch_2g/RUNNING.md)包含 Windows MSYS2/MinGW64 构建步骤，属于旧设备系统仿真，不能代替现代 iOS。
- **touchHLE**：[官方 FAQ](https://touchhle.org/faq.html)确认支持 Windows/macOS，主要运行早期 32 位 iPhone OS 2.x/3.0 应用，兼容数量有限；属于应用高层仿真，不是完整现代 iOS 系统。
- **Corellium**：Windows 浏览器可作为云端虚拟 iOS 的控制端。[浏览器支持](https://support.corellium.com/troubleshooting-faqs/corellium-isnt-working-properly-on-my-browser)；[iOS 限制](https://support.corellium.com/devices/ios)包括无 iCloud 登录、无 App Store 下载、缺少 Metal 支持。实际系统在远端，不是 Windows 本机执行。
- **BrowserStack App Live**：[官方说明](https://www.browserstack.com/docs/app-live)提供远程真机交互测试及 App Store/TestFlight/上传安装入口；与只做网站测试的 Live 产品有区别。适合现代 App 真机兼容性测试；本次未验证会话持久化及长期任务适用性。
- **Appetize**：[官方上传限制](https://docs.appetize.io/platform/app-management/uploading-apps/ios)只接受 iOS Simulator 的 .app 构建，不接受 App Store 真机 .ipa；适合有源码/模拟器构建的应用演示测试。

判断：Windows 本地路线值得优先验证 Inferno；若目标是当前第三方 App 的实际工作流，应优先验证远程真机。两者都是候选判断，未进行安装或采购。

## 补充：macOS 上的 AutoFlow iOS 自动化可行性

- 日期：2026-09-13；状态：confirmed（上游源码事实）/ proposed（接入方向）；未启动 VM 或实施 AutoFlow 功能。
- 用户询问仅在 macOS 使用 AutoFlow 时，能否设计类似安卓的 iOS 自动化。这是条件性可行性讨论，不改变 AutoFlow 原有 Windows/macOS 总体平台范围。
- [VPhoneHostControl.swift](https://github.com/Lakr233/vphone-cli/blob/9c23c8adcd4b362120988ab9d228b959bcc23ae3/sources/vphone-cli/VPhoneHostControl.swift)提供每行 JSON 的 Unix socket 协议：screenshot、tap、swipe、key、type；type 实际仅调用 clipboardSet，不是焦点输入。图像默认缩小到原尺寸 1/3 的灰度 JPEG；传 path 可另存截图。点击坐标使用完整屏幕像素，接入时必须映射。截图及触控路径检查 view.window 非空，因此不能先验宣称支持完全无界面的批量运行。
- [vphoned_accessibility.m](https://github.com/Lakr233/vphone-cli/blob/9c23c8adcd4b362120988ab9d228b959bcc23ae3/scripts/vphoned/vphoned_accessibility.m)明确为 stub，始终返回 accessibility_tree 尚未实现；不能因宿主存在 accessibilityTree 方法就宣称有可用控件树。
- [VPhoneControl.swift](https://github.com/Lakr233/vphone-cli/blob/9c23c8adcd4b362120988ab9d228b959bcc23ae3/sources/vphone-cli/VPhoneControl.swift)已有应用列表/启动/终止、IPA 安装、文件、URL、位置等宿主到 guest 通道方法；这些方法并未全部暴露在上述外部 host socket 中，需要扩展桥接并实测。
- [vphone-mcp](https://github.com/pluginslab/vphone-mcp)证明已有外部 Python 控制封装；README 的 open_app 是预映射桌面导航，不能当通用 bundle ID 启动 API；无需将 MCP 作为 AutoFlow 必选运行依赖。
- 对照 [Android UI Automator](https://developer.android.com/training/testing/other-components/ui-automator)，后者提供元素查找、文本设置、等待和无障碍节点。当前 vphone 更适合作为截图识别 + 触控的基础。Appium/XCUITest/WDA 可作为后续元素定位候选，但官方支持普通 iOS 不代表已适配 vphone，须独立验证。
- proposed：沿用现有工作流执行、变量、条件、循环与日志，增加可选 iOS provider；先用 CLI 管实例、Unix socket 做截图/触控，再补文字输入/应用生命周期桥接和 OCR/图像识别。视觉判断成功需检查实际图像及操作后状态，不能只依赖 ok:true。
- proposed 最小验证：一个真实目标 App，安装/启动/登录 → 截图 → 输入 → 点击/滑动 → 结果断言 → 重启后复跑；之后再测两个实例同时运行及资源成本。完整模块仍需规格、实施计划和用户确认。

## 补充：用户授权实验后的实际状态

- 日期：2026-09-13；状态：confirmed。此前“未运行上游脚本、未实施功能”仅描述前面的调研阶段，该执行状态现已 superseded；平台与协议源码判断不变。
- 两个仓库已固定版本克隆到 `reference`，CLI 含递归子模块，aio 的大体积 LFS 归档未下载。CLI 宿主 app 与 guest daemon 已编译签名。
- 独立 `reference/vphone-demo` 已实现本机诊断、设备管理和截图触控回放；Python 6 项与前端 3 项测试通过，类型检查/lint/构建通过。
- **真实 iOS 仍未启动**：当前宿主 research guests disabled，签名宿主二进制 preflight exit 137。未更改 SIP/AMFI。需用户完成恢复模式配置与重启后继续真实链路验证。
- 详细证据与继续步骤见 [VERIFICATION.md](../../reference/vphone-demo/VERIFICATION.md)。不得将协议单测或页面完成当成真实 iOS 自动化通过。

## 来源及验证方式

- [vphone-aio README](https://github.com/34306/vphone-aio/blob/1db79dccd95391d6247c41f3cc4eac523567f295/README.md)：环境、iOS 版本、作者推荐、磁盘建议。
- [vphone-aio.sh](https://github.com/34306/vphone-aio/blob/1db79dccd95391d6247c41f3cc4eac523567f295/vphone-aio.sh)：macOS/Xcode 前置条件与归档启动流程。
- [vphone-cli README](https://github.com/Lakr233/vphone-cli/blob/9c23c8adcd4b362120988ab9d228b959bcc23ae3/README.md)：主机条件、连接方式、固件变体、测试环境、嵌套限制。
- [Package.swift](https://github.com/Lakr233/vphone-cli/blob/9c23c8adcd4b362120988ab9d228b959bcc23ae3/Package.swift)：平台声明与框架链接。
- [VPhoneVirtualMachine.swift](https://github.com/Lakr233/vphone-cli/blob/9c23c8adcd4b362120988ab9d228b959bcc23ae3/sources/vphone-cli/VPhoneVirtualMachine.swift)：Apple 虚拟化与私有设备配置调用。
- 验证：使用网页读取、`curl` 读取官方原始文件和 GitHub API；交叉核对 README、构建配置和启动源码。未运行上游脚本，未修改主机安全配置。仅新增本记录，现有工作区改动未触碰；无业务代码变更，不适用应用测试/lint/构建。
