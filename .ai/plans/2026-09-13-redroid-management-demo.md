# redroid 管理 Demo 计划索引

- 日期：2026-09-13。
- 状态：proposed；用户要求先计划，本轮不实施代码。
- 来源：用户要求 Python + React、优先直接复用两个参考项目、Windows 可用（可 WSL/Docker）、Demo 放 `reference`。
- 正文：[reference/redroid-demo/PLAN.md](../../reference/redroid-demo/PLAN.md)。
- 方案：一个独立 Demo，保留 RedroidManager Flask + Docker SDK，React 重写界面；Windows 主路径为 WSL2 Ubuntu 内的 Docker Engine；先管理、后交互、批量、Magisk 镜像对照。
- 源码基线：RedroidManager `853b786b29430886ae8db58eb2d9e3432e0c8684`；redroid-script `a4951b782fc8e06c845d9553bf07bb643fd8c158`。
- 验证方式：本地源代码与 redroid/微软 WSL/Docker 官方文档核查；未启动候选服务、构建镜像或执行 Windows 测试。
- 未决验证：当前宿主为 macOS，Windows+WSL2、Android 和具体 Magisk 镜像组合需真实节点验收。
