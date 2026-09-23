# PM9 原子记录组实施计划 G1–G3

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 显式有限记录组在一个节点内本地原子更新，冲突全组不写，响应丢失按原命令恢复。

**Architecture:** 复用既有 project_data/RPC、冻结权限、SQLite短事务和操作账本；从单记录仓库提取接收session的核心，两种入口共享规则。新组入口一次提交，旧入口行为与返回值不变。

**Tech Stack:** Python/SQLAlchemy/SQLite、既有共享Runtime、React/TypeScript；不增加依赖。

**Spec:** `docs/superpowers/specs/2026-09-24-pm9-atomic-record-group.md`

日期：2026-09-24。状态：proposed，等待规格和计划确认后按 G1→G2→G3 在现有 PM9 工作区原地执行。本轮只审计与设计，未写业务代码。

## 全局约束

- records建议1–100条；同项目，精确typed RecordRef与全部版本；重复逻辑/物理身份拒绝。该预算需随方案确认。
- 表/字段/来源身份、人工冲突、lease所有权和作用域校验全部复用，不降级。只有本地数据库组原子；出站远端写仍逐意图。
- 组ID覆盖全组，结果原序，无变化项不推进版本；DataChangeRow.sequence不重复。
- 不增加跨节点事务、第二执行器、新表、重试调度器或跨进程人工恢复；新字段动态权限仍属FR。
- 已有CI保持原运行，新候选稳定后只触发一次all矩阵。草稿PR不合并，releaseAccepted=false。

## Review Focus

- 第一条已准备lease/意图，末条失败或数据库flush异常：全组回滚而先前节点提交保留（G1）。
- 两个不同本地引用指向同一个物理Sheets身份：拒绝组，不隐式合并（G1）。
- 同nodeId在不同子流程调用/并行分支拥有不同权限：仅当前冻结声明有效（G2）。
- 组提交后人工改值、响应丢失：原命令返回原组结果而不覆盖后来值（G1/G3）。
- 输入100/101条、重复grant/字段、跨表结果乱序：有界拒绝/输出原序（G1/G2）。

## G1 同事务组命令与原写入规则复用

**Files:**
- Modify `apps/backend/src/autoflow/domain/project_data/capabilities.py`：新增组命令和严格条目校验、摘要。
- Modify `apps/backend/src/autoflow/application/project_data/capabilities.py`：薄委托。
- Modify `apps/backend/src/autoflow/infrastructure/database/project_capabilities.py`：session内单条核心、组事务、变更序号。
- Test `apps/backend/tests/unit/test_project_data_capabilities.py`, `apps/backend/tests/integration/test_project_capability_fencing.py`；复用现有 capability_context。

**Consumes:** 既有 UpdateProjectRecordCommand规则、TaskCapabilityScope、resolve_record_lease、版本游标和操作账本。
**Produces:** UpdateProjectRecordsCommand(operation_id,execution_generation,records) 和 update_records(scope,command)→({records:[snapshot...]},replayed)。单写接口原样。

- [ ] 写RED：两条其中末条busy/版本旧/值非法，全组无值、游标、变更、意图和新增lease；另有前序写必须保留。
- [ ] 运行 `uv run --directory apps/backend pytest -q tests/unit/test_project_data_capabilities.py tests/integration/test_project_capability_fencing.py`，保留真实失败。
- [ ] 实现严格组条目（范围/非空/typed引用/重复）；将现有单写核心移为内部session函数，无自commit。单写继续使用原结果和idempotency操作种类。
- [ ] 新组入口一次事务与一次操作，先检查组身份重复，再在同一事务内逐项校验并暂存写入，末项通过才提交；物理SourceLeaseKey重复拒绝。所有异常让既有session回滚，不为某项吞错。
- [ ] 修改_change支持显式sequence且单写默认1；组结果原序，所有实际变化记录的意图与账本同commit。
- [ ] 加成功/无变化、同项目跨表、100/101、重复typed/物理身份、flush故障、原ID重放/异摘要、人工后改再重放检查。
- [ ] 跑上述回归到GREEN；Ruff/mypy按现有命令检查。同步报告/.ai并提交G1，此时不开放未装配组节点。


### G1 明确类型、事务接线和首个RED

