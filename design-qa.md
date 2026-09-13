# 安卓四图还原设计验收

日期：2026-09-13。状态：confirmed（下列已测范围）；主线集成 pending。此记录替代旧缩减版 QA，不继承旧版 passed。

四张用户原图为唯一视觉基准；恢复六卡三列看板、等待任务表、三步批量创建、手动输入侧栏和动作边界接管面板。客户端截图只剔除原图的 34px 原生标题栏，没有缩放对齐。生产和开发视觉状态共用组件，发布包不含固定六台设备。

| 页面 | 同尺寸并排证据 |
| --- | --- |
| 资源看板 | [对比](docs/validation/android-exact-2026-09-13/board-side-by-side.png) |
| 手动控制台 | [对比](docs/validation/android-exact-2026-09-13/manual-side-by-side.png) |
| 创建实例 | [对比](docs/validation/android-exact-2026-09-13/create-side-by-side.png) |
| 工作流接管 | [对比](docs/validation/android-exact-2026-09-13/takeover-side-by-side.png) |

[完整记录](docs/validation/android-exact-2026-09-13/README.md)包括实际图、叠图、差异图和真实 Mac 功能证据。[几何检查](docs/validation/android-exact-2026-09-13/geometry-check.json)中 17 处已测矩形全部满足 4px 主区块／2px 控件阈值。原图生成字体、噪声及抗锯齿仍有差别，不能宣称全像素相同或未测控件全部通过。置信度：高（已测布局与功能）。

原先遗漏的控件现在均有正式实现。实际 root 能力按设备结果展示，未将参考图成功徽标用于生产。页面内连续画面和独立 Mac 窗口共享设备控制权；工作流占用时服务端限制人工输入。

最终 Mac 包实测通过 APK 上传、中文、真实触控、应用标签返回画面和结束控制。两设备并发、批量三台、动作边界接管与数据清理见上述记录。性能目标仍有未测项；主线新提交删除旧工作台，与 M5 方案冲突，尚未集成，未宣布整个计划完整交付。
