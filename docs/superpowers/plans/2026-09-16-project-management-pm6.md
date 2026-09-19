# PM6 实施计划：Google Sheets 来源与同步闭环

> **状态：** 2026-09-18 按已批准总计划开工；本卡只展开实施，不改业务规则
> **工作区：** `/Users/zhangtiancheng/Documents/projects/autoflow-project-management-pm6`
> **分支：** `codex/project-management-pm6`
> **基线：** `5f07e2ad`（PM5 合并进 `codex/architecture-baseline` 后的集成点）
> **技能：** 只维护本执行卡；`subagent-driven-development` 按文件所有权分包；交付前 `verification-before-completion`

## 1. 现场核对（2026-09-18）

| 项目 | 事实 | 证据 |
|---|---|---|
| 预计路径 `autoflow-project-management-pm6` | 开工前不存在，本次从 `codex/architecture-baseline` 新建 worktree | `git worktree list` |
| 已批准业务规格 | 有：总里程碑 PM6 节；设计 §10 Sheets、§11 出站队列；HTTP §3.4 已冻结 16 个端点与全部 DTO | `2026-09-13-project-management-milestones.md:208`、`data-and-state-rules.md:307-360`、`api-contracts.md:316-360` |
| 迁移 head | `pm07_environments`；计划里的 `pm06_project_sync.py` 已被 `pm06_project_capability_reads.py` 占用，实际文件必须改为 **`pm08_project_sync.py`** | `migrations/versions/` 实际文件名 |
| 新仓库现有 Sheets 相关代码 | 仅 DTO 占位：`sourceKind` 已含 `sheets`，但建表只接受 `local`；`syncSummary` 硬编码 `notApplicable/0/0`。**无任何 Sheets 后端实现** | `application/project_data/tables.py:123`、`domain/project_data/models.py:51` |
| 旧项目可复用实现 | `browser-automation` @ `b085167` 有 13 个后端模块约 7000 行 Sheets/OAuth 实现、3 个迁移、6 个前端文件；**当前工作树中的 .py 已被删除，只剩 `__pycache__`，必须从该提交取** | `git ls-tree -r b085167 -- autoflow-desktop/backend/src/autoflow` |
| 旧参考导出 | 已导出 31 个文件到 `/tmp/pm6-legacy-sheets/`（backend / migrations / main / renderer/google / renderer/project-data） | `find /tmp/pm6-legacy-sheets -type f` |
| 凭据底座 | 新仓库已有 `domain/credentials.py` + `infrastructure/credentials/system.py`（keyring，macOS/Windows） | 现状代码 |
| 视觉依据 | `latest/05-data/011-source-sheets-8e6927.png`（来源设置页）、`latest/05-data/100-sheets-directions-d6ac8c.png`（拉取/推送/同步边界）。仅全局导航改顶部，其余主体布局跟随原型 | 原型目录 |
| 其他工作区 | 主项目、PM1/PM3/PM4/PM5、`browser-automation` 全部只读 | 本卡只改本 worktree |

本卡是唯一 PM6 执行卡。业务规则只引用已批准合同，不另写设计。

## 2. 目标与验证边界

PM6 交付 Google Sheets 连接与多绑定、字段与身份映射、本地意图到远端确认的完整同步链、公式只读刷新、受控远端增列、来源调整与恢复。保留 PM0–PM5，不进入 PM7/PM8。

**执行方式：**

- Electron 管理界面、FastAPI、SQLite、Operation 查询、领取占用、数据能力必须真实。
- Google 侧要么使用真实 OAuth 访问授权测试表，要么对 REST 层做受控替身；替身运行必须逐条标注，不能写成实网通过。
- 不调用真实 Studio，不改 Studio 画布/transport/bridge，不建第二套执行器。

**外部授权依赖（诚实边界）：** 真实 Google 端到端需要用户提供 OAuth 桌面客户端 JSON（或服务账号 JSON）与明确授权的测试 Spreadsheet。缺少时自动与本地契约照常验收，实网项保持「未执行」，**PM6 不得记完整通过**。报告分两栏写：`管理侧与本地契约已验证` / `实网 Google 端到端未执行`。

## 3. 最近可演示目标（V1 垂直切片）

