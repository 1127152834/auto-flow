# 浏览器管理 实现计划

**执行状态（2026-09-12）：** 用户已授权实施，任务 1–12 及最终修复已完成，独立定向复审 PASS。最终生产修复 `3df5609`；[验收记录](../../migration/browser-management-validation.md)，[审查归档](../../../.ai/sessions/browser-management-review/README.md)。下列勾选表示任务实现与等价验证闭环，原命令示例保留；实际运行命令、计数与平台限制以验收记录为准。Windows/macOS Intel 等待 CI，真实 License 未验证。

> **面向 AI 代理的工作者：** 必需子技能：使用 subagent-driven-development（推荐）或 executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在 Windows/macOS 的 AutoFlow 中交付可持久化的浏览器配置管理，以及从配置表单进入的 CloakBrowser 内核管理弹窗，完成前后端真实闭环。

**架构：** 沿用 `apps/backend/src/autoflow` 的 domain/application/adapters/infrastructure/providers 分层与 `apps/desktop/src/renderer/domains`。共享 shadcn/ui 控件先完成，领域组件随后完成，页面最后组合；HTTP 契约生成前端类型，内核长任务使用受监管的独立 Python 工作进程和 SSE。内核是独立后端领域，但没有独立前端页面或导航。

**技术栈：** Python 3.11、FastAPI/Pydantic、SQLAlchemy 2/Alembic/SQLite、CloakBrowser wrapper 0.5.9（旧项目已锁版本作为迁移起点）、React/TypeScript、shadcn/ui/Radix、Tailwind、TanStack Query、React Hook Form、Zod、Vitest/Testing Library、pytest、Electron、PyInstaller。

**规格：** `docs/prototype/browser-management/browser-management-interactions.md` 与同目录 `browser-management-overview.png`；架构依据为 `docs/architecture/README.md` 和 `docs/PROJECT_STRUCTURE.md`。本计划中的明确行为裁决优先于生成图中的示例文本。全模块旧规格 `docs/superpowers/specs/2026-09-11-autoflow-feature-migration-design.md` 仅保留背景参考，其中 `apps/sidecar`、根级 services 和独立内核页面设想已被实际目录基准和本次用户决策替代。

## 全局约束

- 计划编写阶段不启动业务代码；本文件已获得用户执行确认，实施结果见上述执行状态。
- Windows：x64；macOS：Apple Silicon 和 Intel 分别构建。
- Python `>=3.11,<3.12`；保留现有 sidecar 随机 loopback 端口、实例 token、父进程监管和服务恢复。
- 不兼容或导入旧数据；不修改旧项目源码或用户已有数据目录。
- 不实现浏览器启动/停止、工作流、项目、代理管理页面、模型页面、设置页面或 WebRPA 集成。
- 无独立内核路由；无模块资源侧栏；无表单左侧步骤向导。表单为横向四标签页、双列字段、固定页脚。
- Modal 150ms 淡入并上移不超过 8px；Toast 150ms 淡入、2.6 秒后淡出；进度 300ms linear；尊重 reduced-motion。
- 页面依赖领域组件，领域数据只经 shared API；renderer 不读文件、不启动子进程、不拼接系统路径。
- 每个任务完成测试闭环和独立提交；共享文件与锁文件只有主代理修改。
- 现有未提交草稿和侧对话目录骨架不可整体 reset/stash/覆盖；先记录精确基线，再按任务替换相关内容。
- 继续在用户指定 checkout `/Users/zhangtiancheng/Documents/projects/autoflow` 规划和执行；不为文档工作另外建立空 worktree。隔离任务只在不丢失该基线的前提下进行。

## 0. 已核实基线与范围裁决

核对日期：2026-09-12。旧仓库 HEAD：`324748abe7095f085b4ffb9467be9cb5c8851a5c`；旧仓库可能另有未提交修改，任务开始时记录所参考文件的工作区 hash，而非宣称 HEAD 就包含所有读取内容。

1. 新后端当前只有健康/认证/路径基础，无 profiles/kernel API 或数据库实现。目录占位不代表业务存在。
2. 新 renderer 有未提交 `features/profiles/profile-workspace.tsx`、导航与 UI 草稿；正式目标为 `domains/profiles`，清除被替代草稿只在正式页面集成通过后执行。
3. 旧 `ProfilesPage.tsx` 实际包含创建、编辑、复制、重新生成指纹和删除；没有启用/草稿状态、批量删除或导入。正式列表不制造这些能力。搜索为客户端名称/描述过滤，页大小 10；过滤只按真实代理模式 none/proxy/pool，不引入配置启用状态。
4. 图片中的版本号、哈希样式指纹、下载次数、公开版 Preview、同时登录与退出按钮均非业务契约。指纹为服务端维护的整数；Wrapper 版本只在弹窗摘要出现；全部发布信息来自 provider。
5. 列表和表单沿用旧字段语义；未保存确认、内核弹窗入口、下载取消是这轮批准的增强，不冒称旧接口已支持。
6. 代理资源当前不存在。本轮提供真实 SQLite 支撑的选项查询、引用校验和最小资源表，不做代理 CRUD/检测/导入。空库显示“暂无可用代理/代理池”，不可提交伪造 ID；非空选择通过测试夹具验证。生产中创建代理资源需要下一代理模块切片，本轮不宣称该能力已交付。
7. 图和文字冲突时：用户明确要求 > 本计划行为规则 > 原项目已核实能力 > 生成图装饰。上述裁决在任务 1 同步写入交互说明。

## 1. 文件职责与分工边界

以下均为仓库相对路径；新包目录包含必要 `__init__.py`，不建立空的其他业务领域实现。

