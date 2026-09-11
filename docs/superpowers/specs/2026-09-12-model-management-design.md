# 模型管理设计规格

- 日期：2026-09-12
- 状态：proposed；原型、旧布局与旧交互已获用户确认，本规格与实施计划供开发审查，尚未开始模型业务实现。
- 类型：架构级功能迁移；本轮输出为规格、API 契约、实施计划与源码复用记录。
- 产品依据：[已确认原型与交互矩阵](../../prototype/model-management/model-management-interactions.md)。
- 开发依据：[API 契约](../../references/model-management-api-contract.md)、[实施计划](../plans/2026-09-12-model-management-implementation.md)、[基础设施与来源快照](../../../.ai/knowledge/2026-09-12-model-management-implementation-readiness.md)。
- 事实置信度：高（本地源码、旧应用取证）；外部供应商当前线上兼容性未验证。

## 1. 目标与范围

把旧项目的模型供应商管理和本地模型目录迁入新 AutoFlow。保持用户已确认的页面布局、字段、入口、按钮、反馈位置和关闭行为；允许参考和复制旧源码中的状态机、请求构造、响应解析及测试场景，按新项目分层和组件约束重新组织。

本模块包含供应商预设选择、连接预览、接入与编辑、连接测试、远端目录发现、手动或候选添加模型、模型编辑与单次测试、启停、删除和可调用模型选项查询。连接测试仅检查模型目录；模型测试才实际发送一次简短生成请求。

不迁移旧数据，不实现项目管理、工作流执行或模型消费页面；不增加默认模型、能力徽章、价格、余额、额度、长期健康统计、自动目录同步或采样参数表单。`/models/options` 只提供原有启用过滤契约，不扩展编排运行时。

## 2. 已确认的用户界面

### 2.1 页面与组件组合

应用级顶部导航下为“模型管理”及“添加供应商”。主工作台保持桌面 `278px + minmax(0,1fr)` 双栏：左边选择供应商，右边管理该供应商及其模型。这里的供应商栏是已确认的业务选择入口。不得改为横向 Tabs、全宽统一模型表或多供应商同时展开。

右区保持身份、最近连接状态与时间、说明、连接事实、`FeedbackCard`、模型目录工具栏及五列表格的顺序。五列为模型、标签、上下文、状态、操作。行内“测试”，更多菜单中编辑、启停和删除。未知上下文显示缺省标记，不猜测数值。连接状态只描述最近一次检查，不宣称实时在线。

供应商搜索只过滤左栏；模型搜索匹配名称、ID、标签，状态筛选为全部、启用、停用。供应商或模型为空、搜索无结果、列表加载及读取失败分别呈现原有状态。读取失败不能渲染成“没有数据”。切换供应商清除上一供应商的临时模型测试反馈。页面级连接测试/模型行测试/CRUD 沿用旧互斥保护，不套用到编辑窗独立测试；按钮禁用条件逐个对照旧 ModelsPage。供应商搜索匹配名称与协议，仅隐藏左栏条目，不清空右侧当前选择；搜索和模型状态筛选切换供应商后继续保留。

“同步并添加”使该供应商发现缓存失效后打开模型添加窗；“添加模型”直接打开同一窗口。两者都不会自动修改本地目录。目录请求失败仍允许手输模型 ID。

### 2.2 供应商新增与编辑

新增固定三步：选择供应商 → 连接信息 → 选择模型。步骤指示不可点击跳步。沿用旧目录的十个常用预设及一个独立自定义入口；默认 DeepSeek；预设数据、别名和图标来自旧 `provider-catalog.ts`。本地 Ollama、自定义兼容接口允许无 Key；其余预设要求 Key。协议值保持 `openai / anthropic / gemini / openai-compatible / custom`。

