# 模型管理实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 [subagent-driven-development](/Users/zhangtiancheng/Documents/projects/browser-automation/.agents/skills/subagent-driven-development/SKILL.md)（推荐）或 [executing-plans](/Users/zhangtiancheng/Documents/projects/browser-automation/.agents/skills/executing-plans/SKILL.md) 逐任务实现此计划。步骤使用复选框（`- [ ]`）跟踪进度。用户已指定可由 gpt-5.6-sol 承担有界任务；主代理负责集成和审查。

**目标：** 在新 AutoFlow 中迁移旧模型管理全部已确认能力，保留旧布局与交互，组件先行，前后端按功能切片一起验收。

**架构：** React 领域组件和 hooks 使用生成 DTO 访问本地 FastAPI；应用用例协调领域规则、SQLAlchemy 仓储、现有 CredentialStore 和 httpx 协议适配器。共享控件复用 desktop shared，页面只组合已验证组件。

**技术栈：** 当前 Python 3.11、FastAPI/Pydantic、SQLAlchemy/Alembic、httpx/keyring；React/TypeScript、shadcn/ui 组合方式、Radix/Tailwind 4、TanStack Query 5（新增范围沿用旧 ^5.90.2，实际版本写入锁文件）；pytest、Vitest/Testing Library、Electron 冒烟脚本。

**规格：** [模型管理设计](../specs/2026-09-12-model-management-design.md)、[API 契约](../../references/model-management-api-contract.md)、[已确认交互矩阵](../../prototype/model-management/model-management-interactions.md)。三份都要读。

- 日期：2026-09-12
- 状态：proposed，文档可审查；所有实施复选框未执行。用户本轮要求编写设计和计划，未要求立即编写业务代码。
- 来源与现状：[实施就绪度及旧源码哈希](../../../.ai/knowledge/2026-09-12-model-management-implementation-readiness.md)。

## 全局约束

- Windows x64、macOS arm64/x64；平台差异集中在现有适配器。
- 保留 278px 供应商左栏、split 模型编辑、三步接入和旧反馈位置；不新增 Toast、未保存确认、横向供应商 Tabs 或采样参数。
- 模型测试中允许保存和关闭；供应商测试/保存、模型保存、删除期间锁窗。
- 无旧数据兼容或迁移；只追加新仓库 Alembic 迁移。
- API camelCase，读响应无 apiKey/secretRef；写 Key 省略=保持，字符串=替换，空串=清除（仅可选预设），null 不接受。
- 目录超时 15 秒，模型测试超时 30 秒；提示“只回复 OK”，输出限制 16 tokens，正文/思考预览最多 240/2000 字符。
- httpx `trust_env=False`、`follow_redirects=False`；本地接口允许空 Key 且完全省略认证头。
- 新 DTO 唯一生成到 `apps/desktop/src/renderer/shared/api/generated.ts`，不得手改生成文件或维护第二份 schema。
- 仅增加实际需要的查询层依赖，不安装供应商 SDK，不新建独立组件包、任务队列、通用插件注册器或模型路由器。
- 每个切片由后端契约/实现、领域组件/接线、测试共同验收；测试夹具可以模拟远端，实际应用不得硬编码 mock 目录。
- 每个提交显式暂存自己拥有的路径；不得 `git add .`、覆盖或回滚其他线程改动。

## 1. 开工核对与文件职责

实施从根目录 `/Users/zhangtiancheng/Documents/projects/autoflow` 执行命令。先重读 AGENTS、`.ai/README.md`、memory、相关 decisions、规格、契约和交互说明。运行 `git status --short`，为模型任务创建独立分支/worktree；若用户要求当前目录则遵循用户指令，并按下表锁定文件所有者。快照中的依赖和文件是 2026-09-12 事实，其他模块可能先落地同一基础能力，实际存在时复用而不是再建一次。

### 1.1 后端目标文件

| 操作 | 文件 | 职责/归属 |
| --- | --- | --- |
| 新建 | `apps/backend/src/autoflow/adapters/http/schemas.py` | 从 profile_schemas 提取 ApiModel；共享文件由主代理集成。 |
| 修改 | `apps/backend/src/autoflow/adapters/http/profile_schemas.py` | 仅改共享基类 import，不变更浏览器契约。 |
| 新建 | `apps/backend/src/autoflow/adapters/http/model_schemas.py` | 契约全部模型 DTO、writeOnly Key、严格验证与序列化。 |
| 新建 | `apps/backend/src/autoflow/domain/models/{__init__,models,errors,ports}.py` | 非秘密实体/值对象、错误、仓储和远端调用端口。 |
| 新建 | `apps/backend/src/autoflow/application/models/{__init__,service}.py` | ModelService：预览、接入、更新、目录/生成测试、启停、删除和补偿。 |
| 新建 | `apps/backend/src/autoflow/providers/model/{__init__,http}.py` | HttpModelProvider：旧协议构造/解析函数与异步请求。 |
| 新建 | `apps/backend/src/autoflow/infrastructure/database/model_providers.py` | model_providers/models/清理意图仓储、事务工厂。 |
| 修改 | `apps/backend/src/autoflow/infrastructure/database/models.py` | 添加三张表 ORM；共享 metadata 由主代理集成。 |
| 新建 | `apps/backend/src/autoflow/infrastructure/credentials/model_provider.py` | 通用 CredentialStore 的模型命名包装；不再实现 keyring。 |
| 新建 | `apps/backend/src/autoflow/infrastructure/database/migrations/versions/0002_model_management.py` | 三张表及唯一/外键约束；编号以当前唯一 head 为准。 |
| 新建 | `apps/backend/src/autoflow/adapters/http/models.py` | 14 条目标路由，分切片注册已实现用例。 |
| 修改 | `apps/backend/src/autoflow/adapters/http/errors.py`、`bootstrap/app.py` | 错误 envelope、401、依赖装配、生命周期、路由；主代理所有。 |
| 新建 | `apps/backend/tests/unit/test_model_schemas.py`、`test_model_domain.py`、`test_model_service.py`、`test_model_provider.py` | 输入/规则、补偿/并发、HTTP 协议隔离验证。 |
| 新建 | `apps/backend/tests/integration/test_model_repository.py`、`tests/contract/test_models_api.py` | 临时 SQLite 迁移/约束；带真实应用装配的 HTTP 契约。 |
| 新建 | `apps/backend/tests/fixtures/model_management.py` | MemoryCredentialStore、MockTransport、合成非秘密 payload 及可控失败；不用于生产。 |

