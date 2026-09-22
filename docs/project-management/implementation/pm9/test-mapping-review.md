# PM9 assertion mapping review

2026-09-22 最新机器统计：251 条，235 有范围断言/16 未定位，198 partial/53 planned/0 verified。SH-02 两种顺序写历史/本地值/来源观察与 SYNC-09 拒绝写后拉取/领取已映射；完整 worker/UI/实网子条件保留。具体以 coverage.json 和 coverage-audit.json 为准。

日期：2026-09-21。状态：confirmed（映射审查），完整产品验收仍未完成。来源：原始设计各需求编号、现有测试函数断言及本轮运行记录。

251 条全部保留原 id、来源和预定文件；新增 `testMapping` 是当前审查结果。初审 200 条定位到实际测试断言，其余 51 条明确记录未定位到直接场景测试。部分有测试的条目也有未覆盖条件。73 条失效预定路径全部补了映射或缺测说明，没有创建空测试文件来满足路径检查。

`checks.scope` 只说明该函数实际断言的子集；`gaps` 说明未证明的条件。`test_missing` 表示本次未定位到完整场景的直接断言，不证明实现不存在。`implementation_missing` 必须有代码边界支持；`production_evidence_missing` 表示替身/领域/契约断言不能替代真实生产链；`external_acceptance_pending` 需要外部授权或机器。一个需求可同时包含多类缺口。

原有 22 条 verified 也存在未闭合条件，已逐项按记录中的缺口退回 partially_verified，原状态保存在 `statusBeforeReview`。不把历史 PM1/PM2 等阶段报告删除，也不把它们当作整个 PM9 的重新验收。未批量提升任何状态。

静态检查：`node --test scripts/verify-pm9-coverage.test.mjs`、`node scripts/verify-pm9-coverage.mjs`。检查 251 个唯一 id、实际文件/函数、分类与缺口；拒绝不存在函数、非法分类、带缺口的 verified。它不理解业务断言，不能据其通过宣称规格已实现。

补齐真实场景后，204 条具有断言映射，47 条仍未定位直接场景断言；当前 188 partial / 63 planned / 0 verified。新增场景只将直接匹配的 planned 改为 partial，未清除尚未覆盖的原始业务组合。

本轮真实场景复用 `scripts/project-runtime-smoke.mjs`，源码与打包应用调用同一入口。交付中保存对应原始 JSON；只有报告明确出现且断言通过的场景才可增加生产证据。真实 worker 的响应丢失/人工竞争使用 `test_project_batch_real_cloakbrowser.py`，明确记录故障注入边界；不将受控时钟称为实时时序性能测试。

服务账号 Sheets 与系统凭据已有 PM6 历史实网证据；本轮映射中的当前生产证据缺口不撤销该事实。OAuth、当前 PM9 打包全链、签名及实机专项仍单独待验收。`releaseAccepted=false`。

补测校正：DATA-E2E-06 仅对串行真实加列/增行/修改/状态断言提升为 partial；多个活跃 Run 的能力缺失另列 implementation_missing，不提升为 verified。FLOW-A02 仍 planned；单槽排队证据不是并发隔离正向证据。


2026-09-21 S1 更新：增加冻结子图、显式 IO、两次调用和父撤销的直接断言，XE-C02 不再是零定位断言；当前 205 条有定位断言、46 条未定位完整直接断言。188 partially_verified / 63 planned / 0 verified 不变；局部断言不替代全部资产和三平台验收。

## 2026-09-21 C1–C3 共享身份逐项复核

DATA-ID-06 新增精确公共键、本地身份和游标分离断言；DATA-SH-13 新增容量 2 的实际 worker 人工继续/取消/进程失联后按 Q 独立业务状态再领；DATA-SH-14 新增不同身份列允许保存和读取但拒绝领取的具体原因。UI 只证明已有共享原因展示及隐私，不替代该故障实际页面链。当前 225 有范围断言 / 26 未定位，191 partial / 60 planned / 0 verified；历史 73 失效预定路径不改写。C4 完整回归、新三平台及当前打包 Google 专项仍待闭合。

2026-09-21 R1：DATA-SCHEMA-01 的无断言/实现缺失已由明确结构查询测试替代，逐项指向范围见 coverage.json；当前 226 有断言 / 25 未定位，状态仍 191 partial / 60 planned / 0 verified。

2026-09-21 R2：DATA-SCHEMA-06 按字段删除具体断言从 planned→partial；DATA-SCHEMA-09 只补第二 Task 依赖保护，不冒充同键异型/新字段写回组合验证。当前 227 有断言/24 未定位，192 partial/59 planned/0 verified。