| 阶段 | 操作与状态规则 |
| --- | --- |
| 选择预设 | 搜索只过滤常用列表；自定义入口独立存在。选择预设替换连接表单，清空 Key，启用默认 true。此时不请求远端。 |
| 连接信息 | 名称、协议、Base URL、API Key、描述、启用。名称和地址非空且满足 Key 政策后才能测试。返回第一步保留当前会话表单；另选预设则替换。 |
| 连接预览 | 只读取目录、不保存。失败保留输入并内联显示原因；成功自动进入第三步。每次成功预览都清空模型选择。 |
| 选择模型 | 搜索、复选框、全选；全选针对全部已发现模型，不限于搜索结果。零选择按钮“保存供应商”；N 个选择“保存供应商和 N 个模型”。不增加跳过按钮。 |
| 最终保存 | 再次读取目录，校验所有选择后一次提交供应商及本地模型。返回修改连接会清除预览，再次测试重新开始选择。 |
| 编辑 | 直接进入连接信息，仍显示旧三步指示并高亮连接信息；不能进入第一/第三步，没有返回预设按钮。只改名称、说明、启用时“保存修改”；改协议、地址、预设或 Key 时“测试并保存”。后者验证成功才替换配置。 |

编辑 Key 保留同一个密码输入控件。响应只返回 `apiKeyConfigured`；打开时输入为空，以“已配置，留空保持原凭据”的占位表达原状态。未触碰输入时省略 `apiKey`，触碰后非空为替换，触碰后清空为明确移除（仅可选 Key 预设）。不加入额外清除按钮、密钥读取接口或关闭确认。必填校验必须区分“未触碰且已有凭据”和“已触碰但为空”。连接签名不再依赖读取真实 Key。

新增预览、最终保存和编辑提交期间锁住关闭与重复提交。取消、Escape、遮罩和 X 在非锁定时直接关闭并丢弃草稿；重新打开使用最新服务端值，没有未保存确认。

### 2.3 模型新增、编辑与测试

保持大尺寸 split Modal：约 285px 左侧摘要、供应商标识和测试，右侧字段。新增模型 ID 可搜索发现结果，也可键入并确认；保留“刷新模型目录”按钮，读取中禁用，失败提示仍可手动输入。编辑时 ID 只读且可复制；复制成功内联显示“模型标识已复制”，失败显示“复制未完成，请选中标识手动复制”。字段为显示名称、模型 ID、可空上下文、标签，以及默认折叠的“运行默认值（可选）”。折叠区只含供应商默认参数说明和使用说明输入，不出现温度、top-p 等控件。

选择候选模型按旧规则补全显示名称和有证据的上下文；候选没有返回上下文时，按旧组件规则保留当前上下文草稿（不自动清空）；该输入不代表远端证明。名称、ID、标签、说明在当前窗口管理；模型 ID 改变清除该 ID 的测试反馈。新增保存按钮为“保存模型”，编辑为“保存修改”。保存新模型默认启用，编辑保留原启用值，窗口内不增加启用开关。

标签在 Enter、失焦、保存时按中英文逗号拆分，trim、去空、保持顺序去重；中文输入法组合期间 Enter 不提交。上下文空值为 null，非空仅接受正安全整数 `1..9007199254740991`。

测试不作为保存前提。测试按钮在 ID 空、测试中或保存中禁用；**模型测试中仍允许保存和关闭，只有保存进行中锁窗**。结果展示本次延迟、正文或“未返回正文”，仅实际有思考片段时显示“查看本次返回的思考内容”。关闭、切换模型或供应商后，迟到结果不得更新新窗口。

### 2.4 删除、反馈与焦点

| 场景 | 确认与结果 |
| --- | --- |
| 删除模型 | 标题“删除模型”，说明从目录移除该模型，仅影响本地；按钮“取消 / 确认移除”，处理中“正在移除…”。 |
| 编辑中移除 | “从目录移除”打开叠加确认；父编辑窗保持挂载。取消只关闭确认，保留草稿并回焦点；成功关闭两层并刷新。 |
| 删除供应商 | 标题“删除供应商”，说明同时删除本地模型，历史记录不被改写；“取消 / 确认删除”，处理中“正在删除…”。不显示虚构工作流引用数量。 |
| 操作反馈 | 页面 `FeedbackCard` 或窗口内联错误、测试结果；保存成功关闭窗口并刷新。模型管理不使用 Toast。 |