真实管理界面在项目里连接 Google 账号 → 把一张表绑定到某 Spreadsheet/工作表（含检查、身份校验、映射）→ 本地改一条记录 → 立即推送 → 操作核验显示已确认 → 拉取刷新公式 → 页面看到同步状态与操作证据。

先跑通这一条，再补多绑定重叠、增列、暂停/恢复、未知结果与重启恢复。不等 PM6-C 全部完成才第一次联调。

## 4. 交付包与文件所有权

迁移实际文件为 `pm08_project_sync.py`，`down_revision=pm07_environments`。计划里的 `pm06_project_sync` 名称不再使用。

| 包 | 交付 | 独占范围 | 主协调保留 |
|---|---|---|---|
| PM6-0 | 迁移、DTO、路由注册、`generated.ts`、availability、quiesce 接线 | 迁移与契约文件 | 全部 |
| PM6-A | 连接、多绑定、结构检查、身份策略与全量核验、重叠报告 | `providers/data/google_auth.py`、`providers/data/google_sheets.py`、`application/project_sync/connections.py`、`application/project_sync/bindings.py`、`adapters/http/project_sheets*.py`、`apps/desktop/src/main/google-*.ts` | 迁移、bootstrap、`generated.ts` |
| PM6-B | 出站队列、发送/核验状态机、pull/push、操作查询、reconcile/abandon | `application/project_sync/outbound.py`、`infrastructure/database/project_sync.py` | Operation 契约、幂等键、quiesce、领取占用 |
| PM6-C | 公式刷新、受控增列、暂停/恢复/断连、来源与代次隔离、重启核验 | `application/project_sync/schema_ops.py`、`application/project_sync/recovery.py` | — |
| PM6-UI | 连接面板、绑定向导、同步面板、来源页签 | `domains/project-data/components/SheetsConnectionPanel.tsx`、`SheetsBindingWizard.tsx`、`SyncOperationPanel.tsx`、`SetOperationsSummary.tsx` | 页面装配、路由、`DataTableSourcePanel.tsx`、`DataTableDetailPage.tsx` |
| PM6-F | 端到端、截图同视口对照、覆盖账本、手测方案 | — | 全部 |

共享文件一次只由一人改：`infrastructure/database/migrations/versions/*`、`bootstrap/app.py`、`adapters/http/project_http_routes.py`、`shared/api/generated.ts`、`DataTableSourcePanel.tsx`、`DataTableDetailPage.tsx`、`coverage.json`。

## 5. 不做

不重新设计；不建第二执行器；不调用 Studio demo；不进入 PM7/PM8；不改历史迁移；不删除失败断言或放宽阈值；凭据、OAuth 令牌、Cookie 不进日志、截图报告或提交；不占用 Chrome 调试端口 9222。

## 6. 进度

- [x] PM6-0 现场核对、工作区、契约与迁移
- [x] PM6-A 连接/身份/多绑定
- [x] PM6-B 出站队列与核验
- [~] PM6-C 公式/增列/来源调整/恢复 —— 公式只读刷新、暂停/恢复、断开连接、解除绑定影响预检、未知结果核验与恢复已交付；**远端受控增列未交付**：冻结契约 §3.4 与 OperationKind 都没有对应路由或 kind，属计划与契约不一致，需契约决定后才做。系统身份列按已批准规则需要独立初始化动作，契约中没有，当前明确返回 501 `SYNC_NOT_IMPLEMENTED`。
- [x] PM6-UI 四个组件接真实页面；来源页签按原型 `100-sheets-directions` 的两栏骨架定稿（左栏来源事实/拉取/推送/同步记录，右栏同步边界/来源核对）
- [x] 自动验收与替身端到端已完成，同视口截图 12 张与手测方案已交付。
- [~] 实网 Google 端到端：**服务账号路径已用用户提供的真实凭据与真实 Spreadsheet 跑通**（2026-09-19，10 检查点 / 11 截图）；**OAuth 桌面应用路径未执行**，需要用户的 OAuth 桌面客户端 JSON。

### 6.1 交付记录（2026-09-18）

| 项 | 结果 |
|---|---|
| 后端全量 | `3044 passed, 16 skipped, 0 failed`（8 分 33 秒） |
| PM6 定向 | 契约/身份/同步/恢复/规则 42 passed |
| 静态检查 | Ruff `All checks passed`；mypy 379 文件无问题 |
| 前端全量 | `392 files / 5370 tests passed` |
| 工具链 | openapi:check、typecheck、lint、build、test:scripts(72)、test:structure、`git diff --check` 全绿 |
| 真实界面 | `docs/project-management/implementation/pm6/qa-runs/2026-09-18/`：13 检查点 / 13 截图，status=passed |
| 机器报告 | `docs/project-management/implementation/pm6/verification.json` |
| 手测方案 | `docs/project-management/implementation/pm6/manual-test.md` |

