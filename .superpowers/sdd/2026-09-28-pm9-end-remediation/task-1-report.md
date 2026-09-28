# PM9 R3 End 实施阶段交接

- 日期：2026-09-28。
- 历史阶段状态：BLOCKED、未提交；以下原始交接事实保留。2026-09-28 新 Run 已完成有界收尾，最终结论见末节。
- 初始业务基线：`faf8fc21`。期间主控有独立 QA/文档提交；不得用整个工作区或基线至 HEAD 的所有差异冒充本任务差异。
- 范围：获批的生产 End 纵向切片；没有修改人工重启语义，没有创建第二执行器，没有修改进程归属/清理文件。
- 置信：真实浏览器正向结果高；边界完整性与最终交付状态尚未验证。

## 停止原因与续接规则

上下文压缩后按 AGENTS 发起新的完整 AOCI 读取。误将 `aoci_rules` 与第一块输出合并到默认 10000-token 的 functions 调用，输出共 10213 tokens，被 Host 截断。已停止该认知链，没有使用 cursor 补读或旁路补答，没有修改配置/索引，也没有维护 AOCI。

主控明确要求：本上下文只写阶段交接后停止；新的实施上下文在自身 Run 单独读取合同和每个 8000-token 块（设置足够输出预算），再继续源码工作。不重试本次截断链、不接管另一任务的索引状态。本报告不携带 Whole-Index 正文或语义。

停止后仅核对既有临时验证日志及证据路径以准确交接，没有继续改业务代码。该核对发现先前压缩摘要对 typecheck 的成功推测错误：实际有两个 TS2741，见下。

## 已实现、尚待最终审查的行为

1. 新增 `project_end` 领域配置、目录/编辑器入口、配置组件与生产 executor，复用既有 worker 私有能力 RPC。
2. 宿主基于冻结计划的 End 节点、ACK 后的 nodeVisit、Task/Run/generation、Task 持有的 lease/cursor 验证目标，保存确定性请求键、完整请求与 End 账本；在 worker 退出之前把 Run 置为 finishing。
3. dispatcher 在确认 worker/browser 清理后才调用 End 收尾，在收尾结束前保留 Task 资源；控制锁协调取消，线程文件 IO 使用 shield 并排空后再决策。清理结果未知保持 reconciling/租约，不能继续环境发布。
4. 环境发布与关联事务复核 workerAuthority（代次、finishing 状态、实例归属/使用代次、源占用、目标 lease/cursor），不单信 worker 的 RecordRef/replaceAllowed。
5. 默认选择冻结授权内可写输入；额外目标必须属于当前 Task 有效写租约；query-only 没有写权。关闭后复用原环境 save/association 账本。
6. 持久 Task 详情返回 End 阶段、原业务结果、完整结果或错误，TaskEndPanel 展示。没有将原业务失败改写成成功。
7. 恢复读取已提交 End/save 事实，不重放网页，不复活终态 Run；已发布但未关联识别 saved_unlinked。恢复磁盘证明与错误细节仍需补齐（下列待办）。

## 本任务文件清单（当前均未提交）

以下以仓库根为前缀。新增文件标注 NEW。必须逐项显式 stage；其他 dirty/untracked 文件属于他人或既有现场。

后端，前缀 `apps/backend/`：

- `src/autoflow/domain/workflows/project_end.py` NEW
- `src/autoflow/application/workflows/executors/project_end.py` NEW
- `src/autoflow/application/project_runs/end.py` NEW
- `src/autoflow/domain/workflows/project_data.py`
- `src/autoflow/domain/workflows/catalog.py`
- `src/autoflow/domain/workflows/scope.py`
- `src/autoflow/domain/workflows/run_validation.py`
- `src/autoflow/domain/environments/rules.py`
- `src/autoflow/application/workflows/executors/production.py`
- `src/autoflow/application/workflows/core_runtime.py`
- `src/autoflow/application/workflows/coordinator.py`
- `src/autoflow/application/project_data/capabilities.py`
- `src/autoflow/application/workflows/dispatcher.py`
- `src/autoflow/application/environments/retention.py`
- `src/autoflow/application/environments/service.py`
- `src/autoflow/infrastructure/database/environments.py`
- `src/autoflow/bootstrap/workflows.py`
- `src/autoflow/bootstrap/app.py`
- `src/autoflow/application/project_runs/queries.py`
- `src/autoflow/adapters/http/project_run_schemas.py`
- `tests/integration/test_project_end_worker.py` NEW
- `tests/integration/test_project_end_real_browser.py` NEW