用现有 Radix `Dialog` 组合普通确认层，保留未锁定时 Escape、遮罩、X 关闭；不得直接换成屏蔽遮罩关闭的 AlertDialog。支持嵌套焦点、快速关开、打开者被删除后的合理焦点回退和键盘菜单。具体行为以旧 `modal.tsx` 和 `modal-focus.test.tsx` 对照验证。不得把浏览器配置模块的未保存确认、Toast 或一律请求期间锁窗规则套用到本模块。

视觉使用现有暖灰、黏土棕 tokens 和 Tailwind，遵循 shadcn/ui 可组合控件结构。动效复用现有设计令牌及 reduced-motion；不能增加会改变操作时机的等待动画或自动消失反馈。原型外部注释不进入产品。

## 3. 当前基础与技术选择

| 项目 | 已核对状态 | 本模块决定 |
| --- | --- | --- |
| 模型领域 | 前后端相关目录仅骨架 | 在正式 `domains/models` 和后端同名领域落地。 |
| UI | desktop shared 已有 Radix Dialog/Input/Button 等、Tailwind 4 tokens | 复用；补确实缺少的基础控件及领域组合。`packages/ui` 仍空，不在本模块复制第二套 UI 或扩大为全仓组件迁移。 |
| 服务状态 | App 当前主要是 sidecar 健康页，导航另有并行草稿 | 装配负责人接入最终顶部导航；模型页面不私建第二个应用入口或路由器。 |
| 查询层 | 旧模型实现依赖 TanStack Query 5；新 desktop 未安装 | 加入 `@tanstack/react-query` 5 系列复用旧查询/变更语义；缺少的菜单 primitive 使用同族 Radix DropdownMenu。不引入 Router、Zustand 或另一套 HTTP 客户端。 |
| 远端 HTTP | 已安装 httpx | 使用现有依赖和 MockTransport 测试；不安装各供应商 SDK。 |
| 凭据 | CredentialStore、SystemCredentialStore 和 fake 平台测试存在，尚未装配到应用 | 统一注入，新增模型凭据命名包装；不重新实现平台凭据存储。 |
| 错误与类型 | 后端有 envelope，前端会丢弃正文；401 仍是旧 detail；生成文件落后于路由 | 前置修复解析/401/204，并从真实 FastAPI OpenAPI 重新生成唯一类型文件。 |

平台保持 Windows x64、macOS arm64/x64。模型业务不判断操作系统、不直接操作本地密钥文件、不把浏览器代理模式当模型 API 代理。模型请求默认直接连接，`trust_env=False`，不静默继承启动 shell 的代理变量。

路径以 [PROJECT_STRUCTURE](../../PROJECT_STRUCTURE.md) 为准。本模块具体路径以本规格及计划为准，取代早期迁移总规格中冲突的 `apps/sidecar` 等路径；这不表示全仓旧文档或其他模块已完成迁移。

## 4. 分层与组件边界

```text
ModelManagementPage
  ├─ ProviderSidebar / ProviderDetail / ModelDirectory
  ├─ ProviderWizard → CatalogStep / ConnectionStep / ModelsStep
  ├─ ModelEditor → ModelTestPanel / ModelForm
  └─ ModelDeleteDialog / ProviderDeleteDialog
       ↓ domain hooks / domain api.ts / generated DTO
       ↓ shared ApiClient（sidecar token）
HTTP adapters → ModelService → domain/models
                                ↑ repository / credential / provider ports
                    SQLAlchemy / CredentialStore / HttpModelProvider
bootstrap 负责依赖装配
```

