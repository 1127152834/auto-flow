# DB-01 补充：ORM 与真实迁移结构对齐

日期：2026-09-28；状态：confirmed；置信度：高。来源：当前源码、真实临时 SQLite、`alembic check`，历史迁移版本文件未修改。

根因包括代理模型未注册到 Alembic、Sheets 身份验证列未映射、两个运行唯一约束名称漂移、凭据 description 类型漂移、环境活动名称和代理远端活动操作的唯一索引遗漏。项目表指向当前 generation 的延迟外键与 generation 归属表形成元数据排序环；模型用 `use_alter` 标识该回边，SQLite 实际外键仍内联创建，测试核对其三列外键仍存在。

最小修正只同步当前 ORM 和 Alembic 的模型注册，不升级/降级真实数据，不修改既有迁移，也不改变迁移数据库已有约束。两个仅由历史迁移保留、当前源码没有 ORM 访问者的表 `android_operations`、`project_workflow_debug_commands` 明确不由 autogenerate 删除；排除精确到这两个表，未知未映射表仍触发漂移。它们保留历史数据的升级测试继续执行，不声称此排除能校验这两张历史表全部字段。

受影响调用方：Alembic 自动生成/检查、ORM 查询和基于 metadata 创建的临时测试数据库。现有数据库无需数据迁移与恢复动作；回退本次代码不会改变已经存在的数据字节。

- `metadata-current-analysis.log`：修复前逐项结构差异；`metadata-before.log`：有效回归在旧行为上因真实循环排序警告失败。
- `metadata-fixed-initial.log`：修复后 Alembic 无结构操作、无排序警告，1 通过。
- `metadata-regression.log`：35 通过，包括最终4项 metadata 检查、历史迁移来源字节与保留数据检查、Sheets 身份、代理远端合同。故意删除唯一索引、删除身份字段、增加未知表时检查必须失败；未靠全表排除、关闭警告或关闭类型比较放行。
- `metadata-strict-gate.log`：1041历史债务、0新增；`metadata-ruff.log`：全后端 Ruff 通过。

真实系统的 End/人工恢复仍在实施范围内，此结构修正不代表 PM9 或生产验收完成。