前端，前缀 `apps/desktop/src/renderer/`：

- `domains/workflows/types/workflow.ts`
- `domains/workflows/lib/moduleCatalog.ts`
- `domains/workflows/editor-store.ts`
- `domains/workflows/components/ModuleSidebar.tsx`
- `domains/workflows/components/ConfigPanel.tsx`
- `domains/workflows/components/config-panels/ProjectEndConfig.tsx` NEW
- `domains/workflows/components/config-panels/ProjectEndConfig.test.tsx` NEW
- `domains/environments/components/TaskEndPanel.tsx`
- `domains/project-runs/pages/TaskDetailPage.tsx`
- `shared/api/generated.ts`

另含本报告。尚未写本任务 `.ai/sessions/` 记录，尚未迁入验证日志至仓库；下一实施者应补齐。

## 已执行验证与实际结果

下列日志在停止后直接核对尾部。测试子集和结果是已执行事实；由于压缩后未保留全部 shell 原文，不能将下面的路径/子集描述假称完整历史命令。最后必须在报告补写真正重新执行的精确命令与退出码。

| 日志 | 已执行范围/命令事实 | 结果 |
| --- | --- | --- |
| `/tmp/pm9-end-tests-initial.log` | pytest 初始 End、workflow_dispatch、环境契约 | 43 passed，13.60s |
| `/tmp/pm9-end-expanded.log` | pytest End 扩展边界 | 11 passed，5.69s |
| `/tmp/pm9-end-regression.log` | pytest End、workflow_dispatch、project_environment_finalization、环境契约 | 75 passed，23.35s；1 条 Starlette 弃用 warning |
| `/tmp/pm9-end-control.log` | pytest `tests/integration/test_project_end_worker.py` | 13 passed，6.84s |
| `/tmp/pm9-end-real.log` | `AUTOFLOW_TEST_CLOAKBROWSER` 启用的 `tests/integration/test_project_end_real_browser.py` | 1 passed，10.01s |
| `/tmp/pm9-end-frontend-tests.log` | Vitest 新 ProjectEndConfig + environments/project-runs 相关目录 | 30 files / 190 tests passed，15.03s |
| `/tmp/pm9-end-openapi.log` | `npm run openapi:generate` | 成功生成；未作最终契约一致性检查 |
| `/tmp/pm9-end-mypy.log` | mypy 6 个相关源码文件 | Success: no issues found in 6 source files；不是全部修改文件 |
| `/tmp/pm9-end-ruff.log` | 相关文件 ruff --fix | 6 errors，5 fixed，1 remaining；未过 |
| `/tmp/pm9-end-module-tests.log` | `vitest run src/renderer/domains/workflows/tests/module-scope.test.ts src/renderer/domains/workflows/tests/required-field-protocol.test.ts src/renderer/domains/workflows/lib/__tests__/helpers/addNodeDefaults.test.ts`（npm workspace 包装） | 21 tests：18 过、3 失败 |
| `/tmp/pm9-end-typecheck.log` | `npm run typecheck` → workspace `tsc --noEmit` | **失败**，新组件测试缺少必需 label（第11、18行 TS2741） |

模块测试失败是新增 End 后未更新计数基线：module count 217→218；addNodeDefaults branchCount 163→164、moduleTypeCount 186→187。required-field-protocol 测试通过不意味着 End 已接入生成源；该项仍待补。

ruff 剩余为 `test_competing_end` 附近未使用 factory，需核实后改为 `_factory`。不要用 unsafe fix 批量改他人文件。

未跑整个 pytest，主控负责全量。主控旧快照全量混用新 worker 源码，只是诊断，不是本实现最终验证。尚未完成前端 lint/build、全部变更 Python lint/types、最终 OpenAPI 检查及相关迁移契约检查。

## 红绿与真实运行证据

### 已观察到的开发红绿

