# 安卓模块定位为测试工程平台，首切片集成 ARTEMIS

- 日期：2026-10-04
- 状态：confirmed（定位与范围，用户对话确认）；proposed（规格细节与 S1 是否提前解冻，待用户审阅）
- 来源：用户与 Claude 讨论；规格 [2026-10-04-android-module-audit-and-ai-testing-design.md](../../docs/superpowers/specs/2026-10-04-android-module-audit-and-ai-testing-design.md)

## 已确认

- 模拟器以测试自家 App 为主，兼顾第三方 App，需要多 App 编排；设计按可跨设备的"设备角色"建模，先交付单设备。
- 集成 Google ARTEMIS（Apache-2.0）作为安卓模块内的 AI 测试工具，暂不接入工作流。
- 不伪装真机、不隐藏 root/模拟器、不以通过 Play Integrity 为目标（沿用 2026-09-30 执行环境决定）。

## 提议

- 子项目 S1–S7（见规格 §5），S1 = AI 测试工具 + 外接设备。
- ARTEMIS 运行在独立 Python 3.12 环境（后端为 3.11），经桥接脚本调用；不使用其 Web 控制台、MCP 与一键安装脚本。
- 待决定 D1：S1 是否在整改 M6 前单独解冻。

## 验证方式

只读审计源码与文档（基线 67d08aaf）；ARTEMIS 信息来自其 README，未安装或运行。
