# 模型管理实施就绪度核查

- 日期：2026-09-12
- 状态：confirmed（仓库现状、文件内容、旧源码快照）；proposed（目标文件树、实施顺序与并行协作建议）
- 新仓库：`/Users/zhangtiancheng/Documents/projects/autoflow`
- 旧源码：`/Users/zhangtiancheng/Documents/projects/browser-automation/autoflow-desktop`
- 验证方式：只读检查新旧仓库源码、配置、测试与文档；使用 `git rev-parse HEAD` 读取旧仓库提交，使用 Python 3 标准库 `hashlib.sha256` 读取旧工作树文件。未启动服务、未运行测试、未联网、未修改业务代码。

## 1. 已确认的新仓库现状

### 1.1 模型领域仍为空骨架

以下目录当前只有零字节 `.gitkeep`，没有模型业务实现：

- `apps/backend/src/autoflow/domain/models/`
- `apps/backend/src/autoflow/application/models/`
- `apps/backend/src/autoflow/providers/model/`
- `apps/desktop/src/renderer/domains/models/`
- `apps/desktop/src/renderer/domains/models/{components,hooks,pages,tests}/`

`apps/backend/src/autoflow/adapters/http/` 没有模型 schema 或路由；`apps/backend/src/autoflow/infrastructure/database/models.py` 只有 `ProfileRow`、`ProxyRow`、`ProxyPoolRow`、`KernelSettingsRow` 与 `KernelOperationRow`，没有供应商或模型表。当前唯一 Alembic 版本是 `apps/backend/src/autoflow/infrastructure/database/migrations/versions/0001_browser_resources.py`。

### 1.2 可复用的后端基础

- 分层与事务范例：
  - `apps/backend/src/autoflow/domain/profiles/{models,errors,ports}.py`
  - `apps/backend/src/autoflow/application/profiles/service.py`
  - `apps/backend/src/autoflow/infrastructure/database/profiles.py`
  - `apps/backend/src/autoflow/adapters/http/profile_schemas.py`
  - `apps/backend/src/autoflow/adapters/http/profiles.py`
- `apps/backend/src/autoflow/adapters/http/profile_schemas.py` 的 `ApiModel` 使用 camelCase alias、`populate_by_name=True` 和 `extra="forbid"`。模型 HTTP schema 应遵循同一约定，避免前端字段和错误字段命名漂移。
- `apps/backend/src/autoflow/adapters/http/errors.py` 已生成 `{error: {code, message, details, requestId}}` 错误 envelope，并处理 Pydantic 校验、profiles 领域错误和未预期异常。模型领域错误尚未加入映射。
- `apps/backend/src/autoflow/bootstrap/app.py` 对 `/api/v1/*` 校验 `x-autoflow-token`，并在 CORS 中允许该头与常用 CRUD 方法。
- `apps/backend/pyproject.toml` 已包含 `httpx>=0.28.1`，模型供应商 HTTP 调用不需要为基础客户端新增依赖。
- 数据库启动迁移由 `apps/backend/src/autoflow/infrastructure/database/session.py` 的 `migrate_database()` 执行 `alembic upgrade head`；Alembic metadata 由 `migrations/env.py` 引用同一 `Base.metadata`。

### 1.3 CredentialStore 已实现但尚未装配

- `apps/backend/src/autoflow/domain/credentials.py` 已定义 `CredentialStore.read/write/delete` 端口与不可用错误。
- `apps/backend/src/autoflow/infrastructure/credentials/system.py` 已实现 `SystemCredentialStore`：macOS 限定 `keyring.backends.macOS`，Windows 限定 `keyring.backends.Windows`，以 Base64 编码保存不透明 bytes；不支持其他平台或非系统 backend。
- `apps/backend/src/autoflow/infrastructure/credentials/redaction.py` 可删除已知 secret、Bearer token、常见 query/JSON 凭据和 URL 密码。
- `apps/backend/src/autoflow/infrastructure/credentials/cloakbrowser.py` 展示了如何把共享 CredentialStore 包装为领域专用凭据存储。
- `apps/backend/tests/unit/test_credential_store.py` 使用 fake macOS/Windows backend 验证 bytes round-trip、幂等删除、错误不泄密和文本脱敏。
- `apps/backend/src/autoflow/bootstrap/app.py` 当前没有实例化或注入 `SystemCredentialStore`。现有测试也没有连接真实 Keychain 或 Windows Credential Manager，因此只能确认实现与隔离单测存在，不能声称真实双平台凭据后端已验收。