无浏览器且不保留的 End 新测试先失败于 `_closed_outcome` 不能处理 instance None，修复后又失败于 accepted→completed 不被允许，修正相应语义后通过。首轮真实浏览器测试因测试 payload 遗漏 headless 导致 worker prelaunch 失败；补正确 fixture 后通过，没有放宽生产协议或清理要求。完整首轮红日志未单独保存，不能假称已归档红绿证据。下一实施者可根据保留工具历史补原文；不要制造“历史失败”。

### 真实正向链

成功证据绝对路径：

`/tmp/autoflow-pm9-end.1Tqx12/test_real_login_retained_and_r0/pm9-end-real-evidence.json`

相同工作区实际路径在 JSON 中为 `/private/tmp/autoflow-pm9-end.1Tqx12/test_real_login_retained_and_r0`。安装内核：

`/Users/zhangtiancheng/Library/Application Support/@autoflow/desktop/data/kernels/chromium-145.0.7632.109.2/Chromium.app/Contents/MacOS/Chromium`

这是专用临时 SQLite、真实本地 HTTP login/Set-Cookie、真实 production worker、真实浏览器、环境目录保存/发布与后续恢复。测试资源 fixture 负责提供浏览器 launch payload，未使用完整 Electron UI。它没有预填 cookie 或以假返回替代外部成功。

- 首 Task `8f35fe26-acd7-4d8b-9653-93655b6a2ec8` / Run `2ab1c0b1-203e-43c5-af12-d5318313cb4b`：真实 project_data 读写/状态动作、登录、End，succeeded；End completed；保存环境 `846dcba7-6c07-53f7-ae2f-35581f08fd0a` generation 1，关联两张表的两个目标。
- 第二 Task `3b0e93e0-d9a4-42a5-823e-31cec75f8e2f` / Run `60d62f88-77b4-4f70-b6d0-f8d02a071acf`：从该环境启动，访问 `/status` 并读取页面 signed-in；服务器记录 `/status` signedIn=true；End 不保留 completed，Run succeeded。
- JSON `verified: true`，两个不同 Task/Run；不是单实例内同一页面自证。

其余 `/tmp/autoflow-pm9-end.{tIVOo6,8Bvm1N,S3xS0Q,7zshtm}/.../pm9-end-real-evidence.json` 都只有空 runs，是前述失败尝试，不能作为通过证据。

最新 13 个边界测试涵盖：无浏览器 End、保存关联幂等、迟到 linkRevision 冲突 saved_unlinked、stale generation/visit/跨项目/query-only 拒绝、stage 后撤代次阻断发布、并发同请求与变更请求、恢复不重放/不复活终态、真实 worker 无浏览器跳过后继节点、保存线程屏障期间取消排空且不提前释放、发布后关联前失败恢复 saved_unlinked。仍缺下节所列边界。

后续 pytest 一律使用专属 `--basetemp="$(mktemp -d /tmp/autoflow-pm9-end.XXXXXX)"`，避免默认 pytest 保留代际清理主控证据。真实测试的完整环境变量和 shell 原文需要新上下文读取测试声明后记录，不在这里猜造。

## 必须完成的自审/实现与检查

