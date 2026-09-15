# 项目管理执行账本

- 日期：2026-09-13；状态：PM0 accepted（用户授权PM1）；PM1 delivered；本轮用户授权仅执行至PM2验收点，PM2 inProgress，PM3–PM9 planned。
- 规格：[完整设计](../design/README.md)；[总里程碑](../../superpowers/plans/2026-09-13-project-management-milestones.md)；[PM0执行卡](../../superpowers/plans/2026-09-13-project-management-pm0.md)。
- 机器映射：[coverage.json](coverage.json)；领域/传输：[contracts.md](contracts.md)、[api-contracts.md](api-contracts.md)；合成样例：[fixtures.json](fixtures.json)。

## 1. 责任与共用文件

| 责任ID | 唯一修改责任 |
|---|---|
| integration | 主协调/集成者；独占公共签名、路由装配、迁移汇合、生成类型与覆盖文件 |
| projects | 项目领域交付负责人；组件/API垂直切片 |
| project-data | 项目数据负责人；身份、取数、版本、节点数据操作 |
| project-runs | 自动化与运行协调负责人；核心由Studio所有者提供 |
| environments | 环境与人工负责人；核心终态仍归Studio |
| data-source | 来源同步负责人；Excel/Sheets适配 |
| verification | 平台与全链验收负责人；逐平台记录证据 |

责任ID是一项交付的责任角色，不代表永久团队或新增服务。PM0具体由pm0_domain_contracts独占contracts.md、pm0_api_contracts独占api-contracts.md；集成者统一定稿。其他文件由主协调修改。后续每包开工记录实际执行者，不能让两个代理同时改同一公共文件。

| 共享边界 | 责任与实施时点 |
|---|---|
| UI/页面入口 | 现有desktop shared控件由集成者在PM1接入1fb58e1所需变更及测试；领域组件先于页面。packages/ui仍是骨架，不复制另一套。 |
| OpenAPI/generated.ts | 后端领域包实现真实handler及契约测试后，由集成者一次生成并check；页面不长期依赖mock。 |
| 核心文档/Run/IR | Studio所有者唯一维护；workflowId引用document.id；项目窄端口无执行循环。 |
| 数据库迁移 | pm01项目→pm02数据→pm03自动化→pm04项目Run→pm05环境→pm06同步；具体down_revision以实际已接入head串联；核心Run迁移必须先于pm04外键。 |
| 并行Studio迁移 | 最终只读核对主目录已提交b2e95b3，0005_workflow_documents从0004派生。PM1对齐该提交后沿0005；此前从0004派生的隔离分支需显式迁移汇合，不等待核心Run。集成者解决并发heads，禁止改旧0002/0003脚本。 |
| SQLite工作单元 | 根用例控制提交；core.prepareRun接收同UoW并不自提交，runtime/网络在事务外；核心不得import项目ORM。 |
| 桌面文件/凭据 | main IPC及现有平台/系统凭据适配器；业务层无macOS/Windows判断和任意路径。 |

## 2. 三十个交付包

F0–F9具体目录以总计划第2节为准；本表责任包含该包前后端组件、页面和测试。下列为交付计划，不表示文件已经存在。