| 文件/文件组 | 职责 |
|---|---|
| `apps/desktop/src/renderer/shared/components/ui/{button,input,textarea,select,checkbox,switch,tabs,dialog,alert-dialog,tooltip,progress,skeleton}.tsx` | shadcn/Radix 基础控件；本轮仅在 renderer 使用，不注册没有第二消费者的 UI workspace |
| `apps/desktop/src/renderer/shared/components/{FormField,ResourceState,Toaster}.tsx`、`shared/lib/cn.ts`、`styles/index.css` | 字段错误、加载/空/失败、Toast 和暖灰设计令牌 |
| `apps/backend/src/autoflow/domain/profiles/{models,ports,errors}.py` | 配置值对象、仓储/内核/代理/数据目录端口、领域错误 |
| `apps/backend/src/autoflow/application/profiles/service.py` | 创建、读取、更新、复制、指纹更新、删除用例 |
| `apps/backend/src/autoflow/infrastructure/database/{session,models,profiles,proxy_options}.py`、`migrations/env.py`、`migrations/versions/0001_browser_resources.py` | 连接、事务、表、仓储、代理选项、首个 Alembic 迁移 |
| `apps/backend/src/autoflow/infrastructure/filesystem/profile_data.py` | 配置浏览器数据的安全暂存删除/恢复/清理 |
| `apps/backend/src/autoflow/adapters/http/{errors,profile_schemas,profiles,proxy_options,kernel_schemas,kernels}.py` | 明确请求响应、校验和路由，无直接 SQL |
| `apps/backend/src/autoflow/domain/kernels/{models,ports,errors}.py`、`application/kernels/{service,operations}.py` | 版本/安装状态、默认内核、License、任务状态和取消 |
| `apps/backend/src/autoflow/providers/kernel/{cloakbrowser,catalog,worker}.py` | wrapper 隔离、release 转换、独立下载/License worker |
| `apps/backend/src/autoflow/infrastructure/{credentials/system_store,process/kernel_worker,events/kernel_events,database/kernel_settings}.py` | OS 凭据、子进程监管、任务事件、默认项/任务持久化 |
| `apps/backend/src/autoflow/adapters/events/kernels.py` | 带 token 的 SSE 状态快照，断流恢复 |
| `apps/backend/src/autoflow/bootstrap/{app,kernel_worker}.py`、`__main__.py` | 装配、lifespan、冻结可执行文件 worker 分支 |
| `apps/desktop/src/renderer/shared/api/{client,types,generated,events}.ts`、`app/ApiProvider.tsx` | 204/错误解析、生成类型、认证 SSE 和会话级 QueryClient |
| `apps/desktop/src/renderer/domains/profiles/{api,hooks,form-schema,presets}.ts` | 配置请求、缓存、纯表单约束与预设 |
| `apps/desktop/src/renderer/domains/profiles/components/{ProfileList,ProfileFormDialog,BasicFields,EnvironmentFields,KernelProxyFields,AdvancedFields,ProfileActionDialog,UnsavedChangesDialog}.tsx` | 业务组件；新建/编辑复用；无裸 fetch |
| `apps/desktop/src/renderer/domains/profiles/pages/BrowserManagementPage.tsx` | 单一列表页、弹窗组合、焦点恢复 |
| `apps/desktop/src/renderer/domains/kernels/{api,hooks}.ts`、`components/{KernelManagerDialog,LicensePanel,KernelReleaseList,KernelOperationStatus,DeleteKernelDialog}.tsx` | 内核 API/状态及弹窗内容，无 pages 目录 |
| `apps/desktop/src/main/ipc/kernel-paths.ts`、`src/preload/index.ts` | 仅暴露 `revealKernel({edition,version})`，不接受任意路径 |
| `apps/desktop/src/renderer/app/{App,profile-workspace-nav}.tsx` | 接入页面并保留恢复；移除独立内核入口 |
| `scripts/smoke-browser-management.mjs`、`.github/workflows/ci.yml`、`scripts/build-backend.mjs` | 开发/打包 E2E、资源收集、三平台验证 |

测试放置：后端 `tests/unit/test_profiles.py`、`test_profile_validation.py`、`test_kernel_provider.py`、`test_kernel_operations.py`、`test_kernel_service.py`；集成 `tests/integration/test_browser_database.py`、`test_profile_data.py`、`test_kernel_worker.py`；契约 `tests/contract/{conftest,test_profiles,test_kernels,test_kernel_events}.py`；前端各组件同名 `.test.tsx`，共享 client/events 同名 `.test.ts`，桌面 IPC 同名 `.test.ts`。

## 2. 锁定的接口与行为

### 2.1 配置与代理选项

保持旧 API 使用的 camelCase，Pydantic 请求 `extra='forbid'`。`ProfileWrite`：

```typescript
type ProfileWrite = {
  name: string; description: string; startUrl: string;
  locale: string | null; timezone: string | null;
  geoip: boolean; headless: boolean; humanize: boolean;
  humanPreset: 'default' | 'careful'; userAgent: string | null;
  viewportJson: {width: number; height: number} | null;
  colorScheme: 'light' | 'dark' | 'no-preference' | null;
  extensionPathsJson: string[]; expertArgsJson: string[];
  browserVersion: string; browserEdition: 'public' | 'licensed';
  releaseChannel: 'stable' | 'preview';
  proxyMode: 'none' | 'proxy' | 'pool'; proxyId: string | null; proxyPoolId: string | null;
};
```

这是计划中的契约说明，不复制为手写前端 wire type；实际前端引用生成的 `components['schemas']['ProfileWrite']`。`ProfileRead` 加 `id: UUID`、`fingerprintSeed: int`、UTC `createdAt/updatedAt`。不添加伪造的 `isRunning`。