1. `ProjectRunEnd._accept`：静态 config.recordTargets 必须与 worker 传参一致；只有动态表达式允许解析成受租约约束的 refs。当前 host 已按 lease/cursor 限权，但尚未约束静态冻结目标一致性。
2. generation/attempt 等 int 检查需拒绝 bool（Python True == 1）；复核协议 shape。
3. End name 当前限制已改36，但空白名称前置验证尚未与环境 metadata 验证对齐。
4. `_published_save` 恢复目前核对 DB current_digest/candidate、确定性环境 ID/generation 和关联版本；还需核对实际磁盘 generation 存在且 digest 一致，且将 save 账本 phase 与返回的恢复结论一致地持久化。不能仅凭 DB 指针宣称保存完整。
5. retention `_bind` 返回 saved_unlinked 时需包含完整 ProjectError code/message/details；复核关联时撤权/代次变化导致错误也保留已保存环境信息，不能吞掉部分成功。版本冲突外的缺失目标/替换拒绝同样要完整呈现。
6. finishing End 已接纳时 cancel 分支当前直接回当前状态；复核调用者 expected revision/generation 失配是否应先报冲突。
7. 补 cancel-before-End、force_stop、browser cleanup unknown/失败的真实边界回归，证明不发布/不释放租约；主控正在单独修复已确认 birth 的退出中进程重判缺陷，不要修改其文件或放宽未知活候选检查。
8. 补显式排除输入、动态创建/写入目标的选择边界。复核 End service 的 live-run public guard 对现有测试 reader/mock 的兼容（`.terminal`）。
9. 修改 `scripts/export-studio-required-fields.py` 的 NATIVE_SCHEMAS，加入 project_end，再通过原生成器更新 backend required_fields/frontend module-required-fields。先看生成脚本输出清单，防止覆盖他人报告。当前生成器尚未修改。
10. 修复新测试 label TS2741、ruff unused factory、上述三个计数基线；format 只限本任务文件。尚未修改计数 baseline。
11. 完成有界相关回归、全变更 lint/types、OpenAPI 一致性、必要构建，保留完整命令/退出码。不要重复跑整个 pytest，主控负责最后全仓。
12. 把通过与失败验证证据按独立子目录归档（可用 `docs/qa/2026-09-28-remediation/pm9-end/`，当前未创建）、写 `.ai/sessions/` 阶段记录，更新本报告为最终结论。
13. 最终仔细自审；仅本任务文件显式提交；不 push。向主控报告提交及限制，主控安排独立 review。

## 他人工作与隔离

不要 stage `.gitignore`、AGENTS、`.aoci/`、`aoci*.txt`、`.gitattributes`、已有项目结构/迁移报告、历史 evidence、父任务 QA 台账或其他未列文件。当前工作区还有大量这些未提交资产。父任务已新增独立提交 `963dbe88`、`78b903fc`；它们不是本实现提交。

主控已指出严格 cleanup 的已知退出竞态，并有独立真实故障注入证据 `docs/qa/2026-09-28-remediation/process-exit-fault-probe.py/json`。本实现不处理该根因。无论根因是否修复，End 必须维持“确认失败/未知就不发布且保留恢复责任”的边界。

当前提交：无。当前下一步：由新的实施上下文完成自己的独立认知交付后，按以上清单续接，不能把本报告标成 DONE。


## 2026-09-28 新 Run 最终收尾（DONE，有界交付）

置信：高（以下已执行的源码与本机测试范围）；未知（明确未执行的平台、物理故障与完整PM9能力）。未将人工持久恢复或PM9全部标为完成。

已逐项处理原13项待办：

1. Host对静态 `recordTargets` 与冻结节点精确匹配；动态值仅允许有界完整变量引用，worker按已有JSON解析约定解析列表，host仍复验当前Task租约／cursor／项目身份。补正常动态选择、排除全部输入、实际项目创建记录取得新lease后选择、查询无写权与跨项目拒绝。
2. generation和attempt用严格整数检查拒bool；identity仍绑定确定性commandId和已ACK节点访问。
3. 名称按去首尾空白后的1–36码点提前验证，与环境metadata一致。
4. 恢复复核DB、磁盘目录、标记摘要与实际按版本计算的digest；缺目录／同长度篡改返回明确 `ENVIRONMENT_INTEGRITY_FAILED`，保留已发布环境身份，End/save账本一致记失败。`save_as`恢复代次固定1，update按原预期代次+1；不凭现有DB指针假定磁盘完整。
5. 关联阶段任何明确ProjectError保留 `saved_unlinked`、保存ID／代次与完整code/message/status/details，原错误同时持久到save/End结果；版本冲突、缺失、替换拒绝和发布后撤权均有覆盖。
6. 已接纳End的cancel仍由End持有控制权，但先检查调用者revision/generation；取消在End前则撤销准入、不生成End意图。同步保存线程shield并排空测试通过。
7. force_stop/reconcile的清理未知保留Run与租约；清理确认后只能读已提交阶段，不能发布新环境。真实正向与内部回执故障注入严格分账，物理进程未知仍未验证。
8. 新增/已写动态目标、输入排除、原业务失败保持原结果均有覆盖；公共live-run End guard采用缺失terminal属性时fail-closed的兼容读取。
9. required-fields生成源加入原生End，生成后端／前端metadata和source-coverage。历史capabilities清单保持原字节，生成器将显式原生schema并入当前范围；当前213冻结＋5原生共218。候选生成补无历史验收条目的原生节点默认值，不把新节点套用历史成功。
10. 新组件测试label、Ruff unused、模块数与默认分支基线修正；新增3个后端文件通过strict检查。配置额外记录输入补关联label，教学中说明真实End语义。
11. 验证：100相关后端回归、124 End/metadata、41环境回归、最后33 End/store、212前端、12脚本；重叠集合不相加。全变更22源码mypy、Ruff、ESLint、typecheck、OpenAPI与桌面build过。strict增量门禁1041历史债务／0新增。精确cwd/argv/env/exit在QA的`*.command.json`。
12. 日志与真实JSON归档 `docs/qa/2026-09-28-remediation/pm9-end/`，同目录README解释红绿和证据边界；本Run会话见 `.ai/sessions/2026-09-28-pm9-production-end.md`。
13. 显式文件清单提交；不push、不碰AOCI维护、不改process清理helper，不接管人工恢复。后续由主控独立审查、全仓回归与后续切片验收。

