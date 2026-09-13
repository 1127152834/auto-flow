# 安卓四图实现与验证记录

日期：2026-09-13。状态：隔离分支功能已实现并通过下列验收，主线集成待决策；**尚未宣布主线完整交付**。源码位于 `codex/android-workflow-handoff`；M5 汇合提交 `add29d8`。本记录不继承旧缩减版的视觉 passed。

## 已实现

- 正式 React 页面共用组件：六状态资源看板／实例表格、创建数量默认 3、环境模板、持久／临时、等待分配表、控制台四标签、输入侧栏、工作流暂停接管。生产界面从正式 API 读数据。
- 新迁移 `0009_merge_android_m5` 汇合旧历史，`0010_android_fleet` 保存环境、不可变批次快照、逐台状态、分配队列、控制请求回执。已成功设备不因重试重建。
- 每设备独占锁和运行上下文；VM 预算／创建继续串行。同设备冲突返回 409，其他设备可独立运行。
- 页面 H264 连续画面、点击／拖动／长按、键盘、中文、系统导航、音量、旋转、截图、APK 安装和启动；独立 Mac 窗口与页面切换控制权。关闭、失焦及会话过期释放按键。
- 普通安卓工作流在动作边界确认暂停后才允许接管；继续保留当前 worker 调用栈和 runId，不重放动作。临时成功回收，失败／中断保留；持久保留数据。
- 会话代次和输入序号拒绝迟到／重复消息；未知结果不重发。APK 使用受控临时文件与完成标记，未知结果阻止后续人工输入，清理失败可显式重试。

## 视觉证据

原图顶部 34 像素为原生标题栏，比较时只排除此区域。产品导航没有裁掉。R1 客户区为 1487×1024；R2–R4 为 1489×1022。没有缩放页面来对齐。

| 页面 | 同状态实际图 | 并排 | 50% 叠图 | 差异图 |
| --- | --- | --- | --- | --- |
| 六卡资源看板 | [实际](board-actual.png) | [并排](board-side-by-side.png) | [叠图](board-overlay.png) | [差异](board-diff.png) |
| 手动控制台 | [实际](manual-actual.png) | [并排](manual-side-by-side.png) | [叠图](manual-overlay.png) | [差异](manual-diff.png) |
| 默认 3 台创建 | [实际](create-actual.png) | [并排](create-side-by-side.png) | [叠图](create-overlay.png) | [差异](create-diff.png) |
| 工作流第 3/6 步接管 | [实际](takeover-actual.png) | [并排](takeover-side-by-side.png) | [叠图](takeover-overlay.png) | [差异](takeover-diff.png) |

固定样本只有开发模式入口 `?androidFixture=board|manual|create|takeover`，复用生产的 ResourceBoard、CreateInstances、DeviceConsole。发布构建未包含该入口或六台虚构设备；配置页的手机仅为明示的设备示意。九张裁切素材来源与边界记录在 `docs/references/android-prototype-exact-2026-09-13/asset-measurements.md`。

几何实测见 [geometry-actual.json](geometry-actual.json)。原图带生成图的渐变、噪声和字体抗锯齿，逐像素差异非零；不能把相似度分数写成“一模一样”的证明。已测量的 17 处主要区块和高频控件全部满足各自 4／2 像素阈值；此结论只覆盖列出的矩形，并非每个文字的逐像素一致。边界对比见 [geometry-check.json](geometry-check.json)。

## 真实 Apple Silicon Mac 验证

运行时：Lima `autoflow-redroid`、6 CPU、约 7.9 GB RAM、binder 可用；ARM64 Android 13 固定镜像 `sha256:5a42a569ee1d7c71796c0385e906cbaa4c3e0a162a56d9f26b29bdb1befac13b`；软件渲染；scrcpy 3.3.4。