- `domain/models`：供应商、模型、连接候选、发现和测试结果、唯一性与可用性规则；无 FastAPI、SQLAlchemy、httpx、keyring 依赖。
- `application/models/service.py`：预览、接入、编辑、测试、删除、选项和跨存储提交顺序；不得让 HTTP 路由承担事务。
- `providers/model/http.py`：协议分支、地址构造、固定测试请求、归一化、超时及远端错误；纯辅助函数优先，不为每个品牌建立空类。
- `infrastructure/database/model_providers.py`：具体仓储和事务、凭据清理记录；ORM 不传入 provider 或领域。
- `infrastructure/credentials/model_provider.py`：复用通用 CredentialStore，命名空间 `model-provider/<随机 UUID>`，按需读取短生命周期凭据。
- `adapters/http/model_schemas.py` 与 `models.py`：camelCase DTO、验证、序列化及路由委托。`ApiModel` 提取到 HTTP 共享 `schemas.py`，不跨领域导入 profile schema。
- 领域组件只接受本领域数据和动作；基础输入、Modal shell、菜单等放 desktop shared，供应商 logo、三步流程、模型测试不进入通用 UI。
- `api.ts` 引用 `shared/api/generated.ts`，不手写另一套服务端 DTO；`model.ts` 仅放 UI 派生状态和草稿。

本次复用方案保留现有 desktop shared 作为唯一实际 UI 实现位置；将来整体迁入 `packages/ui` 属于独立受控改动。不能因 packages/ui 还未注册就暂写一次性页面控件。

## 5. 数据、事务与凭据

### 5.1 表与规则

新增 `model_providers`、`models`、`model_credential_cleanup`。供应商表保存名称、预设、协议、Base URL、secret_ref（可空、唯一）、启用、描述、最近连接状态/时间/延迟/消息及创建更新时间。模型表保存 provider_id、model_key、display_name、tags_json、context_window、enabled、description 和时间。清理表只保存随机 secret_ref 与创建时间，无秘密正文。

供应商名和同供应商模型 ID 在 trim 后按大小写敏感唯一；模型唯一约束为 `(provider_id, model_key)`。批量接入与手动添加采用相同规则，纠正旧接入 casefold 与数据库精确匹配不一致。模型编辑不能修改 ID；服务端同样拒绝更换，不依赖只读输入保证。删除供应商通过外键级联本地模型；管理接口保留停用对象，options 同时要求供应商和模型启用。

使用当前 Alembic 单 head 追加迁移，不改已有 `0001_browser_resources.py`。不读取旧 SQLite、旧明文 Key 或兼容旧数据。实际编号由集成负责人核对当前 head 后串行登记。

### 5.2 提交顺序

SQLite 与系统凭据存储没有跨存储事务，不能宣称它们同时 ACID 提交。这里保证业务列表的原子可见性，并用一张持久清理表补偿凭据残留：

1. 接入和连接更新先使用内存中的候选配置完成远端验证；接入再次验证全部选中模型。远端期间不占用 SQLite 写事务。
2. 新凭据使用新的随机引用。先提交该引用的清理记录，再写系统凭据；写入失败保留旧配置并返回可恢复错误，不降级到明文。
3. 单个 SQLite 事务创建/更新供应商及其模型、替换 secret_ref、移除新引用的清理记录，并为旧引用加入清理记录。事务失败不出现半个供应商，原凭据引用不变。
4. 提交后删除当前命令待清理的旧/失败引用；失败保留清理记录。启动时重试持久记录；每次删除前核对引用已不被任何供应商使用。运行中不全表扫描清理其他命令的候选引用。
5. 删除供应商时，供应商、本地模型删除与旧凭据清理记录同一事务。逻辑删除成功返回 204；操作系统临时拒绝清理不让已删除对象重新出现，记录留待重启恢复。没有独立后台任务页面或虚构清理完成状态。

每个长请求捕获供应商连接快照（协议、地址、预设、secret_ref）和 updated_at，写回前在同一事务比较当前记录；删除返回 404，记录已更新返回 409 MODEL_PROVIDER_CHANGED，不把旧测试结果写到新连接或覆盖较新的名称/启用状态。单进程命令的提交临界区串行，远端请求不持有该锁；测试无需引入任务队列或全局版本系统。缺少凭据、凭据后端不可用或异常响应使用契约错误，页面仍能列出、编辑和删除已有配置。

### 5.3 凭据与错误边界

