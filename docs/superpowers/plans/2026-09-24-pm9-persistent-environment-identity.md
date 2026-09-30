# PM9 持久环境身份 I1–I3 Implementation Plan

> For agentic workers: use superpowers:executing-plans task-by-task after approval. 状态：proposed；现有授权允许审计和方案，不把“继续目标”当成本附录确认。

**Goal:** 固定/输入关联环境及人工维护恢复保存时身份，Profile编辑不改变已保存身份。
**Architecture:** 复用环境/实例/保存操作及资源快照，版本化无凭据身份包随内容代次发布；同一组装路径供worker与维护使用，不增加执行器。
**Tech Stack:** Python/FastAPI/SQLAlchemy/Alembic，现有Electron/React及CloakBrowser，Node验收脚本。
**Spec:** docs/superpowers/specs/2026-09-24-pm9-persistent-environment-identity.md。

## Global Constraints

- 原身份包优先；不以当前Profile、Cookie或canvas猜历史身份。
- 旧环境缺少身份时保留目录/代次，启动409 ENVIRONMENT_IDENTITY_UNVERIFIED；不新增默认“采用当前Profile”路径。
- 包含版本/身份/内核/完整无凭据Profile快照；headless和既有明确代理覆盖按规格；P1–P3另案。
- 不引入新执行器、凭据副本、跨进程人工恢复或全Studio接入；没有平台证据不宣称通过。
- 每片代码/契约/UI/测试/文档/.ai一致；最终新候选才做必要全回归与一次all矩阵，不擅自合并发布。

## Review Focus

- 候选文件准备后崩溃、数据库发布后响应丢失：内容与身份同代次，原操作重放不重复保存（I1）。
- 浏览器写入同名身份文件、未知schema或错kernelId：不信任，拒绝发布/恢复且原来源不变（I1）。
- 有Cookie但无可证明身份的旧环境：可查不可静默恢复，不用当前Profile迁移填充（I1）。
- 已准备Task与后来环境g2/当前Profile新seed并存：目录和身份不混代（I2）。
- 任务和维护使用不同启动入口：两条都保持身份，当前Profile换内核不能替代保存内核（I2/I3）。

## I1 身份随内容持久化、旧环境兼容及界面

**Files:** 新建 migrations/versions/pm11_environment_identity.py（实施前复核实际head）；修改 domain/environments/models.py、rules.py，infrastructure/database/environment_models.py、environments.py，filesystem/environment_store.py，application/environments/service.py、retention.py；现有 project_environment_schemas.py及环境详情/来源组件；生成客户端类型。实际路径均位于 apps/backend/src/autoflow 和 apps/desktop/src/renderer/domains/environments。

**Consumes:** 实例权威身份、既有CoreRun冻结资源、保存操作ID/期望代次/摘要。
**Produces:** version1 identity_package；环境/实例内部值和对外非秘密identityStatus/保存内核摘要；缺失身份的可见409及UI解释。

- [ ] 在现有test_environment_persist_restore.py/test_environment_store.py及环境契约测试写RED：保存→Profile改变→身份包不变；两阶段故障重放；同名文件篡改；旧候选不得覆盖g2。
- [ ] 执行定向pytest并保存真实RED；不用仅检查JSON字段存在代替完整不变量。
- [ ] 增加可空持久列并复用实例列；旧库迁移保留null，不批量读取当前Profile。纯校验函数严格检查schema/kernel/ProfileSpec/seed，秘密不入包。
- [ ] 将身份写入纳入候选生成/摘要/发布恢复；数据库内容指针与包同事务。原saveAs/update重放与错误清理继续复用，不另建保存账本。
- [ ] 更新GET详情/来源校验DTO，OpenAPI生成类型，组件显示缺失身份并阻断启动；旧数据仍可查，错误页不隐藏目录/原操作。
- [ ] 覆盖完整可证明save→instance→Run链与缺链反例；只回填能证明的对象，其他留missing。测试额外断言“没有复制当前Profile”。
- [ ] 跑环境契约/规则/保留/迁移及组件检查，Ruff/mypy/typecheck/OpenAPI，文档和.ai记录后提交。

## I2 Task与维护共用身份、绑定同一内容代次

**Files:** application/project_runs/resources.py、coordinator.py、scheduler.py；application/workflows/browser_resources.py；providers/browser/environment_browser.py；现有环境service/仓库选择函数。必要纯快照校验/组装放入domain/environments，不让provider依赖application，也不复制两份字段合并规则。

**Consumes:** I1的版本化已证明包、既有资源策略、权威environmentRef和占用。
**Produces:** 与预约代次一致的CoreRun resource_request和实例身份；保存内核选择；维护与worker一致的Profile组装。

- [ ] RED：固定/输入恢复后当前Profile修改和seed重置不得进入实际资源；当前Profile改内核但保存内核仍在时使用保存内核；保存内核缺失拒绝而不升级。
- [ ] 在Task/预约提交中取同一选定代次和包；参数批次、数据批次两路径均检查，不只修inputEnvironment。既有复验/回滚处理选择变化，无多余Task/lease。
- [ ] 复用ProfileSpec及browser_worker_payload，统一身份快照组装；仅覆盖headless和规格允许的操作字段/显式代理，不把全部当前Profile合并进保存身份。
- [ ] 维护opener与worker使用同一组装规则；新建环境从冻结批次写入实例身份，确保后续saveAs不再丢包。
- [ ] 验证queued后Profile变更、输入环境发布新代次、关联修复、取消/失败回收；明确持久来源最新代次语义，不误改为永远用批次旧代次。
- [ ] 执行资源/环境/调度/维护定向测试和Ruff/mypy，更新证据/.ai并提交。

## I3 真实worker和打包联合验收

**Files:** scripts/project-runtime-smoke.mjs、既有真实浏览器测试；本轮probes/persistent-identity.mjs；coverage.json、pm9报告和.ai。

- [ ] 将探针实际断言并入既有正式harness：保存时原网页UA/locale/timezone和原生seed，公开修改Profile后固定/输入/维护三条路径保持原身份且登录不丢；fresh newFromProfile正向使用新值。
- [ ] 同时验证实例引用代次/内核、独占与零额外Task；保持canvas仅观测，不强求seed变化必然改变canvas。
- [ ] 记录旧库missing的真实UI阻断；旧环境资料不可证明的情况不凭通过数量升级。
- [ ] 定向稳定后完整后端/前端、脚本、类型/lint/OpenAPI/build、当前ARM包；当前候选一次三平台CI，认证未恢复则保留原问题而不重复触发。
- [ ] 报告源码/包/日志SHA及每个场景实际身份；当前探针false必须转为有证据的true后才能移除对应implementation_missing子条件。
- [ ] 更新草稿PR，不合并发布，releaseAccepted=false。

建议命令按实际文件执行：`uv run --directory apps/backend pytest -q tests/unit/test_project_run_resources.py tests/unit/test_project_environment_rules.py tests/contract/test_project_environments.py tests/integration/test_environment_persist_restore.py tests/integration/test_project_data_scheduler.py`；`node --test scripts/*.test.mjs`；`node scripts/verify-pm9-coverage.mjs`。探针完整命令和原始数据见 persistent-identity-audit.json。计划中的新测试在实施时写入现有文件，勿把预定文件名当作已覆盖。