花括号列出同目录的具体文件；首次落地相应 Python 包时移除该目录的 `.gitkeep`。若 Alembic 已有 0002，由主代理选择下一个编号、写准确 down_revision 并同步本计划路径，禁止开第二条 head 或修改已执行的迁移。

### 1.2 前端目标文件

前缀 `R = apps/desktop/src/renderer`，下列 `R/` 均指这个确定路径。

| 操作 | 文件 | 职责/归属 |
| --- | --- | --- |
| 修改 | `R/shared/api/client.ts`、`client.test.ts` | 解析 ApiClientError 的 code/details/requestId，处理 204、AbortSignal 和安全退化。 |
| 生成 | `R/shared/api/generated.ts` | 真实 OpenAPI 输出，主代理统一生成。 |
| 新建 | `R/app/query-provider.tsx` | 一个 QueryClientProvider，随 sidecar instanceId 隔离；不持久化缓存。 |
| 修改 | `R/app/App.tsx`、`App.test.tsx`、`app-state.ts` | 保留 sidecar 恢复，提供当前实例客户端并接应用级导航；按最终已落地 shell 接入。 |
| 新建 | `R/shared/components/Modal.tsx`、`Modal.test.tsx` | 组合现有 Dialog，统一 header/body/footer、大小、split、closeDisabled、焦点归还。 |
| 新建 | `R/shared/components/ui/textarea.tsx`、`badge.tsx`、`dropdown-menu.tsx`、`dropdown-menu.test.tsx` | 实际缺少的基础控件；菜单需键盘方向键/Escape/焦点测试。 |
| 修改 | `R/shared/components/ui/button.tsx` | 如尚缺少则补危险按钮 variant；不改变现有 variants。 |
| 新建 | `R/domains/models/api.ts`、`model.ts`、`provider-catalog.ts` | 类型化 endpoint 封装、UI 草稿/状态、旧预设数据。 |
| 新建 | `R/domains/models/assets/*` | 只复制旧 provider-catalog 实际使用的 9 个图标；保留出处，不生成替代 logo。 |
| 新建 | `R/domains/models/hooks/use-model-management.ts` | 查询 keys、mutations、选中供应商、列表与目录失效和请求会话。 |
| 新建 | `R/domains/models/components/ProviderLogo.tsx`、`ProviderSidebar.tsx`、`ProviderDetail.tsx`、`ModelDirectory.tsx`、`FeedbackCard.tsx` | 无全局布局副作用的领域展示与动作组件。 |
| 新建 | `R/domains/models/components/ProviderWizard.tsx`、`ProviderCatalogStep.tsx`、`ProviderConnectionStep.tsx`、`ProviderModelsStep.tsx` | 向导容器与三个步骤，只从 api/hooks 触发请求。 |
| 新建 | `R/domains/models/components/ModelEditor.tsx`、`ModelForm.tsx`、`ModelTestPanel.tsx`、`ModelIdInput.tsx` | split 编辑、表单/标签、单次测试、可搜索且可自由输入的候选控件。 |
| 新建 | `R/domains/models/components/ModelDeleteDialog.tsx`、`ProviderDeleteDialog.tsx` | 保留两种文案/作用范围与嵌套确认规则。 |
| 新建 | `R/domains/models/pages/ModelManagementPage.tsx` | 只组装已完成领域组件和 hooks。 |
| 新建 | `R/domains/models/tests/{ProviderWizard,ModelEditor,ModelManagementPage}.test.tsx`、`test-utils.tsx` | 旧交互回归；实例 QueryClient、可控 promise 和生成 DTO 夹具。 |
| 修改 | `apps/desktop/package.json`、`package-lock.json` | 主代理串行添加查询依赖及确实缺少的 Radix menu primitive。 |

不建立通用 Table、万能表单引擎或将单模块 FeedbackCard 移入 packages/ui。菜单如已有并行模块实现则直接复用；没有时采用 `@radix-ui/react-dropdown-menu` 与现有 Radix 家族一致，避免自行实现键盘菜单。新增安装仅这项和 TanStack Query；已存在时不重复安装。

### 1.3 测试与交付文件

