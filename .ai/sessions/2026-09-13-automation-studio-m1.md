# Automation Studio M1 实施交接

- 日期：2026-09-13
- 状态：confirmed；用户已批准 M1 方案并明确要求实施。
- 实际仓库：`/Users/zhangtiancheng/Documents/projects/autoflow`，分支 `codex/architecture-baseline`。旧 e7ce worktree 未作为本次实现目录。

完成正式独立窗口中的六节点编辑、连接、位置、参数、五类变量与普通引用、撤销重做、剪贴板、手动保存和打开。使用真实工作区 SQLite、0005 增量迁移、OpenAPI 生成类型和后端节点目录；无模拟运行。正式领域统一 workflows，前端按 components/hooks/pages/tests 归位。

离开握手覆盖新建/打开/关闭/退出/切目录。保存快照不覆盖期间新编辑；首次保存稳定 UUID；409 保留草稿并可另存或重读。保存中撤销后离开会等待写入完成再判断。打开请求期间锁定编辑并校验原文档。变量名称焦点未离开时保存/关窗先提交合法重命名。重命名同时更新引用和同名输出绑定。

共享连接 hook 保留同工作区草稿/历史，拒绝迟到连接响应；目录变更完成健康核验前保持锁定，失败回滚保留原稿。最小化工作台在离开询问前恢复；主窗关闭不影响 Studio。正常退出先保存后 shutdown。Studio 普通/强制刷新入口被禁止，避免绕过草稿保护。

最终验证：桌面 373 测试、后端 438 测试通过；TypeScript、ESLint、完整 Ruff、mypy 129 源文件、OpenAPI、结构/脚本检查、构建和 macOS 打包通过。后端两个旧测试仅补 import 分组空行使完整 Ruff 通过。

实际 Electron 验收覆盖六节点连线、移动撤销、保存重开、应用退出重启、服务恢复、主窗关闭、工作区取消/切换/隔离、目标真实数据库损坏导致失败回滚、最小化询问、未完成草稿，以及真实外部 PUT 引发的 409 和另存。使用独立临时目录，未写入用户现有工作区。开发 Vite URL 与 macOS arm64 `.app` 均通过；打包结果和截图保存在验收目录。

Windows 尚无实机测试；本机 `.app` 未签名或发布。M1 不包含执行、录制、Debug、复杂控制流和崩溃草稿恢复，下一阶段须按后续已批准里程碑实施。

证据：[验收记录](../../docs/migration/automation-studio-m1-validation.md)、[边界决策](../decisions/2026-09-13-workflows-m1.md)、[机器结果](../../docs/migration/automation-studio-m1-qa/packaged.json)。其它模型/UI/redroid 研究任务的原有未提交文件未纳入本次提交。
