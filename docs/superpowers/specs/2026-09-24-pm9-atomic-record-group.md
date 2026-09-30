# PM9 有限记录组原子写入 G1–G3

日期：2026-09-24。状态：proposed，等待确认。来源：原始 `docs/project-management/design/data-and-state-rules.md` §7.2/7.3、DATA-WRITE-12；当前生产1c676965、审计HEAD36528cc8。

## 目标和已确认缺口

原始规则要求显式有限 RecordRef 组在一个节点内原子取得新增 lease、检查全部版本，失败全组不写；既有节点之间的独立提交仍保留。现有 UpdateProjectRecordCommand 只接受一个 record_ref，ProjectDataCapabilityService/worker DATA_COMMANDS/Studio 配置均只有 updateRecord。仓库每次 update_record 自建短事务并提交，循环调用不能提供组原子性。现有双worker反向单记录写证明 LEASE_BUSY 与前序效果保留，不能证明组写。

运行时契约检查向现有 record_ref 传入两条引用得到 VALIDATION_ERROR，操作注册表无组写；这是能力缺失证据，不是组原子性通过。详细证据见 `docs/project-management/implementation/pm9/group-write-audit.json`。业务目标已经列入原始设计；下述新增操作、权限表达和返回形态需确认后实施。

## 最小契约与用户入口

复用现有 project_data 节点，新增 operation=`updateRecords`，明确命名为“原子更新记录组”。旧 updateRecord 文档、返回值与操作身份不变。组内只包含已存在记录的字段 Patch，不混入创建、删除、状态、结构、浏览器或远端推送；这些操作继续按原契约执行。

```json
{
  "operation": "updateRecords",
  "arguments": {
    "records": [
      {"recordRef": "{first['ref']}", "expectedContentRevision": "{first['contentRevision']}", "changes": {"<fieldId>": "value"}},
      {"recordRef": "{second['ref']}", "expectedContentRevision": "{second['contentRevision']}", "changes": {"<fieldId>": "other"}}
    ]
  },
  "variableName": "updated_group"
}
```

- 明确有限非空组，建议上限100条（新增契约预算，非已证性能目标），超限明确422，不截断、不偷偷拆批。changes 非空，版本正整数，引用保留 typed recordKey。既有RPC消息/结果大小上限继续生效，不随条数放宽。只允许同项目，可以跨表和代次引用，但每张表必须仍为当前有效代次。
- 重复精确 RecordRef 拒绝；不同本地引用解析到同一物理 Sheets SourceLeaseKey 也拒绝，不推测合并两个本地 Patch 的顺序。拒绝发生在提交任何新 lease、游标或修改前。
- 返回 `{ "records": [完整原序记录快照] }`，单个命令ID与摘要覆盖整个有序组；无变化项返回原版本，发生实际修改的项各推进一次版本。不按数据库返回顺序重排。
- 复用 ProjectDataConfig 的操作选择、JSON参数、表字段选择和变量示例，增加组操作所需的多表声明行。每行由已有真实项目/表/字段接口加载，不要求手写 UUID；旧单表配置保留。
- 组节点采用可选 `tableGrants` 数组，每项沿用现有 tableGrant 结构，operations 仍声明底层 `updateRecord`。单数与复数互斥；复数仅用于新组操作。同表同代次重复声明拒绝，不能靠重复行扩大字段权限。输入/任务创建记录仍按既有精确引用权限处理，不能把组操作当成整个项目写权限。

## 权限与事务

沿用 TaskCapabilityScope、冻结 PreparedContent、project_command_id、ProjectOperationRow、DataChangeRow、现有 SQLite 短事务、物理来源 lease 和出站意图。没有新执行器、数据库表或第二份记录写实现。

1. 准备阶段校验组节点及全部显式授权目标；旧单 tableGrant 与新组 tableGrants 归一为既有冻结 manifest。每条 grant 必须与实际操作/字段/表代次一致，父项目权限继续作为上限。
2. 父进程从实际冻结节点取得声明，不信任 worker 自报权限；组操作逐项调用既有 updateRecord 授权规则。子流程对每张表分别与冻结子节点声明取交集，不得合并兄弟节点、其他调用或父节点更宽字段权限。运行代次、节点访问、分支/调用隔离按现有 RPC 校验，不增加跨进程恢复。
3. 一次 BEGIN IMMEDIATE 内重验 Task/Run fence、操作幂等、各项作用域/当前代次/字段/内容版本/读取凭据和物理 lease。新增 lease 只能非抢占取得；发现 held/reconciling 他人占用立即返回可见 LEASE_BUSY。不得轮询等待另一记录释放。
4. 提取现有单记录更新的 session 内核心，在同一会话内复用。组外入口只提交一次；禁止在事务中调用现有会自行提交的 public update_record 循环。任一校验或持久化失败回滚本组所有新增 lease、游标、值、版本、变更记录和待推送意图；此前节点提交和已有 lease 不受影响。
5. 成功时一个 ProjectOperationRow，按原序写 DataChangeRow.sequence（现有唯一键operation_id/sequence可复用；当前单记录helper写死sequence=1必须适配）。每条真正变化记录在同一事务内入队精确字段差异；远端 Sheets 各次发送不属于本地事务，不宣称远端多行原子。
6. 提交成功响应丢失后，原 commandId 返回同一整个结果、不再提交或推进版本；同ID不同摘要冲突。成功原命令查询与重放沿用既有可审计边界，不绕过当前调用身份。用户编辑造成旧预期版本冲突时，不自动读最新版本强行覆盖。
7. 沿用现有失败/人工错误边与停止回收。此提案不新建节点重试调度器；当前单记录“配置重试耗尽”的证据仍独立保留，不能由组事务替代。若未来新增重试，必须重新定义命令访问身份，不能改掉当前RPC attempt校验冒充支持。

## 方案比较与边界

推荐复用会话内单条核心、外层组事务：改变现有最少层次并能证明无半组写。循环调用现有单写会留下前项提交，不满足目标；新增通用事务DSL或跨节点事务会扩大原始范围，均不采用。只放宽 operation 白名单而没有事务、权限与界面不构成交付。

本组预算100为待确认设计值；验证100条边界与101拒绝，不把它解释成吞吐承诺。新字段动态返回授权依赖独立FR提案，不能借本组绕过；现有字段足以独立验证G。L/M/S4/W/P/AD补充方案不在本次批准范围内。

## 退出证据

- 混合本任务已持 lease 和新取得 lease 的两条/跨表成功；两条均有正确当前游标、版本、变更序号和意图。
- 任意位置忙、旧版本、旧代次、越权字段、身份/公式字段、非法值、重复引用/物理身份、持久化异常，全部组内事实不变，无新增lease泄漏。
- 双真实worker各持不同记录反向组写均有限时 LEASE_BUSY，前序提交保留，公开停止后释放；不以两个单写测试替代。
- 提交后丢响应原命令恢复、人工新值保护、后续节点失败保留组提交；子流程/并行节点不能借用更宽授权。
- Studio多表选择与参数保存/重开、输出原序和错误定位；源码真实worker与打包HTTP联合链，稳定候选一次三平台验证，外部实网/实机门禁单列。

全部退出条件满足前 DATA-WRITE-12 保持 partial，releaseAccepted=false。
