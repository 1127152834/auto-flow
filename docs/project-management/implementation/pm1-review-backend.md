# PM1 后端独立规格与工程质量审查

- 状态：confirmed review result；规格通过，工程质量通过，当前审查范围内无未关闭的 P1/P2。
- 记录时间：2026-09-13 04:24:35 +08:00（2026-09-12 20:24:35 UTC）。这是整理记录时读取的时间，不冒充每次测试的运行时刻。
- 工作区：`autoflow-project-management-pm1`，分支 `codex/project-management-pm1`。
- 基线：`dbb01f5759f2effd34b70918579cfb9f8bcca67e`；审查对象是该基线之上的未提交后端变更。整理记录前再次读取了下述修复位置。此结论不是提交、合并或完整 PM1 验收声明。
- 审查方式：独立读取实现和已批准契约，先做规格审查，再做工程质量审查；直接运行现有测试及临时反例，不以实现者的通过声明作为证据。除本记录外，审查者未修改源文件或测试文件。
- 依据：[PM1 执行计划](../../superpowers/plans/2026-09-13-project-management-pm1.md)、[API 契约及 PM1 已批准勘误](api-contracts.md)、[共享领域契约](contracts.md)、仓库 `AGENTS.md` 与相关 `.ai` 决策。工作方法遵循 Superpowers requesting-code-review、verification-before-completion，并用 ponytail 原则限制修复范围。

## 1. 审查范围

后端领域与应用：`apps/backend/src/autoflow/domain/projects/`、`application/projects/`。

持久化与装配：`infrastructure/database/projects.py`、`infrastructure/database/models.py`、`infrastructure/database/migrations/versions/pm01_projects.py`、`bootstrap/app.py`。

HTTP：`adapters/http/projects.py`、`project_schemas.py`、统一 `errors.py` 的本次集成。

测试：`tests/unit/test_project_service.py`、`tests/contract/test_projects.py`、`tests/integration/test_project_repository.py`、`test_project_migration.py`，以及既有合流迁移测试的本次修改。路径均以 `apps/backend/` 为根。

规格核对覆盖十个正式 API、六键能力状态与未知计数、默认资源省略和显式完整对象、Unicode 长度与名称唯一性、CAS/no-op、幂等与结果快照、查询归属、排序分页与字面搜索、open 与生命周期、认证与 QuiesceGate、既有数据库迁移。

工程质量核对覆盖当前调用链的职责、数据库事务与回滚、SQL 条件及参数边界、输入校验、仓库现有类型检查和静态检查。没有要求添加未来阶段的框架、能力或端点。

## 2. 规格发现与关闭证据

以下六项首次审查均为 P2，置信度高；现均已关闭。首次审查时现有测试通过，缺陷由独立反例揭示。本文不声称观察过实现者的“先写失败测试、再修复”过程。

### SPEC-01：Operation.resource 使用了请求字典

- 原问题：创建项目后按幂等 key 查询操作，`resource` 实际为 `{scope:"workspace",request:{name,...}}`，缺少资源类型和项目身份。
- 契约：`api-contracts.md` 的 `Operation.resource: ResourceLocator`、项目资源分支 `{type:'project',projectId}`，以及实际 OperationKind 的资源分支约束。
- 修复位置：[application/projects/service.py](../../../apps/backend/src/autoflow/application/projects/service.py) 第 199–218 行将规范请求摘要与资源定位符分开；[project_schemas.py](../../../apps/backend/src/autoflow/adapters/http/project_schemas.py) 第 79–91 行增加并使用 `ProjectResourceLocator`。
- 独立复核：实际创建后查询操作，断言 `resource == {type:'project',projectId:创建所得ID}`；读取 OpenAPI，确认操作的 `resource` 引用具名 `ProjectResourceLocator`。
- 结果：关闭。

### SPEC-02：no-op 操作时间倒流

- 原问题：以新 key PATCH 相同名称时，操作新建于 `2026-09-12T20:02:48.892057Z`，但 `updatedAt/completedAt` 使用项目旧时间 `2026-09-12T20:02:48.874103Z`，早于操作自身创建时间。
- 契约：项目无变化应保持管理修订和 `updatedAt`；新操作仍须记录本次操作的时间事实，不能拿项目旧更新时间代替操作完成时间。
- 修复位置：[domain/projects/models.py](../../../apps/backend/src/autoflow/domain/projects/models.py) 第 67–76 行以本次完成时间更新 Operation。
- 独立复核：新 key 提交 no-op 后查询操作，断言 `completedAt >= createdAt`，同时操作结果中的项目 `updatedAt` 仍等于原值。
- 结果：关闭。

### SPEC-03：open 缺少顶层 lastOpenedAt

- 原问题：POST open 只返回 `{project}`；契约要求 `{project,lastOpenedAt}`。原测试只断言嵌套项目中的时间存在。
- 契约：`api-contracts.md` §3.1；open 只改变最近打开时间，不改变管理修订及 `updatedAt`。
- 修复位置：[projects.py](../../../apps/backend/src/autoflow/adapters/http/projects.py) 第 98–108 行与 [project_schemas.py](../../../apps/backend/src/autoflow/adapters/http/project_schemas.py) 第 107–109 行。
- 独立复核：实际调用 open，断言顶层时间与 `project.lastOpenedAt` 一致，项目 `updatedAt` 保持不变。
- 结果：关闭。

