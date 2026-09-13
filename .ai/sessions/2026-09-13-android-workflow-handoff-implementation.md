# Mac 安卓工作流实现交接

2026-09-13 · confirmed；来源：用户“开始吧”、实际代码和验证产物。

实现：5 个安卓节点、真实设备列表和选择、人工接管面板、原生 scrcpy、截图结果、占用/回执/停止/恢复。工作流画布因运行标记更新丢失 measured 尺寸的问题一并修复。

验证：源码与冻结 sidecar 对真实新 Android 运行；Mac 打包应用人工阶段以原生键盘进入设置子页；关窗等待、显式继续、错误包名、尺寸变化、实际 tap、超时/停止和 sidecar SIGKILL 恢复。浏览器六节点及 M3 进程回收回归通过。具体计数、截图、未测边界见 docs/migration/android-workflow-handoff-validation.md。

专用工作区留在 autoflow-android-handoff/.local/android-handoff-workspace；启动 scripts/open-android-demo.command。原有三台 Demo 设备保留。

主工作区同时开发 M4（新增执行/产物契约与 0007_workflow_artifacts），本轮没有将安卓分支覆盖到该工作区。后续合并需汇合 0007_android_devices 与其迁移，不改写已应用 revision。正式分支基于 M3 d43ee31，不携带临时隔离基线提交。
