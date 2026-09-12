# 项目管理里程碑：实际代码与依赖基线

- 日期：2026-09-13；状态：confirmed（只读核验事实），文件规划为 proposed。
- 设计 worktree：`autoflow-project-management-design`，`codex/project-management-design@349c4be`；PM0开工时干净，设计事实仍固定906deda。
- PM0初读主项目HEAD为 `f3fe3760fd7637819e99b51844767860ad830c62`；交付前另一任务提交Studio M1，最终只读基线为 `b2e95b3c70fcecb9787b133c83fba9e2cc9e9e18`。此前about:blank及“Studio全为WIP”的当前结论均 superseded；其他未提交变更继续保留。
- 主目录有其他任务修改及未跟踪文件，严格只读。实施前再核对实际 heads，不能将本记录当成未来一直有效的checkout状态。

## 事实与计划影响

| 源码/文档证据（相对主目录） | 已有事实 | 计划如何使用 |
|---|---|---|
| `apps/desktop/src/main/ipc/automation-studio.ts`；`apps/desktop/src/shared/automation-studio.ts` | b2e95b3已提交Studio renderer、离开确认桥；openAutomationStudio仍无工作流参数 | PM3需接入稳定文档上下文及真正执行；本轮不复跑另一任务验收 |
| `apps/backend/src/autoflow/` 目录枚举；`bootstrap/app.py` | 尚无项目数据、批次、环境及Studio执行领域/路由；b2e95b3已有工作流文档CRUD与节点目录 | 本计划新增真实模型与用例；不把旧原型当可复用后端 |
| `application/profiles/test_browser.py`；`infrastructure/process/test_browser_worker.py`；`providers/browser/worker.py` | Profile测试浏览器具备启动/关闭/状态和CloakBrowser进程能力 | 复用底层适配经验，不能让测试浏览器服务承担第二执行循环 |
| `infrastructure/database/session.py`、`models.py`、`migrations/versions/` | 单SQLite、SQLAlchemy、Alembic；最终已提交head `0005_workflow_documents`，从0004派生 | 新增领域映射，迁移增量提交；不修改已存在0002分叉/0003汇合历史 |
| `application/settings/runtime.py` | QuiesceGate及mutation/process blocker | 每个新活动用例及时注册阻断，PM8做组合生命周期验收 |
| `infrastructure/credentials/system.py`、`domain/credentials.py` | 已有系统凭据抽象 | Sheets复用凭据引用；日志和业务记录不复制连接秘密 |
| `apps/backend/pyproject.toml`、`uv.lock` | 当前无Excel或Sheets库/适配器，已有httpx/keyring | PM2补Excel依赖及锁文件，PM6复用httpx传输和系统凭据，不伪报现有来源功能 |
| `renderer/app/App.tsx`、`renderer/app/ApplicationHeader.tsx`、`renderer/app/ApiProvider.tsx` | 现有全局页面与重连上下文 | 项目路由通过正式入口接入，保留同工作区重连草稿规则 |
| `renderer/shared/components/ui/` | 主线已有基础Radix控件；较完整控件在独立分支 | 先对齐UI提交，Table/Combobox/ScrollArea等不要重新实现 |
| `scripts/generate-api.mjs` | 从临时后端导出OpenAPI到唯一 generated.ts；check检查过期 | 每个真实API包生成并核对，不手写另一套传输类型 |
| `package.json`、`apps/desktop/package.json`、`.github/workflows/ci.yml` | pytest/ruff/mypy、Vitest/tsc/eslint、构建与三平台CI命令已有 | 当前测试不证明项目管理功能完成；新增范围测试和真实项目冒烟 |

上述表中的 `application`、`domain`、`infrastructure`、`providers`、`bootstrap` 以 `apps/backend/src/autoflow/` 为前缀，`renderer` 以 `apps/desktop/src/` 为前缀；该缩写仅用于证据表，不是新目录。

## 独立UI分支与旧来源