- 修改 `scripts/smoke-desktop.mjs`：页面组装后以 sidecar ready 与真实 health 握手判断就绪，保留进程退出回收检查，不继续依赖旧健康占位页的“服务已连接”正文。
- 新建 `scripts/smoke-model-management.mjs` 与 `apps/desktop/tests/fixtures/model-provider-fixture.mjs`：复用现有 Electron smoke 启动方式，临时数据目录及本地 http.Server；不访问用户数据库或真实供应商。
- 新建 `docs/migration/model-management-source-map.md`：复制时登记文件/commit/工作树哈希/目标/改动/依赖/来源说明。
- 新建 `docs/migration/model-management-verification.md`：按交互矩阵记录真实验收和未验证项。
- 更新 `docs/PROJECT_STRUCTURE.md`、`docs/architecture/README.md` 中本模块实际改变的职责与路径，以及 `.ai/plans/2026-09-12-model-management.md`；不宣称预设目录已经实现。

## 2. 并行安排与依赖

| 波次 | 后端工作者（gpt-5.6-sol） | 前端工作者（gpt-5.6-sol） | 主代理 |
| --- | --- | --- | --- |
| A | 任务 1 的 schema、领域输入与错误测试 | 任务 2 的共享组件与键盘/焦点测试 | HTTP 共享文件、依赖、类型检查；冻结契约 |
| B | 任务 3 供应商完整用例/远端/仓储 | 任务 4 向导组件及状态机；用已冻结 DTO fixture 写组件测试 | 逐接口生成类型；接入向导真实 API 后一起验收 |
| C | 任务 5 模型 CRUD 与测试接口 | 任务 5 split 编辑、标签、候选、嵌套删除 | 合并一个模型切片，检查测试/保存锁差异 |
| D | 审查失败补偿/过期请求 | 任务 6 页面组合与列表交互 | 全局导航和 sidecar 实例装配 |
| E | 定向回归、迁移/凭据验证 | UI/Electron 回归 | 任务 7 综合验收、来源账本和提交 |

同一切片不能在只有组件 mock 或只有后端测试时标完成。前端提前编写纯组件不意味着页面已交付。主代理独占 bootstrap、全局错误、ORM metadata、迁移 head、生成类型、依赖锁、App/导航和全局样式；其他工作者通过消息提交所需片段，禁止同时编辑。每波最多主代理加三名有界工作者；独立审查者检查行为与结构，失败返回原负责者修正。

## 3. 任务 1：冻结 DTO 并打通真实错误语义

**文件：** 后端 `adapters/http/{schemas,profile_schemas,model_schemas,errors}.py`、`bootstrap/app.py`；`tests/unit/test_model_schemas.py`；前端 `shared/api/client.ts`、`client.test.ts`。主代理负责共享修改。

- [ ] **步骤 1：写失败断言。** `ModelInput`、`ModelProviderMetadataUpdateInput`、`ModelProviderConnectionUpdateInput` 名称和字段与契约一致；读 DTO 独立于写 DTO。schema 测试明确如下，不使用真实 Key。

```python
import pytest
from pydantic import ValidationError
from autoflow.adapters.http.model_schemas import ModelInput, ModelProviderMetadataUpdateInput

def test_metadata_update_rejects_connection_fields():
    with pytest.raises(ValidationError):
        ModelProviderMetadataUpdateInput.model_validate({
            "name": "Local", "description": "", "enabled": True,
            "baseUrl": "http://127.0.0.1:11434/v1",
        })

@pytest.mark.parametrize("value", [-1, 0, 1.0, 1.5, "1", True, 9007199254740992])
def test_context_must_be_a_positive_safe_integer(value):
    with pytest.raises(ValidationError):
        ModelInput.model_validate({"modelKey": "sample", "displayName": "Sample", "contextWindow": value})
```

客户端用 `vi.stubGlobal('fetch', ...)` 返回真实 Response，分别断言 409 envelope 的 code/details/requestId 保留、204 解析为 undefined、非法错误正文使用安全通用消息，认证头和 AbortSignal 仍透传。

```ts
vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 204 })))
await expect(createApiClient('http://localhost', 'test-token').request<void>('/api/v1/models/sample', { method: 'DELETE' })).resolves.toBeUndefined()
```

- [ ] **步骤 2：运行并确认失败位置是缺少目标行为。**

```bash
uv run --directory apps/backend pytest tests/unit/test_model_schemas.py -q
npm --workspace @autoflow/desktop test -- src/renderer/shared/api/client.test.ts
```

- [ ] **步骤 3：实现契约与错误基础。** 提取共享 ApiModel；严格拒绝额外字段；contextWindow 使用 strict=True 的整数验证，拒绝 1.0、字符串与 bool。写入 Key 通过 `model_fields_set` 区分省略和空串，不接受 null。将输入错误转换为字段消息时不附带 Pydantic 的 input/ctx 原对象。401 使用统一 envelope；既有 profile 状态码/字段保持。

```ts
// request 成功分支；T=void 用于 DELETE。
if (response.status === 204) return undefined as T
return response.json() as Promise<T>
```

`ApiClientError` 保留现有 status，增加可空 code/requestId 与 details；非 JSON 错误不向 UI 直接回显 body。该任务只落地已定义 DTO，不注册返回假数据的模型路由。

- [ ] **步骤 4：重复上述定向测试，补 profile 契约回归和类型检查。**

```bash
uv run --directory apps/backend pytest tests/contract -q
npm run typecheck
```

- [ ] **步骤 5：审查并提交上述明确路径。** 提交建议 `refactor: preserve structured API errors and define model contracts`。本任务不会宣称 14 条模型路由已运行。

## 4. 任务 2：共享控件先行