视觉对照：`docs/project-management/implementation/pm6/ui-verification.md`——原型 `011-source-sheets` 86 分、`100-sheets-directions` 88 分，均过门槛；唯一未对齐项是「来源核对」卡（冻结契约没有漂移汇总 DTO）。

第三轮（2026-09-18 22:3x）补交付：来源页签改为原型两栏骨架；修复四处 `<td>` 嵌在 `<thead>` 的表头、记录身份重复渲染、解绑确认脱离触发按钮；新增「推送结果未知」状态截图；`scripts/structure.test.mjs` 增加仓库级断言禁止 thead 内嵌 td。全量复核：后端 3044 passed / 16 skipped、Ruff、mypy、前端 392 files / 5371 tests、typecheck / lint / build 全绿，真实界面 QA 13 检查点 / 13 截图 passed。

端到端抓出并修复的真实缺陷：绑定命令用 POST 打只接受 PUT 的路由（真实界面绑定必然 405）、拉取/推送后记录页不重取、来源页把读取失败显示为空事实、连接面板列错位。

基线对照：交接文档记录的「704 项基线失败」是 PM6 工作区缺少被 gitignore 的 `reference/` 参考检出的环境假象。在 `5f07e2ad` 上补齐只读符号链接后，`tests/differential + tests/migration` 956 passed、侧车与崩溃回归 39 passed，基线在受影响范围内全绿。

### 6.2 实网交付记录（2026-09-19）

用户提供了服务账号 JSON 与已授权的测试 Spreadsheet（`ck自动化表格` / `工作表2` / 87 行 / 表头 `邮箱, 是否使用`）。新增 `scripts/qa-pm6-google-live.mjs`，在隔离 Electron + **真实 FastAPI sidecar + 真实 HttpxSheetsTransport + 真实系统凭据库**下用真实点击跑通全链：

| 检查点 | 结果 |
|---|---|
| 界面创建项目 / 数据表 / 两个字段并整体保存 | ✓ |
| 服务账号凭据经主进程交接写入系统凭据库 | ✓ 状态「可用 / 可读可写」 |
| 来源检查与绑定（表头 2 列，身份列 A） | ✓ 来源类型变更为 Google Sheets |
| 从真实 Google Sheet 拉取 | ✓ 87 条，文本身份原样 |
| 推送本地改动并核验远端 | ✓ `工作表2!B2` 实际写入，操作 `confirmed/matched` |
| 还原远端、解除绑定、删除本机凭据 | ✓ 连接列表清空；独立复核整表无测试标记残留 |

`live-result.json` 的 `status` 为 `passed`，证据 `docs/project-management/implementation/pm6/google-live/2026-09-18T16-05-05-012Z/`；缺陷现场保留在 `2026-09-18T15-58-11-615Z/`。

实网抓出并修复的真实缺陷：`sheets-api.ts` 的 `disconnect()` 漏传 HTTP 动词，默认 POST 打只接受 DELETE 的路由 → 405，用户无法删除凭据且只看到「操作失败，请重试」。已修复并补两条动词回归用例（无修复时失败）。这是替身轮没抓到的第三处同类缺陷（前两处是 binding 的 PUT、拉取/推送后不重取）。

本轮定向复核：`project-data` 域 65 文件 / 684 测试、typecheck、lint、build、`test:structure` 4/4 全绿。

## 7. 验证命令

```bash
uv run --directory apps/backend pytest tests/unit/test_project_sheets_rules.py tests/contract/test_project_sheets.py tests/integration/test_project_sheets_identity.py tests/integration/test_project_sheets_sync.py tests/integration/test_project_sheets_recovery.py -q
uv run --directory apps/backend ruff check . && uv run --directory apps/backend mypy src
npm --workspace @autoflow/desktop test -- src/renderer/domains/project-data
npm run openapi:generate && npm run openapi:check
npm run typecheck && npm run lint && npm run build && npm run test:scripts && npm run test:structure
git diff --check
```