组对象内部可复用已验证的单条命令，避免第二份Patch校验；`records: tuple[UpdateProjectRecordCommand, ...]`中的operation_id/execution_generation必须都与组一致，不为子项创建操作账本。wire条目仍只有recordRef/changes/expectedContentRevision。组摘要按有序wire条目生成。

首个单元RED可放入现有单元文件，直到组命令出现前ImportError/AttributeError是真实失败；重复引用不能静默覆盖：

```python
def test_group_rejects_duplicate_record_refs():
    from uuid import uuid4
    def uid():
        return str(uuid4())
    ref = RecordRef(uid(), uid(), uid(), RecordKey('text', 'A'))
    key, field = uid(), uid()
    patch = UpdateProjectRecordCommand(key, 1, ref, {field: 'changed'}, 1)
    with pytest.raises(ProjectError):
        capability_domain.UpdateProjectRecordsCommand(key, 1, (patch, patch))
```

仓库新内部函数签名：`_update_record_in_session(session, scope, task, run, command) -> tuple[dict, dict, DataTableRow]`，返回before/after/table，包含现有单写校验、lease/游标和值暂存，不创建operation/变更/出站意图，也不commit。单写与组写入口在返回后仍在同一事务入账/入队。组入口核心顺序如下（作用域、幂等和重复物理身份预检先完成）：

```python
updates = [self._update_record_in_session(session, scope, task, run, patch)
           for patch in command.records]
result = {'records': [after for before, after, table in updates]}
operation = _completed_operation(scope, command.operation_id, 'updateRecords',
                                 command.request_digest, result)
session.add(_operation_row(operation))
session.flush()
for sequence, (before, after, table) in enumerate(updates, 1):
    if before != after:
        session.add(_change(operation, before, after, sequence=sequence))
self._commit(session)
```

上述循环的每个变化项同时按现有单写差异算法调用enqueue_intent；不可在这个片段之后异步补账。`_change(..., sequence=1)`保留单写默认值。需要完整回滚测试分别在第二项校验、操作flush、意图flush注入异常。相同操作的每条变更序号唯一，未变化项允许留下序号空隙。

## G2 冻结授权、父RPC与Studio组入口

**Files:**
- Modify `apps/backend/src/autoflow/application/project_runs/coordinator.py`：group tableGrants→既有manifest。
- Modify `apps/backend/src/autoflow/application/project_runs/worker_capabilities.py`：组解析与每表冻结权限交集。
- Modify `apps/backend/src/autoflow/domain/workflows/run_validation.py`：受支持操作和声明形态。
- Inspect `apps/backend/src/autoflow/providers/browser/project_workflow_worker.py`：复用嵌套表达式与既有commandId，不新建执行器。
- Modify `apps/desktop/src/renderer/domains/workflows/components/config-panels/ProjectDataConfig.tsx`。
- Test `apps/backend/tests/integration/test_project_capability_rpc.py`, `apps/desktop/src/renderer/domains/workflows/tests/project-data-config.test.tsx`，沿用运行准备契约测试。
- 如公开operation种类/结果schema需要表示组，先更新 `apps/backend/src/autoflow/adapters/http/project_schemas.py`，再 `npm run openapi:generate`，禁止手维护generated.ts。

**Consumes:** G1组命令与原序结果、既有冻结manifest和表字段API。
**Produces:** 新节点operation=updateRecords、多tableGrants冻结；其每条grant operations=[updateRecord]，父RPC逐项权限不扩大。

- [ ] RED：合法两表组准备/运行；错代次、单复数混用、重复grant、伪造group条目/字段拒绝且无副作用。
- [ ] RED：受限子节点不能用父节点更宽字段；同名node的另一次调用/兄弟分支不能授权当前组。
- [ ] 在现有manifest收集和RPC中加入组契约，运行代次/节点访问/commandId仍全量校验；不只放白名单。
- [ ] 为操作选择和多表字段选择完成组件测试；随后装配JSON参数/返回示例及保存重开。旧单节点配置回归。
- [ ] 运行RPC/运行准备相关后端测试、前端组件测试、typecheck/lint；若契约变化运行OpenAPI生成/一致性检查。检查无额外网络调用/授权兜底。
- [ ] 同步规格落地状态/.ai并提交G2。


### G2 接线与具体检查命令

