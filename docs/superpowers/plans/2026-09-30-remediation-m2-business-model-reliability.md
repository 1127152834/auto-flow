# M2 业务模型与可靠性 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> 日期：2026-09-30；r2；proposed任务级计划，未实施。M1退出后各切片细化为步骤级，完成审查后继续执行；不预写未来生产实现。

**Goal:** 先闭合主处理单位与未知结果保护，再交付签名/写回/预览契约，独立交付触发扩展。
**Architecture:** 复用RecordRef、Task终态事务和执行器注册表；参考输入不消费，未知结果门禁在所有领取模式之前；前端消费生成契约。
**Tech Stack:** Python/SQLAlchemy/Alembic/FastAPI、React、已有worker与SQLite。
**Spec:** [M2规格](../specs/2026-09-30-remediation-m2-business-model-reliability.md)。R2/AC2编号以此为准。

## Global Constraints

- M2A/B是M3前置；M2C独立交付，不阻塞可靠性/数据闭环。
- 主输入processingInputId显式冻结；完整作用域含typed key、代次和Sheets namespace，不按裸record_key去重。
- needs_review在全部模式下阻断；worker失联不能无条件infrastructure；外部动作前的持久状态是M3不得批量丢失的状态事件。
- 旧重试配置只转换为候选，显式启用才生效；旧失败后继续策略保留兼容模式。
- 新迁移rm2_接实际唯一head；生产实现前备份与迁移重放；旧解析保留到M6数据门禁通过。

## Review Focus

1. 主行订单共享固定账号，账号不能被一次成功消费（Task1/4，AC2-11）。
2. 提交后失联、成功提交后读取失败、cycle重领、取消后恢复均不重复外部操作（Task2/3/4，AC2-02/04）。
3. 同表重导入/类型不同的同值key/Sheets改绑不得继承错误台账（Task1，AC2-12）。
4. 终态投影重放、人工resolve竞争、退避期间重启（Task3/4，AC2-13/14）。
5. 预览新记录随后查询、临时引用被真实模式消费、旧文档跨版本导入（Task7/9，AC2-08/18）。

## M2A：可靠性

### Task 1: 主处理输入、完整身份与台账仓储

**Files:** `domain/project_runs/ledger.py`、`domain/project_automations/rules.py`、`infrastructure/database/record_ledger.py`、`migrations/versions/rm2_record_ledger.py`（均位于apps/backend/src/autoflow，迁移在infrastructure/database下）；测试 `apps/backend/tests/unit/test_record_ledger_rules.py`、`tests/integration/test_record_ledger_repository.py`。
**Interfaces:** LedgerScope(automation_id,processing_input_id,完整RecordRef,identity_namespace)；LedgerEntry含累计attempts/processing_cycle/cycle_attempts及revision；get/upsert/reset/skip/resolve仅接受完整scope；批次unit membership保留历史统计；模式的eligible查询不返回裸字符串集合。
**验证：**AC2-11/12/13；单输入迁移自动选主输入，多输入歧义列报告并禁止新批；旧未知运行门禁迁移。参考输入继续原租约检查，不建立第二套锁。

### Task 2: 失败分类、整Task重放边界与节点策略

**Files:** `domain/workflows/error_policy.py`、`application/workflows/runtime.py`、`application/workflows/executors/base.py`及网页执行器、`providers/browser/project_graph.py`、`infrastructure/process/project_workflow_worker.py`、`application/workflows/dispatcher.py`；前端workflows的errorPolicy及配置面板。
**Interfaces:** ModuleResult可选error_code/error_category；ErrorPolicy候选迁移与显式启用；持久副作用边界随执行代次、runId、attempt记录，状态ACK后才发出动作；整Task/goto安全判定读取该事实，不仅看最后失败节点。
**验证：**AC2-02/04/05/15；启动前失败与动作中EOF使用相同code也得到不同分类；未知无法用retryOn:any、cycle或新Task绕过；前后端迁移样例一致。

### Task 3: 终态同事务投影、业务结果和人工核实

**Files:** `application/project_runs/events.py`及实际终态投影用例（实施前追踪全调用链）、`domain/workflows/project_end.py`、End执行器、台账HTTP adapter及最小待核实页面。
**Interfaces:** next_ledger_entry(entry,outcome,budget,backoff,now)；Task终态/账本同事务且原终态去重；resolve的三种决定与理由/修订/幂等键按R2-06；公开错误保留M1诊断。
**验证：**AC2-03/13；重复事件只计一次、事务回滚、崩溃重启、active Task和人工决定竞争；unknown不可用reset或skip→reset清除。先完成Task2分类，不以page临时替代。

### Task 4: 三种领取模式、maxRows与退避唤醒

**Files:** `infrastructure/database/project_claims.py`、`application/project_runs/scheduler.py`、自动化/批次rules、`rm2_automation_claim_mode.py`；RunPolicyEditor和批次详情最小计数/待办。
**Interfaces:** 主处理单位的批次membership；统一安全门禁→退避→模式过滤；返回noMatch与未来eligible的最早时刻分开；重启恢复等待，stop不再领取。参数型无数据任务保持原计数，不写行台账。
**验证：**AC2-01/02/11/14；参考输入重复使用、预算3只尝试3次、maxRows不被重试耗尽、cycle延迟、旧unknown门禁与不同批次统计互不覆盖；连续成功多轮后失败按本轮预算，失败跨批次预算不重置，显式人工reset保留审计。