| 方法/路径（统一前缀 `/api/v1`） | 请求/返回 |
|---|---|
| GET `/profiles`、GET `/profiles/{id}` | `{items: ProfileRead[], total}` / `ProfileRead` |
| POST `/profiles`、PUT `/profiles/{id}` | `ProfileWrite` → 201/200 `ProfileRead` |
| POST `/profiles/{id}/duplicate` | `{name}` → 201 `ProfileRead` |
| POST `/profiles/{id}/regenerate-fingerprint` | 无 body → 200 `ProfileRead` |
| DELETE `/profiles/{id}` | 204 |
| GET `/proxy-options` | `{proxies: {id,name,enabled}[], pools: {id,name}[]}`，仅查询本地资源 |

名称 strip 后 1–120 Unicode 字符，SQLite UNIQUE 名称约束处理并发冲突。默认起始网址 `about:blank`，允许 `http/https/about:blank`；缺省字段依旧源码值。locale 使用 BCP47 语法校验，timezone 用 `zoneinfo.ZoneInfo`，Windows 打包 `tzdata`；viewport 整体为空或宽 320–7680、高 240–4320。高级参数按行 trim、移除空行，拦截 `--user-data-dir`、`--fingerprint`、`--remote-debugging-address`、`--remote-debugging-port`、`--proxy-server`、`--load-extension`（包括等号/空白带值形式）。

代理 none 清空两个 ID，proxy/pool 只保留当前模式的 ID；保存时查存在性及 enabled。下拉只列有效资源，原值失效时保留可见标签并阻止提交、要求重新选择。内核保存/复制时确认已安装且可执行；切换公开版立即规范化 Stable。

创建/复制生成 10000–99999 整数种子；复制必须不同于来源，重新生成必须不同于旧值；不保证不同配置之间全局唯一。复制不复制 cookies/浏览器目录。删除先将 `<workspace>/profiles/<uuid>` 原子 rename 到同盘 `.trash`，DB 回滚时恢复；事务提交后清理失败保留待清理记录，不误报“删除失败”或恢复已删除条目；启动时重试清理。拒绝越界、symlink 与被占用目录，不接受客户端目录参数。

错误统一 `{"error":{"code":string,"message":string,"details":object,"requestId":string}}`。验证错误 details 含 camelCase `fields`；业务状态：404 `PROFILE_NOT_FOUND`，409 `PROFILE_NAME_CONFLICT/PROFILE_DIRECTORY_BUSY/KERNEL_NOT_INSTALLED/PROXY_UNAVAILABLE`，422 `VALIDATION_ERROR`。健康响应结构保持不变；API client 兼容原认证 401 `detail` 响应。

### 2.2 内核与长任务

| 方法/路径（`/api/v1`） | 行为 |
|---|---|
| GET `/kernels/catalog`、GET `/kernels/installed` | 真实 CloakBrowser release + 本机扫描；catalog 失败返回已安装项和 `catalogError`；旧来源的公开版 Preview 不作为可下载安装项，避免与公开版 Stable 限制矛盾 |
| POST `/kernels/check-update` | 强制刷新并返回 catalog；不自动升级 |
| GET/POST/DELETE `/kernels/license` | 状态 / `{licenseKey}` 验证保存 / 退出 204；不回传 key |
| GET/PUT `/kernels/default` | `{revision,kernel:{edition,version}|null}`；写带 `expectedRevision`，并发冲突 409 |
| POST `/kernels/download` | `{edition,version,releaseChannel}` → 202 `KernelOperation` |
| GET `/kernels/operations` | 当前实例任务快照 |
| POST `/kernels/operations/{id}/cancel` | 202 cancelling；已终态则返回原终态，未知 404 |
| GET `/kernels/events` | SSE，每次连接先发全量任务快照，随后变更与 15 秒 heartbeat |
| DELETE `/kernels/{version}?edition=…` | 删除本机安装、清除对应默认项并增加 revision；配置引用保留为失效引用 |

`KernelRelease`：`edition/version/chromiumVersion/releaseChannel/publishedAt/archive/size/installed`；`InstalledKernel` 加 `executablePath`。空数据用 null/未知，不编造发布日期、大小或下载次数。LicenseRead：`configured/valid/plan/expires/seats{active,limit}`；未登录只有输入+验证，已登录只有状态+退出（不要同时显示两套动作）。

`KernelOperation`：`id, edition, requestedVersion, resolvedVersion, releaseChannel, state, progress:number|null, message, error`。状态图：`queued → downloading → verifying → extracting → completed`；活动状态可进入 `cancelling → cancelled` 或 `failed`。百分比仅在 provider 有真实下载进度时提供，校验/安装用 indeterminate。取消不等于暂停，不提供断点续传。

运行一个安装工作进程，其他下载请求返回 409 `KERNEL_BUSY`；进程内串行调用旧 wrapper，防止其全局缓存路径/环境变量串扰。worker 从 stdin 收敏感输入，从 stdout 发限定 JSON 消息，不在命令行、数据库任务消息或日志中保存 License。worker 启动时设置 `CLOAKBROWSER_CACHE_DIR=<data_dir>/kernels/.staging/<task-id>`，在 import wrapper 前完成环境设置。下载到任务专有 staging，父进程验证 SDK 返回路径仍在该目录内、安装树无越界链接、可执行文件存在后，原子发布到 `<kernels>/chromium-<resolvedVersion>[-pro]`；若目标已存在，验证后复用而非覆盖。取消/失败不会破坏先前安装。

SSE 使用带 `x-autoflow-token` 的 fetch 流，不能用无法附加该头的原生 EventSource；断流 1/2/5 秒重连并获取快照，重连仅查询，不重放写命令。终态以同一 task id 幂等收敛；新 sidecar instanceId 出现时废弃旧连接/缓存。退出 sidecar 时停止 worker；异常重启把未完成任务标记失败“应用关闭，安装中断”，不自动重试。

