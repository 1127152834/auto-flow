# M2 业务模型与可靠性 设计规格

- 日期：2026-09-30；修订：r2；状态：proposed（用户已授权按评审修订，未实施；步骤级细化后确认）
- 总纲：[整改里程碑总纲](2026-09-30-remediation-roadmap.md)
- 计划：[M2 实施计划](../plans/2026-09-30-remediation-m2-business-model-reliability.md)
- 来源：原方案 B1/A1/A4/A5/B3–B6/C6、当前 RecordRef/多输入领取/失联恢复代码与本轮评审。

## 1. 结论与切片

| 切片 | 交付 | 前置/退出 |
| --- | --- | --- |
| M2A 可靠性 | 主处理单位、完整身份台账、失败分类、未知结果门禁、有限重试、熔断、业务结果 | M1后；AC2-01至06、10至15 |
| M2B 数据契约 | 签名与迁移、写回、最小输出契约、后端项目写入预览 | M2A后；AC2-07/08/16至19；供M3和M5B消费 |
| M2C 独立扩展 | 定时/Webhook、Cookie/Storage和请求拦截 | M2A后独立细化；AC2-09/20；不阻塞M2B/M3 |

不重写执行核心，不优化领取性能（M3），不引入身份资源（M4）。台账和业务状态分离，但保留现有租约、执行代次与原命令幂等。外部网站副作用不能靠本地台账实现“恰好一次”；本阶段保证未知结果不被自动重做。

## 2. 处理单位与兼容

每个数据自动化指定一个 `processingInputId`，指向现有稳定输入ID（签名迁移后作为bindingId保留）。该输入必须required，是进度与台账的主处理行；其他independent/fixedRecord/related输入是参考输入，仍按原规则选择、冻结和租约保护，但不因本Task成功就被台账消费。一次主行处理仍可读取多条关联数据；不在本阶段增加笛卡尔积处理单位。

台账作用域包含 automation_id、processing_input_id 及完整记录身份：project_id、table_id、dataset_generation、record_key.type、规范record_key.value；Sheets额外冻结identity_namespace。内容/状态修订不属于台账主键，同代次同身份修改不自动清除成功状态。换代次、改绑namespace是新作用域，旧账保留可查询、不自动继承。跨表同物理Sheets行仍受原物理租约保护。

单输入旧自动化可自动设置主输入；多输入不能唯一推断时列迁移报告并阻止新批次，用户明确选择后继续，禁止按输入数组第一项猜测。升级前活动/中断运行先按原命令恢复或停止，不重解释被冻结的输入；未核实的旧运行形成启动门禁，不能因“不回填历史台账”遗忘。cycle保留成功行循环用途，但不保留绕过安全门禁的行为。

## 3. 需求

### 3.1 台账与领取

| 编号 | 需求 |
| --- | --- |
| R2-01 | 新表automation_record_ledger以第2节完整作用域唯一约束；state为pending/succeeded/failed_retryable/quarantined/needs_review/skipped；保存累计attempts、processing_cycle、cycle_attempts、last_outcome/error/task/time、next_eligible_at与revision。批次另保存已纳入的主处理单位集合及Task关联，历史批次统计不从自动化“最新状态”倒推。 |
| R2-02 | Task终态与台账在同一事务投影；按task_id及原终态版本去重，重放不重复增加attempts。reset/skip/resolve与运行投影使用修订和活动租约守卫，不能让旧Task覆盖新人工决定。 |
| R2-03 | claimMode=unprocessed/cycle/retryFailed。三者先统一阻止needs_review、quarantined、skipped及未核实旧运行，再检查next_eligible_at。unprocessed只取pending/failed_retryable；cycle另允许succeeded重用；retryFailed只取failed_retryable，quarantined必须先明确reset。同一批次同主处理单位的尝试串行，参考输入不做台账资格过滤。 |
| R2-04 | retryBudget保持字段名但明确为当前处理轮次的总尝试预算（cycle_attempts，含首次），整数≥1，默认3；page失败等已开始的可计费尝试计入，确定未开始的infrastructure与安全取消不计。retryBackoffSeconds默认[60,300,1800]，按失败次数选取并封顶末项；第三次失败在预算3时直接隔离。cycle成功后最小60秒再用，防热循环。 |
| R2-05 | maxRows是本批纳入的不同主处理单位上限，可为空；重试不增加该计数，达到上限后仍完成已纳入行的退避/重试。没有当前候选但有未来next_eligible_at时等待最近到期，不提前completed；等待计划持久化、重启恢复且可停止。unprocessed无未完成单位才结束；cycle不限行数可持续运行，有限maxRows完成已纳入单位后结束本批，后续新批可再用成功行。 |
| R2-06 | GET ledger支持完整scope/state分页；reset/skip接收明确完整单位列表、expectedRevision和幂等键，按state批量操作先预览并冻结目标，不执行无限动态集合。reset/skip均拒绝needs_review，并检查未解决未知事实，禁止skip→reset绕过；新增resolve(reviewDecision=confirmedSucceeded/confirmedNotPerformed/abandon, reason)人工核实命令，只有confirmedNotPerformed允许pending重新领取，保留原未知事实和操作者决定。活动Task拒绝reset/resolve。 |
| R2-07 | 存量claimMode迁移为cycle，不回填可确认终态的历史账；主输入歧义及旧未知运行按第2节门禁处理。模式不再决定能否绕过未知结果；迁移报告明确这项安全行为变化。 |

