# PM3 设计会话

- 日期：2026-09-13。
- 状态：proposed；用户明确继续PM3，先设计再开发。本轮仅设计与只读审查，未开始业务实施。
- 输入：已确认完整设计906deda、PM0契约、PM2 d02dde4；主线正式2b5365e的Studio能力。
- 来源验证：git status/log/show；主线有其他任务Studio/debug WIP，均未复制。
- 产物：[PM3设计](../../docs/superpowers/specs/2026-09-13-project-management-pm3-design.md)。
- 核心差距：现有start自行commit/立即dispatch；缺持久PreparedContent、共享UoW、执行代次、持久停止核验、项目归属和安全恢复。项目不自建执行器。
- 明确待确认：方案A补核心契约；Studio持参数唯一定义，自动化存默认覆盖与本次可填写，修正AU-04和PM0 DTO双源；新增自动化/参数长度与默认超时建议。
- 核验：独立核心源码审计与业务规则审计；本轮未运行任何业务/平台测试，PM2证据维持原范围。
- 下一步：阶段设计确认后使用writing-plans细化逐任务实施卡，再在独立PM3工作区开发。未自动启动代码或合并主线。

- 独立设计复核指出3个歧义，已修订：dispatch外部动作前先持久claim、停止目标及子Operation身份冻结、内部artifact受控GET独立于PM2文件选择令牌。重启不自动推进本批的规则保持。相对文档链接、占位词及diff检查通过。
