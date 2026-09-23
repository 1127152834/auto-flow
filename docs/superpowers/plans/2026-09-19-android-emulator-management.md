# 安卓模拟器管理完善 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在当前代码上交付无需工作流即可独立使用的安卓模拟器管理器，依次完成单实例稳定性、镜像与模板、多实例效率、本机数据维护。

**Architecture:** 保留现有 Mac/Lima/ReDroid provider、设备仓储、归属校验和控制栅栏。增量加入管理状态投影、持久操作历史及独立前端会话控制器，沿现有 API 和数据库历史演进；四批分别交付，不整体换平台或另建执行引擎。

**Tech Stack:** 现有 Electron、React/TypeScript、TanStack Query、共享 shadcn/Radix/Tailwind；Python 3.11、FastAPI/Pydantic、SQLite/SQLAlchemy/Alembic；pytest、Vitest 和隔离真实设备验证。

**Spec:** [安卓模拟器管理完善规格说明书](../specs/2026-09-19-android-emulator-management-design.md)

**Status:** active（2026-09-22 已获用户授权执行 AM1–AM4；真实设备、网络和账号验证仍按条件记录 blocked，不以 mock 替代）。

**Baseline:** 原执行起点为 `codex/project-management-pm9@a92f0688f206d4339ff4468c1871f3ccdd6816dc`；当前实现在隔离 worktree 分支 `codex/android-management-complete`，逐项现状以最新 QA 记录为准。原 `5f07e2ad` 仅保留为规格编写时的历史基线。

**2026-09-24 复审校准：** [最终分支审查](../../qa/android-management/2026-09-24-final-branch-review.md)已覆盖并修复已报告的 Critical/Important；真实五实例、部分失败/容量取消、流式备份恢复和受限高级日志已有证据。十实例本机容量、GApps 专用账号/镜像及若干真实断网/磁盘/归档中断仍按[24 项验收矩阵](../../qa/android-management/2026-09-23-acceptance-matrix.md)保持 `blocked` 或 `partial`。最终软件门禁已通过；102 项 checkbox 已按[逐项追踪审计](../../qa/android-management/2026-09-24-task-evidence-audit.md)重新校准。历史 RED 缺原输出的步骤不追认，真实未运行项和外部 blocked 分开保留。

### 0.1 当前基线重新校准（2026-09-22）

- 主工作区存在未提交 Studio 迁移修改和未跟踪证据目录；它们不属于本任务，已保留在主工作区，实施只发生在隔离 worktree。
- 当前 Alembic 唯一 head 是 `0019_recording_commands`，因此 AM1 新迁移必须以它为 `down_revision`；原文中 `pm07_environments` 是过时规划事实，不能直接使用。
- 当前安卓代码已具备设备生命周期、ReDroid 归属校验、预览、控制台、输入代次/序号和 APK 安装基础；AM1 需要在其上增加独立管理状态、持久操作、只读诊断、控制会话心跳和脱离工作流的管理首页，不重写 provider 安全边界。
- 当前旧接口仍包含 workflows、allocations、runs、temporary 创建路径；它们保留兼容边界，但安卓管理首页不得再依赖这些查询，新的 temporary 请求必须明确拒绝。
- 基线验证在当前 worktree 重新执行；任何真实 macOS/ReDroid、网络或账号验证都单独记录实际状态，缺条件标记 `blocked`。

### 0.2 依赖冲突登记

| 冲突 | 现状 | 处理 |
| --- | --- | --- |
| 规格基线与当前 HEAD 不一致 | 规格编写于 `5f07e2ad`，当前为 `a92f0688` | 以当前 HEAD 和迁移图为准，保留历史引用并在本节记录校准 |
| 迁移父节点不一致 | 原计划写 `pm07_environments`，实际唯一 head 为 `0019_recording_commands` | 新迁移只接当前 head，不修改任何既有迁移字节 |
| 工作流耦合 | AndroidPage/AndroidFleet 仍提供旧工作流查询和分配 | 保留兼容 API/明确拒绝边界；管理 UI 和新管理 API 不调用它们 |
| 操作状态来源不一致 | 既有操作投影在设备 payload，执行任务/console session 部分为内存状态 | 新增独立 Operation/ControlSession 读模型，迁移历史 active 为 `needs_verification` |
| 真实运行条件 | 本轮环境可能缺 Docker/Lima/设备/账号/网络 | 单元/契约/集成测试使用 fake IO 边界；真实链逐项记录 `blocked`，不伪造通过 |

### 0.3 2026-09-23 增量校准

- 本轮基线为隔离分支 `codex/android-management-complete@3ee61947`；保留 worktree 中 3 个 Studio 文档的已有未提交改动，不纳入本轮提交。
- Alembic 当前唯一 head 为 `am01_management_operations`；新核验/容量/诊断修复无数据库形状变化，无需新增迁移。
- T15 发现并修复缺标记误判成功、回执落盘前清除证据、结果未知继续接受新写入及安装后观察失败误分类；完成标记绑定原请求并在持久终态后清除。
- T13 修复 Docker 未限额内存记零、容器枚举失败和不完整 inspect 被准入；该历史待办由9月23日持久预算增量覆盖，18项集成及真实双工作区证据见 `docs/qa/android-management/2026-09-23-capacity-verification.md`；整任务重审仍未完成。
- T19 修复诊断设备归属使用路径而非 runtime hash，默认诊断字段改为白名单；高级日志采集仍未实现，不能以环境 blocked 代替。
- T17/T18 归档安全增量以 `233c09dd` 为基线：内部安全链接、UID/GID/mode、摘要字节复用与源保护已完成；314项聚焦及真实新实例启动读回通过，xattrs/发布耐久性/中断仍待完成。证据见 `docs/qa/android-management/2026-09-23-archive-verification.md`。
- T17 发布增量以 `715cdb16` 为基线：私有目录、staging 摘要、fsync/rename、备份目录记录与成功终态原子事务及回执未知保护已完成；328项聚焦与真实Mac新实例恢复通过。后续真实卷归档暂存完成后、发布前 `SIGKILL` 的孤立文件核实与公开 HTTP 清理已通过；归档传输中断、磁盘不足等仍待完成。证据见 `docs/qa/android-management/2026-09-23-publication-verification.md` 与 `docs/qa/android-management/2026-09-23-backup-hard-interruption-verification.md`。
- T19 清理增量以 `a47bbb9d` 为基线：新增目录契约/UI选择、备份暂存及未登记产物、内容指纹/文件锁和明确retained筛选；后端346、前端Android104项以及真实HTTP清理通过。成功应用操作的完成标记已补持久回执后清理，真实 APK 重跑无新增；新上传的客体 APK 路径已在 push 前持久化，真实状态注入后重启清理通过。未核实应用标记在自动重启/会话收尾时继续隔离，显式核实才释放；无登记旧客体标记、真实 ADB 断连与高级日志仍待完成，证据见 `docs/qa/android-management/2026-09-23-cleanup-verification.md`、`docs/qa/android-management/2026-09-23-command-marker-verification.md`、`docs/qa/android-management/2026-09-23-guest-apk-cleanup-verification.md` 与 `docs/qa/android-management/2026-09-23-app-marker-restart-verification.md`。
- T18 恢复隔离增量以 `be067690` 为基线：恢复意图在IO前持久化，启动/控制/备份隔离，generation/请求/备份栅栏与成功原子发布；真实部分写入、普通recover仍隔离、正常HTTP恢复和重放通过。362项后端、105项前端聚焦通过；后续真实目标卷写入完成、成功发布前 `SIGKILL` 的重启隔离、公开删除和新请求恢复已通过；tar 解包中断/磁盘不足仍待完成，见 `docs/qa/android-management/2026-09-23-restore-isolation-verification.md` 与 `docs/qa/android-management/2026-09-23-restore-hard-interruption-verification.md`。
- 本节为历史快照（superseded）；当前 checkbox 已于 2026-09-24 逐项校准，不再依据旧 blocked 数量判断实现。继续任务、失败门槛和真实验证见 `docs/qa/android-management/2026-09-23-validation.md`。

### 0.4 2026-09-23 当前验收口径

当前隔离分支已提交 `4f612d53` 操作历史、`57fb391c` 保留卷恢复及 `2a7a0c0d` 应用完成标记修复；最新状态以 [24 项验收校准](../../qa/android-management/2026-09-23-acceptance-matrix.md)、[真实控制与保留卷链](../../qa/android-management/2026-09-23-am1-real-control-retention.md)、[真实持久数据属性验收](../../qa/android-management/2026-09-23-persistent-metadata-verification.md)、[全分支审查修复](../../qa/android-management/2026-09-23-final-review-remediation.md)及[高级日志与十台容量](../../qa/android-management/2026-09-24-advanced-logs-and-capacity.md)为准。旧 checklist 的 `blocked` 是各次执行时的快照，不再作为软件任务不能继续的结论。真实 Mac 已验证中文输入、原生切端、30 秒回收、HTTP 重启、APK 操作、同卷保留恢复、五实例运行/并发预览、文件流备份与新实例恢复，以及客体完成标记跨控制台重建后的核实；另已验证新卷恢复的 1792 项持久条目与 417 项 xattrs/55 项 ACL，卷根目录属性及硬/软链接另由客体实验验证。专用谷歌镜像/账号/网络链保持外部 `blocked`，高级日志已完成受限元数据导出；旧应用命令标记清理、桌面精确缩放/真实断网、其他硬中断及 T20 失败矩阵仍是软件或未执行项。十台本机因内存不足标记 `blocked`。前一阶段完整门槛见[记录](../../qa/android-management/2026-09-23-full-gates.md)，本次增量见[审查修复](../../qa/android-management/2026-09-23-final-review-remediation.md)记录；通过代码门槛不代表整目标验收完成。