| 包 | 交付 | 负责人 | 后端文件组 | 开始依赖 | 集成顺序 |
|---|---|---|---|---|---|
| PM0-A | 基线与接口卡 | integration | F0 | 已确认设计 | 本阶段首包 |
| PM0-B | 传输与集成卡 | integration | F0 | 已确认设计 | PM0-A |
| PM0-C | 验收卡与并行边界 | integration | F0 | 已确认设计 | PM0-B |
| PM1-A | 真实项目目录 | projects | F1,F8,F9 | PM0 | 本阶段首包 |
| PM1-B | 组件与导航上下文 | projects | F1,F8,F9 | PM0 | PM1-A |
| PM1-C | 最小生命周期保护 | projects | F1,F8,F9 | PM0 | PM1-B |
| PM2-A | 本地数据与状态 | project-data | F2,F3,F9 | PM1 | 本阶段首包 |
| PM2-B | Excel 导入与替换 | project-data | F2,F3,F9 | PM1 | PM2-A |
| PM2-C | 导出与人工变更证据 | project-data | F2,F3,F9 | PM1 | PM2-B |
| PM3-A | 自动化管理与 Studio 关联 | project-runs | F4,F5,F8,F9 | PM1 | 本阶段首包 |
| PM3-B | 参数型真实启动 | project-runs | F4,F5,F8,F9 | PM1 | PM3-A |
| PM3-C | 基本诊断与停止 | project-runs | F4,F5,F8,F9 | PM1 | PM3-B |
| PM4-A | 完整输入选择与原子领取 | project-data | F2,F3,F5 | PM2,PM3 | 本阶段首包 |
| PM4-B | 显式写入与版本 | project-data | F2,F3,F5 | PM2,PM3 | PM4-A |
| PM4-C | 批次完整调度语义 | project-data | F2,F3,F5 | PM2,PM3 | PM4-B |
| PM5-A | 保存身份、来源与工作副本 | environments | F6,F8,F9 | PM4 | 本阶段首包 |
| PM5-B | End 完整保留及维护 | environments | F6,F8,F9 | PM4 | PM5-A |
| PM5-C | 人工、额度与竞争 | environments | F6,F8,F9 | PM4 | PM5-B |
| PM6-A | 连接/身份/多绑定 | data-source | F2,F3,F9 | PM2,PM4 | 本阶段首包 |
| PM6-B | 本地意图→远端核验 | data-source | F2,F3,F9 | PM2,PM4 | PM6-A |
| PM6-C | 公式、增列与来源调整 | data-source | F2,F3,F9 | PM2,PM4 | PM6-B |
| PM7-A | 完整证据与互查 | project-runs | F5,F7 | PM4 | 本阶段首包 |
| PM7-B | 概览与统计 | project-runs | F5,F7 | PM4 | PM7-A |
| PM7-C | 失败后的新批次快捷入口 | project-runs | F5,F7 | PM4 | PM7-B |
| PM8-A | 归档/恢复/删除影响 | integration | F1,F2,F3,F4,F5,F6,F8 | PM5,PM6,PM7 | 本阶段首包 |
| PM8-B | 跨重启核验与残留处理 | integration | F1,F2,F3,F4,F5,F6,F8 | PM5,PM6,PM7 | PM8-A |
| PM8-C | 工作区与资源集成 | integration | F1,F2,F3,F4,F5,F6,F8 | PM5,PM6,PM7 | PM8-B |
| PM9-A | 全功能闭环 | verification | F1,F2,F3,F4,F5,F6,F7,F8 | PM1,PM2,PM3,PM4,PM5,PM6,PM7,PM8 | 本阶段首包 |
| PM9-B | 故障与规模 | verification | F1,F2,F3,F4,F5,F6,F7,F8 | PM1,PM2,PM3,PM4,PM5,PM6,PM7,PM8 | PM9-A |
| PM9-C | Windows/macOS 安装包 | verification | F1,F2,F3,F4,F5,F6,F7,F8 | PM1,PM2,PM3,PM4,PM5,PM6,PM7,PM8 | PM9-B |

组件独立编写可与后端并行；“集成顺序”表示公共契约和整包接入顺序，不要求所有开发串行。PM3参数链允许在PM2完成前开始，PM3完整退出仍要求其数据输入配置与核心能力。PM7查询可先做，完整退出等待PM5/PM6事实；最终门槛不被开始条件替代。

## 3. 能力依赖与测试责任

每条功能/规则/契约/门槛的primary_package、owner、planned_test_file、acceptance_methods、dependencies及completion_packages均在coverage.json中登记。planned_test_file是需要创建或扩展的测试目标，不冒充当前存在的文件。完整验收的包集合表示必须联合复核的阶段范围；原始first_usable/first_implementation保持原规格。

跨模块接口规范已冻结，但核心Run实现与集成验收依然缺失。PM1/PM2不依赖核心执行。PM3需C01/02/05/06/07，PM4需变量/控制流/子流程与受控项目能力，PM5需检查点和End最终化。不能用Profile测试浏览器扩成第二执行器来绕过依赖。

## 4. PM0验收记录

| 交付 | 状态 | 证据 |
|---|---|---|
| 基线、18契约、传输、样例、覆盖 | delivered | 本目录资产，正式结果见plan-verification.json |
| 规格符合性审查 | passed | pm0_spec_review 独立逐项核对906deda；前轮问题修复后复核通过 |
| 工程可实施性审查 | passed | pm0_quality_review 独立审查后修复并复核；结果见本节与核验报告 |
| 用户PM0验收 | accepted | 用户明确授权下一阶段并给出PM1实施计划 |
| PM1–PM9业务行为 | planned / 未执行 | evidence保持空 |

每次实际验收必须追加：交付包、提交、执行者、日期、OS/架构、命令及退出码、场景编号、测试方式、实际结果和证据路径。真实应用另记操作步骤与脱敏Task/Run/Operation定位；失败、未运行和阻塞分别写清，禁止以自动测试抵扣实网/安装包。

