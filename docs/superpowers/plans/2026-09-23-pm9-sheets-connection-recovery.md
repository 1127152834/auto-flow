# PM9 Sheets Connection Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 保留可靠本地数据身份地恢复连接，并提供不绕过旧未知写的失权处置。

**Architecture:** 扩展现有 connection/SyncOperationRow、影响预览和事务重验；凭据发布复用系统凭据库。旧目标证据保持不可改写，平台所有权证明集中在适配器，无新执行器。

**Tech Stack:** 现有 FastAPI、SQLAlchemy/SQLite、Google provider、Electron、React/生成 OpenAPI 客户端。

**Spec:** `docs/superpowers/specs/2026-09-23-pm9-sheets-connection-recovery.md`

日期：2026-09-23。状态：proposed；本计划不代表 L1–L3 已获批准。L0 三处共享安全围栏修复独立交付。

## Global Constraints

- 保留 datasetGeneration/RecordRef/业务值和状态/关联修订，除非用户明确执行原有更换来源流程。
- 不以显示名或未经验证的 token 内容证明主体；不以 PID 或超时证明发送者退出。
- 旧 SyncOperation 的原目标、原 epoch、原字段快照不可被新授权重解释。
- 不增加第二执行器、不自动重跑旧 Task、不增加云端行变更或跨进程人工恢复。
- 分切片提交和审查；保持草稿 PR 和 releaseAccepted=false。

## Review Focus

1. 旧连接缺主体证据，不能按同名账户自动迁移（L1）。
2. 凭据库写成功但数据库 CAS/响应失败，旧指针和原命令恢复必须正确（L1）。
3. 同名异主体、同 Spreadsheet 不同 Sheet/身份列或已变列归属，不能悄悄保留错误身份（L2）。
4. 已接收的旧发送迟到、旧 owner 不明、跨项目第二绑定，不能以隔离标记解除物理冲突（L3）。
5. 归档/重启后的后台唤醒不能重新发送 quarantined 操作（L3）。

## L1 原位重授权垂直切片

Files: `apps/backend/src/autoflow/providers/data/google_auth.py`、`application/project_sync/connections.py`、`infrastructure/database/project_sync_models.py` / `project_sync.py`、现有 Alembic migrations、`adapters/http/project_sheets.py` / `project_sheets_schemas.py`；`apps/desktop/src/main/google-desktop.ts`、`shared/google-sheets.ts`、`renderer/domains/project-data/sheets-api.ts` / `components/SheetsConnectionPanel.tsx`。测试复用 `test_project_sheets_recovery.py`、`google-desktop.test.ts`、`SheetsSync.test.tsx`。

Interfaces: `reauthorize(project_id, connection_id, key, payload) -> OperationAccepted`；payload 与规格 L1 一致。生成客户端暴露 connectionRevision，不向 Renderer 暴露凭据。

- [ ] 写主体相同/不同/旧锚点缺失、秘密不泄漏、凭据库写失败与 CAS 失败的反例。关键联合断言：
  ```python
  assert after_records == before_records
  assert after_table['datasetGeneration'] == before_table['datasetGeneration']
  assert old_operation['target'] == target_before
  assert transport.changes() == writes_before
  assert replayed['operationId'] == accepted['operationId']
  ```
- [ ] 核实 Google 官方主体验证协议；在现有 provider/host 授权交接中增加服务端主体证据。拒绝未验证主体，不自行引入 JWT 库或第二 token client；若现有依赖不足，先提交依赖取舍再实现。
- [ ] 迁移连接修订/主体证据/凭据代次；按“新 key 暂存→验证/CAS 发布→旧 key 清理”实现，原键查询走已有操作日志。
- [ ] 接 HTTP/OpenAPI 及生成类型，再实现连接面板“重新授权→显示影响→确认→查询原操作”；只允许相同主体，旧身份未知指向 L2。
- [ ] 运行 `uv run --directory apps/backend pytest tests/integration/test_project_sheets_recovery.py -q`、对应 UI/host 测试及 lint/typecheck/OpenAPI；补 `.ai`、范围映射并提交。Google 实网条件单独列待验收。

