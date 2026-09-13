# 安卓模块当前实现

日期：2026-09-13。状态：confirmed（隔离分支实现与已记录验证）。来源：用户确认的四图计划、代码、docs/validation/android-exact-2026-09-13。

- 正式实现位于 `../autoflow-android-handoff` 的 `codex/android-workflow-handoff`，不是 reference 中独立 Demo。
- AndroidPage 组装 ResourceBoard、CreateInstances、DeviceConsole；原图 fixture 和生产复用组件，fixture 只有开发模式可访问。生产设备、批次、分配、控制、应用、历史均从真实 API 获取。
- 仅 Apple Silicon Mac 本轮实测：Lima + Docker + ARM64 Android 13，scrcpy 3.3.4，H264 + WebCodecs 内嵌画面。页面／原生窗口共享设备输入权。
- 默认批量 3、持久／临时、容量等待、按设备并发、动作边界暂停接管、成功临时回收／失败保留均已实现。root 以实际探测显示，不承诺镜像已支持应用级 root。
- 四图及原始素材来源在 docs/references/android-prototype-exact-2026-09-13；最终截图、几何和真机证据在 docs/validation/android-exact-2026-09-13。
- 不将 10 分钟传输稳定性和 HTTP 确认时间称为画面 FPS 或端到端点击延迟；原规格 proposed 性能目标仍需专门测量。
- 主线 `25273d5` 移除了旧工作台。本安卓分支保留已确认的 M5 接管功能，主线集成路线待用户决定。
