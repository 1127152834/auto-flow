# PM9 剩余数据能力：已批准契约与实施切片

日期：2026-09-21。状态：confirmed；用户明确批准两份方案，按 C1–C4→R1→R2→R5→R3→R4 实施。来源：原始 data-and-state-rules.md、coverage 逐条审查、82c067c9 的现有实现。本文不修改发行退出条件。

## 范围与复用

已批准 S1–S5 运行时与 Windows 安全边界继续按原方案收尾。这里单独处理核对台账发现的新增冻结能力/持久协议：DATA-SCHEMA-01/06/07、DATA-ID-05 和 DATA-SH-06 的来源差异查看。它们不能从现有管理接口或 queryRecords 推定为已接通。

复用 ProjectDataCapabilityService、现有 command digest/operationId、Task/Run 权限与事务、DataSchemaService 的完整草稿影响分析、SyncOperationRow 和现有 Google transport。禁止另建执行器或直接从 worker 访问 Google；不接入全部 Studio 节点，不做跨进程人工恢复。下面的名称与字段是待实现契约，不是已存在 API。

## R1：工作流查询表结构（先行只读切片）

在现有 project_data 节点新增 queryTableSchema 操作；请求为 executionGeneration、projectId、tableId、datasetGeneration、fieldIds。fieldIds 必须是非空明确列表，不能用缺省字段扩成全表。

Task scope 的 tableGrant 必须明确允许 queryTableSchema 和对应 fieldIds；子流程取父任务上界与当前冻结节点声明交集。回包只有 projectId/tableId/datasetGeneration/tableRevision、fields（fieldId/key/name/type/required/writable/formula/sourceColumn）以及相应字段的来源能力。系统业务状态单独表达为只读系统属性，不能伪装成字段获得修改权限。

读取校验当前调用存活、Run/generation/项目状态、数据代次与字段归属；不授予新行 lease、创建权限或结构写权限，不推进表/内容/状态修订。冻结的依赖决定可查询的身份与字段，结果反映该合法身份当前结构；若字段已失效，显式报错，不能静默省略。

实现顺序：domain 请求验证和拒绝测试 → capability service/repository → worker 路由与 prepare → 复用 project_data 配置控件提供字段选择和输出变量 → 真实 worker 读取结构后做已有合法写入。先确认旧权限不足、别表/旧代次/不存在字段均无副作用，再测只读回包、重复调用、子流程交集和 UI 操作。

## R2：工作流删除字段

请求沿用 operationId/executionGeneration/projectId/tableId/datasetGeneration，并明确 fieldId、expectedTableRevision、impactRevision。tableGrant 新操作 deleteField，只能命中显式 fieldIds。

复用现有 schema preview/commit 的候选草稿和影响算法；工作流预览基于“当前结构移除一个指定字段”，禁止把其余结构由 worker 任意提交。提交在同一写事务重验候选 digest、当前表/字段身份和 impactRevision。行 lease 不代替结构权限；身份字段、关联键、来源映射、其他活动任务冻结依赖和未决同步操作引用均阻断。操作自身的删除目标声明不形成无法消除的自引用，但该 Task 的其他节点读写依赖仍阻断。

成功只删除本地定义/相应值，不删 Google 列；旧 fieldId 不复用。响应丢失按原 operationId/digest 返回已提交结果，不重复删除。父取消前未接受则拒绝；已提交结果保持。

测试/交付：先管理影响算法复用和能力权限交集，随后节点+预览确认 UI；拒绝各依赖、预览后新增依赖、重复命令和成功后旧引用失效都需要直接断言。新操作进入准入前运行真实 worker 成功/冲突两条链。

## R3：Sheets 系统 UUID 初始化

通过现有主进程授权和绑定向导发起管理操作，worker 不获得原始凭据。请求使用原 Idempotency-Key，包含 connectionId/spreadsheetId/sheetId、expectedTableRevision、impactRevision、拟使用身份列；系统生成的 UUID 集合在第一次发送前持久化在同一 SyncOperationRow(kind=systemIdentity) 请求中，随后不可重生成。