### 0.5 当前任务重审（2026-09-24）

以下状态覆盖后文任务 checkbox 的历史快照；`partial` 包括仍缺软件实现或未跑真实验收的任务，不能读成已完成。自动化和真实证据逐项见[24 项矩阵](../../qa/android-management/2026-09-23-acceptance-matrix.md)。

| 阶段 | 任务当前状态 | 下一验收门槛 |
| --- | --- | --- |
| AM1 | T01–T06 所列功能 `passed`；T07 历史 RED 缺证 | 精确 200%/两种窗口尺寸、键盘焦点、不可达旧快照与桌面应用确认已补；旧 temporary 契约已验，历史实例真实同链另列风险 |
| AM2 | T08/T10 功能 `passed`；T09/T12 `partial`；T11 检测规则 `passed`、专用 GApps 账号链 `blocked` | 固定摘要网络拉取和认证 HTTP 内容删除已实测；待桌面删除、断线核实、候选镜像/账号下载链与阶段回退 |
| AM3 | T13–T16 `partial` | 双实例/五实例、部分失败、修订冲突项重试和容量等待取消已验；十台容量 blocked，运行时瞬时故障/未知结果、应用确认与真实 ADB 断连已补；桌面前台/探测指标仍未完整记录 |
| AM4 | T17–T19 已列功能 `passed`；T20 `partial` | 文件流备份恢复、真实 ENOSPC/传输取消、受限高级日志与全分支审查修复已验；恢复解包中 SIGKILL 已补；目标磁盘不足/取消恢复、多对象清理硬中断已补；备份传输硬中断和完整负向矩阵见后续验证记录 |

本轮各次自建 QA 实例和备份均记录清理及归属核实；这不赋予无来源旧文件可删除资格。Node 22、全量后端与最终审查按实际输出单独登记。102 个步骤的状态、文件映射和缺证原因见[逐项审计](../../qa/android-management/2026-09-24-task-evidence-audit.md)；功能通过与历史 RED 证据是否完备分开记录。

## Global Constraints

- GC-01：本轮运行平台仅 Apple Silicon macOS + 现有 Lima/ReDroid；其他平台明确提示不支持，不影响主应用启动。
- GC-02：Python 保持 >=3.11,<3.12；Node.js 使用 >=22.12 的 22.x；依赖遵循现有锁文件，不因本模块整体升级。
- GC-03：前端保留 React/TypeScript、TanStack Query、共享 shadcn/Radix/Tailwind；后端保留 FastAPI/Pydantic、SQLAlchemy/Alembic。
- GC-04：保留顶部全局导航与暖灰/黏土棕主题，不新增全局侧栏，不建立第二套基础控件或 contracts 包。
- GC-05：后端使用 apps/backend/src/autoflow；前端使用 apps/desktop/src/renderer/domains/android；OpenAPI 类型仍生成到 renderer/shared/api/generated.ts。
- GC-06：本轮不实现工作流执行、自动分配、人工接管工作流、自动回收或旧 Studio 运行时复活；保留历史数据与兼容拒绝边界。
- GC-07：所有改变设备、数据、镜像或运行环境的操作必须显式授权；检查和列表读取不得隐式创建、启动、修复或删除资源。
- GC-08：保留归属校验、独占控制、generation/sequence 栅栏、幂等请求和结果未知保护；不得以清空状态或自动重放解决冲突。
- GC-09：仅采用增量迁移，不修改既有迁移字节、不重建用户数据库；每批保持一个迁移 head。
- GC-10：ADB 与 sidecar 仅监听回环地址，前端不直接执行进程、访问数据库或拼接任意宿主机路径。
- GC-11：不上传账号、输入文本、设备数据、APK、镜像或原始日志到仓库；诊断导出默认脱敏并排除应用数据与屏幕截图。
- GC-12：每个批次同时交付契约、实现、界面、测试与验证记录；mock 测试通过不等于真实设备通过。

---

## 1. 执行规则、路径和依赖

先阅读配套规格、`AGENTS.md`、`.ai/README.md`、`.ai/memory/project-context.md`、`docs/PROJECT_STRUCTURE.md` 和相关架构决定。实施前重新核对默认分支、工作区及 migration head；本文固定提交不是未来主分支永不变化的假设。

AM1=T01–T07；AM2=T08–T12；AM3=T13–T16；AM4=T17–T20。每批获得明确实施授权后开始，完成验收后停止。T11 的可行性实验在 T07 后可提前执行；产品验证记录仍需 T08 的镜像契约。缺账号、网络或目标应用仅阻塞对应验证，不伪造通过，也不阻塞其他管理能力。

每项任务先写一条可观察失败的断言，确认 RED 的原因是缺失行为而不是依赖或环境错误，再实现最小行为、补充边界、运行回归并提交。大步骤按单一断言重复此循环；不先写完整功能再补测试。

### 1.1 路径约定

为避免长路径反复掩盖模块名，任务使用以下固定前缀。它们是仓库相对路径的精确展开，不是可自行选择的目录：

| 前缀 | 精确目录 |
| --- | --- |
| B/ | `apps/backend/src/autoflow/` |
| BT/ | `apps/backend/tests/` |
| F/ | `apps/desktop/src/renderer/domains/android/` |
| DS/ | `apps/desktop/src/` |

例如 `B/application/android/console.py` 就是 `apps/backend/src/autoflow/application/android/console.py`；所有新建路径标记为“新建”，不能宣称基线已存在。测试证据文件 `docs/qa/android-management/` 在实际验收任务中创建，本次不预填通过结果。

### 1.2 已有文件与改造边界

| 既有位置 | 改造责任 |
| --- | --- |
| B/application/android/{devices,management,console,fleet}.py | 保留生命周期、控制及恢复；退出退役工作流耦合 |
| B/providers/android/{mac_runtime,management,stream}.py | 运行时探测、限定命令、镜像发现、视频与进程 |
| B/adapters/http/{android,android_fleet,android_fleet_schemas}.py | 原接口兼容；新增字段与管理路由明确分开 |
| B/infrastructure/database/{android,android_models,android_resources}.py | 设备和通用资源仓储，不直接从 HTTP 访问 ORM |
| B/bootstrap/{app,android,android_prepare}.py | 启动/关闭装配；准备命令不能当作只读检查 |
| F/{api,fleet-api,model}.ts | 原传输和模型边界，客户端 DTO 使用生成类型 |
| F/pages/AndroidPage.tsx | 页面组合，移出会话与非本轮查询 |
| F/components/{ResourceBoard,CreateInstances,DeviceConsole,AndroidVideo,DevicePreview,PrototypeControls}.tsx | 先复用基础控件，再调整业务组件 |
| BT/unit/test_android_{management,handoff,runtime}.py | 既有安全回归保留 |
| BT/integration/{test_android_m4_migration,test_migration_heads}.py | 迁移及历史字节保护 |

花括号为并列文件展开。生成类型、迁移图、bootstrap 和共享会话协议由单一集成人负责；无真实子代理工具时顺序执行，不声称完成独立代理审查。

### 1.3 公共接口约定

首次引入任务负责定义下列类型，后续任务原样消费；Python 内部 snake_case、HTTP camelCase。HTTP DTO 以规格第5节为准，不手写第二套 TypeScript 响应结构。

```text
T02: DeviceFacts(device_id, revision=1, runtime_state='unknown',
                 owner_kind='none', control='idle', operation_action=None,
                 operation_state=None, stale=True)
     ActionPolicy(allowed_actions: tuple[str,...], blocked_reasons: dict[str,str])
     policy_for(facts: DeviceFacts) -> ActionPolicy
     display_state(facts: DeviceFacts) -> str
T03: EnvironmentCheckService(runtime).check(request_id: str) -> EnvironmentCheckResult
T04: OperationRepository.accept(workspace_identity, request_id, target_id,
                                action, request_digest, payload) -> OperationRecord
     get(operation_id: str) -> OperationRecord
     by_request(workspace_identity: str, request_id: str) -> OperationRecord
     page(device_id: str|None, cursor: str|None, limit: int) -> OperationPage
     transition(operation_id, expected_state, next_state, changes) -> OperationRecord
     compact(before: datetime) -> int
T05: createConsoleController(api, identity) -> ConsoleController
     ConsoleController.open(deviceId): Promise<void>
     ConsoleController.send(command): void
     ConsoleController.leave(): Promise<void>
     ConsoleController.switchEndpoint(endpoint): Promise<void>
     ConsoleController.dispose(): Promise<void>
     ConsoleController.subscribe(listener): () => void
```

EnvironmentCheckResult 包含 checkedAt、runtimeId、checks、capabilities；OperationRecord/OperationPage 对应规格 OperationRead/Page，同时保存内部请求摘要。ConsoleController.identity 包含 workspaceIdentity、backendInstanceId，会话再绑定 deviceId/sessionId/generation。input API 使用 T05 扩展后的 fleetApi，不依赖 React。subscribe 返回取消订阅函数；dispose 停止队列并按会话端点执行安全退出。

### 1.4 基线与每批发布命令

以下命令是未来实施时执行的门槛，不是本次已执行结果。除显式 `cd` 外，从仓库根目录运行。