- `/Users/zhangtiancheng/Documents/projects/autoflow-ui-controls-plan` 本轮核对 HEAD `1fb58e188c3b1063c86e19d4c6d80bba0ecbe92e`，工作树干净。
- 已见真实文件：`ui/combobox.tsx`、`table.tsx`、`pagination.tsx`、`scroll-area.tsx` 及相应测试、Dialog/Select测试。最新提交修复下拉展开宽度变化。
- 该提交未作为本轮主线已有UI能力声称；实施集成者先审实际diff，合入已需要的组件、样式和调用适配及其测试，保护其他模块，不复制第二套基础库。
- 旧项目固定 `324748abe7095f085b4ffb9467be9cb5c8851a5c`：`autoflow-desktop/backend/pyproject.toml` 使用 `openpyxl==3.1.5`、`defusedxml==0.7.1`。这是旧来源依赖事实，不声称最新版本；PM2按现有Python3.11与打包链验证并锁定实际迁移依赖。
- 旧状态、身份、Excel/Sheets和并发证据继续见[上一轮设计核验](../design/design-verification.json)，不重写该快照。

## Studio最新范围

主线完整核心目标已确认，Studio M1已在b2e95b3提交。`adapters/http/workflows.py` 提供 `/api/v1/workflows` 创建/列表/读取/条件保存及 `/node-catalog`；`workflow_schemas.py` 使用核心 `document.id`、`revision`、`expectedRevision`，节点目录 `runnable=false`。本轮读取了已提交代码与 `.ai/sessions/2026-09-13-automation-studio-m1.md`、验收文档索引；另一任务记录了M1验证，本轮没有复跑，不能据此把C01幂等操作等新增契约全标通过，也不能抵扣C02准备/Run/检查点。

项目计划消费文档保存、基础执行、变量/控制流、诊断、检查点和平台能力；不假设Studio必须全做完才允许创建项目/编辑数据。原设计R编号由里程碑正文的能力映射解释，双方各保留一个核心实现。

## 核验限制

本轮运行只读Git/源码搜索、文档链接/编号/覆盖/依赖检查。未启动应用、执行pytest/Vitest、安装依赖、操作Sheets或跑Windows/macOS验收。里程碑中的测试文件、路由与新脚本均是后续实施目标，不能把本记录当通过报告。

## PM0 冻结与集成策略（2026-09-13）

- 初始读取时间：2026-09-12T18:27:42Z（北京时间2026-09-13）。主项目61条工作树条目，UI干净，旧项目1744条条目；状态计数只描述读取时点，不复制其他任务全量变更或隐私。旧源码继续使用固定git对象324748a。
- Studio源码快照及读取哈希记录在plan-verification.json；开发中的源文件可能继续变化，交付前重新核对。源码存在、测试文件存在、阶段验收通过分别记录。
- 数据库不执行upgrade：静态读迁移revision/down_revision构图。PM1集成以当时正式接入的唯一head创建pm01；当前主线0005已接入，应先对齐该提交后从0005派生；仍停留0004的隔离分支必须由集成者显式处理迁移汇合，并由唯一集成者在合入并发迁移时建立合法汇合。后续Run外键必须等待核心Run表迁移接入；不预造核心revision、不重写历史0002/0003。
- 当前Shared UoW经验来自SQLAlchemy会话与代理事务用例；还没有可供项目使用的core prepareRun。PM3必须实现并验收同事务参与，不能声称已有端口可直接调用。
- 已有内核事件是operations快照，没有运行事件逐条id/replay；共享events解析器可复用传输部分，核心必须提供Run快照和补读契约。
- 新项目公开DTO沿用camelCase错误封装；命令沿Idempotency-Key（UUID）和持久查询惯例。文件IPC复用DesktopResult/取消null/受控选择，实际project-files接入在PM2。
- UI合入仍属PM1，由集成者核对1fb58e1的组件、样式、测试及页面适配差异，不整片复制或强制覆盖主目录。

PM0的契约是后续实现必须达到的规范，核心所有者尚未提交对应Run实现；本阶段的独立审查不冒充另一任务签收。PM1无须等Run，PM3按能力门槛验收。

最终核对以plan-verification.json时间/哈希为准：主目录已从f3fe376推进至b2e95b3，状态条目由初始61、途中70到最终37；这是其他任务的提交/变更，本任务仅记录且不回滚。静态AST迁移图唯一head为0005_workflow_documents；未执行数据库升级。
