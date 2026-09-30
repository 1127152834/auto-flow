# PM9 P1–P3 代理资源冻结补充契约

日期：2026-09-24。状态：proposed，尚未批准实施；原规格要求已确认，本文补齐其缺失的持久快照与调度交接契约。

## 原规格与已确认缺陷

`docs/project-management/design/execution-and-environment.md` §2、§8.3、XE-A20 要求批次固定代理候选 ID、端点和策略，新成员/改动端点不进入旧批次；固定候选失效后停止新领取，不降级直连，修复后显式新批次。

`WorkflowBrowserResources.freeze` 当前只保存 Profile 的 pool ID；`acquire` 经 `ProxyManagementRuntime.resolve_profile` 调用现有 `ResolveProxyForProfile.resolve_group`，每个 Run 重新读当前成员。受控诊断使用真实资源冻结类和 SQLite 选择/提交器：冻结时池仅 A，改成 B 后第二请求选 B，再改 B 端点后第三请求使用新端点。它是实现缺失，不仅是缺测试。诊断未启动真实代理 worker，合成 Profile/kernel/projection 的边界保留。

## 范围与持久契约

复用现有批次 `frozen_request.resourceRequest.frozenConfiguration`、资源租约、代理池 CAS/cursor/request_id 和凭据加载器；不新增执行器或代理服务，不将密码写入快照/renderer/日志。快照新增 `proxySelection`，版本 `schemaVersion:1`，包含 mode（none/fixed/pool）、原 proxyId/proxyPoolId、固定候选列表。每项包含代理 ID、连接 ID、provider ID、固定选用协议和对应 host/port。ID 唯一、字段白名单、端点和协议类型严格校验；未知版本/字段/损坏快照拒绝。

- none：空候选，继续明确直连；fixed：一个候选；pool：冻结时的初始成员身份与可使用端点集合，不复制凭据。
- 协议由现有优先规则在冻结时选定，后续新增协议端点不能改变旧批次选择。当前健康/启用/凭据可用性仍需复验，不能把冻结的健康状态当作当前许可。
- 新增成员不能进入集合；原成员被移除、禁用、远端缺失、来源身份或已选择端点改变时不可选择。其余原候选仍可按现有池选择机制使用。全部失效则结构化失败。
- 候选可用性复验、探测后的重新读取、选择 CAS 与已存在 request_id 重放，都必须满足同一固定身份/端点约束。旧 request_id 的来源失效时拒绝，不能改选另一个成员。
- 凭据仍仅在拥有浏览器的父进程中临时读取。凭据加载/刷新后再次核对来源与端点，不能把刷新后的新端点放进旧快照。禁止记录凭据或完整命令行。

## 领取与失败收尾

P2 将结构化资源错误接入现有 Batch claim gate 和 selectionOutcome。可确定的引用/成员/端点失效，在下一次领取事务前复验；网络探测和凭据读取在短事务外完成，不能持 SQLite 事务等待网络。

校验和真实 launch 之间仍可能变化；launch 再验证，失败时保留已创建 Task/Run 的失败事实，依现有 ownership 清理并释放已确认资源，关闭本批新领取。即使 continueAfterFailure=true 也不能继续消耗记录；已有其它活动 Task 的已分配代理保持，不回滚已发生的业务效果。UI 复用 configurationError/资源原因，不能显示 noMatch 或无限等待。

输入关联环境的默认代理只在实际选定环境代次时可知：随该代次固定并在 Task 分配/launch 复验，报告来源阶段为 taskEnvironment，不伪称批次已选定具体代理。显式批次代理覆盖仍使用批次快照。

历史快照：none 可继续；历史 fixed/pool 缺 `proxySelection` 时返回明确资源快照缺失并关闭新领取，不能现场读取当前池“修复”旧批次。用户显式新批次获得新候选。已启动实例保留其原实际代理直到结束，不跨进程恢复人工现场。

## 垂直切片

- P1：冻结/校验无秘密候选与端点，正式装配和持久 round-trip；含 fixed/pool/none、回放、竞争与旧快照拒绝。
- P2：任务/环境分配复验及资源失败关闭领取，短事务边界和 existing UI 原因；continueAfterFailure、并发在途任务和输入环境延迟来源。
- P3：真实 HTTP/worker/受控本地代理验证旧批次只用原集合、新批次读取新集合、端点变化和失效停止；打包与三平台验收。需要真实供应商或系统凭据授权的部分单列，不将合成 provider 当成实网验收。

## 验收边界

P1/P2 不以过滤候选列表一个断言替代完整分配契约。P3 记录 Task/Run/选择身份与实际目标代理；Windows/Intel/ARM、打包源哈希和受控 provider 范围分别记账。Profile 冻结的独立验收继续；本附录未批准前不改上述生产契约，不取消现有69baeeb2矩阵。releaseAccepted=false。
