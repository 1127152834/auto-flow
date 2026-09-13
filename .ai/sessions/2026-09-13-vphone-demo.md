# vphone 实验 Demo

- 日期：2026-09-13；状态：confirmed（用户授权、有界实现、本机验证）。
- 用户要求：与安卓实验类似，将帖子中的两个项目克隆到 `reference`，开始 iOS 实验 Demo。
- 已完成：固定版本独立 Git 克隆 `vphone-aio` / `vphone-cli`；aio 跳过大体积 LFS 归档，CLI 递归子模块初始化；上游宿主与 guest 编译和签名完成，未改 upstream tracked source。
- 自有 Demo：`reference/vphone-demo`，Python 标准库 + React；本机检查、专用库设备发现、受控启停、截图触控/按键/剪贴板、最多 20 步串行回放、失败停止与 smoke 证据。地址 `http://127.0.0.1:8083`；数据根 `~/.vphone-autoflow-demo`。
- 验证：Python 6 项、Vitest 3 项、TypeScript、构建、Ruff、ESLint、bash -n 通过；浏览器真实宿主和空状态已检查。
- 实际阻塞：macOS 26.4.1 arm64、Xcode 26.2；SIP enabled、research guests disabled；上游签名二进制 preflight exit 137。没有固件下载、iOS 启动或真实自动化成功，不得写成实机验证通过。
- 未更改系统安全策略或重启；恢复模式及 AMFI 配置需要用户在本机完成，步骤已写入 README。重启后先 check，再 create，再 smoke。
- 范围：独立 reference 实验，不改正式模型管理、Automation Studio、工作流 provider 或其他已有工作区改动。
- 可复核来源：[导入清单](../../reference/README.md)、[运行指南](../../reference/vphone-demo/README.md)、[验收记录](../../reference/vphone-demo/VERIFICATION.md)、[结果 JSON](../../reference/vphone-demo/verification/result.json)。