持久请求冻结账号连接、目标、bindingEpoch、身份列归属标记、初始化前的可辨识行证据和每行拟写 UUID。发送协调与原发送登记复用；未知响应只按原列/原 UUID/原行证据核验，不新增另一列、不重新抽 UUID。归属不明同名列、重复或缺失 UUID、行证据冲突、已换目标/账号均保留待处理，不覆盖。

远端外部协作者没有提供可区分证据的同内容行移动，不承诺可被推断识别；初始化期间检测到位置/内容变化则停止，要求重新确认一份新计划。不能把此前未知操作当作未发送后继续。

测试先用现有 transport 在发送前/发送成功响应丢失/部分写入/列改名或移动处注入故障；断言 UUID、列和网络写次数。UI 展示同一原操作状态与冲突；当前授权测试表的实网验收单独保留。

## R4：受控远端增列

初期只由显式来源字段操作发起，不让普通本地 addField 自动写远端。请求冻结 operationId、connection/bindingEpoch、目标 sheet、本地 fieldId、expectedTableRevision、impactRevision 和拟创建列名/归属标记；SyncOperationRow(kind=column) 保存计划与核验事实。

列初始化未确认时，本地字段和记录保留，新字段值意图依赖该列操作，不能抢先发送。响应丢失核验原列标记；无归属的同名列不被自动接管。已确认列由稳定映射引用，后续本地删除不触碰远端列；原操作重放不重复加列。

先实现持久依赖检查和原命令恢复，再接已有字段配置 UI 的“来源列”明确选项。验证兼容增列与其他 Task 旧 Patch、原列存在但响应丢失、远端失败仍保留本地值、取消/绑定变更和不得提前推值。实网仍要求授权。

## R5：普通远端差异观察

拉取继续保留本地业务值。新增只读差异契约按 tableId/datasetGeneration/recordKey/fieldId/bindingEpoch 标识；记录最近观察到的 remoteValue、observedAt，以及观察时 localContentRevision 和本地值摘要。UI 明确区分来源观察与已提交本地值；本片不新增“采纳来源”或自动回滚动作。

存储优先复用 SyncRecordMarkRow 的 JSON，但必须将 inbound observation 与已有 outbound evidence 分开命名并合并更新，不能让 push.mark 覆盖入站差异；每字段仅保留最近观察，历史审计若另有需求再设计。不借观察推进 contentRevision/statusRevision 或生成出站意图。新代次/解绑不得把观察移给别的记录。

先冻结 HTTP 只读 DTO 并更新 OpenAPI，再做 transport 差异测试和数据详情组件；验证普通值不变、公式既有刷新不退化、观察更新/无差异、推送证据与观察并存、旧代次不可见。新增、查看、取消详情页面不会触发云写。

## 实施顺序与确认边界

1. 用户确认本文后按 R1 → R2 → R5 → R3 → R4 垂直切片，逐片代码/测试/文档/.ai 提交。R3/R4 实网授权不足时完成离线与 UI 测试，准确保留专项待验收。
2. R1/R2 新 command 在 domain、prepare、worker、repository、UI 一致后才开放；R3/R4 未完成持久未知恢复前保持 501。
3. 每片定向 pytest/Vitest、ruff/mypy、typecheck/lint/OpenAPI；稳定候选执行全量与现有三平台矩阵，不用旧运行替代新源码验证。
4. Windows 既有文件替换仍沿 S4 批准的安全要求做原生实验；此附录不放宽目标身份锁或原子提交。读取端口目前只服务需要随后安全提交的现有输出操作，不能靠开放读取宣称整个写入能力完成。
5. 覆盖只登记具体断言；当前 216 有断言 / 35 未定位不是完成率。各条仍未完整退出，releaseAccepted=false；继续现有 PM9 草稿 PR，不合并发布。

阻塞决定：是否批准上述五个新增数据能力的契约与实施顺序。其余已批准运行时/证据收尾继续，不依赖此决定。

2026-09-21 确认更新：用户已批准上述范围及顺序；本文此前等待确认表述已 superseded。批准记录见 `.ai/decisions/2026-09-21-pm9-shared-claims-data-approved.md`；M1–M3 不在本次授权范围。
