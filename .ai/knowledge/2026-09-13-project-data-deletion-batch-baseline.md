# 记录/状态删除与固定批量状态接入基线

- 日期：2026-09-13。
- 状态：confirmed（下列源码和契约现状）；持久块实现建议为proposed，尚未编码或验收。
- 验证：独立智能体只读审计，主协调重新检索api-contracts.md §3.3/Operation映射、project_data_models.py、project_schemas.py、project_data.py。以implementation工作区d37cb1c为代码基线。

## 已确认边界

- DELETE statuses属于PM2-A；要求status/table修订及新鲜impact。当前记录或真实依赖引用阻断，删除本身不改记录状态。DELETE fields属于PM4-B，本包不混入字段删除。
- DELETE records属于PM2-A/PM4-B；完整RecordRef、content/status/link三CAS及impact，返回OperationAccepted，终态为target/deleted结果。DataRecordRow已有deleted列，查询已排除删除行。保留原数据和历史事实，不能物理删除记录再丢失追溯。
- DataStatusRow没有deleted列。主协调进一步核对发现RecordRow.status_id的RESTRICT外键也覆盖tombstone和旧代次；因此“直接物理删除状态”的最初建议被否定，不能把历史引用永久当成当前阻断，也不能暗清历史记录状态来绕过外键。删除实现需要相应存储迁移（例如状态软删除与活动名称唯一约束），保持历史JSON和旧行事实；具体方案须在下一执行卡明确。
- mutation-impact目前仅真实updateField；新删除动作必须新增真实预检和同事务复验，不能复用另一个动作的确认。10分钟有效和事实摘要沿用已确认协议。
- 固定批状态targets最多1000、非空、同身份不同版本422；冻结顺序，blockSize默认100且1–100。每块全成或全冲突，取消仅关闭未开始块；已提交结果不回滚。预检不创建Operation，不授权未来写入。
- 当前HTTP OperationView只允许succeeded且未包含批量kind。当前数据命令同步完成；没有可供本包直接冒充的持久批状态runner或块表。扩展Operation联合类型必须随真实handler与结果共同交付。
- Task占用、持久自动化引用、Sheets同步尚未在该分支实现。后续提供方接入时必须同步增加真实guard和影响事实；当前本地/Excel实现不能宣称这些跨模块边界已验收。

## 下一包实施建议（尚待详细执行卡）

删除核心先按当前真实local/excel来源实现；预检事实包括生命周期、table/generation/source、目标修订及当前引用。提交在BEGIN IMMEDIATE内完成原key检查、CAS、影响复验、删除事实和Operation/DataChange。新增源或依赖不能跳过相应检查。

固定批状态需要耐久的接受、块提交、取消和重启恢复。建议以专用块表保存(operationId,blockIndex)唯一身份及结果，操作级取消状态与块事务共用数据库原子性；不要用HTTP BackgroundTasks当耐久队列。专用迁移由主协调创建并再次核对Alembic head。此建议不是现成能力，也不代表已批准第二个工作流执行器；它只协调数据状态命令，Studio仍独占工作流执行。

## 状态历史引用复核（2026-09-13）

主协调检出RESTRICT外键矛盾后，原审计者复核并撤回物理删除建议。下一迁移采用状态软删除作为存储落点：保留旧statusId及其FK，新建deleted默认false，名称唯一改为仅活动状态的部分索引。目录/更新/目标状态校验过滤deleted，删除后同名新建获得新UUID，不提供墓碑恢复接口。影响阻断只查询当前generation的未删除记录，同时保留旧代次和tombstone关联。幂等查询必须先于目标deleted guard，保证成功删除重放可恢复原事实。此处已确定落点，但迁移、消费者和删除业务验收尚未实施；状态修订推进与最终结果在详细执行卡中对照契约明确。
