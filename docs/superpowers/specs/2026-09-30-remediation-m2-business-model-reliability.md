# M2 业务模型与可靠性 设计规格

- 日期：2026-09-30；状态：proposed，待用户审批
- 总纲：[整改里程碑总纲](2026-09-30-remediation-roadmap.md)；对应整改方案 B1、A1（正式实现）、A4、A5、B3、B4（后端）、B5、B6、C6，以及 G1 的其余网页原语
- 前置：M1 已合并
- 实施计划：[M2 实施计划](../plans/2026-09-30-remediation-m2-business-model-reliability.md)（任务级，M1 退出评审后细化为步骤级）

## 1. 结论

M2 让"每一行数据的处理结果可预期"：系统用处理台账记住每个自动化对每一行做过什么，失败按类别处置，批次按阈值熔断而不是一刀切；流程声明自己需要的输入（流程签名），自动化只负责把签名绑定到表字段；写回不再要求流程自己传版本号；项目批次可以定时启动。

## 2. 背景

- 领取不排除失败过的行、排序固定：永远失败的行排在最前时会耗尽次数或死循环（设计文档 execution-and-environment.md §4.1、验收样例 XE-A21/A22 明确规定"没有批内已消费集合"）。
- 失败只有成功 / 失败两类，批次策略只有"任一失败即停 / 永远继续"。
- 流程内引用项目数据是 `{PROJECT_INPUTS['<输入UUID>']['values']['<字段UUID>']}`，换自动化绑定即失效。
- 写回需要流程传 `expectedContentRevision`；运行时节点可以增删改表字段。
- 定时任务只能启动独立流程（`application/workflows/schedules.py` 使用 workflow_id）。
- M1 隐藏的出错策略、重试、超时动作仍未实现。

## 3. 目标与非目标

**目标**

1. 新表 `automation_record_ledger`，任务终态与台账在同一事务更新；三种领取模式；默认"未成功处理"。
2. 节点级出错策略正式实现（整改方案 A1 表格），并恢复 M1 隐藏的界面（新的统一控件）。
3. 失败五分类（基础设施、页面技术、业务、结果不明、已取消）及处置规则；End 节点支持"业务结果"。
4. 批次熔断：比例阈值、连续基础设施失败、同一错误码连续出现。
5. 坏行只隔离该行。
6. 流程签名（后端模型、校验、运行时解析、迁移脚本），自动化绑定签名。
7. 表结构操作移出运行时；写回当前记录时系统自动使用领取时冻结的版本并按字段判断冲突。
8. 定时与 Webhook 启动项目批次，含重叠策略与错过补跑。
9. 新增 Cookie / 本地存储读写节点、请求拦截节点。

**非目标**

- 领取 SQL 下推与性能（M3）。M2 的台账过滤先在现有领取路径中实现，性能指标不在本里程碑承诺。
- 签名、台账、写回的界面体验重构（M5 的 H2–H7）。M2 只提供最小可用界面：自动化绑定页的字段映射表、批次页的台账分组计数、End 节点的业务结果下拉。
- 身份（M4）。

## 4. 需求

### 4.1 处理台账（B1）

| 编号 | 需求 |
| --- | --- |
| R2-01 | 表 `automation_record_ledger`：主键 (automation_id, table_id, record_key)；列 state（pending / succeeded / failed_retryable / quarantined / needs_review / skipped）、attempts、last_outcome、last_error_code、last_error_message、last_task_id、first_attempt_at、last_attempt_at、next_eligible_at；索引 (automation_id, state, next_eligible_at)。 |
| R2-02 | 任务进入终态时，在投影 Task 终态的同一事务中按失败类别更新台账（见 4.3 表）；基础设施失败与已取消不增加 attempts。 |
| R2-03 | 自动化运行设置增加 `claimMode`：`unprocessed`（默认，新建自动化）、`cycle`（现有语义，存量自动化迁移后的取值）、`retryFailed`。`unprocessed` 只领取 state ∈ {pending, failed_retryable}、attempts < 预算、now ≥ next_eligible_at 的行；`cycle` 只看筛选条件但仍尊重 next_eligible_at；`retryFailed` 只领取 failed_retryable 与（用户确认后的）quarantined。 |
| R2-04 | 自动化运行设置增加 `retryBudget`（默认 3）与 `retryBackoffSeconds`（默认 [60, 300, 1800]）；超过预算进入 quarantined。 |
| R2-05 | "最多任务数"拆成 `maxRows`（本批最多处理几行，可为空表示直到没有可领取的行）；取消 1–100 上限。 |
| R2-06 | 接口：`GET /projects/{p}/automations/{a}/ledger?state=&page=`；`POST .../ledger/reset`（按 record_key 列表或 state 批量重置为 pending）、`POST .../ledger/skip`。批次详情返回按 state 的行数。 |
| R2-07 | 迁移：存量自动化 `claimMode = cycle`（保持行为）；不回填历史台账。 |

