# 2026-09-20 PM8-F 交付会话记录

- 状态：confirmed
- 来源：本会话在 `autoflow-project-management-pm8` 工作区的核对、修复与运行结果
- 里程碑：PM8（完整生命周期、跨重启核验与资源保护）

## 交付范围

归档/恢复/永久删除的真实管理入口、跨重启核验与未知保持未知、退出与切换工作区阻断、全局资源引用保护；端到端脚本 `scripts/qa-project-management-pm8.mjs` 与隔离执行器 `apps/backend/tests/qa/pm8_sidecar.py`。

## 本次会话实际做了什么

1. 重跑阶段全量检查：后端 pytest 3132 passed / 16 skipped、Ruff、mypy（387 源文件）、前端 404 文件 / 5443 项、OpenAPI 检查、typecheck、lint、build、test:scripts 84、test:structure 4，全部通过。
2. 修掉一个真实产品缺陷：`ProjectOperationView.resource` 缺 `task` 分支，工作流数据能力的 `project_operations.resource` 行导致 `GET /projects/{id}/operations` 500，归档影响预检在"有工作流写入的项目"上直接打不开。修复 + 反例测试 + 重新生成 OpenAPI 客户端。
3. 修掉第二个真实产品缺陷：设置页 `BLOCKER_LABELS` 缺 11 个真实阻断码，退出/切换工作区显示成泛化文案。
4. 修掉两处 QA 证据缺陷：`07-resource-referenced` 原先停在项目目录、看不到引用清单（改为真实界面删除路径并断言点名项目与自动化）；`10-deleted-project-kept-neighbour` 原先停在 0 条空视图（改为「全部状态」目录，一屏同时证明 A 消失、B 保留）。
5. 权威端到端运行 `20260919200955`：`passed`、16 检查点、11 截图；源码摘要 `d92004ce…` 与提交 `5e19f190` 的工作树一致。
6. 逐画面视觉审查（自审）写入 `pm8/visual-review.md`：11 张全部满足强制结构要求，最低 85 分；三处与画板的结构差异按规格依据登记为可接受偏离。
7. 覆盖表只升级有直接 PM8 证据的条目，其余 `complete_acceptance=PM8` 条目保持原状态并在 `pm8_note` 里列出原因。

## 未闭合 / 未执行

- 归档对话框的清理残留重试分支只有组件测试证据，端到端未制造真实残留。
- 独立规格/工程审查因智能体投递故障未执行，改为主协调自审并如实登记。
- 真实执行核心、真实 CloakBrowser、Studio demo、Windows、其他架构、打包应用、用户手测、双工作区切换未执行。

## 交付后补齐（提交 2021c74a）

合并到 `codex/architecture-baseline` 后自查完成度时发现上面的第一条登记有误：后端删除代理连接/代理组时**早已**返回 `RESOURCE_REFERENCED` + `details.references`（`tests/contract/test_project_resource_references.py` 8 项通过），失败的是界面渲染——断开 ProxyPanel 只显示裸服务端消息，删除代理组连错误条都不出现。

- 补齐：错误条渲染共享的 `ResourceReferenceList`，被引用阻断时隐藏「重新加载」；代理组删除命中 `RESOURCE_REFERENCED` 时给出明确文案。
- 证据：`ProxyManagementPage.test.tsx` 两项新反例（真实 `ApiClient` + fetch 桩，先红后绿），全量前端 404 文件 / 5445 项、typecheck、lint、build 通过。
- 真实端到端按同一脚本复跑：`qa-runs/20260919202620`（`passed`、16 检查点、11 截图、源码摘要 `3502e24d…`）；与上一轮截图逐像素比对为 4 张完全一致、7 张差异 ≤0.20% 且仅动态值，评分依据见 `visual-review.md` 第 5 节。
- 仍未闭合：代理路径没有真实截图（隔离环境建立不了真实 ProxyPanel 连接），证据边界记为组件测试 + 后端契约测试。

## 环境前置条件

PM8 工作区出厂时缺少 `reference/WebRPA`、`RedroidManager`、`redroid-script`、`vphone-aio`、`vphone-cli` 只读符号链接，已从主项目补齐并写入 `.git/info/exclude`（不入库）。缺少它们时 `recording-source-parity.test.ts` 会失败。

## 本轮补齐（提交 44a3fe7a + 文档提交）

上一节遗留的「清理残留端到端未制造真实残留」已闭合。

- 定位：E2E-8 首次尝试断言「批次启动必须为项目预约一个真实隔离工作副本」并失败（运行 `20260920010249`）。根因是隔离执行器 `apps/backend/tests/qa/pm4_v1_runner.py` 静态调用 `ProjectBatchScheduler.claim_data_task`，不像生产 `_claim_data_task` 那样传 `environments`，所以 PM4/PM7/PM8 的 QA 运行从不产生任务环境实例。
- 取舍：没有去改这条共享执行器路径。改它会让未终结的 `active` 实例落进 `BUSY_INSTANCE_STATES`，把归档/删除真实阻断，并影响已闭合的 PM4/PM7 证据；这属于 QA 夹具保真度，不是 E2E-8 要验的产品行为。
- 做法：QA 侧车新增 `leak-work-copy` 故障注入，按真实环境仓库（`EnvironmentInstance` + `reserve_instance_in_session` + `EnvironmentStore.prepare_instance`）登记一个「浏览器已关闭（state=closed）、工作副本仍在磁盘」的遗留实例，模拟进程在 `close` 与清理之间中断；残留失败、残留上报、重试收敛全部走产品代码。
- 结果：权威端到端 `20260920010843`（`passed`、18 检查点、13 截图、源码摘要 `3502e24d…`）。新增画面 `12-delete-cleanup-residue`（86 分）与 `13-cleanup-residue-retry`（87 分）；与前一轮 11 张逐像素比对为 4 张完全一致、6 张差异 ≤0.23%、1 张 1.686% 且差异只在过期通知条区域。
- 后续如需在 PM8 之上扩展：QA 侧车不启动浏览器这一条边界不变；真实执行核心接入后，本用例应改为在真实浏览器任务中制造中断再复验。