## L2 同物理目标的明确主体替换

Files: L1 连接模块、`application/project_sync/bindings.py`、`infrastructure/database/project_sync_impacts.py` / `project_sync.py`、`components/SheetsBindingWizard.tsx` / `SheetsConnectionPanel.tsx`、原 recovery/identity 测试。

Interfaces: `replace_authorization(project_id, connection_id, key, payload) -> OperationAccepted`；比 L1 多 `confirmDifferentPrincipal: true`。主体证据来自 L1，目标/身份验证复用既有 inspection/identity rules。

- [ ] 写同显示名异主体、同表保留记录、错误 Sheet/身份列、旧预览与旧未知写拒绝用例；每个反例断言无凭据指针发布、无新 generation、无网络写。
- [ ] 将“保留身份的授权替换”与既有“更换来源的新 generation”分支明确区分；仅在物理目标和身份重新验证通过后 CAS 推进 bindingEpoch，旧操作不修改。
- [ ] 新未发计划必须由明确用户命令生成，并引用原意图；反例 `assert old_intent['bindingEpoch'] == old_epoch`、`assert remote_values == before_remote_values` 固定授权替换自身不写云端。
- [ ] 完成 UI 影响确认与原键恢复；运行 recovery/identity/claims 相关集成、组件测试和类型检查，更新文档及提交。

## L3 发送停止证明与隔离处置

Files: `application/project_sync/access.py` / `outbound.py` / `runs.py`、`infrastructure/database/project_sync_models.py` / `project_sync_sends.py` / `project_sync_impacts.py`、现有进程所有权适配器和 Workspace 生命周期协调、`project_sheets.py` / schemas、`SheetsConnectionPanel.tsx` / 同步操作详情组件。测试复用 recovery、lifecycle、现有原生进程边界和桌面脚本。

Interfaces: `isolate_source(project_id, table_id, key, payload) -> OperationAccepted`；payload 与规格 L3 一致。增加受约束持久 `sendDisposition` 与 sender instance identity；unknown 保持 unknown，隔离状态不重用 failed/confirmed。

- [ ] 先写原生所有权探针：当前网络调用未退出、进程身份无法证明、PID 复用、重启遗留 owner 不明均返回 blocker。不能完成证明的平台不开放隔离。复用现有适配器，不让业务层判断 OS。
- [ ] 写 HTTP/SQLite 交错测试：发送已登记但尚未返回时 isolate 必须拒绝；调用结束且所有权退出证据完整后允许；晚响应只更新原历史事实，不能解除新来源身份围栏。
- [ ] 在发送前持久化 owner 证据，隔离提交时重验 sender/目标/epoch/修订。未发意图取消，已发 unknown 的 disposition 设 quarantined；使用同一事务保留本地覆盖值和审计事实。
- [ ] 所有发送、改绑、结构初始化、跨项目共享入口共同检查原物理冲突；重启也从原账本重建。验收断言：
  ```python
  assert old['status'] == 'unknown'
  assert old['sendDisposition'] == 'quarantined'
  assert new_write_same_target.status_code == 409
  assert after_local_values == before_local_values
  assert background_writes_after_restart == 0
  ```
- [ ] 接影响预览/隔离 UI，显示“结果未知，已停止自动重试”与原目标；无证据时展示 blocker。完成归档/不同来源管理的正向链，禁止同目标快捷清空冲突。
- [ ] 每个失败点检查版本、原键、队列和无副作用；候选稳定后完整后端/UI/脚本、现有三平台矩阵及真实 worker/桌面链。仅通过的明确子范围更新 partial，外部真实授权/实机/签名保持待验收。

## 自查与交付

规格 L1/L2/L3 各有独立切片；五项 Review Focus 均有对应反例。实施按 L1→L2→L3，在本工作区原分支提交推送并更新草稿 PR。批准前只保留设计和 L0 安全修复，不启动这些新增能力。