### SPEC-04：错误 details 缺项或转码错误

- 原问题：不存在项目的错误返回 `domainCode:"p_r_o_j_e_c_t__n_o_t__f_o_u_n_d"`；结构不完整的 `defaultResources:{}` 返回 422 时没有 `domainCode/retryable`。
- 契约：PM1 包 2 要求错误 details 包含 `domainCode/retryable`；API 错误使用统一语义注册表，不逐字母拆分代码。
- 修复位置：[errors.py](../../../apps/backend/src/autoflow/adapters/http/errors.py) 第 140–172 行。
- 独立复核：GET 不存在项目，断言 `domainCode == 'project_not_found'` 且 `retryable == false`；提交结构不完整的资源对象，断言 422 的 `domainCode == 'validation_error'` 且 `retryable == false`。定向测试还覆盖缺失 body、非法分页和非法路径 UUID。
- 结果：关闭。

### SPEC-05：操作列表忽略筛选

- 原问题：存在一个创建操作和一个更新操作时，`kind=createProject` 仍返回两个；`status=failed` 也返回两个 succeeded；非法 kind 同样被忽略。
- 契约：`api-contracts.md` §3.7 的 `kind/status/resourceType` 筛选与非法筛选 422。
- 修复位置：[projects.py](../../../apps/backend/src/autoflow/adapters/http/projects.py) 第 124–145 行；[infrastructure/database/projects.py](../../../apps/backend/src/autoflow/infrastructure/database/projects.py) 第 209–239 行，计数和列表应用同一组 SQL 条件。
- 中间复核：首次修复把 status 限定为 `succeeded`，独立反例发现合法 `status=failed` 变成 422，未将该项判为关闭。随后修复为已定义的五种 OperationStatus。
- 最终独立复核：`kind=createProject` 仅返回创建操作；`accepted/running/reconciling/failed` 在当前无匹配时均返回 200、空数组和 total=0；`succeeded` 返回真实匹配；未知状态及未知 kind 返回 422。当前实际资源类型 project 的组合筛选通过。
- 结果：关闭。允许状态筛选不代表 PM1 新增后台操作或失败操作创建机制。

### SPEC-06：OpenAPI 与实际响应不一致

- 原问题：创建只声明 201，缺少重放 200；PATCH 等端点没有实际业务错误状态；422 被声明为 FastAPI `HTTPValidationError`，与运行时统一错误 envelope 不一致。
- 契约：实际 handler 同阶段提供正确 DTO、成功响应和可产生的错误响应，供唯一客户端类型生成使用。
- 修复位置：[projects.py](../../../apps/backend/src/autoflow/adapters/http/projects.py) 第 28–175 行的端点响应声明，复用现有统一错误模型。
- 中间复核：主要响应修正后，独立检查发现十个端点仍未声明公共认证 middleware 实际返回的 401；反馈后补齐。
- 最终独立复核：创建声明包含 200/201/401/409/422；PATCH 包含 200/401/404/409/422/423；十个端点均声明 401；项目 OpenAPI 路由响应不再引用 `HTTPValidationError`，使用统一错误 envelope。
- 结果：关闭。此处验证后端 OpenAPI；不替根协调声明最终前端 generated 文件已重新生成或验收。

## 3. 工程质量发现与关闭证据

上述六项及中间残余关闭后，给出 `SPEC PASSED`，进入工程质量审查。新增两项 P2，置信度高；现均已关闭。

### QUALITY-01：布尔值绕过修订号类型检查

- 原问题：`ProjectPatch.expected_management_revision: int` 将 JSON `true` 强转为整数 1，绕过应用服务中 `type(expected) is int` 的保护。实际 PATCH 返回 200 并修改了项目。
- 修复位置：[project_schemas.py](../../../apps/backend/src/autoflow/adapters/http/project_schemas.py) 第 126 行，使用 `Field(ge=1, strict=True)`。
- 独立复核：逐一提交 `true/false/1.0/"1"/0/-1`，均返回 422；各请求的 key 查询均为 404，项目名称、描述、修订和操作总数不变。随后以正常整数 1 提交更新，返回 200、修订增至 2。
- 结果：关闭。

### QUALITY-02：超大页码进入 SQLite 后溢出

- 原问题：项目列表和操作列表均接受 `page=9223372036854775808`，计算后的 OFFSET 无法绑定为 SQLite 整数，实际返回 500 `INTERNAL_ERROR`。
- 修复位置：[projects.py](../../../apps/backend/src/autoflow/adapters/http/projects.py) 第 38、131 行，对 page 设置 1 至 2,147,483,647 的请求边界；pageSize 仍为 1 至 200。
- 独立复核：两个列表的超大 page、超过上界一位的 page、0、负数及 pageSize=201 均在查询前返回 422；正常 page=1、page=2 和允许的最大 page（pageSize=200）均返回 200。
- 结果：关闭。