模型管理应保留旧界面的“API Key 已配置”状态，但 API 响应不应返回原始 API Key 或 `secret_ref`。SQLite 只保存 `secret_ref` 与是否已配置的投影；写请求中的 API Key 应标记为 write-only。正式契约现已区分未触碰时省略=保持、非空=替换、显式空串=清除（仅可选预设），不再属于未决项。

### 1.4 HTTP 客户端与 OpenAPI

- `apps/desktop/src/renderer/shared/api/client.ts` 会为每个请求注入 `x-autoflow-token`。
- 该客户端遇到非 2xx 时只抛出状态码文本，不解析后端的 `error.code`、`details.fields` 或 `requestId`。旧模型交互需要区分连接失败、校验错误和资源冲突，因此实现前或第一个垂直切片内必须补全结构化错误解析。
- 后端 token middleware 的 401 当前返回 FastAPI 风格 `{"detail":"Unauthorized"}`，不符合 `adapters/http/errors.py` 的统一 envelope。
- `scripts/generate-api.mjs` 会创建临时数据目录、启动临时 sidecar、读取 `/openapi.json`，再生成或检查 `apps/desktop/src/renderer/shared/api/generated.ts`。
- 当前 `generated.ts` 只有 64 行和 `/health`，没有已经由 `bootstrap/app.py` 注册的 profiles 与 proxy-options 路由，因此它已落后于当前后端源码。本次未启动 sidecar，未执行生成或一致性检查。

### 1.5 前端组件与样式

- Tailwind CSS 4 已通过 `apps/desktop/electron.vite.config.ts` 的 `@tailwindcss/vite` 插件接入。
- `apps/desktop/src/renderer/styles/index.css` 已定义暖灰画布、黏土棕强调色、表面/边框/文字 token、控件与卡片圆角、reduced-motion 和 Toast 动画。
- 可直接复用的桌面共享控件：
  - `apps/desktop/src/renderer/shared/components/ui/button.tsx`
  - `input.tsx`
  - `select-radix.tsx`
  - `checkbox.tsx`
  - `switch.tsx`
  - `tabs.tsx`
  - `dialog.tsx`
  - `alert-dialog.tsx`
  - `tooltip.tsx`
  - `apps/desktop/src/renderer/shared/components/FormField.tsx`
  - `ResourceState.tsx`
  - `Toaster.tsx`
- `dialog.test.tsx` 已覆盖 Escape、遮罩关闭、busy 锁定、嵌套 dialog 焦点和关闭后焦点返回，适合复用到旧模型编辑窗及叠加删除确认。
- 旧模型页面直接依赖的 Card、Badge、Textarea、PageHeader、可搜索且可自由输入的 PresetInput 目前不存在。
- `packages/ui` 只有空目录和 `.gitkeep`，没有 `package.json`、`components.json`、导出入口或构建配置；根 `package.json` 的 workspaces 也只有 `apps/desktop`。当前控件是 desktop 内的 Radix + Tailwind 自有实现，不能称为已经完成的 shadcn/ui 包。
- 当前依赖中没有 `@tanstack/react-query`、React Router 或 Zustand。`apps/desktop/src/renderer/app/App.tsx` 仍是 sidecar 健康/恢复界面，没有模型路由、领域查询缓存或正式应用导航。

## 2. 已确认的文档与实际代码偏差

1. `docs/architecture/README.md` 要求组件 API 由 `packages/ui` 统一导出；实际包为空。`docs/PROJECT_STRUCTURE.md` 第 15 行对“尚未注册 workspace”的描述符合现状。
2. `docs/architecture/README.md` 的 provider 树列出 browser、proxy、kernel、platform，遗漏 `providers/model`；较新的 `docs/PROJECT_STRUCTURE.md` 已列出该目录，仓库也已有空骨架。模型规格应以较新的目录基准为准，并在实施改变目录职责时同步架构文档。
3. `docs/architecture/README.md` 写 Python 使用 `mypy strict`，但 `apps/backend/pyproject.toml` 没有 `[tool.mypy]` strict 配置，CI 实际运行 `mypy src`。当前检查不能描述为 strict。
4. `docs/superpowers/specs/2026-09-12-proxy-management-design.md` 与 `docs/superpowers/plans/2026-09-12-proxy-management-implementation.md` 把 CredentialStore 写成待新增或仅有目录骨架；该信息已被现有端口、实现、测试及提交 `a4b881f` 超越。
5. 代理规格/计划把统一 `ApiError` 和生成 DTO 当作目标基础；当前只有部分后端错误 envelope，前端不解析 envelope，且生成文件已过时。模型计划应把这三项列为实际前置工作，不能当成已经完成的公共能力。