PM0交付时只执行静态核验。无pytest/Vitest业务测试、真实应用、浏览器工作流、Sheets实网、Windows或macOS安装包运行。PM0当时停在用户验收点；后续用户明确授权PM1，当前记录见第6节。

## 5. 独立审查问题与收口

规格审查先于工程审查。以下记录本阶段发现及要求落实的修正；最终复核结果写入第4节及plan-verification.json。

| 审查 | 具体风险 | 修正落点 |
|---|---|---|
| 规格 | 可选输入无法整体为空、记录键丢类型/来源精度 | 统一InputSnapshot空态、RecordKey类型和安全范围；路径键base64url，全部写入携类型 |
| 规格 | 人工字段编辑被lease一律拦截，动态写失败可能留下新lease | 人工普通字段CAS例外；动态lease/CAS/值/事件/意图同一短事务 |
| 规格 | 继续已接受被当成已开始，TTL失效 | waiting/resume_requested期限有效，真正恢复与到期竞争同一版本 |
| 规格 | 原输入缺字段映射/关联，日期无时区语义丢失 | 冻结别名、映射、recordSlots；DateScalar保留来源精度及offset/null |
| 规格 | End修复/运行事件恢复/源环境与实例混淆 | queryEnd只读，修复不改历史；lastSeen补日志；持久来源与现场分别查询 |
| 规格 | 样例编号与动作不符、FX01目标字段不存在 | 逐条语义重查场景编号，账号表补真实id字段及字段关联 |
| 工程 | 批量状态若逐行提交将出现非预期部分成功 | 固定选择预览与有限原子块，块身份和取消边界 |
| 工程 | impactRevision无针对目标/动作的来源 | 目标级影响预检及同动作/目标/版本提交校验 |
| 工程 | 持久路由缺OperationKind、环境结果递归 | 路由/命令kind对应，环境纯Outcome与查询包装分开 |
| 工程 | 详情/重连返回无限attempt和outputs | 最多50项预览、计数/续读，历史分页最大200项 |
| 工程 | 核心方法签名及错误代码映射不一致 | 引用C02/C05唯一签名，明确domain→HTTP错误和retryable位置 |
| 工程 | 账本把WIP0005写成PM1等待条件 | 改为实际已接入head；未接入从0004开始，集成者汇合 |

复核的结果只适用于文档和静态契约，不能证明后续代码正确，也不能代替用户里程碑验收。主目录在本轮只读核对期间状态条目61→70→37，HEAD f3fe376→b2e95b3，属于其他任务继续工作并提交Studio M1的观察；本任务没有修改、撤销或提交主目录变更。

## 6. PM1 实际交付与验收

| 包 | 实际负责人 | 交付与提交 | 当前结果 |
|---|---|---|---|
| PM1-A | pm1_backend_implementation、pm1_frontend_implementation；主协调集成 | 真实10接口、两表、管理表单、目录；b3b1574/d694093 | 自动与本机运行验证通过 |
| PM1-B | 前端智能体、主协调 | 组件、六页签、导航与草稿；f1411d0/d694093/4006acc | 组件/既有消费者及真实页面回归通过 |
| PM1-C | 后端智能体、主协调 | 幂等查询、归属、CAS、生命周期与QuiesceGate准入 | 后端并发及只读反例通过；不提供归档/删除 |
| 独立审查 | review_project_data_env、milestone_product_coverage、review_project_product | 三份pm1-review文档，先规格后质量，问题修复后复核 | passed |
| 用户PM1验收 | 用户 | 本阶段交付后的验收 | pending |

验收日期2026-09-13，北京时间；机器UTC时间另记。完整命令、退出码、代码版本、日志与限制见 [PM1机器核验](pm1-verification.json)；实际截图见 [本机QA](../../migration/project-management-pm1-qa/README.md)。PM0历史plan-verification.json仍为静态核验，不回写旧结果。

本机自动测试461项后端、439项前端；脚本12项、结构3项。Electron构建HTML使用独立临时工作区，未触及真实业务数据。PM-02完整验证，PM-01/PM-03/OV-01仅本阶段子范围。Windows、macOS x64、发行包及PM2+未执行。核心Run依赖仍由Studio里程碑提供，PM1不把其标为已实现。

## PM2 当前交付包（2026-09-13，进行中）

