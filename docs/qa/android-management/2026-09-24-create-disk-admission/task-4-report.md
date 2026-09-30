# Task 4 后端与契约实施报告

- 日期：2026-09-24
- 状态：后端及生成契约已完成；前端四入口由父任务另行委派，最终真实批量重试 QA 与全仓门禁由父任务执行。
- 范围：单创建、模板批量/源配置复制、保留数据恢复、备份恢复的磁盘确认贯通；共享 Lima VM 磁盘准入、两次恢复写入边界、幂等与取消；OpenAPI 生成类型。未改数据库形状或迁移。
- 代码提交：`ef0af03f` `Gate Android creation and restore writes on VM disk confirmation`（仅 16 个自有产品、测试与生成类型文件）。

## 实现与自审

四个 HTTP 请求模型加入严格布尔 `allowUnknownDiskEstimate`，默认 `false`。应用层规范化缺省/显式 `false` 为旧摘要结构，不修改调用方 dict；`true` 写入创建配置、设备操作、冻结批次和备份恢复的持久 payload/digest。复制源快照和备份配置里的旧确认不会继承到新请求。

共享 Mac provider 在归属与固定镜像校验后、首次 Docker volume/create 前复用 `require_vm_disk_space`；无重建的现有生命周期分支不会探测。备份清单、摘要、归属及目标意图校验后，在真正解包前再次调用同一磁盘准入。探测失败、零空间、未知占用保留具体错误码；通用错误文案改为“尚未开始写入”。预检取消记 `failed`，实际写入取消仍保持待核实；备份目标已经创建后的恢复预检取消仍保持父操作 `needs_verification`。

自审发现批量首次磁盘预检失败后，旧重试路径可能把缺失容器误报成功。已修复：只有同工作区、同目标、首次创建 `failed` 且持久结果码可证明属于预检拒绝/取消时，才以新操作编号和 `retryOf` 重试；该操作继承冻结批次的确认。provider 重试时重新核对容器和卷，任一资源存在即 `ANDROID_DATA_MISSING`、零写入。普通丢失资源不能空白重建。

## RED → GREEN 证据

1. `uv run pytest tests/unit/test_android_management.py -k 'new_container_disk_rejection or confirmed_creation_checks_disk or false_confirmation_keeps' -q`：初次 RED 为 8 failed；其中 6 个拒绝测试的 mutation fake 返回值不合法，随后已纠正，**不把这 6 个当有效 RED**。`confirmed_creation_checks_disk` 明确失败于预期先检查、实际直接 volume/create，false 重放明确冲突。
2. `uv run pytest tests/unit/test_android_management.py -k 'disk_confirmation_contract or new_container_disk_rejection or confirmed_creation_checks_disk or false_confirmation_keeps' -q --tb=short`：RED 7 failed；其中四模型缺字段为有效 RED，另 3 个 create 参数测试当时把当前 request 当确认权威，已修正为 creationConfig 权威后再验。GREEN 12 passed。
3. `uv run pytest tests/integration/test_android_images_templates.py -k batch_confirmation -q --tb=short`：RED `KeyError: allowUnknownDiskEstimate`，批次确认未写入创建配置；GREEN 1 passed。
4. `uv run pytest tests/integration/test_android_backup_restore.py -k 'stream or does_not_inherit_source' -q --tb=short`：RED 2 failed，解包前无磁盘重检、来源确认被动继承；GREEN 2 passed。
5. `uv run pytest tests/unit/test_android_batch_safety.py -k retry_after_disk -q --tb=short`：RED `succeeded != creating`，缺失容器被误报成功。收紧后的 `retry_after_proven`/`missing_container_after_prior` 再次 RED 3 failed（缺 `retryOf` 且会重建历史成功设备）；GREEN 3 passed。
6. `uv run pytest tests/unit/test_android_management.py -k empty_create_retry -q --tb=short`：RED `DID NOT RAISE AndroidError`，已有卷仍可重建；GREEN 通过。
7. `uv run pytest tests/unit/test_android_management.py -k known_disk_rejection_keeps -q --tb=short`：RED `recovery_required != idle`，明确零写入错误不可安全重试；GREEN 通过。
8. 事件驱动取消：`uv run pytest tests/unit/test_android_management.py -k 'cancelled_create_disk_preflight or false_confirmation_keeps' -q --tb=short` 为 2 passed；`uv run pytest tests/integration/test_android_backup_restore.py -k cancelled_restore_disk_recheck -q --tb=short` 为 1 passed。

## 最终验证

- `uv run pytest tests/unit/test_android_*.py tests/integration/test_android_*.py tests/contract/test_android_*.py -q --tb=short`：**515 passed，2 warnings，31.91s**。warnings 为已有 Starlette `BlockingPortal` deprecation 与重复 ZIP 条目 fixture。
- 受影响批量与创建定向：`uv run pytest tests/unit/test_android_management.py tests/unit/test_android_batch_safety.py tests/integration/test_android_images_templates.py -q --tb=short`：**43 passed**。
- 修改源码及测试的 `uv run ruff check …`：`All checks passed!`。
- 修改后端模块的 `uv run python -m compileall -q …`：退出码 0。
- `npm run openapi:generate` 与 `npm run openapi:check`：退出码 0，`generated.ts` 仅新增四模型的确认字段。
- 父任务首轮真实 QA 已报告单创建、批量、复制、保留卷、备份恢复、源/备份不变及零残留通过；该轮后新增了批量重试安全修复。最终重试 QA 与全后端门禁由父任务并行执行，结果以后续父任务报告为准。

仅提交本任务后端产品、后端测试与 `generated.ts`。前端代理负责四入口和前端验证；父任务负责 QA、`.ai`、计划和最终集成。
