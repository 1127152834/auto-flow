# 项目管理业务梳理与总体方案

- 日期：2026-09-12。
- 状态：研究 confirmed，总体方案 proposed，等待用户审查。
- 范围：旧项目历史讨论/决策/设计与新 AutoFlow 当前前后端基线对照；仅文档，不改业务代码或数据。
- 工作树：`autoflow-project-management-design`，分支 `codex/project-management-design`，基于主线 `2faf2a0`；原主目录的 Studio/模型任务未修改。
- 技能：Superpowers brainstorming、verification-before-completion；Ponytail 用于复用取舍。三项只读研究并行，另做方案独立审查。

旧提交 `324748a` 的 `.ai/01-Project-Management` 共 135 份 Markdown，另加最新数据规格/计划 2 份，已建立内容哈希索引。原型 198 个 PNG、112 个不同内容。历史文件大量不在磁盘，通过固定提交读取，未还原旧工作树。

主要裁定：六页签继续保留；R5 四页签替代五步/独立运行方案；一自动化一配置；最新数据方向仅 Excel/Sheets。旧实际执行、统计、持久环境仍占位，Excel CRUD 和每次 Sheets 推送后核验不能当已有。新主线同样尚无项目领域，Studio 为未接入工作稿；统一 UI 分支 `1fb58e1` 尚未合入主线。

建议管理/数据和 Studio 分工建设，共享执行、事件、资源与人工检查点契约；提出资源冻结、写回版本冲突、失联核验后再分配、现场容量、Sheets 单可写绑定及内部运行证据等明确取舍，均待审查，不篡改历史确认状态。

交付入口：`docs/superpowers/specs/2026-09-12-project-management-design.md`；研究证据在 `docs/project-management/research/`。检查文档链接/JSON/来源哈希、diff、自审矛盾；没有新业务测试或跨平台验收。本方案确认后再读取 writing-plans 并制定详细切片计划。