当前新增磁盘版本规则兼容历史64位摘要，不重签或迁移历史目录。旧无版本摘要仍仅证明路径/大小，不能证明同长度内容未变。这是明确保留的历史验证上限。

完整证据与命令索引：`docs/qa/2026-09-28-remediation/pm9-end/README.md`。本次提交含既有实施者尚未提交的授权End实现与本Run修复；中间主控QA提交不计入本实现。

## 2026-09-28 独立审查修复 round 1/5（FIX_BASE b16e1715）

状态：DONE（两项 Important 有界修复，待主控复审）。置信：高，限以下实际验证范围。原阶段记录保留。

- P1：新增 Context 内 `ProjectEndState`，仅宿主接纳项目 End 后设置，子工作流、自定义模块、画布子流程共享同一对象。既有调度器在并行入口、节点领取、调试等待后、事件绑定锁内、执行器调用前、下一循环及 done 后继检查；嵌套返回后阻止父流程后继。普通 `stop_workflow` 仍是原有 Context 局部原语，没有改成项目 End。
- 四类实际 Runtime/注册表/嵌套实现测试在修复前均失败、修复后通过；3 类普通局部 stop 保持父流程继续。替身仅返回宿主接纳结果，不计真实业务验收。初版测试误用事件名的 7 个失败单列保留，校正后的有效红证据为 `fix1-runtime-red-corrected`（4 fail/3 pass）。
- P2：Task detail 从现有 End→save 外键读取真实 `saveOperationId` 和保存账本 `associationPhase`，投影全部原目标的存在性、当前 linkRevision/currentEnvironmentId；不新增迁移。持久结果页面可在重开后读取最新目标，明确确认当前版本及替换授权，再调用已有 repair。修复后重新读取详情并失效 Task 缓存。历史 End outcome/error 和 Run 失败事实不覆盖；另外展示“关联已修复”。
- 新增真实 SQLite 用例：生产 End service 接纳/保存后因版本冲突 saved_unlinked，重新创建查询/服务从账本取得 save 身份，按全部最新目标修复后关联 completed，原 End saved_unlinked 和 Run failed 不变。此用例的浏览器目录/closer 是明确的内部夹具；不冒称真实浏览器冲突验收。React 用例验证卸载重开、先读新版本 7、未确认不能写、提交 save ID 而非 End ID、成功刷新。
- 实际 SQLite + 生产源码 worker + 安装 CloakBrowser：linear、loop、workflow、module、canvas 各 1 条真实成功链（每条包含两次 Run 的保存/登录复用）。四类控制流均断言 `/before-end` 只访问 1 次、`/forbidden-inner`/`/forbidden-parent` 没有请求且没有对应节点事件。证据 `fix1-real-{linear,loop,workflow,module,canvas}.json` 含精确 Task/Run/工作区/HTTP 记录。
- 首轮真实夹具因重复 edge ID 与未过滤 node_id=None 失败；第二轮 4 pass/1 fail，canvas 使用历史 subflow_header 被现有项目准入拒绝。改为正式 group/isSubflow 与几何成员后单独 canvas 1 pass，未修改或绕过准入。计数按 4+1 唯一场景，不把失败轮累计成通过。
- 真实测试新增 `AUTOFLOW_TEST_PROJECT_WORKER` 环境选择入口：按现有测试惯例配置 manager._command 为指定可执行文件加 `--project-workflow-worker`。本轮全部真实证据使用源码 worker，未设置此变量；冻结构建与冻结 worker 复验由主控执行。

