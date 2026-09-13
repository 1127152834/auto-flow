# Studio API 业务失败语义

2026-09-14；confirmed / implemented。

根据冻结 WebRPA 凭据/通知服务的 HTTP 200 success=false，修复共享 apiRequest 不再无条件确认成功。仅顶层明确失败转换为现有 ApiResponse 错误形状；正常零匹配、数组、对象、null 与嵌套字段不改写。业务失败不触发断线事件。

22 个内存/HTTP 同合同用例、真实凭据组件保存失败输入保留用例通过；相关 43 项、全量 102 文件 / 1,219 项通过，类型/lint/构建通过。证据见 docs/migration/studio-frontend-completion/api-business-failures.md。

完整 142 项服务合同和其他消费者仍需逐项验收，本批不关闭 F1。下一步清理已排除节点的专属中文教程，再推进运行状态和生命周期保护。