### 4.2 节点出错策略（A1 正式实现）

| 编号 | 需求 |
| --- | --- |
| R2-08 | 统一字段 `errorPolicy: { onError: stop\|continue\|retry\|goto, maxRetries, backoff: { kind: fixed\|exponential, initialSeconds, maxSeconds, jitter }, retryOn: [timeout, elementNotFound, network, any], gotoNodeId, onExhausted: stop\|errorBranch\|continue }`；默认 onError=stop。旧键（retryCount、retryDelay、retryBackoff、retryExhaustedAction、timeoutAction、旧 errorPolicy.mode）在读取文档时迁移为新结构，迁移函数前后端各一份并有对照测试。 |
| R2-09 | 每次重试产生新的 attempt 事件，原 attempt 保留；`goto` 回到指定上游节点重跑，受全局调度上限保护。 |
| R2-10 | 每种执行器声明 `side_effect: none\|possible`（点击、提交、按键、HTTP 非 GET、写回类为 possible）。possible 节点只有在失败确定发生在动作之前（元素未找到、导航前超时）才自动重试；动作已发出后超时，归为"结果不明"，不重做。 |
| R2-11 | 每种执行器声明配置 schema（pydantic）；运行前预检对未知配置键报警告；M0 的配置键守门改为"前端面板键 ⊆ 执行器 schema"精确检查，`unreadConfigKeys` 归零。 |
| R2-12 | 恢复界面：配置面板"高级"段中的"出错时"统一控件（替代 M1 隐藏的旧控件），默认值不再自相矛盾；`featureFlags.nodeRetryPolicy` 删除。 |

### 4.3 失败分类与批次熔断（A4、A5）

| 编号 | 需求 |
| --- | --- |
| R2-13 | 运行错误增加 `category`：infrastructure / page / business / unknown / cancelled。执行器把常见异常映射到稳定编码（ELEMENT_NOT_FOUND、NAVIGATION_TIMEOUT、PROXY_CONNECT_FAILED、BROWSER_LAUNCH_FAILED、WORKER_LOST 等）与类别；无法判断时为 page。 |
| R2-14 | End 节点增加 `businessResult: success\|businessFailure` 与 `reason`；到达"业务失败"的 End 时任务结果为业务失败（不是技术失败）。 |

| 类别 | 自动重试 | 台账 | 对批次 |
| --- | --- | --- | --- |
| infrastructure | 是（换资源重新排队） | attempts 不变，next_eligible_at 退避 | 计入"连续基础设施失败" |
| page | 按节点策略 | attempts+1，failed_retryable 或 quarantined | 计入失败率 |
| business | 否 | state=succeeded 之外的终态：记 last_outcome=business，state=skipped（不再领取） | 不影响 |
| unknown | 否 | state=needs_review | 不影响，进入人工待办 |
| cancelled | 否 | 不变 | — |

| 编号 | 需求 |
| --- | --- |
| R2-15 | 批次 `failurePolicy`：最近 N（默认 20）个任务中 page 类失败超过 P（默认 50%）暂停，原因"疑似页面变化"；连续 K（默认 5）次 infrastructure 失败暂停并指出资源；同一错误码连续 M（默认 10）次暂停并置顶该错误。取代 `continueAfterFailure`（迁移：false → N=1、P=0% 的等价阈值；true → 默认阈值）。 |
| R2-16 | 暂停状态 `paused`（新批次状态），可"修复后继续"或"结束批次"；进度保留在台账。 |

### 4.4 坏行隔离（B3）

| 编号 | 需求 |
| --- | --- |
| R2-17 | 候选行解析租约身份出错（如 Sheets 行未通过校验）时，该行在台账中标记 quarantined 并记录原因，领取继续；只有表级问题（表不存在、结构失效、数据源不可用）返回 configurationError。 |

### 4.5 流程签名（B4 后端）

| 编号 | 需求 |
| --- | --- |
| R2-18 | 流程文档顶层 `signature: { inputs: [{ key, name, fields: [{ key, name, type, required, sensitive, sample? }] }], outputs: [...] }`。key 为稳定英文标识，name 为显示名。 |
| R2-19 | 表达式 `{input.<组key>.<字段key>}` 与 `{input.<组key>.$record}`（记录引用，供写回使用）；运行时由签名 + 自动化绑定解析。旧格式 `PROJECT_INPUTS[...]` 在一个版本周期内继续解析。 |
| R2-20 | 自动化 `inputPlan` 改为 `bindings: [{ signatureInput, tableId, fieldMap: { 字段key: fieldId }, filter, orderBy, relations }]`；绑定不完整时不能启动，错误指出缺哪个签名字段。 |
| R2-21 | 敏感判定来自签名字段或表字段定义；不再按别名匹配"password/密码"。 |
| R2-22 | 迁移脚本：扫描现有流程，按对应自动化的输入别名与字段别名生成签名、改写引用；无法自动对应的写入迁移报告（`GET /api/v1/migrations/signature-report`），不静默丢弃。 |