License 使用系统凭据存储：Python keyring 的 macOS Keychain / Windows Credential backend，禁止明文 fallback；不可用返回 `CREDENTIAL_STORE_UNAVAILABLE`，公开版管理仍可用。锁定依赖并在三平台打包验证。wrapper 私有/非类型化接口只在 provider 内使用，以旧 0.5.9 的实测 API 为边界。

### 2.3 弹窗与组件协议

```typescript
type KernelRef = { edition: 'public' | 'licensed'; version: string };
type KernelManagerDialogProps = {
  open: boolean;
  onOpenChange(open: boolean): void;
  selectedKernel: KernelRef | null;
};
```

`ProfileFormDialog` 持有唯一 React Hook Form 实例；内核管理弹窗叠在表单上，底层表单 inert、最上层 focus trap。关闭内核弹窗恢复“管理内核”按钮焦点、保留全部输入并刷新 installed 查询；不擅自覆盖用户选择。新建初次打开时可预选有效全局默认；编辑既有配置绝不随默认项更改。

表单四个横向标签：基础信息/浏览器环境/内核与代理/高级选项；新建/编辑同样布局，不引入强制“下一步”。跨标签提交错误自动切到首个错误所属标签并聚焦。高级说明为 disclosure。管理内核无空库入口问题：未安装下拉显示“暂无已安装内核”，右侧按钮仍可用。

提交/删除进行中禁止关闭；内核下载期间禁用管理弹窗关闭，取消请求成功进入终态后允许关闭。Escape/遮罩只关闭最上层；关闭脏表单先打开未保存确认，放弃才销毁表单。断线保留 mounted 编辑会话；GET 可以重试，mutation 全部 `retry:false`。连接恢复提示核对后手动提交，不假定上一请求失败。

## 3. 任务清单

任务内每一步独立执行，测试先红后绿；测试示例中的 fixtures 在对应任务中显式创建。所有 npm 命令在仓库根目录执行，Python 使用 `uv run --directory apps/backend`。共享配置/依赖由主代理在所属任务内添加并锁定，不单独设脚手架任务。

### 任务 1：可访问的共享控件和弹窗模式

**文件：** 创建文件职责表中的 shared UI/复合组件及 `ui/dialog.test.tsx`、`FormField.test.tsx`、`Toaster.test.tsx`；修改 desktop package、lock、样式、交互说明。既有 button/input/select 按实际 diff 迁成 shadcn 源码风格，保留 Tailwind 接入；不冒用原草稿为完整组件库。

- [x] 写失败交互测试，安装开发测试 `@testing-library/user-event`；示例为真实可访问性行为：
```tsx
it('Escape closes the top dialog and returns focus', async () => {
  const user = userEvent.setup()
  render(<Dialog><DialogTrigger>管理内核</DialogTrigger><DialogContent>
    <DialogTitle>内核管理</DialogTitle><DialogDescription>本机内核</DialogDescription>
    <button>刷新版本列表</button>
  </DialogContent></Dialog>)
  await user.click(screen.getByText('管理内核'))
  await user.keyboard('{Escape}')
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(screen.getByText('管理内核')).toHaveFocus()
})
```
- [x] `npm test -- --run src/renderer/shared/components`，记录预期缺失组件失败。
- [x] 加入实际使用的 Radix dialog/select/tabs/alert-dialog/checkbox/switch/tooltip、clsx/tailwind-merge/CVA；复用其焦点管理，不自己写 focus trap。组件接口：
```tsx
<FormField label="浏览器内核" error="请选择浏览器内核" htmlFor="kernel">
  <Input id="kernel" aria-invalid aria-describedby="kernel-error" />
</FormField>
```
  FormField 生成 `kernel-error` 的 alert；Dialog 支持 `busy` 拦截 Escape/outside；ResourceState 接收 loading/error/empty/retry/children；Toaster 提供 `notify({title,tone})`。实现 reduced-motion CSS 与表单四标签布局基元。
- [x] 运行上面测试、`npm run typecheck`、`npm run lint`；补测嵌套弹窗焦点、busy 不关闭、Toast fake timer 2600ms、字段关联。
- [x] 仅 stage 本任务明确文件，提交 `feat(ui): add accessible browser management primitives`。

### 任务 2：配置领域与新数据库

**文件：** domain/profiles 三文件、database session/models/profiles/proxy_options、Alembic 四文件（包括 `alembic.ini`）、unit validation 测试和 integration database 测试；修改 pyproject/uv.lock、bootstrap app 装配和结构说明。

- [x] 为 `ProfileSpec` 写验证测试（tests 从源码导入 model 而非复制逻辑）：
```python
def test_public_preview_is_rejected(valid_profile_values):
    values = {**valid_profile_values, 'browser_edition': 'public', 'release_channel': 'preview'}
    with pytest.raises(ProfileValidationError, match='Stable'):
        ProfileSpec.from_values(values)
```
  `tests/fixtures/profiles.py` 定义 `valid_profile_values` 的完整默认数据，明确公开版 `146.0.1`、Stable、none、about:blank、无扩展。该版本只是夹具，不作为默认产品版本。
- [x] `uv run --directory apps/backend pytest tests/unit/test_profile_validation.py -q`，确认缺失领域模型导致失败。
- [x] 实现 frozen dataclass `ProfileSpec` 和 `Profile(id,spec,fingerprint_seed,created_at,updated_at)`；port 用 Protocol，domain 不 import SQLAlchemy/FastAPI。采用 SQLAlchemy 2 + Alembic，新增 `profiles`、最小 `proxies(id,name,enabled)`、`proxy_pools(id,name)`、`kernel_settings`、`kernel_operations`；代理表此次仅用于资源查询/引用完整性。事务 API：
```python
with session_factory.begin() as session:
    repository = SqlAlchemyProfileRepository(session)
    repository.add(profile)
```
  `session.py` 导出 `migrate_database(path)` 和 `create_session_factory(path)`；AppPaths 增加 `profiles=<workspace>/profiles`、`kernels=<data_dir>/kernels` 路径，启动应用前迁移，启动失败不能发 ready。
