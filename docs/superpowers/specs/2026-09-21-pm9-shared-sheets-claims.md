# PM9 共享 Sheets 任务领取：已批准补充切片

日期：2026-09-21。状态：confirmed；用户明确批准两份方案，按 C1–C4→R1→R2→R5→R3→R4 实施。来源：data-and-state-rules.md §6.3/§10.1、当前生产源码 82c067c9、`implementation/pm9/diagnostics/shared-sheet-lease.py`。

## 已确认问题与边界

P/Q 在同一 Workspace 绑定同 Spreadsheet、Sheet、业务身份列 A，拉取相同 A-1 后，两者 select_required 都 ready，生成不同的 local/project/table/generation leaseKey。当前唯一索引只保证整个 leaseKey 唯一，不能把这两个键当作同一物理行。失败探针直接断言两键应相同而失败；没有启动两个真实浏览器，不声称已验证所有后续副作用。

DATA-ID-06、DATA-SH-13、DATA-SH-14 应记为 implementation_missing，不能仅列 test_missing。此前不同字段推送不互相覆盖的通过证据继续有效，但出站发送协调不代替任务数据 lease。

## 最小契约

复用现有 ProjectRecordLeaseRow、活动唯一索引、Task cursor 和共享输入选择器；不增加第二调度器或数据库外锁。LeaseKey 改为明确的 local / sheets 两种结构：local 保持原 RecordRef；sheets 使用 spreadsheetId + sheetId + verifiedIdentityNamespace + 精确 RecordKey(type,value)。共享键不得含 projectId、connectionId、本地 tableId/datasetGeneration 或绑定自身 epoch，避免再次人为拆开同一物理记录。

每个 Task 输入快照仍保存原项目 RecordRef、bindingEpoch、所用身份验证修订和共享 leaseKey；这几个本地版本用于事务重验与权限归属，不成为公共排他键。内容、业务状态、字段授权继续留在各自本地表。共享 lease 只决定是否可同时处理，不赋予跨项目读取/写入权限。

最初只接通相同且已完整验证的业务身份列/精确编码规则；不同身份列缺少持久一一对应证明时，保存绑定与本地读取仍允许，领取返回明确身份待修复原因。已有同名列不自动接管；行号不能作为稳定公共身份。跨列对应和系统 UUID 初始化要先有独立确认的持久协议，本片不靠猜测开放。

## 原子性、恢复与生命周期

1. 候选读取在同一 Session 解析 Sheets 绑定和可靠身份；活动键查询按 Workspace 公共键，不能再限定当前 project/table。无证明、远端缺行/重复键的处理必须区别本地推送失败：推送失败且身份仍可靠不能自动阻断领取。
2. commitInputGroup 在现有短写事务重验 bindingEpoch/身份验证修订、公共键、记录各版本和全组资源，提交唯一 lease、完整 Task 与 cursor；竞争失败全组回滚，不创建半 Task 或扣任务上限。
3. queryRecords 取得写占用、初始输入、创建后占用、别名复用都调用同一来源键解析，避免只修初始输入。共享键不等同 RecordRef；同一 Task 跨绑定同一物理行需保留各自本地 cursor，不能用单个快照覆盖另一个项目权限。
4. 解绑、重新绑定、身份列/映射变化、归档和恢复的影响分析应纳入共享 held/reconciling lease 及已冻结依赖；旧绑定失效不能逃脱旧占用。旧 worker 未确认退出/隔离前不得释放公共键。
5. 升级时若存在旧格式的活动 Sheets local lease，先保留阻塞并要求结束/恢复旧任务；禁止在旧键仍 held/reconciling 时授予新公共键。终态历史 lease 不重写其审计事实。迁移与启动门禁须覆盖这一混合版本窗口。

## 实施与验收

- C1：冻结 key/snapshot/错误 DTO；将已失败探针转入正式回归；读写候选与提交源键解析，验证 P/Q 一胜一忙、全组失败无副作用、释放后 Q 按自己状态再领。
- C2：接入所有按查询/创建获取占用的调用点和生命周期影响；验证跨项目权限不扩大、字段推送失败不阻止可靠本地领取、不同身份列阻断且绑定仍可保存。
- C3：升级旧活动 lease、失联/人工现场与取消竞争；共享状态 UI 展示占用原因但不泄露另一项目记录内容。现有授权允许查看的任务跳转复用现有 Locator。
- C4：真实 HTTP/SQLite 两项目与真实 worker 竞争，输出唯一活动公共 lease/完整 Task/源操作次数；定向规则/集成/组件检查后完整本机及三平台打包回归。Google 授权专项单列待验收。

这是共享数据身份/持久占用协议的架构补充，依 AGENTS.md 完成规格后等待确认。此前 R1–R5 数据端口附录的待确认问题不自动包含本片；现有 S1–S5 修复与验证继续。releaseAccepted=false。

2026-09-21 确认更新：用户已批准上述范围及顺序；本文此前等待确认表述已 superseded。批准记录见 `.ai/decisions/2026-09-21-pm9-shared-claims-data-approved.md`；M1–M3 不在本次授权范围。