读取 DTO 只含 `apiKeyConfigured`，不含 `apiKey`、`secretRef` 或掩码伪造的秘密值；写 DTO 的 apiKey 标记 writeOnly。必填与可选政策在后端再次校验。普通供应商更新只接收名称、说明、启用，连接字段走验证更新接口。

只允许 http/https 地址，允许 localhost、局域网和自定义域；拒绝 userinfo、fragment、内嵌认证查询值。模型标识拼接 URL 时正确编码。`follow_redirects=False`，重定向作为可操作错误，避免将凭据转发到另一个地址。响应 endpoint、日志、持久 lastCheckMessage 和 error details 不含 Key、Authorization 或原始远端异常正文。

## 6. 远端协议与接口边界

完整 14 条内部路由、DTO、校验和错误以 [API 契约](../../references/model-management-api-contract.md) 为单一基准。保留旧 UI 实际使用的路由，并提供单供应商读取与 options；不提供旧 UI 未用且可绕过接入验证的直接创建接口。

远端实现参考旧 `model_provider_service.py`：OpenAI 及兼容协议读取 models、测试 chat/completions；Anthropic 使用模型目录和 messages；Gemini 使用 models 与 generateContent；通义千问保留目录路径改写。旧供应商链接、版本头和请求参数是迁移源码基线，并非本轮访问官方接口后的兼容认证。

目录请求超时 15 秒；模型测试超时 30 秒。测试提示“只回复 OK”，输出限制 16 tokens；解码后的响应体最多 8 MiB，超限用契约的响应无效错误；正文和思考预览分别最多 240、2000 字符，绝不伪造无正文为正常文本。空 Key 的可选接口完全省略认证头。外部目录不添加分页 UI 或后台全目录任务；如远端明确返回截断，应如实保留错误/消息边界，不声称已发现全部远端模型。

`POST .../test` 的成功和失败都记录最近连接检查；`GET .../models/discover` 不改变该状态；模型生成测试不持久健康结果。再次连接失败不覆盖旧有效配置。新错误 envelope 保持 `{error:{code,message,details,requestId}}`，包括 sidecar 401；客户端同时正确处理 204 无正文。

## 7. 前端状态与缓存

- TanStack Query 只管理服务端列表、远端候选、查询和变更状态；草稿、步骤、搜索、筛选、展开、选择和临时测试放在组件/领域 hook。
- 查询 key 为 `['model-providers', instanceId]`、`['model-provider-discovery', instanceId, providerId]`、`['model-options', instanceId]`。重启 sidecar 后重新建立客户端并清除旧实例缓存和临时 Key。
- 发现 `staleTime=30000`、`retry=false`，不因窗口聚焦自动调用外部服务。写操作和测试不自动重试，避免重复创建或生成请求。含 Key 的向导 mutation 不把请求体放入 variables/cache；请求完成 reset，卸载后 gcTime=0，不保留含秘密的闭包或快照。
- 供应商、模型 CRUD 及启停刷新管理列表和 options；连接变更开始前 cancel 对应 discovery query，通过 AbortSignal 或请求世代隔离旧结果；成功后再使该供应商发现缓存失效；供应商删除移除其缓存；连接检查成功/失败均重新读取管理状态；单次模型测试不刷新为持久健康。供应商名称也出现在 options 中，因此普通更新和连接更新均使 options 失效。
- 搜索不向远端请求。中途关闭模型测试窗可取消本地观察或 AbortSignal，但不得宣称远端请求已取消/退款；迟到结果按窗口会话和 provider/modelKey 丢弃。
- 首次加载、空态、错误态与有数据时刷新分开。调用失败留在对应 FeedbackCard/内联区域，保留可修复表单和再次操作入口。

## 8. 旧代码复用映射

来源根：`/Users/zhangtiancheng/Documents/projects/browser-automation/autoflow-desktop`。审查时 HEAD 为 `324748abe7095f085b4ffb9467be9cb5c8851a5c`；部分大文件有工作树修改，实际阅读版本和哈希见[来源快照](../../../.ai/knowledge/2026-09-12-model-management-implementation-readiness.md)。不能用 HEAD 冒充全部工作树内容。