**文件：** `R/shared/components/Modal.tsx`、`Modal.test.tsx`、`ui/{textarea,badge,dropdown-menu}.tsx`、`ui/dropdown-menu.test.tsx`、必要 `ui/button.tsx`；依赖修改由主代理操作。

- [ ] **步骤 1：写真实交互失败测试。** Modal API 为 `open/onOpenChange/title/description?/children/footer?/size/variant/closeDisabled`，size 为 small/medium/large，variant 为 default/form/split；组合现有 Dialog，不重写 portal。覆盖键盘与遮罩关闭、busy 禁用 X、两层确认取消保留父窗、快速重开、入口被删除后的焦点回退。

```tsx
it('locks Escape only when closeDisabled is true', async () => {
  const user = userEvent.setup()
  const onOpenChange = vi.fn()
  const { rerender } = render(<Modal open title="连接信息" closeDisabled onOpenChange={onOpenChange}><input aria-label="名称" /></Modal>)
  await user.keyboard('{Escape}')
  expect(onOpenChange).not.toHaveBeenCalled()
  rerender(<Modal open title="连接信息" closeDisabled={false} onOpenChange={onOpenChange}><input aria-label="名称" /></Modal>)
  await user.keyboard('{Escape}')
  expect(onOpenChange).toHaveBeenCalledWith(false)
})
```

- [ ] **步骤 2：运行并确认失败。**

```bash
npm --workspace @autoflow/desktop test -- src/renderer/shared/components/Modal.test.tsx src/renderer/shared/components/ui/dropdown-menu.test.tsx
```

- [ ] **步骤 3：补齐最小共享组合。** 旧 `modal.tsx` 的 focus-return 逻辑及 `modal-focus.test.tsx` 为复用依据；危险确认继续普通 Dialog。新增菜单使用 Radix DropdownMenu，只暴露本次使用的 Trigger/Content/Item/Separator；原按钮 API 不破坏。textarea/badge 只是样式控件，不写镜像实现的测试。表格使用语义 HTML，页面工作台使用 Tailwind grid，不建通用数据表框架。

```tsx
<Dialog open={open} onOpenChange={onOpenChange} busy={closeDisabled}>
  <DialogContent busy={closeDisabled}>
    <DialogTitle>{title}</DialogTitle>
    {description && <DialogDescription>{description}</DialogDescription>}
    <div>{children}</div>
    {footer}
  </DialogContent>
</Dialog>
```

上例是 shell 组合边界；实际实现加入明确的大小、split、滚动区域、X 与已列焦点处理，不添加业务字段。使用现有 tokens，先在测试 harness 中验证各状态后才供领域页面使用。

- [ ] **步骤 4：通过定向测试与现有 Dialog 回归。**

```bash
npm --workspace @autoflow/desktop test -- src/renderer/shared/components
npm run typecheck
npm run lint
```

- [ ] **步骤 5：审查组件后提交明确控件路径。** 提交建议 `feat: add reusable model workflow controls`。

## 5. 任务 3：供应商用例、协议与持久化切片

**文件：** 后端目标树中的 domain/models、application/models、providers/model、database/model_providers、credentials/model_provider、model_schemas、HTTP models；主代理集成 ORM/迁移/bootstrap/errors；对应 unit、integration、contract 与 fixtures。前端任务 4 可并行编写组件，联调完成后一起验收。

- [ ] **步骤 1：先建立隔离 fixture 与失败契约。** `tests/fixtures/model_management.py` 定义 MemoryCredentialStore，接口为 read(key: str) -> bytes | None、write(key: str, value: bytes) -> None、delete(key: str) -> None，支持指定 read/write/delete 抛错；定义 MockTransport 根据 endpoint 返回合成目录 `sample-chat`，并允许预览后改成空目录。这些辅助类由测试文件显式 import；model_client/provider_payload 等 pytest fixture 定义在使用它们的 test_models_api.py，跨 unit/integration helper 也显式 import，不依赖未注册的 pytest_plugins。测试函数内创建独立 app，新增 `create_app(..., model_gateway=..., credential_store=...)` 注入点；不要修改全局 `client` fixture 使浏览器测试隐式依赖模型目录。

`model_client` fixture 位于 `test_models_api.py`：临时 Settings，instance_id=`model-contract`、instance_token=`test-token`，with TestClient，header 同 token；真实临时 SQLite 和应用用例，只有远端与 OS 凭据是 fake。新建 `provider_payload` fixture 返回 name=Local、presetId=ollama、providerKind=openai-compatible、baseUrl=http://127.0.0.1:11434/v1、apiKey=''、enabled=true、description=''。

```python
def test_connect_allows_zero_models_without_exposing_credentials(model_client, provider_payload):
    result = model_client.post('/api/v1/model-providers/connect', json={
        'provider': provider_payload, 'selectedModels': [],
    })
    assert result.status_code == 201
    data = result.json()
    assert data['models'] == []
    assert data['apiKeyConfigured'] is False
    assert 'apiKey' not in data and 'secretRef' not in data
    assert model_client.get('/api/v1/model-providers').json()['total'] == 1
```

同轮补充：选中模型在第二次发现消失→409且 provider/model 数量均零；新 Key 写失败→无新行；连接更新远端失败→旧地址和旧 credential ref 保持；普通 PUT 带连接字段→422；同名/重复模型→409；直接 POST /model-providers 不作为有效创建入口。测试不得断言响应含明文 Key。

- [ ] **步骤 2：定向运行并确认缺失行为。**