### 4.6 写回与表结构（B5、B6）

| 编号 | 需求 |
| --- | --- |
| R2-23 | 运行时移除 addField / modifyField / deleteField / previewFieldDeletion；已有文档中这些节点在预检中报错并提示"表结构请在数据页修改"。 |
| R2-24 | 写回当前输入记录时，`expectedContentRevision` 可省略，系统使用领取时冻结的版本；冲突按字段判断：只有本任务修改的字段在运行期间被他人改过才算冲突，错误列出字段与双方的值。显式传入版本的旧文档行为不变。 |

### 4.7 定时与触发（C6）

| 编号 | 需求 |
| --- | --- |
| R2-25 | 项目自动化可配置定时（cron + 时区）与 Webhook（带密钥）；两者调用同一"启动批次"用例，幂等键 = 调度 ID + 触发时间。 |
| R2-26 | 重叠策略：skip / queue / parallel（默认 skip）；错过的触发：latestOnly（默认）/ ignore。 |
| R2-27 | 接口与最小界面：自动化详情"调度"页签（列表、新增、启停、最近 10 次触发结果）。 |

### 4.8 网页原语（G1 其余）

| 编号 | 需求 |
| --- | --- |
| R2-28 | 新增节点：读写 Cookie、读写 localStorage / sessionStorage、请求拦截（屏蔽资源类型、按 URL 模式改写或模拟响应）。登记方式同 M1 的 press_key。 |

## 5. 设计要点

- 台账更新点：`application/project_runs` 中投影 Task 终态的用例；与 Task 同一个 SQLAlchemy 事务。领取过滤：M2 在 `infrastructure/database/project_claims.py` 的候选筛选中加入台账条件（按 record_key 集合过滤），M3 再下推为 SQL。
- 类别由执行器结果携带（`ModuleResult.error_code`、`error_category`，新增可选字段），运行时透传到运行错误；worker 失联、浏览器启动失败由派发器 / worker 管理器直接给出 infrastructure。
- 熔断在调度器推进批次时评估（`scheduler.py` 的批次推进路径），评估输入为最近任务的类别序列，纯函数实现便于测试。
- 签名解析放在 `domain/workflows/signature.py`（纯函数：解析、校验、表达式重写）；运行时变量注入在项目 worker 的输入上下文构建处完成。
- 定时复用 `application/workflows/schedules.py` 的调度循环，增加 `target: { kind: workflow\|automation }`。
- 功能开关：`ledgerClaimMode`（新建自动化默认开）、`errorSemanticsV2` 已在 M1 以文档字段实现。

## 6. 验收标准

| 编号 | 验收 |
| --- | --- |
| AC2-01 | G2（10,000 行，1% 永远 404）：永远失败的行各尝试 3 次后 quarantined，其余 99% succeeded；批次不停。 |
| AC2-02 | G3 中"提交后响应丢失"的行进入 needs_review，站点对该行只收到 1 次提交（M0 的 xfail 转正）。 |
| AC2-03 | 流程"登录失败 → End(业务失败)"：任务结果为业务失败，台账 state=skipped，批次继续。 |
| AC2-04 | 注入"首次加载超时"，配置 retry 的节点自动恢复，日志有两个 attempt；点击提交后超时的节点不被重做。 |
| AC2-05 | 连续 5 次代理连接失败后批次暂停，原因指出代理；这些失败不消耗行的重试预算。 |
| AC2-06 | 一行 Sheets 数据未通过校验时，该行 quarantined，其余行照常领取。 |
| AC2-07 | 用签名引用 `{input.账号.email}` 的流程可被两个绑定到不同表的自动化复用；绑定缺字段时启动被拒并指出字段。 |
| AC2-08 | 迁移脚本对现有测试夹具中的全部流程生成签名；无法对应的项出现在报告中。 |
| AC2-09 | 定时每分钟触发、批次运行超过 1 分钟时，skip 策略下不产生重叠批次；应用重启后按 latestOnly 补跑一次。 |
| AC2-10 | `node scripts/ratchets.mjs` 中 `unreadConfigKeys` 为 0，并改为 schema 精确检查。 |

## 7. 风险

| 风险 | 应对 |
| --- | --- |
| 台账与现有"业务状态"语义混淆 | 文案与文档明确：业务状态归用户，台账归系统；M5 的数据表页分列显示 |
| 签名迁移改写引用出错 | 迁移前自动备份工作区；报告列出所有改写；旧格式继续解析一个版本 |
| 熔断误暂停 | 阈值可在自动化中调整；暂停原因与样本任务可见 |
| 类别映射不全 | 未知异常默认 page，并在日志中带原始异常类型，按黄金场景结果补映射 |