- [x] 测试空库 upgrade head、连续两次迁移、重建 engine 后持久化、并发重名冲突、所有字段往返。运行 `pytest tests/integration/test_browser_database.py tests/unit/test_profile_validation.py -q`（带统一 uv 前缀）。
- [x] 提交 `feat(profiles): add validated profile storage`。

### 任务 3：配置用例、HTTP 和安全数据删除

**依赖：** 2；内核实际实现依赖 4/6，先以明确的 `InstalledKernelLookup` port 注入测试 double。

**文件：** application/profiles/service.py、http errors/profile_schemas/profiles/proxy_options、filesystem/profile_data.py、bootstrap app；tests unit/profiles、integration/profile_data、contract/conftest/profiles。

- [x] 定义 conftest `client`：真实 create_app、临时 SQLite/data_dir、token header、fake installed lookup（只含夹具内核）、无网络。定义 `profile_payload` camelCase 全字段。写 API 失败测试：
```python
def test_duplicate_keeps_settings_but_changes_seed(client, profile_payload):
    original = client.post('/api/v1/profiles', json=profile_payload).json()
    response = client.post(f"/api/v1/profiles/{original['id']}/duplicate", json={'name': '副本'})
    assert response.status_code == 201
    copied = response.json()
    assert copied['browserVersion'] == original['browserVersion']
    assert copied['fingerprintSeed'] != original['fingerprintSeed']
```
- [x] `uv run --directory apps/backend pytest tests/contract/test_profiles.py -q`，预期路由 404。
- [x] 实现第 2.1 节全部端点，application 暴露 `list/get/create/update/duplicate/regenerate/remove`；数据库 IntegrityError 映射名字冲突。种子算法：
```python
def new_seed(previous: int | None = None) -> int:
    seed = secrets.randbelow(90000) + 10000
    while seed == previous:
        seed = secrets.randbelow(90000) + 10000
    return seed
```
  删除用例调用 `ProfileDataStore.stage/restore/purge`，严格区分 DB 提交前/后；按确定文件目录授权而非任意用户路径。实现请求验证字段错误映射，隐藏原始异常敏感信息。
- [x] 验证 CRUD、复制隔离、指纹变化、重名409、无内核拒绝、无效代理拒绝、204空体、删除目录占用不删DB、DB失败恢复目录、提交后清理失败可重试、路径越界。运行上述 contract/unit/integration 测试。
- [x] 提交 `feat(profiles): expose profile lifecycle APIs`。

### 任务 4：真实 CloakBrowser provider 与系统 License

**依赖：** 与 1/2 可并行；领域模型/端口由此任务负责。

**文件：** domain/kernels 三文件、providers/kernel/cloakbrowser.py/catalog.py、infrastructure/credentials/system_store.py；tests/unit/test_kernel_provider.py；pyproject/uv.lock 变更由主代理串行应用。

- [x] fixture 从旧源码构造公开 release（含 Windows/macOS 多资产）与授权响应，测试选当前平台：
```python
def test_catalog_ignores_other_platform_assets(github_release_payload):
    releases = parse_public_catalog(github_release_payload, platform='darwin-arm64')
    assert len(releases) == 1
    assert 'darwin-arm64' in releases[0].archive
    assert releases[0].edition == 'public'
```
- [x] `uv run --directory apps/backend pytest tests/unit/test_kernel_provider.py -q`，确认缺失 parser 失败。
- [x] 按旧 `kernel_manager.py` 的 release 解析和 license 调用提取 provider；锁 `cloakbrowser[geoip]==0.5.9`、httpx、keyring、tzdata。当前平台匹配在 provider，支持 windows-x64/darwin-arm64/darwin-x64，不能拿 macOS 资源代替 Windows。端口：
```python
class CredentialStore(Protocol):
    def read(self) -> str | None: ...
    def write(self, value: str) -> None: ...
    def delete(self) -> None: ...
```
  使用 `keyring.get_password/set_password/delete_password('AutoFlow','cloakbrowser-license')`，仅允许系统后端；映射锁定/不可用为结构化错误。License validation 在 worker 中隔离 wrapper 状态，校验成功才替换已存 key，失败不丢原凭据。退出使凭据失效，阻止活动授权任务中退出（409），但不删除已安装内核。
- [x] 测试公开/授权、free plan 解析到实际版本、过期、无 seat 信息、catalog 断网、本机已安装回退、目录扫描不把 staging 计入 installed、所有错误不泄露测试 key。
- [x] 提交 `feat(kernels): adapt cloakbrowser catalog and credentials`。

### 任务 5：可取消内核安装工作进程与 SSE

**依赖：** 2、4。

**文件：** application/kernels/operations.py、providers/kernel/worker.py、bootstrap/kernel_worker.py、infrastructure/process/kernel_worker.py、events/kernel_events.py、adapters/events/kernels.py、__main__.py；unit/kernel_operations、integration/kernel_worker、contract/kernel_events 测试。

- [x] 用测试 worker（只往临时 staging 写文件、输出进度、等待退出，不下载外网）验证取消会停止实际工作：
```python
async def test_cancel_does_not_publish_install(worker_manager, fake_job):
    task = await worker_manager.start(fake_job)
    await worker_manager.cancel(task.id)
    await worker_manager.wait(task.id)
    assert worker_manager.get(task.id).state == 'cancelled'
    assert not fake_job.final_dir.exists()
    assert worker_manager.active_processes() == []
```
  fixtures 在 integration 文件中定义，使用临时路径和 mock worker executable，不允许生产 API 选择测试模式。
