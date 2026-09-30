# 安卓备份发布与事务一致性

- 日期：2026-09-23。
- 状态：confirmed（本增量），完整目标 active/partial。
- 基线：隔离分支 `codex/android-management-complete@715cdb16`；3份既有 Studio 文档未纳入修改或提交。
- 来源/验证：`docs/qa/android-management/2026-09-23-publication-verification.md` 及同目录原始 JSON、实验脚本。
- 完成：私有目录与根链接拒绝；staging 内摘要；文件/目录 fsync + rename；失败清理；备份可用记录与操作成功原子事务；提交回执丢失重新核实，未知保留文件/禁止重放；取消语义。
- RED 分别4/1/3/1失败；GREEN Android unit/contract/integration + migration heads 328 passed，定向 Ruff、compileall、Node22 OpenAPI、结构4项通过。
- 真实源240402a1-83ba-44a1-884e-7bef621076c6→目标194d09a0-0a44-4025-8579-8f60952a6a4f：真实落盘与SQLite提交、18,274,988bytes备份、新实例启动后三条链接读回，源测试条目不变；容器卷清理0，LimaStopped。
- 不冒充真实故障：ENOSPC/权限/同步/事务异常是文件/SQLite边界注入，未拔盘或断电。
- 待办：硬中断孤立文件核实清理、恢复部分写入/xattrs、模块临时文件/高级日志、完整门槛与分支审查。无模型或API形状变更，无新增迁移。