```bash
uv run --directory apps/backend pytest tests/unit/test_model_domain.py tests/unit/test_model_service.py tests/unit/test_model_provider.py tests/integration/test_model_repository.py tests/contract/test_models_api.py -q
```

- [ ] **步骤 3：实现 domain/仓储/凭据顺序。** 实体没有明文 Key；候选调用凭据只存在请求生命周期。仓储 transaction 模式参考 profiles。name 与 modelKey trim 后精确唯一；FK cascade、可空上下文和标签去重。model_credential_cleanup 按规格 §5.2 执行先记意图、后写系统凭据、最后提交引用；删除/替换后清理失败持久保留，不实现无限重试线程。测试逐个插入失败点：凭据写、DB commit、旧凭据删除、启动恢复。

```python
# 凭据命名是每次替换生成新引用，不能覆盖旧条目后再尝试提交数据库。
from uuid import uuid4

def new_model_secret_ref() -> str:
    return f"model-provider/{uuid4()}"
```

ModelService 公开用例为 list/get、preview、connect、update_metadata、update_connection、test_connection、discover、delete_provider、options；任务 5 再加入模型 CRUD/test。ModelRepository 端口提供这些实体的 get/list/add/update/remove 和 cleanup 引用操作；实现留在 SQLAlchemy 文件。ModelGateway 端口仅 discover 与 test_model 两种能力，HttpModelProvider 实现它。端口参数为领域连接值对象及短生命周期 secret，不能传 SQLAlchemy row。

- [ ] **步骤 4：迁移旧目录协议并写协议断言。** 复用旧 provider 构造与归一化函数；改成 `httpx.AsyncClient(transport=..., trust_env=False, follow_redirects=False, timeout=15)`，应用关闭时释放客户端。验证 OpenAI/compatible、Anthropic、Gemini、Qwen 目录路径和 headers；自定义/Ollama 空 Key 无 Authorization；使用 AsyncClient 构造 spy 断言 trust_env=False（MockTransport 请求成功本身不能证明忽略环境代理）；重定向不跟随。MockTransport 逐个模拟 401/403/404/429/5xx/无效 JSON/错误结构/超时/超过8MiB解码体，断言契约码和脱敏。外部等待不持有 SQLite 写事务。

```python
def empty_key_directory(request):
    assert 'authorization' not in request.headers
    assert request.url.path == '/v1/models'
    return httpx.Response(200, json={'data': [{'id': 'sample-chat'}]})
```

- [ ] **步骤 5：注册已实现的十条供应商/目录/options 路由，生成类型并接入任务 4。** 主代理装配共享 store；不支持 OS keyring 或凭据被锁时要允许 app 启动/列表访问，只有需要凭据的操作返回契约错误（注入安全的 unavailable 实现或惰性初始化，禁止生产 memory fallback）。比较长请求前后连接快照和 updated_at，供应商删除返回404、任何较新更新返回409 MODEL_PROVIDER_CHANGED，最终事务内检查，拒绝迟到覆盖（包含名称/启用等metadata）。POST test 失败也持久最近状态；GET discover 不写状态。新 app 不调用真实供应商来生成 OpenAPI。提前在本任务覆盖“候选 Key 已写而 CAS 失败”的清理记录，以及测试失败/成功两个分支的 CAS。

```bash
npm run openapi:generate
npm run openapi:check
uv run --directory apps/backend pytest tests/unit/test_model_domain.py tests/unit/test_model_service.py tests/unit/test_model_provider.py tests/integration/test_model_repository.py tests/contract/test_models_api.py -q
uv run --directory apps/backend ruff check .
uv run --directory apps/backend mypy src
```

- [ ] **步骤 6：与任务 4 一起验收后提交。** 可先提交独立通过的后端提交 `feat: add verified model provider management`；切片完成状态必须等向导真实接口联调。更新来源账本中的实际复制函数与旧测试改动。

## 6. 任务 4：供应商向导与连接编辑切片

**文件：** `R/domains/models/api.ts`、`model.ts`、`provider-catalog.ts`、assets、ProviderLogo、ProviderWizard/三步骤、tests/ProviderWizard.test.tsx、test-utils.tsx；`R/app/query-provider.tsx` 与依赖由主代理接入。

- [ ] **步骤 1：从旧组件测试迁移失败场景。** 定义 `renderModelUi` 测试 helper：独立 QueryClient、retry=false、不共享缓存、注入 ApiClient、返回 userEvent；使用生成 schema 类型检查 fixture。API 通过 `createModelApi(client)` 工厂，JSON写请求显式设置 Content-Type: application/json、JSON.stringify(body)，测试 spy 校验 header 和 body；方法名沿用旧 listProviders/previewConnection/connect/updateProvider/updateConnection/removeProvider/testProvider/discoverModels/testModel/createModel/updateModel/removeModel，额外 getProvider/listOptions。不要复制旧 getOpenApiClient 或 schema.ts。

ProviderWizard 接口固定 `open/onOpenChange/provider? /api/onSaved`，provider 未传为新增，已传为编辑。组件内部调用已注入 api，成功回调返回 ModelProviderRead。至少先断言编辑保留不可点击的旧三步指示、高亮连接信息且不能返回，以及更改连接才切换按钮：