| 场景 | 结果和证据 |
| --- | --- |
| 真实批量创建 3 台、独立容器／卷 | 通过，[functional.json](functional.json)，含逐台创建／启动／就绪记录 |
| 两台手动连接、同设备争抢、旧序号和原生代次 | 通过，同上 |
| 两台真实工作流并发，继续不重复执行 | 通过，同上，真实 worker 进程 |
| 中文、APK、启动、持久文件重启仍保留 | 通过，同上，[设备输入](real-chinese-input.png) |
| 当前动作未结束时禁止输入／安装，确认暂停后接管 | 通过，[functional-followup.json](functional-followup.json) |
| 长按和旋转 | [长按截图](real-long-press.png) 显示剪切／复制／粘贴／分享／全选；旋转截图尺寸 1280×720。原 XML 没有浮动选择菜单，因此 JSON 中 `long_press_menu_in_hierarchy` 的 XML 检测为 false，不能将其静默改写成 true；截图提供实际补充证据 |
| 临时成功回收、卷删除 | 通过，functional-followup.json |
| 真实容量等待／取消，临时运行失败保留 | 通过，[functional-final.json](functional-final.json) |
| 新 APK 安装完成标记 | 通过，functional-final.json |
| Mac 包实际解码和侧栏中文发送 | 通过，[桌面实时画面](packaged-live-console.png)、[桌面中文输入](packaged-chinese-input.png)；由应用内点击启动 API Demos 并发送“页面中文验收” |
| 最终 Mac 包复测 | multipart 上传显示“APK 已安装”；应用标签返回控制台、真实点击偏好列表、结束控制均通过。[最终控制台](packaged-final-console.png)。修复缓存 GOP 集中解码导致误报延迟的问题，按解码队列背压送帧，未丢弃任意依赖帧 |
| 10 分钟连接稳定性 | 600.44 秒、901 个传输包、4,604,297 字节、0 个传输错误。20 组音量按键请求的 HTTP 确认 p95 为 5.14 ms。此值不是画面反馈延迟，静态界面不用于证明动画帧率 |

API Demos 来自 Appium 官方 [v6.0.17 release](https://github.com/appium/android-apidemos/releases/tag/v6.0.17)，APK SHA-256：`90cc1041c063a7fb68889143250fefa3139ef0c81e4208f67dbaafe8f15c8be9`。测试 APK 与工作区留在忽略的 `.local`，不加入正式包。

## 工程检查与边界

最终命令结果见 [checks.json](checks.json)。全量覆盖 Python、React、M4/M5、迁移、OpenAPI、一致性、类型／lint、脚本、构建和 Mac 包。一次并行重负载回归出现旧 browser worker 50 ms 清理测试失败，独立重跑 3 个变体通过，随后全量 611 项通过。React 最终 441 项通过。

Mac 包没有可用 Developer ID 签名，适用于本机验收；未测试 Windows。实际 root shell 显示“不可用”，应用级 root 显示“待独立验证”，没有沿用视觉样本的 root 成功标记。15 fps／点击到可见反馈 p95≤250 ms／两路只读加一路人工是原规格中的 proposed 性能目标，本轮只实测上述传输稳定性和单控制台真实画面，未宣称这些性能目标已通过。

## 主线集成变化

验证期间主线新增 `25273d5`，删除旧工作台及大量工作流实现。本次经过确认的 M5 安卓接管与该变更冲突。已向用户提出交付路线选择，未恢复或覆盖主线旧代码。此前“主线 M5 已完成、可直接汇合”的判断不再适用于最新主线。

## 启动

在安卓隔离工作树执行 `scripts/open-android-demo.command [已准备的工作区路径]`，默认使用 `.local/android-handoff-workspace`。先保存并关闭正在运行的旧版 AutoFlow 窗口，再启动新包，避免旧进程继续显示缓存的旧界面。当前用户窗口的未保存流程没有被关闭或改写。

包：`apps/desktop/dist/mac-arm64/AutoFlow.app`。构建命令：`npm run build`、`npm run backend:build`、`npm run package:dir`。生产入口为全局导航“安卓模拟器”。独立窗口入口在设备详情“更多设备操作”中。所有测试创建的容器和卷清理及原 Demo 恢复记录见 [cleanup.json](cleanup.json)。
