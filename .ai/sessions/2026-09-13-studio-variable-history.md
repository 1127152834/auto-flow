# Studio 全局变量编辑

日期：2026-09-13；状态：局部implemented/verified。

已修复未标脏、缺失历史、节点默认变量撤销残留、loadWorkflow变量泄漏、重命名与引用两步拆分及无效类型静默默认。93文件/1,122测试通过，真实UI保存重开已验证。详细证据：docs/migration/studio-frontend-completion/variable-editing-validation.md。

下一步保存/离开：只有变量的零节点文档当前被拒绝保存；新建快捷键和AI路径绕过确认；不能仅按nodes.length判断草稿。保留完整F0–F6待办，不停止于本提交。