- integration：隔离工作区、执行卡、pm02迁移/ORM和中断升级恢复；规格/工程复核通过。
- project-data：typed身份/标量63测试，表资料4项真实HTTP与原始操作恢复；已提交。字段/状态目录A2b：完整身份、JSON安全修订、原子默认回填、有界读取、CAS/幂等与历史快照均通过审查，HTTP投影独立复审。
- data-source：流式XLSX解析/输出，7项规格和5项工程问题全部闭合；30项适配器测试通过，已提交。文件IPC与真实导入发布未交付。
- 前端：DataTableDirectory、DataTableFormDialog、校验与13项组件测试已提交a872db2，最终并发会话问题闭合；尚未装配正式数据页。
- A2c：字段更新影响确认d3f76af，18项测试与规格/工程复核通过；真正字段PATCH同事务调用仍需接通。
- A2d：记录create/get/patch/显式状态正在实现；列表筛选、删除影响、批量状态、五页签、文件IPC和Electron数据场景仍待完成。
- PM2-A/B/C尚未整体交付，不把基础包/目录API通过当作DT功能完整验收。PM1真实应用回归另存pm2-foundation-qa并明确scope，原PM0/PM1历史报告保留。
- 主线已正式交付Studio M2 9490924，未来按PM3契约核对接入；此分支仍M1，未宣称项目执行已接通。

### PM2 A2d/A2e 命令包（2026-09-13）

- A2d：pm2_data_rules_impl实现，pm2_rules_spec_review独立规格/工程及类型增量复核；cc86607。
- A2e：pm2_excel_adapter_impl实现，pm2_data_rules_impl独立规格/工程复核；3630e78。
- HTTP：主协调实现，record由pm2_excel_adapter_impl、field由pm2_data_rules_impl独立复核；7a2986f。
- 证据：pm2-records-fields-verification.json；只标记上述命令包通过，DT完整功能验收和未来编号证据不提升。A2f服务端查询与C1b状态组件继续实施。

### A2f/C1b 与后续边界（2026-09-13）

- A2f：pm2_excel_adapter_impl实现，pm2_rules_spec_review独立规格/工程复核，5137c1b；根协调HTTP由pm2_data_rules_impl独立审查，068d9e3。
- C1b：pm2_data_rules_impl实现，主协调规格/工程复核修复，5a90c55；12组件测试。
- A3b：主协调客户端，pm2_data_rules_impl独立复核，beb6a3b；17新API测试。
- 最新完整自动回归698后端/490前端；PM2实际应用未执行，完整DT编号证据不提升。后续字段/记录组件、删除/批状态、受控Excel和五页签继续实施。

### C1c–C1f/A3c–A3d（2026-09-13）

- C1c、C1e组件：pm2_data_rules_impl实现，主协调与pm2_rules_spec_review独立审查；8c25641、737ce3e。record-draft由主协调实现、pm2_rules_spec_review审查，113f0c7。
- C1d：pm2_excel_adapter_impl实现，pm2_rules_spec_review独立两阶段及修复复核；ad8a5d7。
- C1f：主协调实现，pm2_data_rules_impl规格/工程与列宽修复复核；d37cb1c。
- A3c：主协调实现，pm2_rules_spec_review审查；bc3aa24。A3d主协调实现，pm2_excel_adapter_impl审查；dc9ddf2。
- 最终564前端测试及工程检查通过，报告pm2-editors-verification.json。未提升任何完整DT验收条目，未运行PM2真实应用；C2页面、筛选、删除/批状态、Excel文件流程继续实施。

### A2g/C1g/C2a–C2b（2026-09-13）

- A2g迁移由主协调、删除核心由pm2_data_rules_impl、HTTP由主协调/pm2_data_rules_impl完成；pm2_rules_spec_review和pm2_http_review独立规格/工程复核，提交e58877d、2cded8e、32c3395、f4e1d08。
- C1g/C2a组件由pm2_excel_adapter_impl、目录与App由主协调、C2b由pm2_excel_adapter_impl完成；pm2_rules_spec_review独立审查并闭合4个作用域/竞争探针。
- 719后端、606前端，macOS arm64真实目录和既有模块回归证据见pm2-directory-deletions-verification.json。仅DT-01/02/10/12对应子范围登记部分证据，不提升完整验收。
- 下一责任：C2c共享命令准入/编辑器/页面、A2h批状态、B2文件发布；PM2退出条件不变。

## PM2 修订交付检查点（2026-09-13）

- 后台提交 `32e424e`：批量状态、受控检查、隐藏分段导入/替换、快照导出与核验；[后台核验](pm2-backend-verification.json)记录759项全量测试。
- [前端核验](pm2-frontend-verification.json)：803项全量测试，目录新表导入真实Electron通过；重新导入、导出、批量状态组件与选择工具已准备，尚未接入原任务负责的详情页。
- [一万行测量](pm2-data-volume-verification.json)是后台与真实文件实测，不代表大表界面性能。
- [修订包状态](pm2-revised-delivery.json)保持inProgress，静态核验11项首次可用功能及34项首次实施验收编号；不改变完整规格的48/178/18/7编号集合。
- 原编辑任务仍在进行；六个原WIP文件哈希与起点一致，未由本任务提交。全量lint仅在原任务测试文件的未使用参数处失败。
- [页面接入清单](pm2-page-integration-handoff.md)列出依赖、真实消费者和仍需执行的验收。当前不是PM2完整交付，未进入PM3。