- [x] `uv run --directory apps/backend pytest tests/integration/test_kernel_worker.py -q`，确认未实现 supervisor 失败。
- [x] 实现第 2.2 节状态机、单安装锁、staging 原子发布、持久化 operation；冻结进程复用 `autoflow-backend --kernel-worker`，开发进程用 `python -m autoflow --kernel-worker`。消息 schema：
```json
{"type":"progress","state":"downloading","progress":62}
```
  完成消息含经过验证的 resolvedVersion/可执行相对路径；父进程校验后发布；worker 限定输入命令 `catalog/license/download`，不允许任意 shell。取消先请求终止，3 秒后强制停止，再 wait 确认退出后清 staging。生命周期关闭也执行该路径，异常中断记录 failed。SSE 每次连接先快照，队列满则丢弃旧中间进度保留最新快照，终态不丢。
- [x] 验证取消竞态、重复取消、cancel-vs-complete终态、并发启动409、worker崩溃、取消不会改变已安装旧版本、sidecar退出无孤儿、SSE token/断线快照及 unknown total indeterminate。
- [x] 提交 `feat(kernels): supervise cancellable install operations`。

### 任务 6：内核 API、默认项、删除和目录能力

**依赖：** 2、3、4、5。

**文件：** application/kernels/service.py、database/kernel_settings.py、adapters/http/kernel_schemas.py/kernels.py、main/ipc/kernel-paths.ts、preload/index.ts、shared/api/types.ts、bootstrap/app.py；tests/contract/test_kernels.py、unit/test_kernel_service.py、IPC同名测试。

- [x] 写默认项版本冲突测试；`installed_kernel` 为 fake provider 返回的合法安装引用：
```python
def test_default_uses_revision(client, installed_kernel):
    body = {'expectedRevision': 0, 'kernel': installed_kernel}
    assert client.put('/api/v1/kernels/default', json=body).status_code == 200
    stale = client.put('/api/v1/kernels/default', json=body)
    assert stale.status_code == 409
```
- [x] `uv run --directory apps/backend pytest tests/contract/test_kernels.py -q`，预期路由404。
- [x] 实现所有内核端点及默认 revision compare-and-swap：
```sql
UPDATE kernel_settings SET value=:value, revision=revision+1
WHERE key='default' AND revision=:expected_revision;
```
  默认指向存在安装；删除冲突返回409；成功删除清默认并保留配置的原引用以便提示修复。main 接收 `revealKernel(ref)`，通过已认证 sidecar installed 查到路径并校验位于应用 kernels 根、验证 sender frame 后 `shell.showItemInFolder`；不接受任意 renderer 路径。
- [x] 运行内核契约、默认/删除回滚、409/404、License脱敏、invalid path/sender、公开版离线管理测试；集成 profile 用真实 InstalledKernelLookup 取代默认测试装配。执行 `npm run openapi:generate`；核对生成 schemas 和路径。
- [x] 提交 `feat(kernels): expose embedded kernel management APIs`。

### 任务 7：类型化客户端、查询与流恢复

**依赖：** 3、6；公共 generated.ts 只有主代理生成。

**文件：** shared/api/client.ts/events.ts/types.ts/generated.ts、app/ApiProvider.tsx；domains/profiles/api.ts/hooks.ts 与 domains/kernels/api.ts/hooks.ts；同目录测试。

- [x] 测试已有 client 的 204 缺陷，另测业务错误正文：
```ts
it('accepts an empty delete response', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, {status: 204})))
  const api = createApiClient({baseUrl: 'http://127.0.0.1:1/api/v1', token: 'test'})
  await expect(api.request<void>('/profiles/id', {method: 'DELETE'})).resolves.toBeUndefined()
})
```
- [x] `npm test -- --run src/renderer/shared/api`，确认旧 response.json 导致失败。
- [x] request 对204返回 undefined，非空解析error fields/code/requestId，body发 JSON 自动 Content-Type；SSE fetch 共用 token 和 AbortController。Query key 包含 instanceId 与资源名；提供固定 API：`profiles.list/create/update/remove/duplicate/regenerate`、`kernels.catalog/installed/license/connect/disconnect/default/setDefault/download/cancel/remove/checkUpdate`、`proxyOptions.list`；schema类型全部 alias生成文件。
```ts
const mutation = useMutation({ mutationFn: profiles.create, retry: false,
  onSuccess: () => queryClient.invalidateQueries({queryKey: [instanceId, 'profiles']}) })
```
- [x] 测试204、422字段、401、超时、SSE分块拆行/CRLF/心跳、重新连接快照、旧instance事件不更新新实例、终态只通知一次、write不自动重试。
- [x] 提交 `feat(api): connect browser resources and kernel events`。

### 任务 8：配置字段与纯表单规则

**依赖：** 1、7；可与任务10的内核组件并行。

**文件：** domains/profiles/form-schema.ts/presets.ts、components/BasicFields.tsx/EnvironmentFields.tsx/KernelProxyFields.tsx/AdvancedFields.tsx；同名测试。

- [x] 写纯规则与字段交互测试：
```ts
it('requires a real installed kernel selection', () => {
  const result = profileFormSchema.safeParse({...emptyProfileForm, browserKernel: ''})
  expect(result.success).toBe(false)
})
```
  `emptyProfileForm` 在 form-schema.ts 导出，取第2.1节默认；`ProfileFormValues` 为 UI 值（browserKernel选择键、textarea字符串等），不重定义wire DTO。
- [x] `npm test -- --run src/renderer/domains/profiles`，预期schema/字段缺失失败。
- [x] 加 React Hook Form/Zod/resolvers，按旧 `profile-presets.ts` 提取 locale/timezone/UA/viewport选项。实现 `toForm(ProfileRead)` 与 `toWrite(ProfileFormValues): ProfileWrite`，UUID/种子不在输入；切换代理/公开版清理互斥值。
```tsx
<div className="flex gap-2">
  <Select aria-label="浏览器内核" />
  <Button type="button" onClick={onManageKernel}>管理内核</Button>
</div>
```
  实际控件使用 FormProvider/Controller 绑定；无安装和加载失败也可打开管理。高级参数提示和保留参数错误对应真实字段。
