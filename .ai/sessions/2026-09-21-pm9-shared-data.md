# PM9 共享领取和数据能力后续

日期：2026-09-21。状态：confirmed / implementing。来源：用户批准、实际代码与定向测试。

C1 复用现有 lease 唯一索引和输入选择/提交事务，新增 Sheets 公共键、完整拉取身份验证及逐记录来源证据。nullable pm09_shared_sheet_identity 迁移让旧绑定等待重新拉取；终态旧锁不改写。推送证据合并保存，不抹除身份观察。旧活动 local Sheets 锁保守阻断同 Spreadsheet 新领取（旧事实未保存 sheetId，不猜测来源）。

10 项新场景及相关规则、迁移、输入/同步共 158 passed / 2 warnings / 57.88s；mypy 403、ruff 通过。直接断言范围与剩余缺口见 shared-data-follow-through.json。C1 只验证 HTTP/SQLite，释放测试明确模拟已确认终结，不冒称实际 worker。C2 query 写绕过和绑定变化现已 RED，继续修共同入口与生命周期；C3/C4/R1–R5 未完成。

f580 本机真实 public145 内核 26 passed / 279.99s，早前错误 Pro 路径尝试保留为失败配置记录。旧矩阵 35590418456 Windows 全量 3317 passed / 71 skipped / 1 failed：100ms 合成任务自动预算在第二次 pause 前耗尽；需修测试时序并复验，另两平台继续。releaseAccepted=false，不合并发布。

## C2 全入口与本地游标（confirmed）

共同来源键已用于动态 query 写和新建后的占用；新建的本地记录只在 create 事务跳过远端成员存在检查，仍竞争公共键且不触发远端新增行。相同 Task 跨两个本地绑定拥有一个物理 lease、两个本地 RecordRef 游标；pm10_shared_sheet_cursors 无损升级，存在多个游标时拒绝降级。原命令重放、拒绝冲突后无局部记录/操作均有直接断言。

解绑/改绑/归档检查原来源及目标来源的 shared held/reconciling 锁，界面 blocker 只包含当前项目表定位。来源验证采用最新兼容扫描，同时冻结绑定集合；解绑/删除同伴会要求重新拉取，不能消除已知的坏身份后放行。普通空身份拉取仍可读取有效本地行，但完整身份缺失时不能领取。不同身份列允许绑定/读取但暂不准入；普通推送失败不会撤销可靠本地领取。

147 项相关规则、数据能力/来源/生命周期/迁移回归通过（95.58s），mypy 404、ruff 通过；额外降级拒绝及游标保留断言通过。C3 完整恢复/UI、C4 两真实 worker 与 R1→R2→R5→R3→R4 继续。旧 C2 待修表述被本节 superseded。