本轮独立提交：`32e424e`后台，`a9c0b75`批量选择/状态组件，`747395b`Excel组件与目录真实导入。原任务六处文件未提交；SHA-256保护核对见docs/project-management/implementation/pm2-worktree-isolation.json。等待原编辑任务提交后，按pm2-page-integration-handoff.md继续详情页接入和完整验收。


## PM2 最终执行记录（2026-09-13）

| 项目 | 结果 | 证据与边界 |
|---|---|---|
| P0–P5 | verified | [pm2-revised-delivery.json](pm2-revised-delivery.json)；交付状态passed，用户验收pending |
| 自动回归 | passed | pytest 760；Vitest 833/112文件；ruff；mypy 195文件；desktop type/lint/build；OpenAPI；脚本21；结构3，汇总见[pm2-verification.json](pm2-verification.json) |
| 本地数据真实应用 | passed | macOS arm64源码构建；[run-3HOD1Y](../../migration/project-data-directory-qa/run-3HOD1Y/result.json) |
| Excel、批状态及10000行 | passed | macOS arm64源码构建；[run-Z9O6af](../../migration/pm2-detail-qa/run-Z9O6af/result.json) |
| 原生文件面板 | passed | 真实macOS open取消/选择与save取消；[run-Lr9nj8](../../migration/pm2-native-picker-qa/run-Lr9nj8/result.json) |
| 全局回归 | passed | 构建HTML；[run-4K8zpg](../../migration/project-management-regression-qa/run-4K8zpg/built-html.json) |
| Windows / packaged | notExecuted | 不以macOS源码构建结果替代 |
| 用户PM2验收 | pending | 当前停在用户验收点；不自动进入PM3 |

本记录取代本文件较早的PM2“进行中”结论，但保留过程历史。PM2未实现的Sheets、项目Run/Task/lease、归档生命周期及PM3–PM9能力仍按原计划为空，未伪造成功。

最终实施提交：`7ad1033` 页面及耐久编辑恢复、`79230f0` 实际应用脚本/证据、`d05bbe1` 数据能力状态及生成契约。最后重跑760后端/833前端全量和全部工程检查通过；修订文档另独立提交。

## PM3 当前授权管理范围（2026-09-15）

本节取代本文件早期“PM3 planned”的当前解释，不改写历史检查点。权威报告为 [pm3/verification.json](pm3/verification.json)。

| 包 | 当前结果 | 实际证据与剩余边界 |
|---|---|---|
| PM3-A 自动化管理 | partially_verified | 管理目录、四页签、统一保存、校验、资源摘要、冲突与响应丢失恢复已通过 `pm3/management-runs/run-eSwQYK/result.json`；原包中的 Studio 打开/返回由用户排除，未标通过。 |
| PM3-B 参数型真实启动 | verified | Batch、Task、原始输入快照、queued CoreRun 与 Operation 同一短事务；真实 UI 双任务及 CloakBrowser 输入、点击、读取见 `pm3/qa-runs/uuid-runs-1789458500247/result.json`。 |
| PM3-C 诊断与停止 | verified | 批次/任务目录、日志、输入输出、失败 PNG、普通停止、强停、恢复、重启和隔离均有真实证据；强停只用受控 OS 暂停制造不响应 worker，产品停止链和持久事实保持真实。 |
| 独立审查 | passed | 新增 SSE、恢复身份、终态刷新、强停门槛、证据分页、对象 URL 与禁用状态的 8 项问题全部闭合，无新增 P0/P1。 |
| 用户验收 | pending | 手测入口 `pm3/manual-test.md`。 |

产品与证据提交包括 `d5f27ba`、`bacbccf`、`bdff9dd` 及其前置自动化管理提交。后端全量 1407 passed/8 skipped，前端全量 3224 passed，真实 CloakBrowser 定向 8 passed；Ruff、mypy、OpenAPI、类型、lint、build、脚本、结构、sidecar 和 desktop smoke 通过。Studio smoke 按用户后续范围指令排除。

Windows、其他 CPU 架构、打包应用和用户手动测试未执行。PM4–PM9 没有被提前实现或标绿。