- [x] 测试所有字段往返、中文名称长度、网址、locale/timezone、viewport界限、UA内核预设、public切换Stable、代理模式互斥、空proxy选项、缺资源阻止保存。
- [x] 提交 `feat(profiles-ui): add reusable profile editor fields`。

### 任务 9：新建/编辑与配置操作弹窗

**依赖：** 8。

**文件：** ProfileFormDialog.tsx/ProfileActionDialog.tsx/UnsavedChangesDialog.tsx，同名测试；只操作测试fixture，不触碰真实用户数据。

- [x] 先测试跨标签错误聚焦和脏表单保留：
```tsx
it('does not lose the draft when dismissing discard confirmation', async () => {
  const user = userEvent.setup()
  render(<ProfileFormDialog open initialProfile={null} onOpenChange={vi.fn()} />)
  await user.type(screen.getByLabelText('名称'), '工作环境')
  await user.keyboard('{Escape}')
  await user.click(screen.getByRole('button', {name: '继续编辑'}))
  expect(screen.getByLabelText('名称')).toHaveValue('工作环境')
})
```
  测试 renderer 包装 ApiProvider 与 fake queries，在同文件 `renderEditor` helper 固定实例数据；示例 render 用 helper 替换默认 render 以提供上下文。
- [x] `npm test -- --run src/renderer/domains/profiles/components/ProfileFormDialog.test.tsx`，预期组件未实现失败。
- [x] 同一FormProvider实现四横向Tabs、固定底栏“取消/创建配置或保存”；API422映射字段并跳tab；`onOpenChange` 对脏数据打开确认。复制输入名称，不复制数据；删除默认focus取消，提交中busy；指纹更新走列表用例而非编辑seed。
```tsx
const requestClose = () => {
  if (isSubmitting) return
  if (form.formState.isDirty) setDiscardOpen(true)
  else onOpenChange(false)
}
```
- [x] 验证新建/编辑payload、保存中双击仅一次、409重名不丢输入、最上层Escape、删除/复制错误留弹窗、成功Toast、编辑不受默认内核变化影响。
- [x] 提交 `feat(profiles-ui): implement profile editing dialogs`。

### 任务 10：内核管理组件与表单内嵌交互

**依赖：** 1、7、8；与9可并行，集成文件归主代理。

**文件：** domains/kernels/components 五文件及测试；集成 ProfileFormDialog 的 onManageKernel 由主代理合并。

- [x] 用完整createTestQueryClient包装测试 LicensePanel 的互斥状态：
```tsx
it('only offers disconnect when licensed', () => {
  render(<LicensePanel status={{configured:true, valid:true, plan:'pro', expires:null, seats:null}}
    busy={false} onConnect={vi.fn()} onDisconnect={vi.fn()} />)
  expect(screen.getByRole('button', {name:'退出登录'})).toBeEnabled()
  expect(screen.queryByRole('button', {name:'验证并登录'})).not.toBeInTheDocument()
})
```
- [x] `npm test -- --run src/renderer/domains/kernels`，确认缺失组件失败。
- [x] 内核组件纯props优先，KernelManagerDialog负责hook组合；四筛选、真实release信息、installed/default、refresh、License、download/cancel/retry、reveal/delete。无百分比显示indeterminate；缺外网catalog仍显示本机项。
```tsx
<KernelManagerDialog open={kernelOpen} onOpenChange={setKernelOpen}
  selectedKernel={selectedKernel} />
```
  表单组件始终mounted；关闭管理后 invalidate installed，不自动选择新安装；删除所选内核后表单显示原值不可用。创建时默认仅应用一次。busy禁关闭、取消终态后可返回。删除内核使用最上层AlertDialog，返回内核弹窗焦点。
- [x] 测试无License锁定、登录/退出失败、安装后下拉刷新、关闭不丢draft、嵌套focus、catalog降级、取消按钮真实API调用、失败重试新id、下载中禁止关闭、默认冲突刷新、删除已选内核失效提示。
- [x] 提交 `feat(kernels-ui): embed cloakbrowser manager in profile editor`。

### 任务 11：真实列表页、服务恢复与草稿替换

**依赖：** 9、10。

**文件：** ProfileList.tsx、pages/BrowserManagementPage.tsx、app/App.tsx、app-state.ts、profile-workspace-nav.tsx、对应测试；验证后移除未使用 features/profiles/profile-workspace.tsx 草稿。

- [x] 写列表与断线后草稿测试，test API fixture含一个配置和相同token：
```tsx
it('filters profiles by name without another write request', async () => {
  const user = userEvent.setup()
  renderBrowserPage({profiles: [workProfile, testProfile]})
  await user.type(await screen.findByRole('searchbox'), '工作')
  expect(screen.getByText(workProfile.name)).toBeVisible()
  expect(screen.queryByText(testProfile.name)).not.toBeInTheDocument()
})
```
  `renderBrowserPage/workProfile/testProfile` 在页面测试文件定义，使用生成类型的 fixture 和 ApiProvider；服务断线由 fetch mock抛错或新instance返回驱动。
