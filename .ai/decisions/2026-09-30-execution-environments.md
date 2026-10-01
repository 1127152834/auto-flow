# 执行环境扩展：浏览器内核渠道、安卓设备平台、iOS

日期：2026-09-30；状态：proposed（待用户审批规格与计划）

## 背景

用户确认：CloakBrowser 使用免费版；安卓设备会跑各种网站或各种 App，不针对特定应用；整改期间冻结安卓 / iOS。

## 决定（提议）

1. 浏览器继续用 CloakBrowser 公开版内核（GitHub Releases），不接入"登录后的最新免费版"（同时只能 1 个会话）；若将来接入，强制并发 1。
2. 引入 `BrowserEnginePort`，CloakBrowser 为唯一实现；Camoufox 仅在以下任一条件成立时评估接入：公开渠道停止发布超过 6 个月、落后 Chrome 稳定版 ≥ 8 个大版本、出现并发限制。
3. 安卓做成通用设备平台：官方 Android Emulator（AVD）为 Mac 与 Windows 主运行时，ReDroid-on-Lima 保留；不伪造硬件标识，不以绕过 Play Integrity 为目标。
4. iOS 不做；重新立项条件：明确业务需求且接受实体 iPhone。
5. 厂商 ROM 为研究轨道，不进入产品承诺。

## 顺序

E1 在整改 M1 后，E2 在整改 M4 后，E3–E5 在整改 M6 后；E6 研究随时可做。

## 正文

- 规格：docs/superpowers/specs/2026-09-30-execution-environments-design.md
- 计划：docs/superpowers/plans/2026-09-30-execution-environments-milestones.md
