# 整改计划（M0–M6）
日期：2026-09-30。状态：confirmed（用户 2026-09-30 批准整改计划及总纲第 6 节全部决定）。来源：用户要求依据《AutoFlow 整改方案》构造里程碑式、渐进式的设计规格与实施计划。

背景：两份评审（docs/qa/2026-09-30-remediation-reviews/）确认批量自动化存在静默失效、失败原因丢失、并发写死为 2、没有处理台账、身份不隔离、界面暴露内部模型等问题。整改方案见 docs/superpowers/specs/2026-09-30-autoflow-remediation-proposal.md。

决定（待审批）：按 docs/superpowers/specs/2026-09-30-remediation-roadmap.md 分 7 个里程碑推进；M0、M1 计划已细化到步骤级（代码已在基线上原型验证），M2–M6 为任务级、在上一里程碑退出评审后细化。

若批准，将替代以下既有决定（生效里程碑）：
- 运行容量只允许 1 或 2（application/workflows/dispatcher.py；docs/superpowers/plans/2026-09-26-parameter-batch-concurrency.md 全局约束）→ 按机器配置，执行名额与存活浏览器分开（M1）。
- 人工等待占用执行名额 → 只占存活浏览器名额（M1）。
- 错误分支接住的失败仍使运行失败（沿用 WebRPA）→ 新建流程使用 v2 语义，旧流程保留旧语义可切换（M1）。
- 没有批内已消费集合（docs/project-management/design/execution-and-environment.md §4.1、XE-A21/A22、2026-09-12-project-data-workflow-semantics.md）→ 处理台账，新建自动化默认"未成功处理"（M2）。
- 运行时可增删改字段 → 表结构只在设计期修改（M2）。
- 指纹种子属于浏览器配置 → 属于身份，全局唯一（M4）。

代价：M1 起旧流程需用户手动切换出错语义；M2 起存量自动化保持循环复用语义；M4 迁移可能触发网站重新验证（默认保留原种子以避免）。

用户确认（2026-09-30）：1) 同意全部替代关系；2) 清除 git 历史中的 QA 截图（M0 Task 11，推送前再次确认）；3) 身份迁移默认保留原种子；4) 同意冻结 Android/iOS 模拟器、桌面触发器、Sheets 双向同步扩展。开发将在 Codex 中按 M0、M1 步骤级计划执行。