## 3. 审查阶段的初步文件树（proposed，正式方案优先）

以下为独立核查时的初步建议，不代表文件已经存在；正式文件拆分、凭据语义和顺序以[设计规格](../../docs/superpowers/specs/2026-09-12-model-management-design.md)、[契约](../../docs/references/model-management-api-contract.md)和[实施计划](../../docs/superpowers/plans/2026-09-12-model-management-implementation.md)为准。

```text
apps/backend/src/autoflow/
  domain/models/{__init__,models,errors,ports}.py
  application/models/{__init__,service}.py
  providers/model/{__init__,http}.py
  infrastructure/database/model_providers.py
  infrastructure/credentials/model_provider.py
  adapters/http/{model_schemas,models}.py
  infrastructure/database/migrations/versions/0002_model_management.py

apps/backend/tests/
  unit/{test_model_domain,test_model_service,test_model_provider}.py
  integration/test_model_repository.py
  contract/test_models_api.py

apps/desktop/src/renderer/domains/models/
  api.ts
  model.ts
  provider-catalog.ts
  components/{ProviderLogo,ProviderWizard,ModelEditor,ProviderSidebar,ModelDirectory}.tsx
  hooks/use-model-management.ts
  pages/ModelManagementPage.tsx
  tests/{ModelManagementPage,ProviderWizard,ModelEditor}.test.tsx
```

`model.ts` 只保存 UI 派生状态或视图类型；HTTP DTO 从 `shared/api/generated.ts` 使用，不另写一套契约。API Key 由 sidecar 的 CredentialStore 处理，模型模块不需要新增 Electron main/preload 通道。

拟议实施顺序：

1. 完成共享结构化错误解析，冻结模型 schema、错误码和凭据写入/回显语义。
2. 完成 domain、repository、CredentialStore 领域包装、provider、application service 与 HTTP adapter 的第一个完整垂直切片。
3. 生成并提交唯一的 `shared/api/generated.ts`。
4. 补齐最少的共享基础控件，再迁移模型领域组件；ProviderWizard、ProviderLogo、ModelEditor 等业务组件留在 `domains/models`。
5. 组装页面与路由，覆盖旧交互的加载、空态、失败、关闭、锁定、叠加确认和模型/供应商测试状态。

供应商 `connection-preview`、首次 `connect + selectedModels` 和连接变更必须由 application service 协调远程验证、凭据写入与数据库事务。失败不能留下“数据库已连接但密钥未保存”或“供应商已保存但选中模型只保存一部分”的状态。

## 4. 拟议的并行修改边界

以下文件或资源应指定单一所有者并串行合并：

- `apps/backend/src/autoflow/bootstrap/app.py`：共享依赖装配和路由注册。
- `apps/backend/src/autoflow/adapters/http/errors.py`：全局错误码映射。
- `apps/backend/tests/contract/conftest.py`：应用 fixture 与依赖注入。
- `apps/backend/src/autoflow/infrastructure/database/models.py`：共享 SQLAlchemy metadata。
- Alembic 当前 head 与下一个 revision：代理模块也可能创建 `0002_*`，必须先确定唯一 revision/down_revision 链。
- `apps/desktop/src/renderer/shared/api/generated.ts`：只能由一次统一 OpenAPI 生成更新。
- 根和 desktop 的 `package.json`、`package-lock.json`：增加查询层或路由依赖时会冲突。
- `apps/desktop/src/renderer/app/App.tsx`、`main.tsx` 与全局导航/路由文件。
- `apps/desktop/src/renderer/styles/index.css`、共享 UI 文件和 `packages/ui` 的 workspace 注册。
- `apps/backend/src/autoflow/domain/credentials.py`、`infrastructure/credentials/*`：模型应新增领域包装并复用现有端口；若代理模块同时修改 key namespace 或 bootstrap 装配，需要统一设计。

领域内部文件可以按“后端 domain/provider/repository”和“前端无业务请求的组件”并行，但共享契约生成必须在后端 schema 稳定后进行，页面联调必须在生成类型更新后进行。

## 5. 验证命令