- [x] `npm test -- --run src/renderer/domains/profiles/pages src/renderer/app`，确认页面不存在失败。
- [x] 页面只组合资源列表+表单+操作弹窗；字段齐全、搜索/代理模式过滤、每页10条、筛选后回第一页、删除末项回有效页。全局不暴露内核入口；服务连接状态与编辑数据分离：
```tsx
<>
  {connection.state === 'offline' && <ServiceOfflineNotice onReconnect={reconnect} />}
  <BrowserManagementPage disabled={connection.state !== 'connected'} />
</>
```
  `ServiceOfflineNotice` 定义在 app/App.tsx，只负责提示/按钮；页面实例不因offline被卸载。成功重新握手更新ApiProvider并invalidate查询，write不重放。分别核对旧草稿hunks后替换，不修改其他领域文件。
- [x] 验证真API无硬编码示例数据、全部操作、加载/空/错误/Toast、键盘完成流程、窄窗1280/最小1024不横向溢出、断线保留表单、新instance更新token；`npm run typecheck && npm test && npm run lint && npm run build`。
- [x] 提交 `feat(browser-management): integrate live profile workspace`。

### 任务 12：契约、跨平台打包与验收记录

**依赖：** 11。

**文件：** scripts/smoke-browser-management.mjs、scripts/build-backend.mjs、ci.yml、backend/bootstrap worker打包资源、`docs/migration/browser-management-validation.md`；Python/TS测试按前述路径补齐缺口。

- [x] 在现有桌面smoke模式上创建真实sidecar测试，不增加生产fixture endpoint。pytest集成临时资源安装目录与DB，Electron E2E通过临时data_dir运行；代理fixture只由测试进程写临时DB。
```js
assert.equal(created.browserEdition, 'public')
assert.notEqual(duplicated.fingerprintSeed, created.fingerprintSeed)
assert.equal((await reloadProfile(created.id)).name, updatedName)
```
  `created/duplicated/updatedName` 来自测试实际CRUD，`reloadProfile` 在脚本定义为带测试实例token的GET；不用固定生产端口。
- [x] `node scripts/smoke-browser-management.mjs`，先记录缺失场景或打包资源导致的失败，再改打包收集。
- [x] 把SQLAlchemy/Alembic迁移资源、keyring系统后端、tzdata、cloakbrowser动态导入和worker入口收进PyInstaller；app退出停止worker。CI继续 win2022/macOS Intel/macOS arm64现有矩阵，增加本模块测试和packaged smoke；不用在mac上模拟宣称Windows通过。
- [x] 执行最终验证：
```bash
uv run --directory apps/backend ruff check .
uv run --directory apps/backend mypy src
uv run --directory apps/backend pytest -q
npm run openapi:check
npm run typecheck
npm test
npm run test:scripts
npm run lint
npm run build
npm run smoke:desktop
node scripts/smoke-browser-management.mjs
npm run backend:build
npm run package:dir
```
  CI复用现有打包可执行定位方式执行worker和desktop smoke。公开内核实际下载/安装/目录检查至少本机一次并记录平台、真实版本、产物；授权下载只在环境已有有效License时手工测试，不索要明文key，缺凭据记录“未验证”；CI provider网络测试使用固定responses，不宣称商业服务实测成功。
- [x] 记录各平台通过/失败/未运行、公开/授权能力证据、取消是否真正退出进程、截图对比和已知代理资源限制，提交 `test(browser-management): verify desktop lifecycle and packaging`。

## 4. 并行调度与合并

用户已选择多子代理方向；正式执行使用新子代理逐任务、gpt-5.6-sol 负责普通实现，主代理负责契约、共享文件、两阶段审查。最多3个子代理与主代理并行，不另建用户可见任务。

| 波次 | 可并行任务 | 汇合条件 |
|---|---|---|
| A | 1 共享UI、2 数据、4 provider | 组件API和领域接口固定；主代理串行应用锁文件 |
| B | 3 配置API、5 工作进程 | 同一bootstrap和迁移由主代理整合；不改彼此文件 |
| C | 6 内核API → 7 客户端 | 两个顺序任务，统一OpenAPI生成一次 |
| D | 8 字段 → 9 配置弹窗 与 10 内核弹窗 | 先完成字段props，再并行两套弹窗；组件验收先于页面 |
| E | 11 页面 → 12 集成打包 | 真实HTTP、服务重连与三平台验证 |

每个实现提交先规格符合性审查，再代码质量/测试审查；失败退回当前任务，不用下一任务覆盖遗留问题。没有必要为了占满槽位创建无依赖价值的“审计代理”。任务1/2/4前可读取契约，禁止跨域编辑 `generated.ts`、App、bootstrap、迁移、锁文件。

## 5. 覆盖矩阵与交接条件

| 用户要求 | 任务与证据 |
|---|---|
| 配置创建/编辑/复制/指纹/删除+数据 | 2/3/8/9/11；API、事务和组件交互测试 |
| 完整环境/代理/高级字段 | 2/3/8；预设、schema、往返和真实引用校验 |
| 无额外侧栏，组件先于页面 | 1/8/9/10→11；视觉检查、DOM焦点和布局 |
| 内核下拉旁的管理弹窗 | 8/10；嵌套Modal、返回焦点、草稿不丢 |
| 仅CloakBrowser、License、版本/默认 | 4/6/10；真实provider、revision和互斥登录UI |
| 下载/安装/进度/取消/失败重试 | 5/6/7/10；worker终止、SSE和任务终态 |
| 复制/删除/未保存确认 | 3/9/10；busy锁、取消焦点、错误不丢上下文 |
| 加载/空/错误/Toast/动效 | 1/7/11；2600ms定时、reduced-motion、状态截图 |
| Windows/macOS、路径和进程 | 4/5/6/12；实际CI与packaged smoke |
| 不迁旧数据、不扩其他模块 | 2/11/12；空库迁移、导航和代码依赖审查 |

执行完成须同时交付代码、生成契约、验证记录和一致文档。只有本机通过时不能宣称三平台通过；只有fake provider通过时不能宣称真实授权下载已验收。实施计划本身交付后停在计划审查，不因原型已确认而自动启动任务1。
