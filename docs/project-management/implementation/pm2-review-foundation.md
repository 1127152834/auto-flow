# PM2 基础包审查记录

日期：2026-09-13。状态：inProgress。范围：身份/标量、迁移/ORM、Excel解析；不是完整PM2。

## 迁移规格审查

- P1 当前代次缺完整作用域FK：已通过延迟复合FK修复，新增失败→通过测试，禁止不存在或其他项目/表代次。
- P2 change.project_id与operation_id可分别指向不同项目：已加复合FK及父表唯一索引，本次迁移维护，不改PM1历史。
- 独立规格复核通过；13项迁移测试通过，包括重启impact身份不复用、downgrade/upgrade和PM1数据保留。工程质量审查发现并修复 SQLite legacy 模式半迁移：显式 BEGIN IMMEDIATE 使 DDL 与 alembic_version 同事务；base/pm01 中途失败后无残留可重跑。独立工程复核通过，连同PM1仓储和HTTP共31项通过。

## 领域规则规格审查

- P1 日期offset重复编码与PM0契约相反：已修复并通过规格复核；value必须不带offset，offset独立保存。
- P1 隔开量词仍可导致不可控回溯：已修复并通过规格复核；增加成熟regex引擎timeout，不依赖手写子集声称线性。依据[regex官方超时说明](https://pypi.org/project/regex/#timeout)，timeout覆盖整个匹配操作。
- P2 巨大整数、非法offset、畸形精度和巨大重复计数泄漏异常：已修复并通过规格复核，统一领域422。

- 工程复核：总量词展开≤10000、禁用用户pattern隐式全局缓存、统一UPPER_SNAKE错误码；63项测试通过，独立工程复核通过。

## Excel规格审查

- P1 全部行驻留内存，公式来源丢失，表头公式注入和读取路径竞态：修复中。
- P2 日期导出损精度/offset拒绝，operation时间预算未覆盖整个workbook：修复中。
- 16项初始测试通过不等于规格验收。修复后重新做定向测试、独立复审，再工程质量审查。

真实Electron、IPC、HTTP、Google实网、Windows及其他架构：本包未执行。

Excel原七项规格问题复核通过，工程审查新发现字符串32768截断、ContentTypes无界解压、未关闭worksheet生成器、writer临时文件残留和坏数字解析异常；修复中，尚未验收。

## Excel B1 最终复核

原七项规格问题、五项工程问题全部闭合；最后修复公共迭代边界的数值解析异常（表头和数据），避免仅流读取处理而inspect泄漏。定向30测试、Ruff/mypy通过，独立工程复核通过。接口read_sheet返回可关闭的ExcelRowStream/ExcelRow，inspection保留有限sample及全量公式来源统计。这里只是文件适配，文件IPC、持久inspection、原子发布和实际导入页面尚未交付。

## A2a 表资料与目录 API 最终复核

规格闭合：原始UUID先验证后转换；name/description孤立surrogate、q控制字符统一422；Unicode casefold搜索维护持久search_text（本阶段未发布pm02结构同步补齐）。工程闭合：CAS冲突在回滚前捕获currentRevision，避免释放锁后ORM刷新混入另一次写入。35项仓储/HTTP测试、17项命令恢复测试通过，独立工程复核通过。

四个真实HTTP操作为表目录GET/POST和详情GET/PATCH；项目Operation查询扩展真实createTable/updateTable结果。数据记录、字段、状态和文件IPC仍未交付，因此没有启用数据页能力或冒充完整PM2。

前端纯组件规格问题（session、父级关闭、busy确认、fixture）及工程问题（render阶段ref副作用）全部闭合。session/epoch变更改在useLayoutEffect提交生命周期；startTransition + Suspense回归证明被丢弃的B渲染不污染已提交A的请求。独立工程复审通过，13项组件测试、TypeScript和ESLint通过；稳定代码全量前端461项通过。组件尚未装配正式数据页，不能作为PM2页面验收。

## A2c 字段修改影响确认基础

完整FieldRef/RecordRef、规范change、table/fieldRevision和全量当前记录事实绑定持久确认，10分钟有效；预检不创建Operation。最初实现把逐值规则验证放在数据库事务内，真实并发写反例复现SQLite锁失败后，改为只读快照提取单值投影到2MiB spool，释放读事务后运行规则。最终写入前由调用方同一短事务重新计算事实摘要；旧确认必须412。18项集成测试、Ruff/mypy通过，独立规格与工程审查均通过。

当前只有预检/复验适配器，字段PATCH尚未接入。后续必须在同一BEGIN IMMEDIATE中复验后立即修改并提交操作事实；没有该真实调用链时不能标记字段编辑交付。

## A2b 字段与状态目录审查（进行中）

原P1状态更新幂等摘要遗漏statusId、P1字段/记录变更缺数据代次、P2修订超出JSON安全整数均已修复，规格复核通过。43项目录/原表回归通过，包含默认回填中途失败整体回滚。工程发现无默认值的可选字段仍加载全表记录，正在改为按需查询和有界回填；未经最终复核不提交本包。

### A2b 最终闭合

工程复核通过：无默认值时不读取整表；真实回填按200条流式读取/flush并释放ORM实例，仍一次最终commit。独立451条有效记录+3条删除记录验证无遗漏/重复，452条证据；第403条证据失败时此前flush的所有批次完整回滚。44项仓储/原表回归通过。

HTTP独立复审发现可省略状态PATCH字段在OpenAPI中错误声明可null；已用非nullable字段与default_factory、exclude_unset组合修复，显式null422、仅name更新保留color/order。8项HTTP测试、生成类型检查、TypeScript、Ruff/mypy通过，规格与工程最终复核通过。字段GET/POST、状态GET/POST/PATCH及统一操作查询均为真实接口；字段编辑和记录操作不在本次HTTP交付范围。

## A2d 记录命令最终闭合（2026-09-13）

记录 create/get/update/set_status 的独立规格审查发现标量摘要先于校验导致非法数值/Unicode泄漏，以及 keyType 未完整校验；均已修复。原始值保持类型、不trim，字段规则在幂等结果查询后校验，历史重放不受后来字段变化影响。规格和工程复核通过；14项记录测试及独立非法/合法标量探针通过。最后补齐应用、领域、仓储类型边界，畸形identity.fieldId统一422且无持久残留，独立复核再次通过。记录/字段和HTTP合计33项定向回归通过，Ruff全量通过，mypy 163源文件通过。

本包只有显式创建、单条读取、内容修改和业务状态设置。状态清空推进statusRevision，内容和关联修订分别维护；未实现记录列表、删除、执行占用或完整PM2页面。

## A2e 字段编辑最终闭合（2026-09-13）

真实字段更新在同一BEGIN IMMEDIATE中执行幂等查询、生命周期、表/字段CAS、影响事实重验和字段/Operation/change提交。旧影响确认在记录被修改、新增或删除后返回412；新确认不得越过公式、身份类型、已有值兼容性和唯一键约束。无变化编辑不推进修订；记录原值及三类记录修订保持不变。14项实际消费者测试覆盖两线程竞争、提交中途失败全回滚、旧代次和历史重放。独立规格审查后补充消费者异常测试，最终工程复核通过。

A2d/A2e真实HTTP分别由不同于实现者的智能体审查，规格及工程最终通过；GET/POST/PATCH记录、PUT状态、POST mutation-impact 和 PATCH字段连通真实SQLite。生成类型仅覆盖已实现handler，null/date/bool投影与操作结果查询通过5项新HTTP测试。列表查询与正式页面不在这些接口验收范围。

## A2d 缺项与null投影修复（2026-09-13）

A2f设计复审发现先前记录测试未覆盖的缺陷：共享_snapshot对未存储字段调用get，输出伪造null，违反冻结contracts.md RecordSnapshot规则。修复只输出实际存在fieldId；显式null保留，PATCH missing→null仍推进contentRevision。四个新增参数化用例先RED再GREEN，涵盖新增无回填字段、GET/create、原Operation/change不改写及模拟旧格式历史结果原样查询/重放。21项记录集成/HTTP测试通过；扩大相关107项通过。独立规格与工程复核通过。原通过报告保留为当时范围证据，不作为该此前遗漏边界的证明。

## A3b 目录客户端恢复（2026-09-13）

catalog-api提供真实字段/状态查询、字段影响预检和四项命令；恢复时核对project、key、kind、action及完整资源身份，只有明确OPERATION_NOT_FOUND才能原key/原请求快照重发一次。请求体复制防止草稿在等待期间改变重发载荷。17项新客户端测试，连同原表API共25项通过；TypeScript/ESLint通过，独立规格及工程审查通过。接口不直接写缓存/Toast，正式页面仍负责服务实例和会话隔离。

## C1b 状态编辑组件最终闭合（2026-09-13）

主协调独立规格审查发现无变化编辑会发空PATCH、dirty未卸载清理；工程复核又发现无效输入被差异函数当作无变化，使后台刷新覆盖正在输入的草稿。均以失败测试复现后修复：合法值按规范化比较，无效值保留原始差异；Enter与按钮同样阻止空PATCH，dirty随关闭/会话/卸载清理。组件成功不擅自关闭，迟到结果与未提交Suspense渲染不污染当前会话。

12项组件测试覆盖创建/编辑、失败草稿、关闭忙态、会话隔离及readonly、Unicode120/121、安全整数上限；独立复核最终通过。全量TypeScript和ESLint通过。状态组件尚未装配正式五页签页面；不据组件验证标记DT状态管理完整交付。

## A2f 服务端记录查询最终闭合（2026-09-13）

规格审查逐项修复：未验证联合标签导致TypeError、深JSON导致RecursionError、巨大数值溢出、query日期格式偏离权威Scalar规则、datetime及Decimal上下文截断任意小数秒、额外全局group限制、分页遗漏sort。日期比较使用类别及整数秒/精确小数分离表示，aware仅在比较时应用显式偏移，存储值不改。缺失与null复用已修复记录投影，筛选含义与返回事实分开。

工程审查实测404条记录含16KiB无关字段，旧默认身份排序反复解码116.4MiB；已改为空all不运行过滤UDF、默认typed身份直接SQL排序、显式排序仅将所需字段放入比较键。后发现清理发生在rollback归还池之后，会删掉下一查询的临时函数；确定性双线程RED复现后改为持有连接时先注销，再rollback。

38项查询/记录测试、Ruff及mypy通过；独立规格和工程最终通过。仓内新增pool复用与WAL并发回归：count后另一连接删除，本次total/items均4，后续查询3。独立扩展探针同时使用过滤/排序且复用同一DBAPI连接，两查询均成功；callback异常后下一查询可正常工作。

HTTP由主协调接入GET records集合、真实DataRecordPage和bootstrap；独立审查2项契约测试/mypy通过，import排序问题修复后Ruff复核通过。最后完整后端698项、前端490项通过，查询与组件仍不能代替PM2正式页面验收。

## A3c 记录客户端与命令恢复复用（2026-09-13）

记录查询与create/update/status直接使用真实生成DTO； typed记录键UTF8编码，原key、请求快照、完整RecordRef和历史结果恢复均校验。目录和记录两个消费者复用data-command，不新增操作框架；表资料客户端保持既有行为。

独立审查通过真实createApiClient/fetch发现NaN/Infinity在JSON序列化时变为null的P1问题，三个实际客户端失败测试复现后修复为发送或恢复前拒绝非有限值。合法null与有限数字不变，目录默认值同样覆盖。独立规格→工程最终通过；主协调重新运行41项API测试通过。组件与记录页面尚未完成，不据此提升PM2业务验收。

## C1c 标量编辑与C1e记录草稿（2026-09-13）

C1c独立规格及工程闭合：四种类型与missing/null/空串分离，严格数字和日期格式，任意小数秒及显式offset保真，原始非法输入不隐藏dirty。新增真实label点击/Select打开/Escape焦点恢复验收；FormField自动注入id，原“缺少id”推断经实测否定，未重复添加无意义属性。9项测试通过。

C1e纯record-draft经独立规格→工程审查通过，8项测试覆盖必填、码点、数字边界、原日期、仅变化字段、公式/身份/不可读字段、missing与null。额外探针验证required的0/false、受保护必填字段新增拒绝及100位小数秒。组件尚在独立实现，草稿测试不能代替记录页面。

## C1f 记录表格组件（2026-09-13）

独立规格审查通过typed身份与完整record回调、missing/null/空串/false/原日期、不可读值不进入DOM、状态目录失效和未设置区分、服务端分页回调、加载/空/筛选/错误保留旧页与只读保护。工程审查发现表格声明列宽合计漏104px；新增0/2业务列两项RED后修正为192+160+112+200*N。8项定向测试与ESLint通过并经独立复核。此宽度证据只验证DOM样式计算，不宣称Electron布局、缩放或平台验收。

## C1d 字段编辑最终闭合（2026-09-13）

独立真实组件探针发现并以RED回归修复：空表required字段错误强制默认值、blocked仅禁按钮但提交入口无guard、异步RHF校验跨session仍提交、切类型后隐藏非法规则阻断、关闭主Modal后确认层残留、合法trim无变化仍预检。规范no-op修复引入的非法dirty表单无法显示错误也以RED修复。最终17项仓内测试及8项独立原始探针通过，定向ESLint/desktop typecheck通过。

新建默认值由用户显式填写或省略，非空表权威校验仍由后端负责；编辑真实impact预检后才确认，草稿变化废弃旧确认，blocked和生命周期guard覆盖同步/异步入口，关闭与换会话撤销迟到结果。独立规格及工程复核通过；尚未装配字段页，不据此宣称完整PM2通过。

## A3d 表资料客户端复用恢复（2026-09-13）

C2前复查发现旧表客户端请求体没有冻结、恢复没有核验Operation自身projectId。新增测试先RED两失败，随后复用目录/记录已验证的createDataCommand，删除重复恢复分支；表资源和结果guard及公开签名保持。表11+目录18+记录15共44项API测试通过，TypeScript及定向ESLint通过，独立规格→工程审查通过。后续页面仍必须管理原key、冻结版本与服务实例迟到响应。

## C1e 记录编辑组件最终闭合（2026-09-13）

独立探针发现并以RED修复：脏草稿后台刷新后扩大写入字段、排队提交跨会话/关闭仍执行、同步重复提交、合法数字等值仍显示可保存、关闭后确认层残留。最后补充排队时外部readonly/saving变化guard和精确错误焦点/ARIA；必填missing/null定位presence，已填写空串与非法数字定位value，非法offset定位offset。

实现冻结草稿原始record/fields/identity比较基线，未修改字段不写回；命令在微任务执行前复验提交时期的会话和外部保护状态，自己的submitting不阻止合法提交。ScalarDraftError/RecordDraftError通过结构化control定位，错误交已有FormField生成ARIA，不匹配错误文案或手工改DOM属性。

独立最终规格→工程通过：原11探针及5个真实焦点/ARIA探针全部通过，仓内标量/编辑/草稿共30项通过。主协调在最终稳定源码运行完整前端564项/86文件、typecheck、lint、build全部通过。组件尚未挂载正式数据页面；只有后续真实页面和Electron操作才能作为完整PM2验收。

## A2g1 状态历史存储（2026-09-13）

状态删除采用持久墓碑，保留旧代次及已删除记录的外键证据；活动名称部分唯一索引允许删除后以新身份建立同名状态。新增 pm02_status_tombstones，历史迁移未修改。

- RED：四项新迁移测试因缺少迁移/deleted列及故障点未触发失败。
- GREEN：真实空库/已有库、历史引用、同名约束、故障回滚、降级保护共17项通过；Ruff与两源码mypy通过。
- 独立规格与工程审查通过。额外在升级/降级各三个重建故障点注入异常（共六项），比对sqlite_master/完整状态和记录/版本，均回滚且可重跑；ORM与迁移列/默认值/约束/索引一致。
- 此结论仅覆盖存储迁移；删除命令、HTTP、UI及平台业务验收分别登记，不将此包视为PM2完成。

## C2a 数据表目录与表单恢复（2026-09-13）

真实数据表API接入目录搜索/来源/排序/分页、创建/编辑、固定原操作身份恢复和明确冲突重新载入。工作区/项目身份重置表单，服务实例仅撤销请求，后台刷新不修改编辑基线。DataTableFormDialog新增应用离开guard、dirty/saving回调、独立恢复动作及提交epoch。

- 页面8项与表单15项测试通过；首次错误不伪报曾载入数据；真实请求fixture验证原key/body和tableRevision。
- 独立规格审查发现异步关闭许可晚于开始保存时误关表单。新增RED测试确认（1失败），批准落地重新检查提交/恢复锁与recoveryPending后通过。
- 独立复核三项探针：上述竞争、跨工作区迟到reload、重连后查询未接受才用原body/key重发，均通过；五文件ESLint通过，规格和工程审查闭合。
- 本包只证明目录和表单，App装配、表内五页签与Electron另行验收。

## C1g 筛选排序与 A2g2 删除核心（2026-09-13）

C1g：all/any/not、四类型比较、系统状态及八项唯一排序使用统一控件；Apply输出合法JSON，由客户端统一编码。独立审查补齐not(status/group)构造、64 KiB实际UTF8/base64url预算和根not错误显示。14项仓内测试、六项独立探针及ESLint通过，规格/工程审查闭合。

A2g2：状态/记录删除预检绑定完整身份、当前代次、项目生命周期/管理修订、目标修订与当前引用；提交同短事务复验后保存墓碑、Operation和DataChange。状态仅被历史行引用可删除，旧快照不变；记录删除不暗改三类业务修订或清空关联。

- 独立审查发现未知槽被视为空、生命周期变化未使impact失效；新增真实RED并修复。畸形recordKey.type（list/dict等）也改为明确unsupported blocker。
- 状态/记录引用扫描使用必要列投影、yield_per=500、流式计数与摘要，最多20条详情；601行独立探针由601次整行ORM载入/19,693,568个无关业务字符降至0/0。
- 当前47项删除/catalog/record/query集成通过；Ruff、mypy及独立规格/工程审查通过。过期、跨作用域、旧代次、并发、原key回放、当前引用变化和事务故障均有覆盖。
- Task/Sheets/automation引用提供方尚未实现，后续接入必须扩展实际检查；此包不证明这些跨模块能力通过。HTTP单独审查。

## A2g3 删除 HTTP 与生成类型（2026-09-13）

新增状态/记录DELETE，复用统一mutation-impact中的三个action分支、同一个删除服务和项目Operation查询。202的operation是实际已提交succeeded结果，不把接受当成未执行任务；原字段预检分支保留。最新generated由真实handler统一生成。

- 22项相关HTTP测试通过；矩阵新增deleteRecord操作kind过滤曾422，修正真实查询枚举后通过。覆盖strict payload、typed identity、scope/auth、引用blocker、影响变化、CAS、归档和quiesce。
- 独立规格/工程审查通过；额外TestClient探针覆盖9种畸形typed key、5种action错误、4种编码路径错误、六必填、安全整数、精确result/Operation查询及墓碑/归档后的原key重放。7源码mypy、Ruff通过，生成类型只读核对通过。
- 全量后端首次713通过/6失败，失败均为其他迁移回归仍断言旧head。已仅更新两测试文件的head/最终version期望为pm02_status_tombstones，保留旧资源内容与FK检查；该6项重新通过。全量重新核验单独记最终报告。

## C2b 详情与 App 装配（2026-09-13）

独立规格、工程审查通过。三项P2已用失败测试修复：记录详情绑定key+generation并禁止旧键查询新代次；重复离开请求不得覆盖未决resolver；目录加载失败时记录页重试真实失败的catalog查询。连同表A→B迟到响应/AbortSignal共4独立探针通过，四文件37项仓内测试及10个renderer文件ESLint通过。

最终606前端/719后端全量通过。真实隔离Electron两组脚本通过，覆盖表目录创建/编辑/冲突/重连/重启、五页签读取和PM1/既有模块回归。最新图像records与200%下拉已人工读取。首次QA脚本把aria-label当可见文本、第二次把document滚动条宽度变化当应用撑宽，均纠正测试观察；实际root宽708、trigger宽192在下拉展开前后保持，未修改已正确的CSS。旧run-P0vTUA的“directory CRUD”范围词不准确，由最新run-MJZJp0明确create/read/update取代；不声称表删除或记录编辑UI通过。

Ruff首次命令将uv --directory之后的相对路径重复拼接，退出1，改为backend工作目录下src/tests后Ruff和mypy172源码通过。未把错误调用算成通过。

## C2c Task1 共享命令发送准入（2026-09-13）

DELETE的202结果与原操作查询使用相同identity/kind/succeeded及领域投影校验；lookupOnly始终只读，精确未接受错误独立表示；每次真实写入含404后原key重发前动态检查canSubmit。pm2_command_admission_impl先RED10项失败，再实现；独立pm2_command_admission_review规格→工程通过，4文件61测试与22项畸形wrapper/readonly/撤权/Abort探针通过。root最终单文件17测试及eslint通过，TypeScript通过。当前Task1仅共享算法，实际目录Task1b与删除客户端Task2单独审查，不把helper存在当成所有消费者已受保护。

## C2c Task1b 实际目录恢复准入（2026-09-13）

目录表API四个命令入口透传动态策略。scope包含workspace/project/client/instance/session，发送前校验，恢复只查询；精确未接受保原key/body，可明确重试或放弃未接受请求。client改变推进独立submissionEpoch，草稿保留。RED新增7反例失败：五种撤权仍发生第二次POST、两项缺恢复操作；修复后目录/API/表单41测试通过，独立审查同41测试+7仓外探针通过，包括readonly成功核对、新client、非精确404、双击及迟到结果。TypeScript与限定ESLint通过；更后并行Editor写入期间出现的全仓类型暂态不算本包验收。最终目录和两客户端联合102测试通过。
