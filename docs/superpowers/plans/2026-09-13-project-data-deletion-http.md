# PM2 A2g3 删除 HTTP 接入执行卡

日期：2026-09-13；状态：confirmed；依据：`docs/project-management/implementation/api-contracts.md` 3.3 与 A2g2 已验证服务。

## 范围

新增删除 router/schema/contract tests；扩展现有 mutation-impact discriminated union、Operation DTO 与 bootstrap。复用 DataDeletionService、session factory、既有 HTTP 鉴权和全局 QuiesceGate。不修改 ORM、迁移、生成客户端或页面。

## 契约

- mutation-impact 接受 updateField、deleteStatus、deleteRecord。删除 target 必须是完整 status locator 或 RecordRef，projectId 必须等于路径 project。
- DELETE status body 精确包含 expectedStatusRevision、expectedTableRevision、impactRevision；DELETE record body精确包含 datasetGeneration、recordKeyType、三类 expected revision、impactRevision。都要求 canonical Idempotency-Key。
- 成功与同 key 同 body replay 均返回 202 OperationAccepted；当前实现同步完成，operation.status=succeeded，结果是冻结 StatusDeleteResult 或 RecordDeleteResult。
- Operation kind 仅增加已实现 deleteRecord；mutateStatus 结果 union增加 delete action。错误沿用统一 401/404/409/410/412/422/423；写请求经过全局 gate。

## TDD 与验证

先以真实临时数据库和 TestClient 写失败 contract：状态/记录 preview→delete→operation 查询→replay；引用 blocker；墓碑目录/查询拒绝；scope、UUID、payload、key、impact、CAS、生命周期、quiesce、auth。实现后运行该文件与既有 project-data HTTP 16 项回归，再跑定向 Ruff/mypy和diff check。OpenAPI生成由主协调统一执行。