以下命令均为仓库当前脚本或拟议模型测试路径对应的真实调用形式；本次只记录，未执行。

定向后端模型验证：

```bash
uv run --directory apps/backend pytest tests/unit/test_model_domain.py tests/unit/test_model_service.py tests/unit/test_model_provider.py tests/integration/test_model_repository.py tests/contract/test_models_api.py -q
```

后端全量质量检查：

```bash
uv run --directory apps/backend pytest -q
uv run --directory apps/backend ruff check .
uv run --directory apps/backend mypy src
```

前端定向和全量检查：

```bash
npm --workspace @autoflow/desktop test -- models
npm test
npm run typecheck
npm run lint
npm run build
npm run test:structure
```

OpenAPI：

```bash
npm run openapi:generate
npm run openapi:check
```

最终桌面与打包风险验证：

```bash
npm run smoke:sidecar
npm run smoke:desktop
npm run backend:build
npm run package:dir
```

只有模型业务与共享前端改动时，先运行定向测试、OpenAPI 检查、typecheck、lint 和 build；修改 sidecar 依赖、应用装配或打包输入后再运行打包与桌面 smoke。

## 6. 旧源码复用快照

- 旧仓库 HEAD：`324748abe7095f085b4ffb9467be9cb5c8851a5c`
- 哈希对象：旧仓库当前工作树文件内容，不推断其是否与 HEAD 相同。
- 算法：SHA-256，由 Python 3 `hashlib.sha256(path.read_bytes())` 计算。

| SHA-256 | 旧仓库相对路径 |
| --- | --- |
| `ebe0a8d6d6e350f9faf5159fa4d25ba388c7716797bfd8494cd52aca671ab9a9` | `src/renderer/pages/ModelsPage.tsx` |
| `a054cdc44dda63de3858dea3d3ed7f0bc6e608f13f5ad141d6c877170abd819c` | `src/renderer/features/models/ModelEditor.tsx` |
| `1d427e3ff77f945e56f196d8a5a00e3dcb3704d58bc05a4242b05de8fa44250e` | `src/renderer/features/models/ProviderWizard.tsx` |
| `ec2adb1b73c00999c40caf0555a48ed01c37cccfb2f6f09176f733bee069b7ff` | `src/renderer/features/models/provider-catalog.ts` |
| `1a7e3e662ec4ba0d80fe8929f4e8efdb0f1fe8f619ecd0551f80bbe3082c6b3e` | `src/renderer/features/models/model-api.ts` |
| `b6c43463cacdef67fc5e56a595c34c67712a55fe7e16845ea37f73e631b9895b` | `backend/src/autoflow/api.py` |
| `1672cff4e1a58302a7a3f5cad177bc34e1d9ab01e1f7689aa183be4b8d54e20a` | `backend/src/autoflow/schemas.py` |
| `19e156093ee792dfd8d298fa2e0204fbbe625786cea01838245351cc86a28b4e` | `backend/src/autoflow/model_provider_service.py` |
| `dffc32886fefaa0f75dd611fd4d9be3c7cefaa49dac1d3747190a3b6065c5d61` | `backend/src/autoflow/models.py` |
| `c032e281fb7004a576ac60a7006ea0708e727e9627d1e3fe566bd74257f64f13` | `backend/tests/test_model_editor_simplification.py` |
| `6b9be61805a68b5d703a0ce7486e941b90b3c2a6a16796c84e4068d4fc9d6194` | `backend/tests/test_model_provider_service.py` |
| `4d94978e5358ebf7448adc2ecc996d10b4fcb5c0868bd57384ce96c139c47d48` | `backend/tests/test_models.py` |
| `ee3414aad46f3518c80c71f7b305aa0b039a8400a98ece7e1a9497084e44dcb0` | `src/renderer/features/models/ProviderWizard.test.tsx` |
| `17d1fed3f09c86062b015435f485a883153708e373b7e16eb346b45c4576e04f` | `src/renderer/features/models/model-row-styles.test.ts` |

该快照用于后续确认复用来源。若旧工作树文件发生变化，实施记录必须重新计算哈希并说明采用了哪个版本，不能只引用仓库路径。

## 实施后更新（2026-09-12，confirmed）

本文保留开工前源码/基础设施快照，不继续用作当前实现状态。关于缺少业务代码、Query依赖与应用装配的旧现状已被独立分支实现取代（superseded）。当前事实及验证见 [实现验收](../../docs/migration/model-management-verification.md)。
