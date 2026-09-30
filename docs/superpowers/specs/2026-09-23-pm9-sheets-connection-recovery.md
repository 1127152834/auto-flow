# PM9 Sheets 连接恢复与未知发送处置附录

日期：2026-09-23。状态：proposed；L0 为既有安全要求的修复，L1–L3 新契约尚未批准。
来源：`data-and-state-rules.md` §12.1（DATA-LIFE-01/02/07）、当前连接/绑定/发送实现及隔离 HTTP/SQLite 探针。不是 Google 实网证据。

## 已确认现状

- `project_sheets_connections_router` 只有连接 list/create/delete；`SheetsConnectionService` 每次授权创建新连接。`SheetsConnectionRow` 无稳定主体证据或凭据修订；账号名称不能证明同一主体。
- `SqlAlchemyProjectSync.put_binding` 无条件新建 datasetGeneration；不能据“同物理表重新绑定成功”声称保留记录身份、状态和关联。
- 临时受控网络探针：旧值发送 unknown=1，同物理 Sheet 改绑返回 202 并更换代次，新值仍可写入原单元格，而旧 unknown 仍为 1。已新增四项正式反例（改绑/解绑 × 新预览/旧预览提交）。
- L0 复用 `require_source_idle(..., structural=True)`，在改绑新/旧来源和解绑的共享事实计算中检查未决值发送。预览和提交事务都拒绝，读、领取及普通发送入口不改。它不提供永久失权逃生入口，不关闭 LIFE-07。

## 目标和范围

恢复授权时保留可靠的本地身份和业务状态；永久失权时允许用户保留数据并管理本地项目，同时未知旧写不得借换账号、解绑或新 epoch 绕过原物理目标冲突。复用现有凭据库、ProjectOperationRow、SyncOperationRow、GoogleAccess 协调和影响预览，不增加第二执行器。

L1 同一主体重新授权；L2 经明确确认更换主体但保留同物理来源的数据身份；L3 停止旧发送并隔离未决上下文。云端行新增/删除/模板 M1–M3、跨进程人工恢复、更多 Studio 节点和自动恢复旧网页任务均不包含。

## L1：连接原位重新授权

1. 主机授权交接必须带服务端验证的稳定主体证据；OAuth 以经验证的 issuer/subject 为身份，服务账号以经令牌交换验证的账号身份为依据。账号显示名、Renderer 字段、仅解码未验证的 ID token 均不得作为证据。具体 Google 验证协议在实现前用官方文档和既有依赖核实；验证不可用时拒绝，不提供弱验证降级。
2. 连接增加单调 `connectionRevision`、凭据代次和主体证据引用；密钥仍只存系统凭据库，HTTP/日志不返回 token 或私钥。旧连接没有主体锚点时，不按账号名称自动推断：能够验证旧凭据则建立证据，否则只允许走 L2 的显式重新连接。
3. 新命令 `POST /api/v1/projects/{projectId}/sheets/connections/{connectionId}/reauthorize`：`authorizationToken`、`expectedConnectionRevision`、`impactRevision`，沿用 Idempotency-Key/OperationAccepted。项目归属、旧连接修订、新主体一致、所有既有目标可读及结构/身份兼容都必须重验。
4. 用新 credential key 暂存已验证凭据，再 CAS 发布连接指针；失败保留旧指针，补偿删除仅限本命令新 key。提交后才清理旧 key，清理失败作为可重试维护事实，不回滚已发布凭据。原键重放返回原操作，不再兑换一次性授权 token。
5. 同一主体不改变 datasetGeneration、RecordRef、业务值、状态/关联修订和字段身份；不重写旧发送的目标/epoch/快照。先用新凭据对原目标做只读核验，再由用户明确恢复待发送队列。恢复授权本身不云写、不重跑任务。

## L2：更换主体但保留同物理来源

1. 新命令 `POST .../connections/{connectionId}/replace-authorization` 使用 L1 字段并要求 `confirmDifferentPrincipal: true`；影响预览列出受影响表、原/新主体的安全显示信息及未决操作。
2. 必须证明 Spreadsheet、Sheet、身份策略、列归属和当前可靠记录身份未变；重新读取和提交之间按当前修订 CAS 重验。不能证明时保持拒绝，另走现有明确更换数据来源流程，不静默清空本地身份。
3. 显式主体替换只推进连接修订和相关 bindingEpoch，保留数据代次、RecordRef、状态和关联。旧操作固定原目标及 epoch；未发意图不得自动改写为新主体下已同意发送，用户确认后产生关联原意图的新发送计划。
4. 有未决已发操作时先核验，或先完成 L3；无上述结果不得借新主体发送冲突字段。显示名相同而主体不同必须走本入口。

## L3：永久失权后的隔离

1. 新命令 `POST .../tables/{tableId}/sheets/isolate`：`expectedTableRevision`、`expectedBindingEpoch`、`impactRevision`、非空 `reason`；沿用原操作幂等。预览逐项列出未发/已发未知操作和物理冲突范围，不将未知结果显示为失败或取消。
2. 停止新网络写，并证明所有旧发送者已结束。当前实例须等待实际网络调用退出；重启恢复须使用持久发送实例身份与平台适配器提供的所有权/退出证据。PID、时间超时、界面“已停止”均不够。历史操作缺发送者证据时保持阻断，不伪造已退出。
3. 复用 SyncOperationRow：未发操作明确取消且保留本地覆盖值；已发未知保留 `status=unknown`，新增受约束的 `sendDisposition=quarantined` 与原发送者/目标证据，禁止后台自动重试。独立审计字段必须持久，不只存在内存或日志。
4. 隔离后允许本地归档和连接不同物理来源；同物理目标的原记录/字段仍处于冲突围栏，跨项目、账号、代次、UUID/文本身份及重启都不能绕过。身份映射不足时保守封锁该 Sheet，不猜测冲突范围。
5. 隔离不是“核验已应用/未应用”。只有原目标的可靠核验或有明确业务含义的用户处置，才能单独推进对应历史事实；本附录不提供一键清空未知冲突，也不承诺撤销 Google 已收到的请求。

## 验证与退出条件

- 正向：同主体凭据更新、不同主体明确确认、相同来源身份保留、失权后隔离本地管理；反向：伪装主体、错误目标、旧预览、凭据写/CAS/清理失败、迟到发送、未知 owner、新绑定绕过。
- 每项均断言记录身份、值和三类版本、原操作/epoch、网络副作用、原键恢复；复用真实 HTTP/SQLite 和受控 transport，再接现有真实 worker 与 Electron 入口。
- 原生发送者身份验证先在 Windows/macOS 适配器实验，未通过则 L3 入口继续拒绝；不能删围栏换取成功。
- Google/OAuth、系统凭据与当前打包全链另需真实授权；三平台 CI 不替代实机/签名。L0 和本附录均不使 releaseAccepted 变为 true。

## 取舍

继续使用“新增连接+普通改绑”最省代码，但会重置身份且不能处理旧未知上下文，拒绝采用。复制新的恢复执行器也不采用。选择扩展现有连接/操作事实与影响重验；L1、L2、L3 分别验收，任何一步证据不足不开放下一步。