```tsx
await user.clear(screen.getByLabelText('供应商名称'))
await user.type(screen.getByLabelText('供应商名称'), '新名称')
expect(screen.getByRole('button', { name: '保存修改' })).toBeEnabled()
await user.clear(screen.getByLabelText('服务地址'))
await user.type(screen.getByLabelText('服务地址'), 'http://127.0.0.1:11435/v1')
expect(screen.getByRole('button', { name: '测试并保存' })).toBeEnabled()
expect(screen.getByText('选择供应商')).toBeInTheDocument()
expect(screen.getByText('连接信息')).toHaveAttribute('aria-current', 'step')
expect(screen.queryByRole('button', { name: '上一步' })).not.toBeInTheDocument()
```

- [ ] **步骤 2：确认组件测试失败。**

```bash
npm --workspace @autoflow/desktop test -- src/renderer/domains/models/tests/ProviderWizard.test.tsx
```

- [ ] **步骤 3：迁移三步状态机与 Key 草稿。** ModelProviderRead DTO 不能初始化明文 Key。`model.ts` 定义 draft 的 `apiKey` 与 `apiKeyTouched`，初始为空/false；Key 输入的 onChange 才置 touched，不能把 placeholder 当提交值。草稿 reset 只发生在重开或选择另一个预设；返回上一步维持当前规则。

```ts
const connectionChanged =
  draft.presetId !== original.presetId ||
  draft.providerKind !== original.providerKind ||
  draft.baseUrl.trim() !== original.baseUrl ||
  draft.apiKeyTouched
const keyPatch = draft.apiKeyTouched ? { apiKey: draft.apiKey } : {}
```

原配置没有 Key 的 optional 预设保存空值不应构造 Bearer；required 判断 `!touched && original.apiKeyConfigured` 或新输入非空。含 Key 请求体不传给 mutation variables，采用短生命周期调用闭包，结束后 reset、卸载后 gcTime=0；不记录请求体。连接 mutation 开始前 cancel 该供应商 discovery，queryFn 传入 AbortSignal；即使底层请求不取消，也按请求世代丢弃返回，成功后 invalidate。此竞态在本任务写延迟测试。preview 与 final connect 两次请求独立，不保存 preview token；选择模型传完整 ModelInput，但服务端再次校验目录 membership。预设列表/图标复制后登记，保留自定义永远可达及十个常用预设顺序。

- [ ] **步骤 4：覆盖全流程的关键差异。** 成功自动进第三步、零模型保存、全选不受搜索影响、返回重测清空选择、失败保留输入、编辑只改 metadata 不测连接、Key untouched 不发字段、显式清空 optional 发送空串、required 空值阻止请求、请求中锁窗、取消丢弃且无确认、重开恢复服务器值。向导错误在 Modal 内，不发 Toast。

- [ ] **步骤 5：接真实 sidecar 接口验证。** 使用任务 3 的本地远端 fixture +临时 app 数据，完成新增零模型、多模型、失败接入、编辑/取消、连接变更失败和成功；读取真实列表确认无半保存。禁止把测试 helper 放入生产入口。

```bash
npm --workspace @autoflow/desktop test -- src/renderer/domains/models/tests/ProviderWizard.test.tsx
npm run openapi:check
npm run typecheck
npm run lint
```

- [ ] **步骤 6：与任务 3 合并审查后提交。** 提交建议 `feat: preserve legacy provider onboarding and editing`。API 和组件测试、真实本地联调证据一起登记。

## 7. 任务 5：模型编辑、单次测试与本地删除切片

**文件：** 后端 service/provider/http schemas/routes 与 unit/contract；前端 ModelEditor、ModelForm、ModelTestPanel、ModelIdInput、ModelDeleteDialog、tests/ModelEditor.test.tsx、api.ts。主代理重新生成 DTO。

- [ ] **步骤 1：先写 API 与 UI 失败断言。** 模型 CRUD/test 共四条剩余路由；编辑 ID 改变返回契约校验错误；供应商不存在404；重复模型409；删除204且仅本地变化。测试模型不要求本地已创建，不持久测试结果。后端 MockTransport 检查固定提示/16tokens及正文/思考截断。

ModelEditor 接口 `open/onOpenChange/provider/model?/api/onSaved/onRemoved`，model 未传为新建；ID 变化与窗口会话标识共同约束反馈。先写“测试未完成仍能关闭”的测试，不能照搬供应商锁窗：

```tsx
await user.click(screen.getByRole('button', { name: '测试模型' }))
expect(screen.getByRole('button', { name: '保存模型' })).toBeEnabled()
await user.keyboard('{Escape}')
expect(onOpenChange).toHaveBeenCalledWith(false)
// testModel 使用 test-utils 的可控 promise，关闭后才 resolve，不能影响重新打开的窗。
```

该测试使用新增模型；按钮文案已由旧源码核对为新增“保存模型”、编辑“保存修改”，不得统一改写。

- [ ] **步骤 2：确认定向测试失败。**

```bash
uv run --directory apps/backend pytest tests/unit/test_model_provider.py tests/contract/test_models_api.py -q
npm --workspace @autoflow/desktop test -- src/renderer/domains/models/tests/ModelEditor.test.tsx
```

- [ ] **步骤 3：实现后端四条路由与协议生成。** ModelService 增加 create_model/update_model/delete_model/test_model；ModelInput 非秘密字段映射领域。迁移旧测试请求：OpenAI 用 max_completion_tokens，compatible 用 max_tokens，Anthropic messages，Gemini generateContent；不引入 SDK，reasoningPreview 只来自响应。Key 缺失不可推测为无需认证；preset 政策一致。模型新增不依赖发现成功，允许 manual ID；编辑保留 modelKey，不触碰远端目录。