### 3.2 错误策略与副作用边界

| 编号 | 需求 |
| --- | --- |
| R2-08 | errorPolicy统一为{onError:stop/continue/retry/goto,maxRetries,backoff:{kind,initialSeconds,maxSeconds,jitter},retryOn,gotoNodeId,onExhausted}。旧retryCount/retryDelay/retryBackoff/retryExhaustedAction/timeoutAction/errorPolicy.mode转换为候选配置，前后端对照测试；原来无效的旧重试值必须用户明确启用后才执行，不能因打开/读取文档激活。 |
| R2-09 | 节点每次尝试有独立attempt事件；goto受调度上限约束并检查整个回流区间的副作用。已成功外部提交后后续读取失败，也不能自动重跑整个Task或回流经过提交节点。 |
| R2-10 | 执行器声明side_effect=none/possible；执行可能外部副作用前同步持久化“已进入不可证明安全重放区域”的状态并ACK，完成后也不允许凭后续节点为只读就自动重跑整Task。只有能证明动作未发出或使用原外部幂等身份核实安全时可重试；证据缺失默认needs_review。已有本地幂等命令只允许原命令核验/重放，不能换新Task规避。 |
| R2-11 | 执行器配置schema统一导出；预检未知键警告；前端键按对应节点与schema比较。键在schema中存在不证明生效，每项可配置行为仍须实际执行测试；unreadConfigKeys归零不得靠把任意键加入schema。 |
| R2-12 | 恢复“高级→出错时”统一控件；旧文档展示迁移候选及启用提示；所有入口接入后删除M1隐藏开关与inert提示，但保留旧文档行为版本。 |
| R2-13 | category=infrastructure/page/business/unknown/cancelled。只有确定执行未开始的启动/代理预检故障为可重排infrastructure；执行中WORKER_LOST、动作阶段无法核实、已有副作用后的整Task重跑风险为unknown。纯读取且可证明无外部动作时未分类异常可为page，否则默认unknown。原始code/异常类型保留用于诊断。 |
| R2-14 | End businessResult=success/businessFailure与reason；业务失败台账skipped，不触发技术失败熔断。多个End/分支结果以既有运行终态仲裁为准，未处理技术失败不被成功End掩盖。 |
| R2-15 | 新自动化failurePolicy：最近20个已结束Task中page超过50%、连续5个确定未开始的infrastructure、连续10个相同技术错误码时暂停；业务失败与unknown不计同码/技术失败阈值，unknown单列待办。存量continueAfterFailure保留legacyAnyFailure/legacyContinue兼容策略，明确切换后才用新阈值；不声称N=1/P=0等价所有旧失败语义。 |
| R2-16 | paused批次可修复后继续或结束；恢复不重置预算/台账/未知门禁，不自动再做needs_review行。 |
| R2-17 | 坏行仅在能唯一识别主行且其他行身份可信时quarantined并继续。Sheets重复键、namespace不明或来源一致性未证实仍属输入/表级门禁，不能凭“跳过坏行”解除现有来源身份保护；参考输入坏行按依赖传播，不能标错主行身份。 |