```bash
uv sync --directory apps/backend --locked
npm ci
npm run test:structure
npm run test:scripts
(cd apps/backend && uv run pytest tests/unit/test_android_management.py tests/unit/test_android_handoff.py tests/unit/test_android_runtime.py tests/integration/test_android_m4_migration.py tests/integration/test_migration_heads.py -q)
npm --workspace @autoflow/desktop test -- src/renderer/domains/android/tests
npm run typecheck
npm run lint
npm run openapi:check
```

API变更后先执行 `npm run openapi:generate`，再执行 `npm run openapi:check`。每批合并前追加 `npm test`、`npm run build`、`(cd apps/backend && uv run pytest -q)`。测试使用临时数据库和fake provider；普通测试发现过程中不得启动真实模拟器。真实Mac、设备和网络条件不具备时标blocked，不能用mock测试代替。

## 2. AM1：基础管理稳定版

### T01：建立隔离测试夹具与基线

**覆盖：** AM-R17/R18；AM-AC23/AC24。**依赖：** AM1实施授权。

**文件：** 新建 `BT/fixtures/android_management.py`、`F/tests/management-fixtures.ts`；读取并小范围调整上述既有Android测试，不改生产行为。

**接口：** 测试工厂提供合法UUID、内存Repository、fake Runtime、可控时钟、每设备独立调用日志；前端导出DEVICE_ID、PROFILE_ID、makeDevice、makeSession、makeApi。makeApi为现有fleetApi的typed mock，未知写操作默认拒绝，不默认假成功。

