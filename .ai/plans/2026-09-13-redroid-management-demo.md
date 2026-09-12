# redroid 管理 Demo 计划索引

- 日期：2026-09-13。
- 状态：confirmed；用户已确认并授权实施，独立 Demo 已实现。
- 来源：用户要求 Python + React、优先直接复用两个参考项目、Windows 可用（可 WSL/Docker）、Demo 放 `reference`。
- 正文：[reference/redroid-demo/PLAN.md](../../reference/redroid-demo/PLAN.md)。
- 方案：一个独立 Demo，保留 RedroidManager Flask + Docker SDK，React 重写界面；Windows 主路径为 WSL2 Ubuntu 内的 Docker Engine；先管理、后交互、批量、Magisk 镜像对照。
- 源码基线：RedroidManager `853b786b29430886ae8db58eb2d9e3432e0c8684`；redroid-script `a4951b782fc8e06c845d9553bf07bb643fd8c158`。
- 验证方式：Python 关键分支测试、React 类型/交互/构建检查、Compose 构建与真实管理服务 HTTP/浏览器验证；详情见 [验证记录](../../reference/redroid-demo/VERIFICATION.md)。
- 2026-09-13 范围更新（confirmed，用户明确要求只在 Mac 测试）：采用 Apple Silicon + Lima VZ + Ubuntu 24.04 ARM64 + 原生 Engine，实际完成 Android 13、三实例隔离、APK 安装/失败、Magisk 构建与 ADB/shell root；结果见 [Mac 验证](../../reference/redroid-demo/MAC_TEST.md)。早期“Android/Magisk 无节点未验证”结论已 superseded。
- 未决验证：Windows+WSL2 延期；应用内申请 root、摄像头、环境伪装等能力仍未验证。
