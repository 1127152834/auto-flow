# PM9 生产节点接通

日期：2026-09-20；状态：confirmed（实施/本机证据），发行验收仍 in_progress。
来源：`docs/superpowers/plans/2026-09-20-pm9-production-runtime.md`、真实浏览器测试、`scripts/project-runtime-smoke.mjs`。

用户确认使用 GitHub Actions；缺少的实机和真实 Sheets 证据保留待验收。基线合并已推送 `codex/architecture-baseline@8e5564e0`；PM9 后因 Studio 同目录并行编辑迁入独立 `codex/project-management-pm9-runtime`。

R1 共享图、R2 数据 RPC、R3 End/人工现已接入。R4 新同构 smoke 用正式 Studio HTTP 保存、项目批次、真实 worker 和浏览器执行多表/参数/人工继续/保存关联/登录复用，源码与 PyInstaller 产物均通过。原仅四节点浏览器或 QA fixture 证据不代表此范围；独立审查及本机工程回归现已完成，三平台 CI 持续以验证报告为准。

人工恢复仅延续存活 owner；持久检查点作为版本与中断证据。中断不重放，不冒称跨进程恢复。相应取舍与成本已写入计划 Ruling。

最终审查 4 P1 / 3 P2 已逐项处置，见 `pm9/final-review.md`。本机后端候选 b72938b8 全量 3195、CI 候选 66a428aa 前端 5455、真实浏览器 12 场景通过；生产打包万行 UI 与千条日志测量通过。Windows 发现旧代码页中文协议错误及负载预算不足，分别增加 UTF-8 协议回归和独立测量预算。归档前复用任务 End 命令明确清理失败任务工作副本，避免把保留现场的正常阻断当成自动丢弃授权。

后续三平台 CI 暴露并修复 Framework Python 原生进程身份、schema 默认代码页与 UTF-8 测试夹具问题；Windows/macOS 两套 mypy 均通过 396 文件。Windows 原生文件输出和无原生所有权证据的孤儿回收仍明确拒绝，不因构建安装包或跳过 POSIX 场景而升级为已验收。来源：R4 实施账本与 Actions 实际日志；状态：confirmed。

2026-09-21 追补（confirmed；来源：Actions 候选 0f883cb1 的 step conclusion 和平台回归）：Windows 扩展原生边界检查已通过。修复了只读句柄 fsync 的 XLSX 失败、运行产物的目录 fsync 平台差异、冻结对照子进程环境丢失和 EOF 夹具等待；原生工作流任意路径输出限制保持。全量 CI 与最终安装包结果见机器报告，不据前置检查通过提前关闭发行验收。

2026-09-21 固定负载追补（confirmed；来源：a314ead1 本机打包报告）：60.032 秒生成并通过真实 HTTP 读回 1000 条合成日志，期间万行记录翻页 114–131 ms，最大生成批次延迟 38 ms。通过现有事件仓库写入 smoke 临时工作区，不新增生产接口、不把合成日志算作真实 worker 吞吐。该 a314ead1 为历史候选，最终三平台状态由 verification.json 给出。

2026-09-21 写竞争修复（confirmed；来源：原生 Windows 7aacd53f 堆栈、d59607f3 持锁 HTTP 红绿回归与本机重新打包）：保留原五路单条写入一万行场景。SQLITE_BUSY 从 500 改为可识别 503；测试调用保留原命令键、最多尝试 10 次并报告 busyRetries，不重试其他内部错误。70 项相关后端、97 项脚本、两平台 mypy 397 文件及 OpenAPI/lint/typecheck 通过；本机真实源码和重新打包链均通过，一万行 busyRetries=0，合成 1000 条/60.031 秒且最大批次延迟 41 ms。当前代码候选 d59607f3，Actions 35531206432；全量平台结果随后记入同一验证报告。

2026-09-21 最终候选 d59607f3（confirmed；来源：Actions 35531206432 三个原生 job 全部 success）：Windows 后端 3180 passed / 57 skipped；Intel/ARM 各 3214 passed / 23 skipped；前端各 5455 passed / 405 文件。源码及打包真实执行链、原规模五路万条、固定 1000 条/分钟合成输入、安装包构建及上传全部通过。Windows 万条耗时 725733 ms，发生 1 次明确 503 忙重试且保留原键，最终正好 10000 条；真实 worker 1004 条耗时 112121 ms（537 条/分钟），不能把独立合成输入通过写成 worker 达到千条/分钟。Windows/Intel/ARM 合成 1000 条全部读回，分别 60105/60038/60055 ms，最大批次延迟 143/181/202 ms。实网 Sheets、物理安装/原生专项、签名公证和历史完整规格余项仍待验收，releaseAccepted=false。