## 4. 独立执行的验证

测试命令均从本工作区根目录执行。临时反例通过 `uv run --directory apps/backend python -` 运行，使用 `TemporaryDirectory`、独立 SQLite 文件及 TestClient；没有操作用户业务库、真实浏览器或外部账号。

| 阶段 | 独立运行 | 实际结果 | 适用范围 |
|---|---|---|---|
| 首轮规格审查 | 下列四个 PM1 文件的 pytest | 21 passed，0.56 秒 | 修复前测试状态，不能证明原六项不存在 |
| 首轮规格审查 | `uv run --directory apps/backend pytest -q -p no:cacheprovider` | 459 passed，55.14 秒 | 修复前的完整后端运行；不是最终修复后的全量 QA |
| 首次修复复核 | 同四个 PM1 文件的 pytest | 22 passed，0.65 秒 | 当时仍有合法状态筛选和 401 声明残余 |
| 最终后端复核 | 同四个 PM1 文件的 pytest | 23 passed，0.67 秒 | 当前两轮修复后的定向测试结果 |
| 最终后端复核 | `uv run --directory apps/backend mypy src` | 138 个源文件通过 | 按仓库现有 mypy 配置，不声称额外启用严格模式 |
| 最终后端复核 | 下列定向 Ruff 命令 | All checks passed | 本次项目代码、统一错误集成及项目测试 |

定向 pytest 命令：

```sh
uv run --directory apps/backend pytest -q -p no:cacheprovider \
  tests/unit/test_project_service.py \
  tests/contract/test_projects.py \
  tests/integration/test_project_repository.py \
  tests/integration/test_project_migration.py
```

定向 Ruff 命令：

```sh
uv run --directory apps/backend ruff check \
  src/autoflow/domain/projects \
  src/autoflow/application/projects \
  src/autoflow/infrastructure/database/projects.py \
  src/autoflow/adapters/http/projects.py \
  src/autoflow/adapters/http/project_schemas.py \
  src/autoflow/adapters/http/errors.py \
  tests/contract/test_projects.py \
  tests/integration/test_project_repository.py \
  tests/integration/test_project_migration.py \
  tests/unit/test_project_service.py
```

pytest 输出含两项既有 Starlette/httpx 与 anyio 弃用警告；没有测试失败。这里保留本审查实际运行的文件范围与数量，不照抄其他智能体不同范围的 19/25 项声明。

独立临时反例及现有测试进一步提供了以下证据：

- 同 key 并发创建：两个调用得到同一 projectId 和 operationId，仅一项创建、一次重放；同 key 并发更新只产生一个操作和一次修订增加。异命令复用 key 返回 `OPERATION_PAYLOAD_MISMATCH`。
- 旧修订的原 key 重放返回历史结果，先于当前 revision 检查；创建结果快照不因后续编辑而改写，重启后仍可找回；跨项目操作和错误 workspace 查询返回 404。
- 在 Operation 插入前注入失败，项目创建、项目更新和 Operation 均回滚，没有只写项目的半提交事实。该检查是短事务故障注入，不是进程断电或磁盘故障模拟。
- 36 个 emoji 的名称与 120 个 emoji 的描述可创建；37/121 被拒绝。`Straße/STRASSE` casefold 冲突，归档项目仍占名。
- 省略默认资源得到批准的默认对象；显式完整但引用不存在的对象可保存；PATCH 省略资源保持原对象。非法组合被拒绝。
- 六种项目排序和分页可用；最近打开时间空值排后并使用约定收尾顺序；`%`、`_` 搜索按字面处理。
- 修改仅允许 active；closing/archived/deleting/deleted 使用批准的状态码；open 允许 active/closing/archived；GET 可读取 deleting。
- 完整应用中的缺失或错误 token 返回 401；QuiesceGate 暂停后只读 GET 仍为 200，创建、PATCH、open 为 409；恢复后 open 可用。
- 迁移从 `0005_workflow_documents` 派生。空库及包含 profiles、proxies、proxy_pools、model_providers、models、workflow_documents 的既有库重复升级后保留原数据，外键检查通过。首轮全量运行亦包含既有分支合流迁移测试。

## 5. 最终结论与局限

**规格结论：PASSED。工程质量结论：PASSED。** 原六项规格问题和新增两项质量问题全部关闭。当前审查范围内未发现其他需要阻止本后端包推进的 P1/P2；结论置信度高，适用于上述工作树时点、代码范围和已执行验证。

职责、幂等顺序、CAS、查询归属和 SQL 条件、项目与操作共同提交以及失败回滚未见新增实质问题。修复使用现有验证、错误模型及数据库机制，没有因审查引入未来阶段的调度、归档或环境框架。

最终修复后没有重复完整 459 项测试；本记录不代表根协调后续全量 QA 已完成。未验证桌面端联调、最终生成客户端、浏览器与外部供应商、Windows 桌面、真实进程崩溃、磁盘耗尽、生产规模性能或跨进程压力。修复前全量测试与修复后定向复核必须分别引用，不能合并为一次“最终全量通过”。
