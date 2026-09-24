# Studio 合入 baseline

日期：2026-09-24。状态：in_progress。依据：用户明确要求“代码合并到 baseline 分支”。

- 源：`codex/project-management-pm9@82d2659761d03b0f62b29b5a4c4d36e146e4c92e`。
- 集成起点：`codex/architecture-baseline@c6e024270c0a264bc49785fa4952a9cbf4804ccc`，已包含另一任务合入的 PM9 runtime。
- 在独立 `codex/studio-baseline-integration` 工作区处理 68 个文件冲突；主目录未提交改动、来源分支及其他任务工作区保留。
- 保留 PM9 并发 owner、人工处理/End、Windows Job、资源锁、安全产物边界；接入 Studio 的节点、项目归属、模型、凭据及交互请求。单读取命令分发兼容 capability_result 与 Studio 控制消息。
- 迁移采用新增 `0022_merge_studio_pm10` 汇合两个旧 head；不改写旧迁移、不操作用户数据库。字段元数据生成同时保留可冻结 JSON 与 Python 产物，实际接口读取包内 JSON。
- 批准范围仍为 213 个 WebRPA 节点，14 个通知节点继续排除；PM9 的 3 个项目原生节点单独计数。节点验收仍为 204 已验收、9 项待实机验收；本次合并不将待验收标为通过。
- PM9 原有 `releaseAccepted=false`、Actions 35935288512 失败及各平台外部验收缺口保留；本次不发布或推送。

## 验证

进行中：后端完整 pytest、前端完整 Vitest 及合并边界回归。已完成：执行器专项 240 项、后端 507 源文件 mypy、TypeScript、OpenAPI 一致性、目录检查、renderer/main/preload 构建。最终结果以本记录后续核销为准。
