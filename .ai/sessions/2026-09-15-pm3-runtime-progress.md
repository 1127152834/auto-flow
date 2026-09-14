# PM3 运行契约修复交接

- 日期：2026-09-15；状态：进行中。
- 工作区：`autoflow-project-management-pm3`，分支 `codex/project-management-pm3`。
- 来源：已批准 PM3 计划、当前源码、迁移定向 pytest。

Task 2 已提交 `ffa8df2`，恢复的是当前 WebRPA 包装文档，不是已退役 M1–M5 IR。Task 3 未提交实现继续修复：深度不可变、源修订验证、调用者短事务、幂等竞争、事件序号与代次撤权。

迁移新增缺失源文档、旧 0006 嵌入产物和降级证据保护回归，先复现 2 个失败后修复；六组迁移测试共 37 项通过。旧活动运行迁为 interrupted，原启动快照/状态/时间/错误/事件/产物/debug 保留。存在 PreparedContent 时拒绝有损降级；空库可往返迁移。

主目录只读核对 HEAD `865bb963d0ff19a920c2447beb99ae6ee668db07`，有 Studio 等其他任务改动；不接管这些文件。旧项目 HEAD `324748abe7095f085b4ffb9467be9cb5c8851a5c`，其大量删除是既有状态，本任务未触碰。

服务修复、独立审查、全量验证和提交仍未完成；真实 worker、前后端和 Electron 验收未执行，不能把本记录解释为 PM3 交付。

## Task 3 闭合

状态：confirmed，来源 task3-verification.json/task3-review.md。迁移与运行各完成规格、工程独立审查；最后新增 legacy 不可运行准入、数据库错误分类及撤权屏障回归。全量后端 1193 passed，最终运行/迁移定向 34 passed，Ruff/mypy（215 源文件）通过。当前可以进入 Task 4，仍未交付真实网页运行或 PM3 页面。前段“服务修复与审查仍未完成”是本次修复过程记录，以本节当前结果为准。