| 旧路径 | 新目标（相对对应源码根） | 复用方式 |
| --- | --- | --- |
| renderer/pages/ModelsPage.tsx | renderer/domains/models/components、hooks、pages | 拆出供应商栏、详情、表格、确认与状态组合；保持操作顺序和文案。 |
| renderer/features/models/ProviderWizard.tsx | domains/models/components/ProviderWizard.tsx + 三个步骤组件 | 复用状态转移和按钮条件；重写秘密初始化与签名、使用生成 DTO。 |
| renderer/features/models/ModelEditor.tsx | components/ModelEditor、ModelForm、ModelTestPanel | 复用字段、候选、标签及测试规则；阻止过期结果污染。 |
| renderer/features/models/provider-catalog.ts、ProviderLogo.tsx、assets/model-providers | models/provider-catalog.ts、components/ProviderLogo.tsx、assets | 复用预设和现有图标，保留来源说明；不新增品牌。 |
| renderer/features/models/model-api.ts | models/api.ts、hooks/use-model-management.ts | 复用请求职责和失效场景，改接新 ApiClient 与生成类型。 |
| renderer/features/models/models-page.css | 领域组件 Tailwind 类 | 复用布局与断点意图，不复制全局旧主题。 |
| renderer/components/ui/modal.tsx | shared/components/Modal.tsx 与现有 ui/dialog.tsx | 复用焦点回退场景与测试，保持新 UI 基础控件唯一。 |
| backend/src/autoflow/model_provider_service.py | providers/model/http.py | 复用请求构造与解析函数，去 ORM 依赖，修空认证头、代理、重定向和错误泄密。 |
| backend/src/autoflow/api.py、schemas.py、models.py | application/models、domain/models、http/model_schemas、database/model_providers | 迁移规则与非秘密字段；不复制全局路由大文件和明文 ORM。 |
| 旧模型前后端测试 | 新 unit/integration/contract 与领域组件测试 | 迁移断言场景，删除明文回显预期；旧数据库兼容迁移测试不迁入。 |

实施时在 `docs/migration/model-management-source-map.md` 按实际复制文件记录来源路径、HEAD/工作树哈希、目标、改动、保留依赖和原有许可证/资源来源。该账本在真正复制时填写；本轮只保存来源快照，不虚构已迁移文件。

## 9. 验收与开发顺序

| 编号 | 必须验证 | 实施任务 |
| --- | --- | --- |
| M01 | 生成契约、结构化错误、204、401、无秘密回显 | 1、3、7 |
| M02 | 控件键盘/焦点、布局、反馈位置、不新增 Toast/关闭确认 | 2、4、5、6 |
| M03 | 三步接入、零模型、重新发现、原子保存和失败保留 | 3、4 |
| M04 | 编辑按钮分支、凭据保持/替换/清除、普通更新不能绕过验证 | 3、4 |
| M05 | 手工候选添加、标签/上下文、测试/保存锁差异、叠加删除 | 5 |
| M06 | 目录发现与连接测试副作用区别、协议、错误、单次生成 | 3、5 |
| M07 | 启停、唯一性、级联本地删除、双重 enabled options | 3、5、6 |
| M08 | 凭据补偿、重启、过期请求、跨平台运行与交互回归 | 3、6、7 |

先完成可复用组件及 API 边界，再组装页面。任务 1、2 的有界部分可并行；随后每条切片后端契约、用例、组件、真实接口联调和测试一起交付。主代理负责共享文件、迁移 head、装配、生成 DTO 和最终审查；gpt-5.6-sol 可负责有界后端、组件和测试任务。

验收不把 MockTransport 等同线上服务，不把 macOS 构建等同 Windows 验收。最终需记录实际平台、供应商、本地夹具、版本及运行结果；无法取得的真实平台/供应商证据明确列出。既有八张旧应用截图与源码提供交互基线，不是新实现的通过证据。

本轮验证只针对文档、来源、相互引用及需求覆盖，不运行或声称通过尚不存在的模型业务测试。用户确认实施计划后再进入业务开发。
