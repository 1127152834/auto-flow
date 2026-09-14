# Task 3 审查与修复记录

- 日期：2026-09-15；状态：通过。
- 工作区：autoflow-project-management-pm3；基线：ffa8df2。
- 范围：PreparedContent / CoreRun / RunEvent、运行仓储、应用内端口和 0011 迁移。不是 PM3.0 或 PM3 整阶段验收。

| 问题 | 修复与验证 | 状态 |
| --- | --- | --- |
| 冻结 dataclass 仍可改嵌套字典；恢复/直接构造绕过冻结 | 所有入口递归冻结，独立 UTC/直接构造回归 | 双审通过 |
| SAVEPOINT 在 SQLite legacy 模式下可意外提交外层 UoW | 仓储开启真实物理事务；测试先 SELECT 再 prepareRun 后 rollback | 双审通过 |
| 并发事件/状态更新可能回退序号或绕过撤权 | 序号、代次 CAS；状态更新不写旧序号 | 双审通过 |
| 准备对象信任外部编译结果或先修订再查操作 | 服务端读取编译；原操作先查回；来源读取前 BEGIN IMMEDIATE | 双审通过 |
| 旧 Run 源文档缺失时抹掉启动快照 | 分开保存占位文档与原启动 snapshot；RED 后修复 | 已通过 |
| 降级丢失新证据且有循环引用崩溃 | 有 PreparedContent 则 DDL 前拒绝有损降级，空库允许往返 | 已通过 |
| 旧 interrupted 终态的原错误被改写 | 仅本次从活动状态中断时生成迁移错误；RED 后修复 | 已通过 |
| 只读 legacy 准备对象可创建并派发新 Run | 核心准入拒绝，原请求结果查询仍保留 | 双审通过 |
| 所有 OperationalError 被误报并发冲突 | 区分 SQLite busy/locked 与真实存储故障 | 双审通过 |

迁移规格审查：PASS（pm3_migration_spec）；工程审查：PASS（pm3_migration_quality）。39 项迁移定向测试通过；额外强制所有 SQLAlchemy 连接 FK=ON 的 10 项迁移测试通过。失败迁移的原 schema、revision 和数据 dump 均原样保留。

运行仓储第二轮发现的两项阻断已修复，最终规格复审 PASS（pm3_runtime_spec_final）。新增真实 0008 迁移经公开 service 的只读准入回归、SQLite BUSY/LOCKED 与 I/O 区分，以及 Barrier 控制的撤权竞争；24 项定向测试独立通过。工程复审 PASS（pm3_runtime_quality_final）：额外验证旧 ORM 强引用下的序号交错、保存点主键/事件插入失败后的 Session 可用性和外层 rollback。未将曾通过的 20 个基础测试当作全部行为通过。首次后端全量 1189 passed / 2 warnings（158.02 秒）；修复后重新全量：1193 passed / 2 warnings（131.32 秒）；最终 34 项运行/迁移定向、Ruff 和 mypy 215 源文件通过。

未执行：真实 CloakBrowser 工作流、HTTP/SSE、Electron 页面、Windows、其他架构、打包版本及用户手测。Task 4 起才接真实网页执行，Task 3 不提供伪装的应用演示。