- [x] 记录实施分支、提交、依赖、平台和当前测试结果，保护未提交改动，隔离测试数据目录。（状态：passed；隔离分支和三个 Studio 保护哈希已核对；[证据 T01.1](../../qa/android-management/2026-09-24-task-evidence-audit.md#t01)）
- [x] 抽取既有测试的重复fake，保留原断言；加入下面的基本约束以及未知设备读取404、不隐式新增记录的测试。（状态：passed；现有隔离夹具与未知设备 404 回归通过；[证据 T01.2](../../qa/android-management/2026-09-24-task-evidence-audit.md#t01)）

```python
from uuid import UUID
DEVICE_ID = '11111111-1111-4111-8111-111111111111'
PROFILE_ID = '22222222-2222-4222-8222-222222222222'

def test_fixture_ids_are_valid_and_distinct():
    assert UUID(DEVICE_ID) != UUID(PROFILE_ID)
```

- [x] 执行1.4节Android聚焦命令；基线失败单独记录，不删除断言，不把环境缺失当RED。（状态：passed；本轮按原 glob 命令执行，447 passed；[证据 T01.3](../../qa/android-management/2026-09-24-task-evidence-audit.md#t01)）
- [x] 确认测试不读取真实账号、用户工作区或已有设备；真实设备调用只出现在后续受控smoke中。（状态：passed；普通测试边界与 opt-in 真机脚本分离；[证据 T01.4](../../qa/android-management/2026-09-24-task-evidence-audit.md#t01)）
- [x] 提交 `test(android): establish isolated management fixtures`；此任务不是AM1完成。（状态：passed；夹具已在历史提交中；非 AM1 整体验收；[证据 T01.5](../../qa/android-management/2026-09-24-task-evidence-audit.md#t01)）

### T02：统一状态模型和动作策略

**覆盖：** AM-R03；AM-AC03。**依赖：** T01。

**文件：** 新建 `B/domain/android/management_models.py`、`management_rules.py`、`B/adapters/http/android_management_schemas.py`、`BT/unit/test_android_management_state.py`、`F/state/management-state.ts`、`F/tests/ManagementState.test.ts`；按需调整 `B/domain/android/ports.py` 兼容导出。

**接口：** 产出1.3节DeviceFacts/ActionPolicy及纯函数；新增ManagementDevice DTO，不覆盖原AndroidDeviceRead。

- [x] 先写停止、删除、恢复、manual、unknown、stale、历史未知占用的状态矩阵。（状态：passed；状态矩阵存在，当前集合通过；[证据 T02.1](../../qa/android-management/2026-09-24-task-evidence-audit.md#t02)）

```python
from autoflow.domain.android.management_models import DeviceFacts
from autoflow.domain.android.management_rules import display_state, policy_for

def test_delete_is_not_presented_as_starting():
    f = DeviceFacts(device_id='d', control='managing',
        operation_action='delete', operation_state='running')
    assert display_state(f) == '正在删除'
    assert 'start' not in policy_for(f).allowed_actions
```

- [ ] RED：`(cd apps/backend && uv run pytest tests/unit/test_android_management_state.py -q)`；首次失败必须指向缺失模型或错误状态。（状态：not_run；当前 GREEN 已验证；该步骤独立历史 RED 输出未找到，不追认通过；[证据 T02.2](../../qa/android-management/2026-09-24-task-evidence-audit.md#t02)）
- [x] 按规格优先级实现纯规则；blockedReasons给出原因；unknown/stale绝不走绿色ready分支。分离旧工作流特定类型时保留兼容导出。（状态：passed；规则与动作投影已实现，当前回归通过；[证据 T02.3](../../qa/android-management/2026-09-24-task-evidence-audit.md#t02)）
- [x] 前端仅格式化状态，消费后端动作策略；运行ManagementState.test.ts、既有安全回归、生成类型和typecheck。（状态：passed；ManagementState 与生成类型已验证；[证据 T02.4](../../qa/android-management/2026-09-24-task-evidence-audit.md#t02)）
- [x] GREEN后提交 `feat(android): unify management state and action policy`。（状态：passed；软件切片已入历史；历史 RED 缺证单列；[证据 T02.5](../../qa/android-management/2026-09-24-task-evidence-audit.md#t02)）

### T03：只读环境诊断与能力入口

**覆盖：** AM-R02；AM-AC02。**依赖：** T02。

**文件：** 新建 `B/application/android/diagnostics.py`、`B/adapters/http/android_management.py`、`BT/contract/test_android_management_environment.py`、`F/management-api.ts`、`F/components/RuntimeDiagnostics.tsx`、`F/tests/RuntimeDiagnostics.test.tsx`；修改mac_runtime.py及bootstrap/app.py。

**接口：** 产出EnvironmentCheckService、GET management/environment和capabilities。bootstrap只读探测填充快照，未探测项unknown；持久POST checks在T04接入前不注册空实现。

- [x] 写不支持平台、工具缺失、Docker超时、镜像缺失和资源未知测试；监视所有变更入口。（状态：passed；负向只读环境契约与 runtime 单元通过；[证据 T03.1](../../qa/android-management/2026-09-24-task-evidence-audit.md#t03)）

```python
from unittest.mock import AsyncMock
import pytest

@pytest.mark.asyncio
async def test_check_never_manages_a_device():
    from autoflow.application.android.diagnostics import EnvironmentCheckService
    runtime = AsyncMock()
    runtime.environment.return_value = {'available': False,
        'platformSupported': False, 'runtimeId': 'autoflow-redroid',
        'message': '不支持', 'images': []}
    await EnvironmentCheckService(runtime).check('check-1')
    runtime.manage.assert_not_called()
```

- [ ] RED：`(cd apps/backend && uv run pytest tests/contract/test_android_management_environment.py -q)`。（状态：not_run；当前 GREEN 已验证；该步骤独立历史 RED 输出未找到，不追认通过；[证据 T03.2](../../qa/android-management/2026-09-24-task-evidence-audit.md#t03)）
- [x] 输出规格固定检查项、时间、状态、原因；保留available兼容投影。不得调用android_prepare.prepare，不安装工具、不创建设备。（状态：passed；固定检查项已由生产 Mac 及契约验证；[证据 T03.3](../../qa/android-management/2026-09-24-task-evidence-audit.md#t03)）
- [x] 用共享控件显示环境面板、处理步骤和重新检查；运行RuntimeDiagnostics.test.tsx，覆盖unknown值、无设备引导、键盘访问。（状态：passed；RuntimeDiagnostics 键盘/未知状态回归通过；[证据 T03.4](../../qa/android-management/2026-09-24-task-evidence-audit.md#t03)）
- [x] GREEN后提交 `feat(android): add read-only runtime diagnostics`。（状态：passed；软件切片已入历史；[证据 T03.5](../../qa/android-management/2026-09-24-task-evidence-audit.md#t03)）

### T04：持久操作、核实与增量迁移

**覆盖：** AM-R04/R06/R17；AM-AC04/AC08/AC09/AC23。**依赖：** T02/T03。

**文件：** 新建 `B/infrastructure/database/android_operations.py`、`B/infrastructure/database/migrations/versions/am01_management_operations.py`、`BT/integration/test_android_management_operations.py`、`BT/contract/test_android_management_operations.py`；修改application/android/management.py、providers/android/management.py、android_models.py、android.py、管理HTTP、bootstrap及migration-head测试。

**接口：** 实现OperationRepository；注册operations/page/get/by-request/verify和环境checks。原生命周期接口仍202返回AndroidDeviceRead并附operationId。唯一约束(workspace_identity,request_id)。

- [x] 用tmp_path和现有create_session_factory/migrate_database构造repo fixture；写幂等、摘要冲突、写意图后崩溃、归档回执、删除归属重检。（状态：passed；真实临时 SQLite、幂等/归档/未知/归属回归通过；[证据 T04.1](../../qa/android-management/2026-09-24-task-evidence-audit.md#t04)）

```python
def test_request_id_cannot_change_target(repo):
    first = repo.accept('ws', 'r1', 'd1', 'stop', 'digest-a', {})
    again = repo.accept('ws', 'r1', 'd1', 'stop', 'digest-a', {})
    assert again.operation_id == first.operation_id
    import pytest
    from autoflow.domain.android.ports import AndroidError
    with pytest.raises(AndroidError):
        repo.accept('ws', 'r1', 'd2', 'stop', 'digest-b', {})
```

- [x] RED/GREEN：`(cd apps/backend && uv run pytest tests/integration/test_android_management_operations.py tests/contract/test_android_management_operations.py -q)`；当前 Android 聚焦集合 `159 passed, 1 warning`。（状态：passed；当前对应契约/集成包含在 447 项；后续事务修复 RED 见最终审查 QA；[证据 T04.2](../../qa/android-management/2026-09-24-task-evidence-audit.md#t04)）
- [x] 基线迁移父节点已重查为当前 `0019_recording_commands`；`transition_with_device` 在同一 SQLAlchemy 事务保存操作状态与设备投影，外部命令仍在事务外；保留锁、marker和标签校验。（状态：passed；唯一 am01 head、父节点 0019，同事务设备/操作投影已验；[证据 T04.3](../../qa/android-management/2026-09-24-task-evidence-audit.md#t04)）
- [x] 加by-request静态路由、verify、90天历史紧凑化；未知只能核实，缺卷不能补空卷。旧1000回执上限语义已移除，紧凑回执保留重复请求保护；迁移和API类型回归通过。（状态：passed；静态 by-request、90 天紧凑回执及缺卷保护回归通过；[证据 T04.4](../../qa/android-management/2026-09-24-task-evidence-audit.md#t04)）
- [x] GREEN后纳入最终交付提交 `feat(android): complete management implementation and acceptance evidence`。（状态：passed；软件切片已提交至 30eb0926 及其历史；[证据 T04.5](../../qa/android-management/2026-09-24-task-evidence-audit.md#t04)）

### T05：独立控制会话与原生窗口生命周期

**覆盖：** AM-R05；AM-AC05/AC06/AC07。**依赖：** T04。

**文件：** 新建 `F/state/console-controller.ts`、`F/hooks/useConsoleController.ts`、`F/tests/ConsoleController.test.ts`、`BT/unit/test_android_console_lifecycle.py`；修改DeviceConsole.tsx、AndroidPage.tsx、fleet-api.ts、后端console.py/devices.py及android_fleet.py/schemas。

**接口：** 产出1.3节ConsoleController；新增heartbeat，GET不续租；原生进程按既有身份核实。T01的makeApi提供session/action/input日志与对应完整返回值。

- [x] 写返回重进、组件卸载、切设备/工作区/后端、旧输入、切原生、心跳失联和正常原生窗口不被误回收的测试。（状态：passed；ConsoleController、会话租约及原生存活回归通过；[证据 T05.1](../../qa/android-management/2026-09-24-task-evidence-audit.md#t05)）

```typescript
it('does not replay old input after leaving', async () => {
  const api = makeApi();
  const c = createConsoleController(api, {
    workspaceIdentity: 'w', backendInstanceId: 'b'
  });
  await c.open(DEVICE_ID);
  c.send({kind: 'text', text: 'sample'});
  await c.leave();
  await c.open(DEVICE_ID);
  expect(api.calls.filter(x => x.kind === 'text' && x.text === 'sample')).toHaveLength(1);
});
```

- [x] RED：运行ConsoleController.test.ts和`(cd apps/backend && uv run pytest tests/unit/test_android_console_lifecycle.py -q)`，先证明故障路径。（状态：passed；页面竞态 RED→GREEN 见 control-session-verification QA；[证据 T05.2](../../qa/android-management/2026-09-24-task-evidence-audit.md#t05)）
- [x] 输入队列绑定完整身份；leave停止新输入、释放、核实结束，不停止Android。新会话才初始化序号；切端先关闭旧写端并递增generation，不直接清零后端sequence。（状态：passed；完整身份输入队列和切端 generation 栅栏已实现并回归；[证据 T05.3](../../qa/android-management/2026-09-24-task-evidence-audit.md#t05)）
- [x] 复用主应用关闭协调；嵌入式5秒心跳/30秒失联，原生端按进程存活。失败保持可见占用；普通详情/缩略图不claim。运行旧AndroidVideo/AndroidPage回归与typecheck。（状态：passed；关闭协调及 5/30 秒租约已验；真实桌面SSH/ADB断线及恢复见2026-09-24-desktop-control；[证据 T05.4](../../qa/android-management/2026-09-24-task-evidence-audit.md#t05)）
- [x] GREEN后提交 `fix(android): manage console ownership independently of navigation`。（状态：passed；控制软件已入历史；真实桌面往返/原生离页/断线恢复已验；[证据 T05.5](../../qa/android-management/2026-09-24-task-evidence-audit.md#t05)）

### T06：管理首页、创建与保留数据入口

**覆盖：** AM-R01/R06/R07；AM-AC01/AC08/AC10。**依赖：** T03–T05。

**文件：** 新建 `B/application/android/management_queries.py`、`F/components/DeviceGrid.tsx`、`DeviceTable.tsx`、`DeviceStatus.tsx`、`DeviceOperationDialog.tsx`、`OperationHistory.tsx`、`F/hooks/useDeviceManagement.ts`、`F/tests/DeviceManagementPage.test.tsx`；修改管理HTTP、AndroidPage.tsx、ResourceBoard.tsx、CreateInstances.tsx、android.css、fleet.py及BatchCreate。

**接口：** GET management/devices返回ManagementDevice分页；AM1先聚合现有设备观察与持久操作，T14再换后台快照。UI只消费ActionPolicy。创建沿用batch/profile revision。

- [x] 新测试使用T01夹具和现有ApiProvider mock，验证默认一台、无工作流请求、stale、空态、筛选计数及历史temporary保留。（状态：passed；管理快照、无工作流、筛选和旧 temporary 拒绝/重放回归通过；[证据 T06.1](../../qa/android-management/2026-09-24-task-evidence-audit.md#t06)）

```typescript
expect(screen.getByRole('spinbutton', {name: '数量'})).toHaveValue(1);
expect(screen.queryByRole('button', {name: '分配给工作流'})).not.toBeInTheDocument();
expect(requests.some(p => /workflows|allocations|\/runs/.test(p))).toBe(false);
```

- [x] RED：管理页测试按当前代码位置执行 `AndroidPage.test.tsx` 和 `ManagementOverview.test.tsx`，后端执行管理设备/操作契约与集成测试。（状态：passed；历史查询/焦点/过滤 RED→GREEN 见 operation-history-verification QA；[证据 T06.2](../../qa/android-management/2026-09-24-task-evidence-audit.md#t06)）
- [x] 先共享控件组成状态/卡片/表格/确认框，再挂页面；新temporary请求后端拒绝，旧同编号回执优先返回。生产入口不导入测试数据，不删除历史数据和迁移。（状态：passed；页面复用控件，保留历史数据；禁止新 temporary 回归通过；[证据 T06.3](../../qa/android-management/2026-09-24-task-evidence-audit.md#t06)）
- [x] GET profiles退出隐式保存；新增显式创建标准模板。创建仅一台persistent默认；复制参数不复制账号。retained可恢复，永久删除显示范围。验证窗口尺寸、缩放、长名称、键盘焦点和断线旧数据。（状态：passed；同卷恢复与默认配置已有证据；本轮精确1280×800/1440×900、100%/200%、长名、键盘确认与sidecar不可达旧快照均真实通过；[证据 T06.4](../../qa/android-management/2026-09-24-task-evidence-audit.md#t06)）
- [x] GREEN后提交有界 T06 增量；旧三列原型断言改为新行为，不删安全回归。（状态：passed；4f612d53、57fb391c、c3f9d94e 等有界提交；阶段真实验收未关闭；[证据 T06.5](../../qa/android-management/2026-09-24-task-evidence-audit.md#t06)）

### T07：AM1真实链与交付验收

**覆盖：** AM-R13基础/R18；AM-AC01–AC10/AC18基础/AC23/AC24。**依赖：** T01–T06。

**文件：** 新建 `apps/backend/scripts/android-management-smoke.py`、`BT/unit/test_android_management_smoke_args.py`、`docs/qa/android-management/am1-verification.md`；按实际失败修改DeviceConsole.tsx、mac_runtime.py的安装/启动结果核实和文本发送。

**接口：** smoke需要`--workspace <隔离目录>`、`--allow-device-mutation`；只操作本轮生成且标签匹配的资源。普通测试仅parser/fake runtime。

- [x] 写缺授权参数拒绝、`--help`无副作用、安装响应丢失不得假成功的测试。（状态：passed；smoke opt-in、help 与安装结果未知测试存在并通过；[证据 T07.1](../../qa/android-management/2026-09-24-task-evidence-audit.md#t07)）

```python
import subprocess
import sys

def test_smoke_requires_explicit_permission():
    r = subprocess.run([sys.executable, 'scripts/android-management-smoke.py'],
        capture_output=True, text=True)
    assert r.returncode != 0
    assert '--allow-device-mutation' in r.stderr
```

- [ ] RED/GREEN：`(cd apps/backend && uv run pytest tests/unit/test_android_management_smoke_args.py -q)`；CLI任何设备变更前先校验授权和范围。（状态：not_run；当前 GREEN 已验证；该步骤独立历史 RED 输出未找到，不追认通过；[证据 T07.2](../../qa/android-management/2026-09-24-task-evidence-audit.md#t07)）
- [x] 经授权在Mac隔离工作区验证：创建→安装测试应用/写入数据→中文输入/截图→返回重进→切原生/切回→停机重启→重启AutoFlow→中断恢复→删除隔离。（状态：passed；基础链及桌面控制已有真实证据；安装执行中ADB断线/HTTP进程树强杀、重启核实保持未知和应用数据不变已补，分轮资源ID归档；[证据 T07.3](../../qa/android-management/2026-09-24-task-evidence-audit.md#t07)）
- [x] 执行1.4节完整门槛；证据包含平台、imageId、commit、命令、结果及未测项。无Mac时记录blocked，不宣称真实链完成。（状态：passed；最终完整门禁和真机限制已独立记录；不宣称全真实场景完成；[证据 T07.4](../../qa/android-management/2026-09-24-task-evidence-audit.md#t07)）
- [x] 提交 `test(android): verify standalone management lifecycle`；停在AM1验收点。（状态：passed；阶段证据已提交；用户 AM1–AM4 连续授权覆盖旧暂停点；[证据 T07.5](../../qa/android-management/2026-09-24-task-evidence-audit.md#t07)）

## 3. AM2：镜像、模板与谷歌组件验证

### T08：不可变镜像目录与引用保护

**覆盖：** AM-R08/R17；AM-AC11/AC23。**依赖：** AM2授权、T07。

**文件：** 新建 `B/domain/android/image_models.py`、`B/application/android/images.py`、`B/providers/android/image_catalog.py`、`BT/unit/test_android_image_catalog.py`；修改providers/android/management.py、android_resources.py及管理HTTP。

**接口：** ImageMetadata字段image_id/source_digest/architecture/os/android_version；`ImageCatalog.inspect(reference)->ImageMetadata`；`ImageService.register(request_id,reference)->ImageRead`、`references(image_id)->list[ImageReference]`。ImageReference含kind/id/name，ImageRead符合规格。

- [x] 写Linux/ARM64要求、tag漂移、本地ID与源摘要不同、未知系统版本和引用保护。（状态：passed；架构、tag 漂移、固定 ID 与引用保护回归通过；[证据 T08.1](../../qa/android-management/2026-09-24-task-evidence-audit.md#t08)）

```python
from autoflow.domain.android.image_models import ImageMetadata

def test_local_id_is_not_a_registry_digest():
    m = ImageMetadata(image_id='sha256:'+'a'*64, source_digest=None,
        architecture='arm64', os='linux', android_version=None)
    assert m.source_digest is None
    assert m.android_version is None
```

- [ ] RED：`(cd apps/backend && uv run pytest tests/unit/test_android_image_catalog.py -q)`。（状态：not_run；当前 GREEN 已验证；该步骤独立历史 RED 输出未找到，不追认通过；[证据 T08.2](../../qa/android-management/2026-09-24-task-evidence-audit.md#t08)）
- [x] 提取固定IMAGE发现，原镜像作为默认候选；创建绑定imageId，登记仅inspect不执行镜像/脚本。（状态：passed；固定 imageId、只读登记和默认候选已实现；[证据 T08.3](../../qa/android-management/2026-09-24-task-evidence-audit.md#t08)）
- [x] 历史未知镜像保留原ID；引用保护包括实例、retained、模板及backup资源，不因备份UI尚未发布忽略已有记录。运行旧创建/恢复测试。（状态：passed；实例/保留卷/模板/备份引用回归通过；[证据 T08.4](../../qa/android-management/2026-09-24-task-evidence-audit.md#t08)）
- [x] GREEN后提交 `feat(android): introduce immutable image catalog`。（状态：passed；软件切片已入历史；[证据 T08.5](../../qa/android-management/2026-09-24-task-evidence-audit.md#t08)）

### T09：镜像登记、拉取和管理界面

**覆盖：** AM-R08；AM-AC11。**依赖：** T04/T08。

**文件：** 新建 `F/components/ImageManager.tsx`、`F/tests/ImageManager.test.tsx`、`BT/contract/test_android_images.py`；扩展images.py、image_catalog.py、management-api.ts及管理HTTP。

**接口：** images查询/登记/删除及image-pulls；拉取返回OperationRead。输入只接受受允许来源的registry/repository:tag或digest，不接受命令或Docker附加参数。client fixture在本测试文件用临时Settings/TestClient和fake ImageCatalog创建。

- [x] 写不可信来源、恶意换行/选项、拉取中断、引用冲突删除拒绝测试。（状态：passed；来源/参数、未知拉取与引用冲突回归通过；[证据 T09.1](../../qa/android-management/2026-09-24-task-evidence-audit.md#t09)）

```python
def test_pull_rejects_command_in_reference(client):
    r = client.post('/api/v1/android/management/image-pulls', json={
        'requestId': '11111111-1111-4111-8111-111111111111',
        'reference': 'repo:tag\n--privileged'})
    assert r.status_code == 422
```

- [ ] RED：`(cd apps/backend && uv run pytest tests/contract/test_android_images.py -q)`及ImageManager.test.tsx。（状态：not_run；当前 GREEN 已验证；该步骤独立历史 RED 输出未找到，不追认通过；[证据 T09.2](../../qa/android-management/2026-09-24-task-evidence-audit.md#t09)）
- [x] 使用限定argv、来源检查、持久拉取状态和摘要核实；断线先查原操作，不假定tag内容未变。引用校验到删除执行间持有同一管理锁，防止并发新引用。（状态：passed；来源先验、限定 argv、持久回执与共享锁已通过最终审查回归；[证据 T09.3](../../qa/android-management/2026-09-24-task-evidence-audit.md#t09)）
- [x] UI分开取消登记/删除内容；展示引用和未验证状态；不加入私有仓库凭据管理、tar导入或全局prune。（状态：passed；界面区分登记/内容删除与技术/GApps 状态；[证据 T09.4](../../qa/android-management/2026-09-24-task-evidence-audit.md#t09)）
- [x] GREEN后提交 `feat(android): manage image registrations and controlled pulls`。（状态：passed；30eb0926 及 a5bf3073 已交付软件；桌面删除/真实断线另列任务缺口；[证据 T09.5](../../qa/android-management/2026-09-24-task-evidence-audit.md#t09)）

### T10：模板版本与实例创建快照

**覆盖：** AM-R09/R07；AM-AC10/AC12。**依赖：** T08/T09。

**文件：** 新建 `B/application/android/templates.py`、`BT/contract/test_android_templates.py`、`F/components/TemplateManager.tsx`、`F/tests/TemplateManager.test.tsx`；修改fleet.py、android_fleet.py/schemas、CreateInstances.tsx。

**接口：** TemplateService.get/save/archive，沿用EnvironmentProfile与revision；archive软归档。创建快照冻结具体镜像和全部参数，不随模板变化。

- [x] fixtures使用真实TemplateService及临时资源/设备仓储，测试冲突、归档、参数范围、偶数宽高及快照不被改写。（状态：passed；使用既有 AndroidFleet 真实服务及临时仓储，revision/快照回归通过；[证据 T10.1](../../qa/android-management/2026-09-24-task-evidence-audit.md#t10)）

```python
def test_template_edit_keeps_existing_device_snapshot(templates, devices):
    before = devices.get(DEVICE_ID)['creationConfig'].copy()
    p = templates.get(PROFILE_ID)
    templates.save({**p, 'memoryMb': 2048})
    assert devices.get(DEVICE_ID)['creationConfig'] == before
```

- [ ] RED：`(cd apps/backend && uv run pytest tests/contract/test_android_templates.py -q)`及TemplateManager.test.tsx。（状态：not_run；当前 GREEN 已验证；该步骤独立历史 RED 输出未找到，不追认通过；[证据 T10.2](../../qa/android-management/2026-09-24-task-evidence-audit.md#t10)）
- [x] 支持模板新建/编辑/复制/归档；冲突409；实例除名称外只读，改配置引导新建，不偷偷docker update/recreate。（状态：passed；新建/复制/编辑/归档及已有实例快照已实现；[证据 T10.3](../../qa/android-management/2026-09-24-task-evidence-audit.md#t10)）
- [x] 创建UI展示真实镜像资料、模板默认值和用户覆盖；unknown不补默认Android13；Root不从模板名猜测。运行旧profile/batch兼容测试。（状态：passed；TemplateManager 与创建 UI 消费真实镜像、unknown 保留；[证据 T10.4](../../qa/android-management/2026-09-24-task-evidence-audit.md#t10)）
- [x] GREEN后提交 `feat(android): version templates and freeze configuration snapshots`。（状态：passed；软件切片已入历史，未另建重复模板服务；[证据 T10.5](../../qa/android-management/2026-09-24-task-evidence-audit.md#t10)）

### T11：谷歌组件候选镜像实验与验证记录

**覆盖：** AM-R10；AM-AC13/AC14。**依赖：** 实验最早T07，产品记录接入需T08。

**文件：** 新建 `B/domain/android/image_verification.py`、`BT/unit/test_android_image_verification.py`、`docs/qa/android-management/gapps-validation.md`；扩展images.py和ImageManager.tsx。不提交GApps、APK、账号或登录后数据。

**接口：** VerificationObservation含check_id/status/checked_at/evidence_id/reason；`summarize_verification(observations)->VerificationResult`，结果status/checked_at/checks/limitations由服务端归并，不接受任意passed开关。

- [x] 写只检测到包不能通过、缺登录条件blocked、任一必需项失败不能被其他成功覆盖、组件更新需复验测试。（状态：passed；六项必需证据、失败优先/缺项不通过的单元回归通过；[证据 T11.1](../../qa/android-management/2026-09-24-task-evidence-audit.md#t11)）

```python
from autoflow.domain.android.image_verification import summarize_verification

def test_no_observations_cannot_mean_passed():
    assert summarize_verification([]).status == 'not_tested'
```

- [ ] RED：`(cd apps/backend && uv run pytest tests/unit/test_android_image_verification.py -q)`；固定规格检查项，完整成功才passed，失败优先于blocked，缺项不能通过。（状态：not_run；当前 GREEN 已验证；该步骤独立历史 RED 输出未找到，不追认通过；[证据 T11.2](../../qa/android-management/2026-09-24-task-evidence-audit.md#t11)）
- [ ] 实验单独取得网络/设备变更授权和测试账号条件；固定候选来源、架构、imageId及构建说明，只用新测试实例。（状态：blocked；无专用 GApps 候选镜像和测试账号；本地测试 APK 已可用；[证据 T11.3](../../qa/android-management/2026-09-24-task-evidence-audit.md#t11)）
- [ ] 验证启动、商店、登录、免费测试应用下载/启动、停机重启、第二实例隔离；缺条件写blocked。不冒充正式认证，不绕过完整性限制，未核对许可不分发镜像。（状态：blocked；商店登录/下载/重启/第二实例隔离缺候选镜像及账号条件；[证据 T11.4](../../qa/android-management/2026-09-24-task-evidence-audit.md#t11)）
- [x] 提交 `docs(android): define and record google image validation evidence`；未实测就明确未执行，不打通过勾。（状态：passed；GApps 文档和独立 validation 字段已提交；实验明确未通过；[证据 T11.5](../../qa/android-management/2026-09-24-task-evidence-audit.md#t11)）

### T12：AM2集成及镜像生命周期验收

**覆盖：** AM-R08–R10/R17/R18；AM-AC11–AC14/AC23/AC24。**依赖：** T08–T11。

**文件：** 新建 `BT/integration/test_android_images_templates.py`、`F/tests/ImagesTemplatesFlow.test.tsx`、`docs/qa/android-management/am2-verification.md`；扩展受控smoke。

**接口：** scenario fixture由真实ImageService/TemplateService/AndroidManagement和临时库组成，仅Docker边界fake，记录实际启动命令的imageId。

- [x] 写登记→模板→创建→模板修改→tag变化→原实例重启→引用删除阻止的集成场景。（状态：passed；真实服务生命周期集成包含模板变化/tag 变化/固定 ID/引用阻删；[证据 T12.1](../../qa/android-management/2026-09-24-task-evidence-audit.md#t12)）

```python
def test_tag_change_does_not_upgrade_existing_instance(scenario):
    old_id = scenario.device_image_id
    scenario.retag_source_to('sha256:'+'b'*64)
    scenario.restart_existing()
    assert scenario.last_start_image_id == old_id
```

- [ ] RED/GREEN：`(cd apps/backend && uv run pytest tests/integration/test_android_images_templates.py -q)`及ImagesTemplatesFlow.test.tsx。（状态：not_run；当前 GREEN 已验证；该步骤独立历史 RED 输出未找到，不追认通过；[证据 T12.2](../../qa/android-management/2026-09-24-task-evidence-audit.md#t12)）
- [x] 真实验证基础与一个候选自定义镜像；谷歌失败不阻塞基础镜像交付，但状态必须保留failed/blocked/not_tested。（状态：passed；基础与自定义 ReDroid 均ready；模板/tag变化后旧实例固定ID、备份恢复和三类引用阻删实测通过；Google仍not_tested；[证据 T12.3](../../qa/android-management/2026-09-24-task-evidence-audit.md#t12)）
- [ ] 完整发布命令、迁移回归、旧实例恢复、镜像引用和回退检查；记录未覆盖条件。（状态：not_run；完整软件门禁通过；阶段停用入口及向前回退演练尚未运行；[证据 T12.4](../../qa/android-management/2026-09-24-task-evidence-audit.md#t12)）
- [x] 提交 `test(android): verify image and template lifecycle`；停在AM2验收点。（状态：passed；生命周期代码/证据已入历史；阶段仍有真实未验项；[证据 T12.5](../../qa/android-management/2026-09-24-task-evidence-audit.md#t12)）

## 4. AM3：多实例管理效率

### T13：冻结目标的批次与容量准入

**覆盖：** AM-R11/R12；AM-AC15/AC16。**依赖：** AM3授权、T12。

**文件：** 新建 `B/application/android/bulk.py`、`B/domain/android/capacity_rules.py`、`BT/unit/test_android_bulk.py`、`BT/integration/test_android_capacity_reservations.py`、`F/components/BulkActions.tsx`、`BulkProgress.tsx`、`F/tests/BulkActions.test.tsx`；扩展provider capacity与管理HTTP。

**接口：** BulkService.submit/action返回BulkRead，含冻结请求与逐项operationId；`can_admit(total_memory,running_limits,reserved_memory,requested_memory)->bool`使用bytes，任何未知输入None返回False。

- [x] 写1–20项、重复目标拒绝、筛选变化不改目标、部分失败、取消未开始项及预留竞态。（状态：passed；1–20/重复/冻结/失败/取消/预留竞态回归通过；[证据 T13.1](../../qa/android-management/2026-09-24-task-evidence-audit.md#t13)）

```python
from autoflow.domain.android.capacity_rules import can_admit

def test_unknown_memory_is_not_zero():
    assert can_admit(8*1024**3, None, 0, 1536*1024**2) is False

def test_reservations_count_towards_capacity():
    assert can_admit(4*1024**3, 2*1024**3, 1024**3, 1024**3) is False
```

- [x] RED：`(cd apps/backend && uv run pytest tests/unit/test_android_bulk.py tests/integration/test_android_capacity_reservations.py -q)`。（状态：passed；批次修订号/容量栅栏 RED→GREEN 见最终审查及容量 QA；[证据 T13.2](../../qa/android-management/2026-09-24-task-evidence-audit.md#t13)）
- [x] 复用Operation执行器，初始生命周期并发仍1。按规格计入512MiB保留量和待启动预留；停止未经核实不能提前释放预算。CPU为配额，不声称独占核。跨workspace/取消/进程重建、文件损坏、发布失败和真实限额漂移已验证；证据见9月23日容量记录。（状态：passed；512 MiB 保留、持久预留、未知占用和跨工作区真实容量已验；[证据 T13.3](../../qa/android-management/2026-09-24-task-evidence-audit.md#t13)）
- [x] UI确认冻结目标、破坏范围及阻塞项，逐项显示成功/失败/未知；取消不撤销已执行项，未知项不得retryFailed。（状态：passed；UI 冻结与逐项结果、未知禁止重试回归通过；[证据 T13.4](../../qa/android-management/2026-09-24-task-evidence-audit.md#t13)）
- [x] GREEN后提交 `feat(android): add safe bulk operations and capacity admission`。（状态：passed；软件切片已提交；真实容器消失故障重试与回执前强杀后的只读核实已通过；[证据 T13.5](../../qa/android-management/2026-09-24-task-evidence-audit.md#t13)）

### T14：后台观察、聚合查询和可见预览

**覆盖：** AM-R12；AM-AC17。**依赖：** T13。

**文件：** 新建 `B/application/android/observations.py`、`BT/unit/test_android_observations.py`、`F/tests/DevicePreviewVisibility.test.tsx`；修改devices.py、management_queries.py、bootstrap/app.py、useDeviceManagement.ts及DevicePreview.tsx。

**接口：** DeviceObservationService.snapshot(device_id)->Observation、refresh_due(now)->None；Observation保存runtimeState/observedAt/stale/error；管理GET只读快照。client/runtime fixture使用真实查询服务和fake observer，清除启动探测调用日志后再断言。

- [x] 假时钟测试活跃3秒/停止15秒/故障退避、10秒/45秒陈旧；列表读取无同步inspect。（状态：passed；假时钟周期/退避/陈旧及无同步 inspect 测试通过；[证据 T14.1](../../qa/android-management/2026-09-24-task-evidence-audit.md#t14)）

```python
def test_list_does_not_inspect_devices_synchronously(client, runtime):
    runtime.inspect.reset_mock()
    assert client.get('/api/v1/android/management/devices').status_code == 200
    runtime.inspect.assert_not_called()
```

- [x] RED：`(cd apps/backend && uv run pytest tests/unit/test_android_observations.py -q)`及DevicePreviewVisibility.test.tsx。（状态：passed；可见预览首次/取消 RED→GREEN 见 frontend-validation QA；[证据 T14.2](../../qa/android-management/2026-09-24-task-evidence-audit.md#t14)）
- [x] 观察器纳入bootstrap关闭协调；替换而不是叠加旧轮询；失败保留最后状态并标陈旧，不隐式修复。单一探测调度避免同设备积压。（状态：passed；观察器 bootstrap 协调和最后快照已实现；[证据 T14.3](../../qa/android-management/2026-09-24-task-evidence-audit.md#t14)）
- [x] UI3秒读聚合、隐藏页面暂停展示轮询；心跳独立。可见ready卡片5秒最小预览间隔、最多2并发；取消或换工作区丢弃旧响应并释放ObjectURL。（状态：passed；聚合轮询、可见性、2 并发与 ObjectURL 清理回归通过；[证据 T14.4](../../qa/android-management/2026-09-24-task-evidence-audit.md#t14)）
- [x] GREEN后提交 `perf(android): aggregate observations and bound previews`。（状态：passed；软件切片已入历史；真实性能剩余在 T16；[证据 T14.5](../../qa/android-management/2026-09-24-task-evidence-audit.md#t14)）
- [x] 2026-09-23 前端增量：首次可见性确认、最多2并发、排队/在途取消、共享消费者、后端切换迟到响应及 ObjectURL 释放已完成；Node22 Android 14文件/100项通过。真实规模指标仍未执行，T14/T16整体不据此关闭。证据：`docs/qa/android-management/2026-09-23-frontend-validation.md`。（状态：passed；历史前端增量保留；当前 Android 前端为 14 文件/135 项，另有备份说明增量；[证据 T14.6](../../qa/android-management/2026-09-24-task-evidence-audit.md#t14)）

### T15：常用应用管理

**覆盖：** AM-R13；AM-AC18。**依赖：** T05/T13。

**文件：** 新建 `B/application/android/apps.py`、`BT/contract/test_android_apps.py`、`F/components/ApplicationsPanel.tsx`、`F/tests/ApplicationsPanel.test.tsx`；修改mac_runtime.py、console.py、android_fleet.py/schemas。

**接口：** AppRead含packageName/versionName/versionCode/systemApp/protected；GET设备apps不claim；会话apps/actions包含requestId/generation/packageName/action；原安装路径增加requestId。

- [x] 写真实字节超限、损坏Manifest、不支持split包、只读拒写、保护包拒卸载、结果未知核实、卸载/清数据确认。fixture只fake包管理器。（状态：passed；APK Manifest/split/大小、只读、保护包、未知结果及确认测试通过；[证据 T15.1](../../qa/android-management/2026-09-24-task-evidence-audit.md#t15)）

```python
def test_readonly_session_cannot_clear_app_data(client, readonly_session):
    r = client.post(f'/api/v1/android/sessions/{readonly_session.id}/apps/actions',
        json={'requestId': DEVICE_ID, 'generation': readonly_session.generation,
              'packageName': 'com.example.fixture', 'action': 'clearData'})
    assert r.status_code == 409
```

- [ ] RED：`(cd apps/backend && uv run pytest tests/contract/test_android_apps.py -q)`及ApplicationsPanel.test.tsx。（状态：not_run；当前 GREEN 已验证；该步骤独立历史 RED 输出未找到，不追认通过；[证据 T15.2](../../qa/android-management/2026-09-24-task-evidence-audit.md#t15)）
- [x] 受控临时文件增量读取并计算摘要，256MiB上限，绑定幂等ID和目标；安装后核实版本，不重复执行未知结果；安全包名argv不拼任意shell。（状态：passed；受控上传/摘要/幂等/版本核对/命令标记恢复已实现并真实 APK 读回；[证据 T15.3](../../qa/android-management/2026-09-24-task-evidence-audit.md#t15)）
- [x] UI列表/搜索/启动/停止，卸载与清数据独立确认；刷新不隐式启动应用。系统与保护包不开放普通卸载，禁用原因可读。（状态：passed；列表搜索/动作/确认/禁用原因回归通过；[证据 T15.4](../../qa/android-management/2026-09-24-task-evidence-audit.md#t15)）
- [x] GREEN后提交 `feat(android): complete everyday application management`。（状态：passed；软件切片已入历史；9月24日桌面真实确认/执行/备份恢复与 ADB 断连已补；[证据 T15.5](../../qa/android-management/2026-09-24-task-evidence-audit.md#t15)）
- [x] 2026-09-23 增量：完成标记先验证语义，启动等待超时及旧零标记保持unknown；最终Android后端271项通过，真实单实例启动/停止与人工丢响应读回通过。真实APK/卸载/清数据、完整HTTP重启仍未关闭。证据：`docs/qa/android-management/2026-09-23-command-verification.md`。（状态：passed；历史命令语义增量保留；后续真实 APK 全动作和 HTTP 重启已补；[证据 T15.6](../../qa/android-management/2026-09-24-task-evidence-audit.md#t15)）

### T16：AM3隔离与性能验收

**覆盖：** AM-R11–R13/R18；AM-AC15–AC18/AC24。**依赖：** T13–T15。

**文件：** 新建 `BT/integration/test_android_multi_device.py`、`F/tests/MultiDeviceManagement.test.tsx`、`docs/qa/android-management/am3-verification.md`；扩展受控smoke。

**接口：** console fixture必须是真实AndroidConsole；session_a来自create，stream_a/stream_b为每台独立AsyncMock，不验证mock自身的预设返回值。

- [x] 写两个设备输入、占用、生命周期和数据隔离，批次部分失败/取消场景。（状态：passed；双设备隔离与批次取消/部分失败集成通过；[证据 T16.1](../../qa/android-management/2026-09-24-task-evidence-audit.md#t16)）

```python
import pytest

@pytest.mark.asyncio
async def test_input_never_reaches_another_device(console, session_a, stream_a, stream_b):
    await console.command(session_a['id'], {'generation': session_a['generation'],
        'sequence': 1, 'kind': 'text', 'text': 'sample'})
    assert stream_a.command.call_count == 1
    stream_b.command.assert_not_called()
```

- [ ] RED/GREEN：`(cd apps/backend && uv run pytest tests/integration/test_android_multi_device.py -q)`及MultiDeviceManagement.test.tsx。（状态：not_run；当前 GREEN 已验证；该步骤独立历史 RED 输出未找到，不追认通过；[证据 T16.2](../../qa/android-management/2026-09-24-task-evidence-audit.md#t16)）
- [ ] 获授权后实测至少两台独立实例。记录1/5/10台规模；硬件不足写blocked，不删除其他设备来满足测试。（状态：blocked；至少两台及五台已实测；十台最低 8192 MiB 超出 Lima 7921 MiB；[证据 T16.3](../../qa/android-management/2026-09-24-task-evidence-audit.md#t16)）
- [ ] 记录聚合API延迟、后台探测、预览并发、隐藏页行为与内存；执行完整发布门槛，确定性规则不得被平均性能掩盖。（状态：not_run；API/双预览/五台内存已记录；探测次数、隐藏页同链和前台交互指标未完整记录；[证据 T16.4](../../qa/android-management/2026-09-24-task-evidence-audit.md#t16)）
- [ ] 提交 `test(android): verify multi-instance isolation and responsiveness`；停在AM3验收点。（状态：not_run；软件与局部规模证据已提交；完整 T16 验收未结束；[证据 T16.5](../../qa/android-management/2026-09-24-task-evidence-audit.md#t16)）

## 5. AM4：数据与维护

### T17：本机一致性停机备份

**覆盖：** AM-R14；AM-AC19。**依赖：** AM4授权、T16。

**文件：** 新建 `B/application/android/backups.py`、`B/providers/android/backup_storage.py`、`B/domain/android/backup_models.py`、`BT/integration/test_android_backups.py`、`F/components/BackupPanel.tsx`、`F/tests/BackupPanel.test.tsx`；扩展资源仓储和管理HTTP。

**接口：** BackupService.create(request_id,device_id,expected_revision)->OperationRead；BackupRead对应规格格式1。BackupStorage.stage/finalize/discard只接受服务生成ID，不接受任意用户路径。

- [x] 写运行中/控制中拒绝、磁盘不足、中断/取消、摘要失败和权限测试。fixture用临时卷目录和真实服务。（状态：passed；运行/控制拒绝、errno28、取消、权限和发布故障回归及真实磁盘/取消已验；[证据 T17.1](../../qa/android-management/2026-09-24-task-evidence-audit.md#t17)）

```python
def test_running_device_cannot_be_backed_up(client, running_device):
    r = client.post('/api/v1/android/management/backups', json={
        'requestId': DEVICE_ID, 'deviceId': running_device.id,
        'expectedRevision': running_device.revision})
    assert r.status_code == 409
```

- [x] RED：`(cd apps/backend && uv run pytest tests/integration/test_android_backups.py -q)`及BackupPanel.test.tsx。（状态：passed；发布故障及本轮可访问说明有 RED→GREEN，测试映射至 ManagementTools；[证据 T17.2](../../qa/android-management/2026-09-24-task-evidence-audit.md#t17)）
- [x] 核实停机、持有设备操作互斥后复制卷，保存UID/GID/mode及经验证必要属性；写staging，校验再原子发布；失败仅清理本作业staging。（状态：passed；停机/归属/独占、GNU tar 属性、私有 staging 和原子发布已验；[证据 T17.3](../../qa/android-management/2026-09-24-task-evidence-audit.md#t17)）
- [x] UI说明可能含私密数据及本机未加密边界，限制文件权限；不加入外部上传/账号模板/运行中热备份。（状态：passed；本轮补本机未加密/私密数据说明并绑定操作的可访问描述；权限回归通过；[证据 T17.4](../../qa/android-management/2026-09-24-task-evidence-audit.md#t17)）
- [x] GREEN后提交 `feat(android): add consistent local stopped-device backups`。（状态：passed；备份核心已入历史；本轮说明/真实故障证据为待提交增量；[证据 T17.5](../../qa/android-management/2026-09-24-task-evidence-audit.md#t17)）

### T18：安全恢复到新实例

**覆盖：** AM-R15；AM-AC20。**依赖：** T17。

**文件：** 扩展backups.py/backup_storage.py；新建 `BT/integration/test_android_backup_restore.py`、`F/tests/BackupRestore.test.tsx`。

**接口：** BackupService.restore(backup_id,request_id,new_name)->RestoreRead；RestoreRead包含新deviceId/operation/backupId；validate_archive_path(path:PurePosixPath)->None，非法路径抛ValueError。只支持格式1和exact imageId。

- [x] 写新ID、不变源卷、损坏摘要、镜像不符、必要属性丢失、越界/链接穿越和失败隔离。（状态：passed；新身份/源保护/摘要/镜像/属性/链接/隔离回归通过；[证据 T18.1](../../qa/android-management/2026-09-24-task-evidence-audit.md#t18)）

```python
from pathlib import PurePosixPath
import pytest

def test_parent_traversal_is_rejected():
    from autoflow.providers.android.backup_storage import validate_archive_path
    with pytest.raises(ValueError):
        validate_archive_path(PurePosixPath('../outside'))
```

- [x] RED：`(cd apps/backend && uv run pytest tests/integration/test_android_backup_restore.py -q)`；必须同时覆盖链接穿越、合法内部链接和目标属性，不只检查一个字符串。（状态：passed；恢复隔离与 manifest/身份 RED→GREEN 见对应 QA；[证据 T18.2](../../qa/android-management/2026-09-24-task-evidence-audit.md#t18)）
- [x] 生成新deviceId/容器/卷/标签，清旧进程/控制/操作引用；仅处理本作业资源，原备份及源实例不改。无法安全恢复属性时明确失败。（状态：passed；新目标意图和归属、源保护及安全属性失败已实现；[证据 T18.3](../../qa/android-management/2026-09-24-task-evidence-audit.md#t18)）
- [x] 同机同镜像真实演练检查测试数据；UI称恢复应用数据，不保证登录/DRM/私有密钥或完整身份克隆。（状态：passed；真实源/目标数据与属性读回；本轮补登录/DRM/私钥限制说明；[证据 T18.4](../../qa/android-management/2026-09-24-task-evidence-audit.md#t18)）
- [x] GREEN后提交 `feat(android): restore verified backups into new instances`。（状态：passed；恢复软件已入历史；真实解包中 SIGKILL 已验，取消/目标磁盘不足真实验收亦通过；[证据 T18.5](../../qa/android-management/2026-09-24-task-evidence-audit.md#t18)）

### T19：清理预览与脱敏诊断

**覆盖：** AM-R16；AM-AC21/AC22。**依赖：** T17/T18。

**文件：** 新建 `B/application/android/cleanup.py`、`BT/contract/test_android_cleanup.py`、`BT/unit/test_android_diagnostic_redaction.py`、`F/components/DataMaintenance.tsx`、`F/tests/DataMaintenance.test.tsx`；扩展diagnostics.py。需要导出时新建 `DS/main/ipc/android-diagnostics.ts`，接入现有preload白名单，不加入任意文件写接口。

**接口：** CleanupService.preview(resource_ids)->CleanupPreview；execute(preview_id,confirmation_digest,request_id)->OperationRead；CleanupPreview冻结资源/revision/引用/摘要；redact_diagnostics(payload)->dict；IPC只接受diagnosticId和单次用户保存确认。

- [x] 测试预览后引用变化、外部卷、标签不符、过期预览、重复请求；诊断白名单剔除私密字段。（状态：passed；预览变化/外部标签/过期/幂等/白名单回归通过；[证据 T19.1](../../qa/android-management/2026-09-24-task-evidence-audit.md#t19)）

```python
from autoflow.application.android.diagnostics import redact_diagnostics

def test_private_payloads_are_not_exported():
    result = redact_diagnostics({'code': 'ANDROID_BUSY',
        'inputText': 'private', 'accounts': ['private'], 'logcat': 'raw'})
    assert result == {'code': 'ANDROID_BUSY'}
```

- [x] RED：`(cd apps/backend && uv run pytest tests/contract/test_android_cleanup.py tests/unit/test_android_diagnostic_redaction.py -q)`及DataMaintenance.test.tsx。（状态：passed；清理与高级日志 RED→GREEN 见 cleanup/advanced QA；复用现有测试文件；[证据 T19.2](../../qa/android-management/2026-09-24-task-evidence-audit.md#t19)）
- [x] 冻结候选并执行时重检引用/归属；变更则409；禁止全局prune及外部路径递归删除。预检和执行不能绕过设备锁。（状态：passed；冻结指纹/引用与设备锁、异步父子收敛回归通过；[证据 T19.3](../../qa/android-management/2026-09-24-task-evidence-audit.md#t19)）
- [x] 诊断默认只输出白名单，额外日志单次同意并限时限量、脱敏；IPC拒绝过期/跨工作区导出ID，不自动发送任何文件。（状态：passed；高级日志单次确认、5 分钟/64KiB/200行、真实196条仅元数据已验；[证据 T19.4](../../qa/android-management/2026-09-24-task-evidence-audit.md#t19)）
- [x] GREEN后提交 `feat(android): add scoped cleanup and redacted diagnostics`。（状态：passed；软件切片已提交；多对象硬中断已验；无来源旧客体文件仍不能推断归属；[证据 T19.5](../../qa/android-management/2026-09-24-task-evidence-audit.md#t19)）

### T20：AM4恢复演练与最终交付

**覆盖：** AM-R14–R18；AM-AC19–AC24。**依赖：** T17–T19。

**文件：** 新建 `docs/qa/android-management/am4-verification.md`、`docs/qa/android-management/README.md`；扩展smoke与本轮集成测试；更新 `.ai/plans/android-emulator-management.md` 完成状态和证据索引。

**接口：** 证据记录最终commit、固定imageId、平台、命令、逐项结果、源/目标资源ID及脱敏摘要；不是全量设备数据。

- [x] 执行数据写入→停机备份→恢复新实例→核对数据→清理预览→确认清理；源实例保持。使用真实服务与临时库验证下列断言，再做授权实机演练。（状态：passed；真实数据写入/备份/新卷恢复/读回/清理与源保护见 AM4 QA；[证据 T20.1](../../qa/android-management/2026-09-24-task-evidence-audit.md#t20)）

```python
assert restored.device_id != source.device_id
assert restored.volume_id != source.volume_id
assert restored.owner_kind == 'none'
assert source_data_digest_after == source_data_digest_before
```

- [x] 再测磁盘不足、损坏备份、恢复中断、引用阻止镜像删除、诊断隐私，确认失败不会发布假成功备份或清理外部资源。（状态：passed；真实备份/恢复 ENOSPC、取消、在途硬中断、损坏包与多对象清理已验；引用和脱敏保护包含本轮451项回归，高级日志有真实证据；[证据 T20.2](../../qa/android-management/2026-09-24-task-evidence-audit.md#t20)）
- [ ] 运行1.4节全部发布命令与真实设备回归；逐项填写规格24个验收项，无法执行的项目单列blocked。（状态：not_run；软件门禁已通过，24 项均有说明；仍有具备条件的真实项尚未运行；[证据 T20.3](../../qa/android-management/2026-09-24-task-evidence-audit.md#t20)）
- [x] 检查向前回退策略，无破坏性downgrade、旧迁移篡改或新工作流执行器；更新证据索引但保留历史事实。（状态：passed；迁移头/旧迁移字节与业务回归通过；回退策略为关闭新入口并向前修复，实操演练另列 T12；[证据 T20.4](../../qa/android-management/2026-09-24-task-evidence-audit.md#t20)）
- [x] 提交 `test(android): complete management recovery and maintenance acceptance`；报告实际完成和限制，不自动接入工作流。（状态：passed；30eb0926 已交付代码/证据并报告 partial；整体目标仍 active；[证据 T20.5](../../qa/android-management/2026-09-24-task-evidence-audit.md#t20)）

## 6. 需求—任务—验收追踪

| 需求 | 任务 | 验收 |
| --- | --- | --- |
| AM-R01 | T06/T07 | AM-AC01 |
| AM-R02 | T03/T07 | AM-AC02 |
| AM-R03 | T02/T06 | AM-AC03 |
| AM-R04 | T04/T07 | AM-AC04/AM-AC09 |
| AM-R05 | T05/T07 | AM-AC05/AM-AC06/AM-AC07 |
| AM-R06 | T04/T06/T07 | AM-AC08/AM-AC09 |
| AM-R07 | T06/T07/T10 | AM-AC01/AM-AC10 |
| AM-R08 | T08/T09/T12 | AM-AC11 |
| AM-R09 | T10/T12 | AM-AC12 |
| AM-R10 | T11/T12 | AM-AC13/AM-AC14 |
| AM-R11 | T13/T16 | AM-AC15 |
| AM-R12 | T13/T14/T16 | AM-AC16/AM-AC17 |
| AM-R13 | T07/T15/T16 | AM-AC18 |
| AM-R14 | T17/T20 | AM-AC19 |
| AM-R15 | T18/T20 | AM-AC20 |
| AM-R16 | T19/T20 | AM-AC21/AM-AC22 |
| AM-R17 | T01/T04/T08/T12/T20 | AM-AC23 |
| AM-R18 | T01/T07/T12/T16/T20 | AM-AC24 |

## 7. 审查与执行交接

执行前核实详细规格已批准、当前批次已授权、工作区隔离、迁移图正确。每个任务审查API与字段一致、旧安全保护未降级、读取无隐式变更、未知结果未重放、类型已生成、测试确实调用生产服务。

代码块是任务中的测试示例，不是本次已经实现的功能。fixture必须按各任务说明创建并调用真实被测服务，只fake IO边界；不得只验证mock自己的返回值。文档结构检查与业务测试、真实Electron、真实ReDroid及谷歌网络验证分别报告。

规格及计划评审后，先执行AM1。具备实际子代理工具时可按独立任务分工并审查；否则按依赖顺序执行。文档完成不代表AM1–AM4已实施，也不自动授权设备变更或默认分支合并。