- [ ] **步骤 4：实现 split 组件与字段规则。** ID 编辑只读可复制；候选读取缓存 30 秒且发现失败仍可手输。上下文不猜测；候选返回合法上下文才覆盖，未返回则按旧组件保留当前输入。标签收敛函数保持顺序去重与中英逗号，IME 事件由调用处阻止提交。

```ts
export function mergeModelTags(current: string[], input: string): string[] {
  return [...new Set([...current, ...input.split(/[,，]/)].map(value => value.trim()).filter(Boolean))]
}
```

“运行默认值（可选）”只解释默认行为并编辑 description。ModelTestPanel 只显示当前会话结果；仅实际 reasoningPreview 非空时显示 disclosure。ModelEditor 的 closeDisabled 仅 savePending，test 按钮禁用条件为 invalid ID/testPending/savePending。嵌套移除成功关闭两层，取消保留原 draft。

- [ ] **步骤 5：完整回归并真实联调。** 覆盖中文输入法、标签 Enter/失焦/保存、null上下文/负数/小数/溢出、ID更换清测试、发现失败手输、测试失败不阻止保存、测试晚回不污染、复制只读 ID 成功/失败的内联反馈、目录刷新按钮读取中禁用、候选无上下文保留当前输入、嵌套删除取消和成功。本地 fixture 连通保存→生成测试→编辑→移除，检查没有 Toast、无采样字段。

```bash
npm run openapi:generate
npm run openapi:check
uv run --directory apps/backend pytest tests/unit/test_model_schemas.py tests/unit/test_model_provider.py tests/contract/test_models_api.py -q
npm --workspace @autoflow/desktop test -- src/renderer/domains/models/tests/ModelEditor.test.tsx
npm run typecheck
```

- [ ] **步骤 6：审查并提交切片。** 提交建议 `feat: migrate model editing testing and local removal`；记录协议 fixture 通过与真实线上未验证的区别。

## 8. 任务 6：工作台组装、缓存与异常流程

**文件：** ProviderSidebar、ProviderDetail、ModelDirectory、FeedbackCard、ProviderDeleteDialog、hooks/use-model-management、pages/ModelManagementPage、tests/ModelManagementPage.test；主代理集成 App/app-state/query-provider。

- [ ] **步骤 1：写跨组件失败测试。** 多供应商切换、五列表格、搜索/状态过滤、页头和左栏加号同入口、行测试/更多菜单、两种添加入口、空/加载/错误、启停和删除失效。QueryClient 夹具为每个测试独立实例，默认 retry=false；模型/供应商 fixture 均来自生成类型。

```ts
expect(screen.getByRole('columnheader', { name: '模型' })).toBeInTheDocument()
expect(screen.getByRole('columnheader', { name: '上下文' })).toBeInTheDocument()
await user.click(screen.getByRole('button', { name: '同步并添加' }))
expect(api.discoverModels).toHaveBeenCalledWith(selectedProvider.id)
expect(api.createModel).not.toHaveBeenCalled()
```

- [ ] **步骤 2：运行失败测试。**

```bash
npm --workspace @autoflow/desktop test -- src/renderer/domains/models/tests/ModelManagementPage.test.tsx
```

- [ ] **步骤 3：先完成领域展示组件，再组装页面。** 页面不内联向导、复杂表单或 API fetch；hooks 统一 Query keys 和 mutation 后失效。选中 supplier 删除后落到剩余有效项或空态；搜索导致无匹配时保留与旧代码一致的选择/详情逻辑，不能自行引入 URL 路由状态。

```ts
export const modelKeys = {
  providers: (instanceId: string) => ['model-providers', instanceId] as const,
  discovery: (instanceId: string, providerId: string) => ['model-provider-discovery', instanceId, providerId] as const,
  options: (instanceId: string) => ['model-options', instanceId] as const,
}
```

ModelManagementPage 接收当前实例 `api` 与 `instanceId`；App 保留启动/离线/恢复流程。在最终顶部全局导航注册模型页面，不复制旧项目的项目列表、全局侧栏或 settings router。实例改变清除旧缓存/草稿；模型测试请求依据会话丢弃迟到结果。所有写操作关闭自动重试，discover 禁止聚焦自动刷新。

- [ ] **步骤 4：补一致性回归。** 供应商停用后管理列表仍显示、options排除全部子模型；模型停用只排除自身；重新启用恢复。test失败刷新持久连接状态，discover失败不改状态。provider更新连接后清目录缓存；delete后移除；旧supplier测试不能写新supplier面板。供应商搜索只匹配名称/协议、隐藏条目但不清右区；切换供应商不清搜索/筛选。逐个保留旧页面的CRUD/连接测试/模型行测试互斥按钮条件，编辑窗测试仍独立。表格与 Modal 使用旧布局断点，在窄窗口保持可滚动、不越界。

- [ ] **步骤 5：验证布局与真实页面动作。** 对照三张已确认图片及旧取证截图，检查 1440×1024 主视口与当前应用最小窗口；低于旧 920px 断点按旧 CSS 意图调整左栏位置而非改为横向 Tabs。检查键盘操作、中文 IME 和 reduced-motion。生成图不用于逐像素尺寸测量。

```bash
npm --workspace @autoflow/desktop test -- src/renderer/domains/models src/renderer/app
npm run typecheck
npm run lint
npm run build
```

- [ ] **步骤 6：审查并提交。** 提交建议 `feat: assemble model management workspace with legacy interactions`。只有已接真实本地 API 的页面才算完成。