### Task 5: 熔断、坏行隔离与暂停恢复

**Files:** `domain/project_runs/circuit_breaker.py`、scheduler、project_claims、`rm2_batch_failure_policy.py`、批次接口和页面。
**Interfaces:** legacyAnyFailure/legacyContinue与thresholds显式模式；暂停原因含样本；仅身份可信的坏主行可隔离；模糊Sheets身份保留来源门禁。
**验证：**AC2-05/06/15；旧行为不静默迁为新阈值，业务与unknown不计技术熔断，暂停/继续不清空账本。

### Task 6: 配置schema与M2A退出

**Files:** 执行器注册表的配置schema导出、`bootstrap/executor_schema_export.py`、`scripts/ratchets.mjs`及对应测试。
**Interfaces:** 每个节点的schema与面板键对应；有效选项有行为测试，未知键警告；恢复统一出错控件，删除M1隐藏开关前覆盖全部入口。
**验证：**AC2-01至06、10至15逐项真实测试，G3独立xfail转正；文档/台账状态同步后独立退出。M2A未退出不做性能重构。

## M2B：数据契约

### Task 7: 流程签名、绑定与可重入迁移

**Files:** `domain/workflows/signature.py`、`domain/workflows/validation.py`/`document.py`、`domain/project_automations/rules.py`、`application/workflows/signature_migration.py`、项目worker输入上下文；GET `/api/v1/migrations/signature-report`；最小绑定界面。
**Interfaces:** R2-18至22；bindingId沿用inputId，不丢mode/required/relations/代次；保留旧解析和未决报告。
**验证：**AC2-07/08；两自动化复用流程、改名、敏感值、跳版本、旧文件导入与歧义不中断旧执行。迁移失败不是删除兼容代码的许可。

### Task 8: 自动版本写回与设计期结构

**Files:** `domain/project_data/capabilities.py`、现有application/infrastructure写回路径、前端数据节点最小界面。
**Interfaces:** 自动expectedContentRevision基于冻结值与Task写游标；字段冲突保留原命令恢复，敏感冲突值打码；结构操作预检指向数据页。
**验证：**AC2-16；两次本Task写、他人同字段/不同字段更新、显式旧版本、丢响应重放；不放宽租约与来源身份校验。

### Task 9: 后端预览写入模式（M5试跑前置）

**Files:** `domain/project_runs/rules.py`、批次/运行HTTP schema、coordinator快照、worker私有协议、`application/project_data/capabilities.py`、End保存边界；对应真实HTTP/SQLite/worker集成测试。
**Interfaces:** executionMode=previewWrites/realWrites冻结在原请求；默认预览仅针对试跑入口，普通批次保持realWrites。运行私有覆盖层提供写后读与新记录预览引用，真实能力接口拒绝临时引用。生产台账不消费预览任务，诊断记录与预览数据隔离。End保存预检明确拒绝，浏览器外部动作仍真实。
**验证：**AC2-18；读取/查询均看到覆盖层，真实记录/版本/台账/同步意图/环境不变；改worker请求不能提权；显式realWrites才写入；重启仅核验原预览事实，不自动重跑。API生成后供M5B使用。

### Task 10: 最小输出契约与必有/条件输出

**Files:** 既有执行器注册表、`domain/workflows/references.py`、`providers/browser/project_graph.py`、目录HTTP/export与前端生成类型。
**Interfaces:** 稳定nodeId/outputKey、name/type/sensitive/availability；旧变量别名兼容，新引用不靠可改显示名寻址。使用当前结构化图分析判定所有有效路径均定义的输出；条件输出必须显式判空/默认值，不能用简单可达性。
**验证：**AC2-17；分支汇合、零次循环、错误边、节点重命名。此时不引入表达式函数库或大规模旧节点转换（M6）。

### Task 11: M2B退出与native吞吐基线

AC2-07/08/16至19逐项验收；保留M0受控场景，新增native-batch-v1（真实台账领取+写回），固定数据/故障/硬件/内核/并发至少5次采样。记录commit与分布，作为M3优化前对照；不把M0不同口径当分母。独立退出后M3和M5B可接入。

## M2C：独立扩展

### Task 12: 定时/Webhook

**Files:** `application/workflows/schedules.py`、HTTP调度adapter、`rm2_automation_schedules.py`、自动化调度页签。
**Interfaces:** R2-25至27；定时使用计划时间身份，Webhook要求来源事件ID/幂等键，复用loopback鉴权，不扩公网服务。
**验证：**AC2-09；时区/重启/重叠三策略、密钥错误、同事件重放只启动一次。步骤细化时单独确认。

### Task 13: 网页原语及M2C退出

**Files:** 执行器web_storage/web_intercept或既有web_basic、scope/catalog、前端登记点（沿M1登记清单）。
**验证：**AC2-20真实浏览器Cookie/Storage/拦截，配置schema/副作用/敏感输出一并测试；单独退出不追改已关闭的M2A/B证据。

## 验证命令与证据

步骤级细化后每个Task先RED后GREEN；使用 `uv run --directory apps/backend pytest -q <本任务测试>`、Ruff/mypy、`npm run openapi:check`及对应前端测试。切片退出运行受影响全量、类型/lint/build与真实黄金场景，记录平台边界。所有AC逐条挂实际报告；本文件为计划，不能写入通过数字。
