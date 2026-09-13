# 先清除旧 Studio，再讨论迁入

- 日期：2026-09-13；状态：confirmed。
- 来源：用户明确要求“先把现有代码都清除，然后我们再思考如何进行 webrpa 迁入”。
- 执行范围为现有 Studio 及其专属基础设施/测试/旧原型，不是删除整个 AutoFlow 主应用。
- 源码移除前以 Git 检查点归档；仅留正式独立空窗口和领域目录骨架，不新增兼容层或替代原型。
- 用户未要求删除既有业务数据，因此历史迁移、数据库表和产物不删除；启动仍可处理原工作区 schema。
- 浏览器 Profile 的通用清理测试从旧 workflow 测试中抽出，保留真实使用的公用基础设施。
- 此决定替代 source-migration 计划的立即实施顺序；下一阶段先重新讨论迁入，不把之前 proposed 架构当自动获批。
- 正文及验收：[清除记录](../../docs/migration/studio-removal.md)；当前状态：[studio-status](../memory/studio-status.md)。