| 类别 | 自动处理 | 台账 |
| --- | --- | --- |
| infrastructure（确定未开始） | 退避重排；资源替换遵守绑定策略 | attempts不增，保留资格 |
| page（已证明整Task安全再做） | 节点/行预算内重试 | attempts增加；failed_retryable或quarantined |
| business | 不重试，批次继续 | skipped，记录业务原因 |
| unknown | 所有claimMode禁止自动领取 | needs_review，明确人工核实才解除 |
| cancelled（无副作用不确定性） | 不自动继续 | 原账保持；若动作结果无法确定则改unknown |

### 3.3 M2B 数据契约

| 编号 | 需求 |
| --- | --- |
| R2-18 | signature={inputs:[{key,name,fields:[{key,name,type,required,sensitive,sample?}]}],outputs:[...]}。key为稳定标识（新建建议英文，旧中文key保留支持），name可改；输入的bindingId保留原inputId，processingInputId不因改名变化。 |
| R2-19 | 解析{input.<组key>.<字段key>}及$record；旧PROJECT_INPUTS格式保持兼容，直到M6迁移门禁通过，不能按经过一个版本自动删除。 |
| R2-20 | bindings保留bindingId、signatureInput、完整表身份/代次、字段映射、筛选排序、原输入mode/required/relations；新绑定不完整拒绝启动，错误指向缺失字段。迁移不丢fixedRecord/related或可选输入语义。 |
| R2-21 | 敏感标记由签名或表字段定义驱动，输出/错误/预览继承；不用名字正则替代。 |
| R2-22 | 扫描并改写可确认引用，生成可重入迁移报告；歧义不改写、不静默丢弃，保留旧执行能力。覆盖文档、仍需运行的冻结内容、跳版本升级及后续旧文件导入。 |
| R2-23 | 运行时移除表结构add/modify/delete/previewFieldDeletion；旧节点预检指向数据页维护；正常读取/写入/删除记录能力保留。 |
| R2-24 | 当前输入写回可省expectedContentRevision；使用冻结值与本Task写游标作字段级冲突判断，本Task二次写不误判自己冲突；显式旧版本行为不变。冲突双方值按敏感规则遮蔽。 |
| R2-29 | 最小节点输出契约前置：执行器导出稳定nodeId/outputKey、显示名、类型、敏感性和是否必有；新引用内部按稳定标识，改节点名不失效。保留旧变量别名/执行行为至M6，编辑器只把所有有效到达路径均定义的输出列为必有；条件输出单独标注，不能用可达上游代替必然定义。 |
| R2-30 | 项目试跑请求新增executionMode=previewWrites/realWrites；预览入口默认previewWrites，后端将模式冻结入原运行命令，worker不可自行提升。previewWrites对项目记录/状态写入使用运行私有覆盖层，后续读和查询看见本次预览变更，新增记录使用仅该预览可解析的引用；不改变真实记录/版本、生产台账、Sheets出站意图、持久身份或环境。仅运行诊断可落库；End保存登录状态在预览中明确拒绝/预检提示，不假装成功。网页/HTTP外部操作仍真实执行，文案明确不是外部副作用沙箱；真实写入须显式选择。覆盖层与临时引用无法传入真实写回，重启后只查询原预览事实，不自动重跑外部动作。 |

### 3.4 M2C 触发与网页原语

| 编号 | 需求 |
| --- | --- |
| R2-25 | cron+时区/Webhook密钥调用同一启动用例；定时幂等键=调度ID+计划触发时刻，Webhook使用来源事件ID/客户端幂等键，不使用每次接收时刻制造不同任务。复用loopback鉴权边界，不为Webhook暴露公网sidecar；外部接入方式另行设计。 |
| R2-26 | overlap=skip/queue/parallel（默认skip），错过触发latestOnly/ignore（默认latestOnly）；停止/重启不重复补跑同触发。 |
| R2-27 | 自动化“调度”页签、最近10次触发结果与启停；契约先于界面。 |
| R2-28 | Cookie/localStorage/sessionStorage读写、请求拦截按M1节点登记方式接入；副作用、敏感性和配置schema一并声明。 |

## 4. 验收标准

