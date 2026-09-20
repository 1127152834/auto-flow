# 项目管理 PM9 验证

日期：2026-09-21；状态：生产运行时已接通，本机与三平台 CI 工程、打包和安装包构建通过；**最终发行验收保持未关闭**。

有效代码先合入并推送 `codex/architecture-baseline@8e5564e0`。实施分支现为 `codex/project-management-pm9-runtime`，工作树独立，避免与 Studio 任务交叉编辑。

权威入口：[机器报告](../project-management/implementation/pm9/verification.json)、[覆盖核对](../project-management/implementation/pm9/coverage-audit.json)、[独立审查处置](../project-management/implementation/pm9/final-review.md)、[R1–R4 实施卡](../superpowers/plans/2026-09-20-pm9-production-runtime.md)。早期“四节点/待架构确认”结论已由用户确认后的 R1–R4 实施取代，历史报告不删除。

生产链使用正式 Studio HTTP 保存、生产 sidecar、SQLite、项目调度、真实 worker 与 CloakBrowser，没有 QA 执行器。覆盖参数、多表条件读写、End 保存关联、另一自动化读回登录、人工继续/终结/超时/停止/重启/进程丢失、原键恢复、真实超时后的原输入组后续、统计下钻及归档恢复。失败工作副本通过现有任务收尾命令明确清理后再归档，不自动丢弃现场。

打包 Electron 候选 d59607f3：通过五路并发正式 HTTP 单行命令创建 10,000 条记录，每页显示 50 行；保持原规模验证。另以既有事件仓库按 1000 条/分钟生成合成日志，同时测量真实 HTTP 分页、记录翻页和 GC 后堆；本机全部读回，60031 ms，最大批次延迟 41 ms。详细逐次数据见机器报告；合成输入与实际 worker 吞吐分别记录，一次短时测量不是持续压力或无泄漏保证。

Windows 前置回归已取得写锁故障堆栈：BEGIN IMMEDIATE 报 database is locked。复用既有 SQLite 错误分类，HTTP 返回 503 DATABASE_BUSY 与 Retry-After；仅该明确响应在并发 smoke 中用原命令键有界重试，其他错误继续失败。原规模万条写入保留，并记录 busyRetries。真实持锁/释放/原键重放验证仅一条记录；最终 Windows 原规模万条运行通过，发生 1 次忙重试后仍正好 10000 条，原生持锁 HTTP 回归也通过。万行 Excel 导入/分页/导出另见 volume.json。

```sh
node scripts/smoke-project-management.mjs --runtime-kernel /absolute/path/to/installed/Chromium --output-dir /tmp/pm9-source
npm run backend:build
npm run package:dir
node scripts/smoke-project-management-desktop.mjs --executable /absolute/path/to/AutoFlow --runtime-kernel /absolute/path/to/installed/Chromium --output-dir /tmp/pm9-packaged
```

两个 smoke 只写本次创建的临时工作区，拒绝 QA sidecar/开发 URL 注入。桌面入口提供键盘焦点、六个真实页签、200% 原生缩放、Studio 双窗口共享服务与重启证据。报告不保存 token。

三平台同一代码候选 d59607f3 的 [Actions 运行](https://github.com/1127152834/auto-flow/actions/runs/35531206432) 已全部成功，原始报告与安装包摘要如下。Windows 负载测量预算为 600 秒，实际吞吐必须保留，不能把放宽超时当作性能提升。

Windows 原生安全工作流文件输出与缺少原生所有权证据的孤儿进程回收仍明确拒绝；POSIX 输出场景在 Windows 跳过，拒绝与证据保留行为独立测试。这些限制不影响已验证的项目记录写入链，但不能算作 Windows 完整工作流能力通过。

实网 Sheets、签名/公证、物理安装、原生文件面板与凭据专项仍待验收。包含循环或人工节点的并行图、跨进程人工恢复及未接入项目端口的 Studio 节点明确不支持。48 功能、178 场景、25 契约的历史状态逐项保留；新增有界证据不等于整个产品规格全部通过。

| 原生 CI 平台 | 后端通过 / 跳过 | 前端通过 | 五路万条耗时 / 忙重试 | 真实 worker 日志/分钟 | 安装包及报告 |
| --- | --- | --- | --- | --- | --- |
| Windows x64 | 3180 / 57 | 5455 | 725733 ms / 1 | 537 | [EXE 与原始报告](../project-management/implementation/pm9/ci-win32-x64.json) |
| macOS Intel | 3214 / 23 | 5455 | 104904 ms / 0 | 1642 | [Intel DMG 与原始报告](../project-management/implementation/pm9/ci-darwin-x64.json) |
| macOS Apple Silicon | 3214 / 23 | 5455 | 85377 ms / 0 | 1539 | [ARM DMG 与原始报告](../project-management/implementation/pm9/ci-darwin-arm64.json) |

各平台前端均为 405 文件；五个报告分别记录 HTTP 前置、源码 API、源码桌面、打包 API 和打包桌面。所有安装包均已上传到同轮 Actions artifact，链接、摘要与过期时间见平台报告。Windows 万条准备约 12.1 分钟，真实 worker 未达到每分钟千条；独立合成输入 1000 条全部读回只证明该输入速率下的有界分页与界面行为。工程交付与 CI 已完成，发行验收仍保持未关闭。