阶段退出再跑原计划全量检查（后端全量 pytest、Ruff、mypy，前端全量 Vitest 及以上全部）。Windows/其他架构/打包/用户手测未执行时保持未验收。

## 8. 旧项目复用映射（只读参考）

参考导出目录：`/tmp/pm6-legacy-sheets/`。语义按新设计重述，不整段照搬；旧实现是单机镜像模型，新要求 bindingEpoch、操作级证据与租约分层。

| 旧文件 | 行数 | 可复用什么 | 新落点 |
|---|---|---|---|
| `backend/google_auth.py` | 789 | PKCE + 回环授权 + 系统浏览器打开、服务账号 JWT 签名、令牌刷新/吊销、系统凭据存取 | `providers/data/google_auth.py` |
| `backend/google_auth_api.py` | 92 | 端点形状与同源校验思路 | `adapters/http/project_sheets*.py` |
| `backend/project_google.py` | 300 | 每项目连接实例缓存、生命周期互斥 | `application/project_sync/connections.py` |
| `backend/sheets_adapter.py` | 668 | Sheets REST 客户端（metadata/values/batchUpdate）、Grid 解析、公式错误、时区取值、请求节流、回执核验 | `providers/data/google_sheets.py` |
| `backend/sheets_identity.py` | 394 | 行指纹、系统列归属标记与校验、隐藏系统列、身份冲突拒绝 | `application/project_sync/identity.py` |
| `backend/sheets_merge.py` | 179 | 本地覆盖层与远端网格合并 | `application/project_sync/merge.py` |
| `backend/sheets_push.py` | 235 | 请求分包、体积上限、持久批次登记与恢复 | `application/project_sync/outbound.py` |
| `backend/sheets_scheduler.py` | 1182 | 按 Spreadsheet 串行、后台循环、暂停/唤醒、每项目互斥 | `application/project_sync/scheduler.py` |
| `backend/sheets_service.py` | 863 | 候选代次暂存、身份检查、结构预检、短事务发布切换 | `application/project_sync/bindings.py` |
| `backend/sheets_records.py` | 1801 | 内容版本、变更日志、记录 CRUD 与同步状态投影、影响计算 | `application/project_sync/outbound.py`（并入新 `project_data` 存储） |
| `migrations/v2_0007/0009/0012` | 200 | 表结构草图：绑定、内容版本、变更日志、发送批次 | `pm08_project_sync.py` |
| `renderer/project-data/SheetsBindingDialog.tsx` | 746 | 绑定向导步骤与校验交互 | `SheetsBindingWizard.tsx` |
| `renderer/project-data/SheetsSyncPanel.tsx` | 297 | 拉取/推送/核验面板与状态文案 | `SyncOperationPanel.tsx` |
| `renderer/google/GoogleConnectionPanel.tsx` | — | 连接状态与授权入口 | `SheetsConnectionPanel.tsx` |
| `main/google-desktop.ts` | 18 | 只允许打开 Google 授权地址的白名单校验 | `apps/desktop/src/main/google-desktop.ts` |

**旧状态到新契约的映射（必须按新契约重述）**

| 旧字段 | 新契约 |
|---|---|
| `sheets_bindings.model_id` | `tableId` |
| `sync_epoch` | `bindingEpoch` |
| `data_record_changes.state` = `pending/sending/verifying/synced/failed/superseded/cancelled` | `SyncStatus` = `pending/sending/verifying/confirmed/failed/unknown/paused`（`superseded/cancelled` 归入合并与放弃语义，不新增状态） |
| `sheets_push_batches` | `SyncOperation` + `SyncEvidence{checkedAt,target,fields,outcome}` |
| `data_record_content_versions.revision` | 记录 `contentRevision`（已有） |
| 旧 `IdentityCheck`（系统列/业务列） | `identityStrategy{kind:'column'|'system',columnId?}` |

**不可照搬的三点**

1. 旧实现直接把候选数据写进 SQLite 业务表并切换代次；新仓库数据由 `application/project_data` 与 `infrastructure/database/project_data.py` 管辖，候选写入必须走该存储，不能重写第二套。
2. 旧实现只有「绑定级」状态；新契约要求每条出站操作独立 `statusRevision`、`operationId` 与核验证据。
3. 旧实现把未知结果按失败重试；新契约要求未知结果先核验，不换目标重放。