| 编号 | 验收 |
| --- | --- |
| AC2-01 | native-batch-v1 G2一万行：1%永久404各总尝试3次后隔离，其余正确输出；退避等待不提前完成、无漏行/饿死。 |
| AC2-02 | G3提交后丢响应/worker死亡，在unprocessed、迁移cycle和retryFailed下均恰好一次提交，needs_review不再自动领取；M0独立xfail转正。 |
| AC2-03 | 登录失败→End业务失败：台账skipped，批次继续。 |
| AC2-04 | 首次只读超时按策略恢复，attempt可追踪；已提交后读取失败、goto跨提交和停止期间失联均不自动重做整Task。 |
| AC2-05 | 连续5次启动前代理故障暂停且预算不消耗；执行中同类错误无安全证据时unknown，不能只按code决定。 |
| AC2-06 | 身份可确定的单坏行隔离；重复Sheets身份/namespace不明/来源未验证仍拒绝输入，不误消费参考行。 |
| AC2-07 | 同签名流程绑定不同表可运行；缺字段拒绝；改显示名不破坏引用。 |
| AC2-08 | 可迁移项转换，歧义报告且仍可按旧格式使用；跳版本/旧文件导入保留明确路径。 |
| AC2-09 | 定时skip无重叠，重启latestOnly一次；Webhook同事件重放一次，错误密钥不启动。 |
| AC2-10 | 每个可执行节点schema与面板对应，无新增无效键；行为测试证明选项实际生效。 |
| AC2-11 | 两订单共享fixedRecord账号、related参考以及同一行多别名：各主行一次，参考行不被消费。 |
| AC2-12 | 同表同key重新导入、更换Sheets namespace进入新台账作用域；text“1”与integer 1不混同，同代次内容修订不自动清账。 |
| AC2-13 | 投影重放/回滚/崩溃不重复计数；active Task阻止reset；needs_review只经resolve解除，旧未知运行不能因迁移遗忘。 |
| AC2-14 | maxRows计唯一主单位，重试不额外占行数，未来退避到期继续，重启保留计数；cycle成功重用仍受最小间隔和终态规则限制。 |
| AC2-15 | 旧未生效重试值不会自动激活；原continueAfterFailure两种语义保留，显式切换才用新熔断。 |
| AC2-16 | 字段级冲突、本Task连续写、敏感值遮蔽通过真实SQLite/worker验证。 |
| AC2-17 | 分支汇合、零次循环和错误分支的条件输出不冒充必有；节点改名不改变稳定引用。 |
| AC2-18 | 真实HTTP/worker/SQLite预览：写后读看见预览值；真实记录/版本/台账/同步出站/环境均不变；临时引用不能真实写入；realWrites显式选择才变更。 |
| AC2-19 | M0受控场景保留，新增native-batch-v1固定数据/故障/硬件/并发/内核，至少5次记录用于M3对照。 |
| AC2-20 | Cookie/Storage和拦截真实浏览器用例通过、配置和敏感字段契约完整。 |

## 5. 实施约束

台账更新复用Task终态事务，完整身份复用现有RecordRef和typed RecordKey规范化；不创建另一套租约。M2A先建立主输入和安全门禁，再挂分类/投影与领取，禁止分类尚缺时把unknown临时当page上线。schema/output声明共用既有执行器注册表，不建立重复节点目录。M2B输出元数据供M5使用，M6才清理旧变量分支。

批次统计按本批纳入的处理单位/历史Task投影，不以全自动化最新台账冒充历史批次进度。所有变更先增量迁移、可恢复备份与失败报告；M2A/B/C分别细化、验收、记录状态。

### r2 补充：循环预算

累计attempts保留历史；retryBudget比较当前processing_cycle的cycle_attempts，含该轮首次执行。只有已确认succeeded的单位开始新的cycle轮次才递增processing_cycle并清零cycle_attempts；失败后换批次继续保持原轮次与预算。人工reset是明确、可审计的新处理轮次，须先通过全部未知结果门禁；不能在自动重开批次时隐式reset。终态按Task/轮次去重，启动前确定未执行的基础设施失败不消耗预算。

AC2-14增加：连续成功三轮后第四轮首次安全失败仍可在该轮剩余预算内重试；失败后跨批次不重置预算。AC2-13增加：needs_review不能通过skip→reset清除，只有resolve(abandon)可跳过未知项且保留原事实。