### 2026-09-21 R5 来源观察（confirmed，局部证据）

普通远端值通过现有 SyncRecordMarkRow.inboundObservation 保存最近每字段观察；与 identity/outbound 证据合并。当前 generation/epoch、字段/映射与记录存在性约束后，只读 HTTP/详情显示来源值、观察时本地值和修订。普通值、状态/关联、内容修订和待发送意图不改；公式保留既有刷新。重复身份不更新观察。无采纳/回滚/云写入口。

59 项后端、18 项组件/客户端检查通过；ruff/mypy(404)、typecheck/lint/OpenAPI/build 通过。DATA-SH-06 移除对应 implementation_missing，仍 partially_verified；251 条、227 有定位断言、24 无定位断言、192 partially_verified/59 planned/0 verified 均不变。早期 PM6 记录对“远端差异可查看”的范围已明确纠正，不否定其既有服务账号实网及系统凭据证据。

C4 35597323657 @21f8bb1e：ARM 已通过；Windows 全量后端 3338 passed/74 skipped、前端 5460 passed/406 files，但真实 worker 13 failed/5 passed/11 deselected，进程失联原因待诊断；Intel 当时仍在运行。以上 C 候选不含 R1/R2/R5；不得算当前候选三平台通过。R3/R4 仍按批准顺序待实施，releaseAccepted=false。

### 2026-09-22 R3 与 C4 更新（confirmed，局部验收）

R3 已冻结原操作 UUID、身份列归属及行证据，单次 Sheets batchUpdate 新列/值/metadata。未知响应仅核验；仅证明未发送的原计划允许重试，UUID 不重生成。原操作发布绑定与成功状态同事务；资料修订变化须重新预览影响后明确核验。复用本工作区已验证系统列不云写；同名未知归属拒绝。UUID 拉取/推值接通，文本视图和 UUID 本地键解析同一公共 lease。未决结构发送阻断其他绑定推值、领取和改绑；值发送未知先阻断结构发送。共享 GoogleAccess 使用标准库 RLock 序列化读计划到发送，并以现有 SQLite 账本保留跨请求/重启的未决围栏。没有第二执行器。

90 项后端相关检查、25 项组件/客户端通过，ruff/mypy（406）、typecheck/lint/OpenAPI/build 通过。覆盖账本 251 条中 228 有定位断言、23 未定位，193 partially_verified / 58 planned / 0 verified。DATA-ID-05 只升级 partial；真实 Google 和当前打包完整应用链仍待验收。

C4 Mac @21f8bb1e 的 ARM/Intel 全部通过；Windows @07619b6d 完整流水线 35605861737 通过：3384 后端（77 平台 skip）、5464 前端（407 文件）、21 真实 worker、源码/包链/安装包和万行写入。万行发生 8 次明确 busy 重试，不构造新的性能门槛。两份源码范围分别保留，R3 不包含在这些 CI 中。此前 C4 “Intel pending/Windows failed”当前状态由本节 supersede；失败日志仍保留历史。R4 接续，完整当前候选矩阵与一次整批复审在 R4 后执行。releaseAccepted=false。

### 2026-09-22 R4 受控增列（confirmed，局部验收）

显式选择普通本地字段、列名并确认远端写入后，原操作冻结目标/epoch/field/revision/owner，在网格末尾单次追加列、表头和归属 metadata。未知响应只核验原列；同名外部列、移动/改名/缺 metadata/非空列不猜测接管。仅确认未发送可原计划重试或取消，取消保留本地字段和值。确认事务兼容扩展 mapping、保持 generation/epoch/记录版本，并将已有新字段值放入现有队列，值发送依赖原列成功。既有冻结 Task 可以继续旧字段修改，不能因此扩大新字段权限；后续同步重验已创建列归属。

HTTP/SQLite/受控 transport 相关回归 113 passed（138.65 秒），组件/客户端 38 passed（5 文件），ruff/mypy（407）、typecheck/lint/OpenAPI/build 通过。另发现通用放弃接口跨项目及结构命令越界，两项 HTTP 反例复现，修复范围限定共享入口的项目归属与内容意图类型。覆盖账本仅 DATA-SCHEMA-07 新增具体断言并改 partial：251 条中 229 有定位断言、22 未定位，194 partially_verified / 57 planned / 0 verified。现有历史统计按日期保留。

R1/R2/R5/R3/R4 与 C1–C4 已有实现和分范围证据；最终整批独立审查、当前完整回归和三平台矩阵接续。真实 Google、当前打包完整 Sheets 链、OAuth、物理安装和签名仍未验收；S4 已存在文件安全覆盖/追加/读取与未批准 M1–M3 仍为实际缺口。releaseAccepted=false。

