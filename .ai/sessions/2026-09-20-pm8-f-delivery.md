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
