# PM9 生产节点接通

日期：2026-09-20；状态：confirmed（实施/本机证据），发行验收仍 in_progress。
来源：`docs/superpowers/plans/2026-09-20-pm9-production-runtime.md`、真实浏览器测试、`scripts/project-runtime-smoke.mjs`。

用户确认使用 GitHub Actions；缺少的实机和真实 Sheets 证据保留待验收。基线合并已推送 `codex/architecture-baseline@8e5564e0`；PM9 后因 Studio 同目录并行编辑迁入独立 `codex/project-management-pm9-runtime`。

R1 共享图、R2 数据 RPC、R3 End/人工现已接入。R4 新同构 smoke 用正式 Studio HTTP 保存、项目批次、真实 worker 和浏览器执行多表/参数/人工继续/保存关联/登录复用，源码与 PyInstaller 产物均通过。原仅四节点浏览器或 QA fixture 证据不代表此范围；最终工程回归/三平台 CI/独立审查仍待收尾。

人工恢复仅延续存活 owner；持久检查点作为版本与中断证据。中断不重放，不冒称跨进程恢复。相应取舍与成本已写入计划 Ruling。

最终审查 4 P1 / 3 P2 已逐项处置，见 `pm9/final-review.md`。本机全量后端 3191、前端 5454、真实浏览器 12 场景通过；生产打包万行 UI 与千条日志测量通过。Windows 发现旧代码页中文协议错误及负载预算不足，分别增加 UTF-8 协议回归和独立测量预算。归档前复用任务 End 命令明确清理失败任务工作副本，避免把保留现场的正常阻断当成自动丢弃授权。