### 2026-09-22 整批审查修复与映射复核（confirmed，回归进行中）

一次独立审查发现 3 项 Important：UUID 公共 lease 查询未归一类型、未知值核验缺来源归属检查、推送明确发现坏身份后未失效旧领取证据。均已用直接 HTTP/SQLite 反例复现，按共享入口修复；推送与核验复用完整身份观察，可靠身份的普通推值失败不受牵连。新组合断言明确失败意图和本地新值保留、后续拉取正常、真实 Task 领取冻结本地值并继续公共排他。新增 R4 测试也直接证明加列后旧 Patch 推回原 B 列与旧 Task 权限兼容。

DATA-CLAIM-09、DATA-SCHEMA-08 仅新增上述范围映射，未证明的来源读取失败/界面提示、删除本地字段不删远端和生产端到端条件仍保留。当前 251 条中 231 有定位断言、20 未定位，196 partially_verified / 55 planned / 0 verified。完整前端 5469 passed / 409 文件 / 198.85 秒，前端源码之后未改；最终后端和三平台仍在验证。详见 shared-data-final-review.json。releaseAccepted=false。

### 2026-09-22 原生 CI 期间继续补证（confirmed）

新增两项直接业务场景，生产源码未变：DATA-LIFE-09 在真实 HTTP 归档收尾后保留未发送本地值及原意图，新推送 409、远端无写；DATA-SCHEMA-08 先由未决意图阻断本地字段删除，明确放弃后删除本地字段而同名远端列/值保持，状态与关联修订不变。两个相关完整文件 21 passed（17.71 秒），全目录 Ruff 通过。这两项为当前 Mac 本地追加证据，不混入 d75297fb 冻结 CI 的测试总数。

当前 251 条中 232 有定位断言、19 未定位；197 partially_verified / 54 planned / 0 verified。LIFE-09 的活动 worker/保存/未知写联合链、完整打包和实网条件仍保留，releaseAccepted=false。

2026-09-22 最新补证：已有坏业务值 fixture 的 HTTP 状态设置/占用 held 与 reconciling 拒绝/模拟释放后清空通过；17 项共享领取回归。D1 实现后，Sheets/XLSX 普通来源业务格式错误保留原值并派生诊断；身份与 unsafe wire scalar 严格拒绝；必填来源缺失保持缺失；Sheets 先全量预校验再物化，避免坏身份造成半批发布。真实 worker、打包完整链和实网授权仍未验收。当前机器统计 251/235 有断言/16 未定位，198 partial/53 planned/0 verified；前文 197/54、233/18 为阶段性手工统计，本节 supersede。未改变任何条目状态。当前补跑固定 0d7524d9，后补的状态场景单独保留本机范围。

### 2026-09-22 D1 review修复与三平台候选（confirmed）

D1 独立审查发现的三个重要问题已 RED→GREEN：Excel 身份字段业务格式错误不再降级为文本身份；Excel/Sheets 必填来源缺失不写入 values，由当前字段快照派生 REQUIRED_FIELD_MISSING；Sheets 先全量预校验身份和 unsafe wire scalar，再写入任何记录，晚到坏身份不会留下半批物化。D1 相关定向后端 138 passed、2 warnings；RecordFieldsView/RecordDetailPage 11 passed；Ruff 全目录、mypy 407、OpenAPI、typecheck 通过。UI 诊断为字段列表后的聚合面板，仍能区分格式问题与读取失败，记作 Minor 表达差异。

候选 ae347de9f5fc1922efa7c4af99c0e606e6bde26a 的 Actions 35677887974 在 Windows x64、macOS Intel、Apple Silicon 全部通过：各平台后端 3443/3453 passed（平台 skip 保留）、前端 5470 passed、21 个既有真实 worker 场景通过；同提交源码/打包链、五路万行写入和 1000 条/分钟合成日志报告已保存为 ci-d1-final-*.json。这证明 CI 平台链，不等于物理安装、签名、公证或真实 Google/OAuth 验收；native probe/worker probe job 被跳过。

当前台账仍为 251 条、235 条有明确范围断言、16 条未定位，198 partially_verified、53 planned、0 verified。D1 专门坏业务值 worker 筛选未命中，仍未宣称；S4 已存在文件覆盖/追加/读取、M1–M3、真实 Google/OAuth、完整打包 Sheets 链和三平台实机安装/签名仍是实际或外部条件缺口。releaseAccepted=false，草稿 PR 不合并、不发布。