## 9. 任务 7：跨存储、桌面与跨平台验收

**文件：** 模型测试、`scripts/smoke-desktop.mjs`、`scripts/smoke-model-management.mjs`、`apps/desktop/tests/fixtures/model-provider-fixture.mjs`、source-map、verification、目录文档和 .ai 索引；若需修正实现只修改本模块明确路径。

- [ ] **步骤 1：先补高价值失败场景。** 临时 DB 中注入新凭据写失败、commit失败、旧凭据删除失败；重启应用确认 cleanup 恢复，仍引用的 Key 永不清除。并发让连接测试晚于连接更新/删除返回，必须拒绝旧结果覆盖。后端重启不重放创建或生成 POST。抓取 API/日志/SQLite 文件确认没有合成秘密明文。

```python
def test_options_require_both_provider_and_model_enabled(model_client, provider_with_two_models):
    provider = provider_with_two_models
    model_client.put(f"/api/v1/model-providers/{provider['id']}", json={
        'name': provider['name'], 'description': '', 'enabled': False,
    })
    assert model_client.get('/api/v1/models/options').json()['items'] == []
    managed = model_client.get('/api/v1/model-providers').json()['items']
    assert len(managed[0]['models']) == 2
```

`provider_with_two_models` fixture 通过真实 connect 请求在当前 model_client 中创建两个合成模型，不直接绕过用例插库。

- [ ] **步骤 2：建立 Electron 冒烟。** 按 `scripts/smoke-desktop.mjs` 的现有启动/临时目录/清理方式新增模型脚本；同步把旧 smoke 依赖占位页正文的就绪判断改为 sidecar ready+health，保留退出监管断言。fixture 用 Node `http.createServer`，只监听127.0.0.1，OS分配空闲端口，提供 `/v1/models` 与 `/v1/chat/completions`；含可控401/延迟/目录变化。脚本在 finally 关闭 Electron、sidecar、fixture，测试数据库不能是用户目录。不复用以前失败的固定端口假设。

- [ ] **步骤 3：定向通过后运行本切片最终质量检查。**

```bash
uv run --directory apps/backend pytest -q
uv run --directory apps/backend ruff check .
uv run --directory apps/backend mypy src
npm run openapi:check
npm test
npm run typecheck
npm run lint
npm run test:structure
npm run build
npm run smoke:sidecar
npm run smoke:desktop
node scripts/smoke-model-management.mjs
```

该任务新增 schema/路由/装配/依赖，需验证后端与 Electron 打包输入：

```bash
npm run backend:build
npm run package:dir
```

不要把 `mypy src` 称作 strict；当前仓库未启用 strict。发现既有不相关失败记录基线和具体错误，只修本次引入的问题，不掩盖失败或扩大重构。

- [ ] **步骤 4：记录平台与外部证据。** 在可用 macOS 与 Windows 主机/既有CI分别运行迁移、启动、菜单焦点、IME、Keychain/Credential Manager 合成临时条目往返（结束删除），记录OS/架构/命令。某平台不可用时标明未验证，不能以 mock Windows 后端或 macOS 构建替代。真实供应商仅在可用且已获授权的测试凭据下验证目录及短生成；未验证品牌清晰列出，不自动读取旧数据库密钥或账户。

- [ ] **步骤 5：完成逐条需求验收与文档。** verification 按原型交互矩阵逐行记录结果与证据，包含 loading/empty/error/success、第三步零选择、编辑分支、嵌套确认、Key缺失与补偿；source-map 给每个实际复制文件填写来源HEAD+hash+目标+改动+资源来源。更新本计划勾选和 .ai 状态；只有真实通过的项才标完成。

- [ ] **步骤 6：最终审查并提交。** 提交建议 `test: verify model management parity and desktop lifecycle`。最后报告变化、验证、尚缺的平台或外部服务证据；用户未要求发布，不发布安装包或发送外部消息。

## 10. 覆盖与完成条件

| 产品/工程约束 | 主要任务 | 验收证据 |
| --- | --- | --- |
| 原型视觉、旧主从关系、局部侧栏、表格/菜单 | 2、6 | 组件测试 + Electron截图/键盘操作 |
| 三步接入、返回、全选、零模型、失败保留 | 3、4 | API契约 + Wizard测试 + 临时数据联调 |
| 编辑连接签名、Key保持/替换/清空、普通更新限制 | 1、3、4 | schema/API及交互断言 |
| 模型字段、标签、只读ID、上下文、默认说明 | 1、5 | schema + ModelEditor + 复制测试 |
| 连接与生成测试差异、错误/截断、禁空Bearer | 3、5 | MockTransport断言 + 本地fixture |
| 关闭锁、取消丢弃、嵌套确认、焦点 | 2、4、5、6 | 用户事件和真实Electron回归 |
| 唯一性、启停、options、删除、无旧数据迁移 | 3、5、7 | SQLite迁移/约束/契约 |
| 秘密存储、失败补偿、迟到请求、sidecar重启 | 3、6、7 | 故障注入 + 桌面实例恢复 |
| Windows/macOS、来源可追溯、无虚构线上通过 | 7 | 平台记录与来源账本 |

计划交接方式采用用户已提出的子智能体并行协作；无需再次选择执行模式。当前仅交付文档，确认进入实施后，从任务 1、2 的有界并行开始，不先搭页面再补控件，不将本计划全部内容一次交给一个代理盲目执行。