在已有worker注册表增加唯一一项，不能另外建组执行器：

```python
'updateRecords': ('update_records', commands.UpdateProjectRecordsCommand),
```

RPC的records条目逐项严格白名单解析，沿用RecordRef/RecordKey构造；每项内部命令注入同一已核验commandId和generation。manifest收集中的底层授权映射为：

```python
required = {'updateRecords': 'updateRecord',
            'previewFieldChange': 'modifyField',
            'previewFieldDeletion': 'deleteField'}.get(operation, operation)
```

组节点对子流程table_grants做现有交集时，以(tableId,datasetGeneration)查当前冻结tableGrants行，再交集operations/fieldIds/readPurposes；找不到行则不给该表授权。不得把所有行字段先取并集再套每张表。组件操作标签新增 `updateRecords: '原子更新记录组'`，参数模板为 `{ records: [{recordRef, changes: {}, expectedContentRevision}] }`，结果示例使用 `updated_group.records`。

运行：`uv run --directory apps/backend pytest -q tests/integration/test_project_capability_rpc.py tests/integration/test_project_run_start.py`；`npm test -- src/renderer/domains/workflows/tests/project-data-config.test.tsx`；随后 `npm run typecheck`、`npm run lint`、`npm run openapi:check`。

## G3 真实worker、响应恢复和发行候选证据

**Files:**
- Extend `apps/backend/tests/integration/test_project_sheets_real_cloakbrowser.py`：shared_tables/start_real等已有真实worker夹具。
- Extend `apps/backend/tests/integration/test_project_batch_real_cloakbrowser.py`：原命令丢响应、人工值与后续节点失败。
- Extend `scripts/project-runtime-smoke.mjs`：公开HTTP/打包业务组合，复用现有脚本。
- Update coverage.json、pm9/verification.json、group-write-audit.json 与 `.ai/knowledge/`。

**Consumes:** G2完整生产入口；**Produces:** 明确候选源码的测试/打包/三平台报告，不引用旧绿为新能力验收。

- [ ] 两真实worker先各提交一条、再反向组写：同时可见LEASE_BUSY、无半组修改、无新增lease泄漏、停止释放，前写保留。
- [ ] 真worker组成功→人工屏障→后续节点失败仍保留组写；原命令响应丢失→查询/重放无重复推进；人工新值不被旧预期覆盖。
- [ ] 实际跨表混合既有lease/查询新增lease成功，返回原序；共享Sheets同物理身份双本地引用拒绝，远端未被同步写入。
- [ ] 对新场景运行源码和打包脚本；补Studio实际组入口保存/重开/执行，不只测试组件。Google transport替身明确标记，实际授权缺失保留实网验收。
- [ ] 候选稳定后完整后端、前端必要回归、类型/lint/OpenAPI/build、必要完整打包；认证恢复后一次GitHub Actions all，检查三平台日志/产物。
- [ ] 按每条验收实际证据更新DATA-WRITE-12及相关映射，无证据不升级verified。提交推送并更新草稿PR，列明实网/实机/签名余项。


### G3 可核对的不变量

沿用真实worker测试的人工屏障安排在组写前后，失败时逐字段核对记录值/版本，并直接检查SQLite游标/lease/操作/意图，而不只看Task状态。最终后端命令为 `uv run --directory apps/backend pytest -q`；真实worker采用现有AUTOFLOW_TEST_CLOAKBROWSER路径和CI固定版本，不加载用户浏览器资料。脚本继续使用既有打包路径和隔离工作区。

```python
assert first_after == first_before
assert second_after == second_before
assert leases_after == leases_before
assert cursors_after == cursors_before
assert pending_after == pending_before
```

上述对象均从当前两条记录、当前Task的lease/cursor和两个表的sync_operations在调用前后取得，不用mock返回值。对于“前节点已提交”，before在那个提交之后采集。成功恢复测试保存首次整组result；重放后严格比较原result，另读取当前记录证明人工后改仍保留。

## 自审裁定

原始§7.3给出组原子性目标，但现有已实现接口没有组表达；这是新增契约设计而非删除校验即可修复。G1/G2会涉及账本结果与权限形态，所以等本规格和计划确认；其它已授权验证不受阻。条件“允许已配置有限重试”不作为已存在重试引擎的证据，此计划不借此扩建调度器。