验证（精确 cwd/argv/env/exitCode 见 QA `fix1-*.command.json`）：100 后端聚焦通过（End、调度、嵌套协议、环境与store）；最后事件绑定锁闸门加入后20 runtime测试通过；前端 TaskEndPanel/TaskDetail 14通过，最后状态标题微调后5通过；6源码mypy、后端cwd Ruff、ESLint、TypeScript、OpenAPI一致性通过；strict最终1041/1041、新增0。集合重叠不相加。保留全部红日志，包括错误root cwd的Ruff/strict命令与正确cwd复验；strict一次检查跨越源码两行追加产生符号位置差异，停止修改后的稳定复验通过，未改baseline。

未验证边界：实际关闭回执丢失/物理未知进程清理、本轮Electron人工修复操作、冻结worker、Windows/Intel；未扩大为全部PM9或人工跨重启恢复。AOCI完成本Run新传输与一次校验，治理仍dirty/stale，按隔离要求不维护资产。没有修改主控process probe的一行WIP、进程清理helper或其他任务资产；不push。

## 2026-09-28 独立审查修复 round 2/5（FIX_BASE 1fdda1c8）

状态：DONE（新增P2未知修复结果处理，待主控复审）；已验证范围置信高。保留round1结果与边界。

- 生产DurableEndResult复用 `createOperationCommand` 原键提交/查询。发送前在localStorage持久保存修复键（workspace/project/task/End身份分区，不含连接instance以便重连恢复）；存储失败不发POST。连接client/instance/workspace/task变化重建页面资格，旧异步结果不更新新页面或删除旧键。只有确定终态或明确未接纳才清除pending；未知/仍在进行只允许“核对原修复操作”，不允许重新确认后用新键发送。键恢复是既有操作对话框模式，无新框架、无自动重发网页/修复。
- 已确认终态后刷新持久End/Task缓存；旧preview不作为下一次授权。跨工作区不读取/查询旧键；同工作区重开或换连接保留原键供只读核验。修复历史Run语义不变。
- 类型检查暴露必要的公共查询契约缺口：`ProjectOperationView` 未包含现有 `repairEndAssociation`、environment定位器及EnvironmentOutcome结果，真实FastAPI by-key响应会失败。仅补这三个既有形状与Outcome.error字段，重新生成类型；没有新操作、权限、运行状态或所有权改变。主控已确认该补齐属本轮范围。
- 红证据：`fix2-red` 3新增组件失败/5旧项通过；`fix2-typecheck` 拒绝repair kind；`fix2-http-red` 是真实SQLite已保存修复操作被FastAPI响应模型拒绝。绿：`fix2-final` 29项（TaskEndPanel、operation-command、TaskDetail）；`fix2-http-final` 1项真实SQLite + TestClient/ASGI路由校验项目/key/operationId及完整结果；`fix2-contracts` 6项；TypeScript、OpenAPI、ESLint、后端cwd Ruff和2模型mypy通过。所有精确命令/退出码归档同QA `fix2-*`，集合不累计。
- 新组件回归覆盖：服务器提交后丢响应立即原键查回；提交与查询双未知后按钮禁新发；卸载重开/instance重连原键只查（共仅1次repair POST）；旧连接迟到成功不清新页面pending；跨workspace隔离；存储失败阻止POST。传输由组件替身明确模拟，不冒称物理网络断连验收；后端单例验证实际SQLite事实和FastAPI序列化，未经过真实TCP断连。
- 无需重跑原100项后端或真实浏览器；本轮未构建冻结包、未做Electron手工、Windows/Intel或物理故障测试。未改AOCI、主控QA脚本、清理helper、其他WIP；不push。
