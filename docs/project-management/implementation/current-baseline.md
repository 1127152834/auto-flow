# 项目管理里程碑：实际代码与依赖基线

- 日期：2026-09-13；状态：confirmed（只读核验事实），文件规划为 proposed。
- 设计 worktree：`autoflow-project-management-design`，`codex/project-management-design@906deda`，本轮起始无未提交变化。
- 主线本轮先核对 `ec18662`，交付前为 `f0b115c6510464b18b56414bc1753c30cc46afb4`。后一个提交仅登记 redroid 参考仓库，未改变项目/Studio 运行能力。
- 主目录有其他任务修改及未跟踪文件，严格只读。实施前再核对实际 heads，不能将本记录当成未来一直有效的checkout状态。

## 事实与计划影响

| 源码/文档证据（相对主目录） | 已有事实 | 计划如何使用 |
|---|---|---|
| `apps/desktop/src/main/ipc/automation-studio.ts`；`src/shared/automation-studio.ts` | 实际入口加载 about:blank；公开桥仅打开窗口 | 有窗口不等于已有工作流保存或执行；PM3依赖真实核心能力 |
| `apps/backend/src/autoflow/` 目录枚举；`bootstrap/app.py` | 尚无项目数据、批次、环境及Studio执行领域/路由 | 本计划新增真实模型与用例；不把旧原型当可复用后端 |
| `application/profiles/test_browser.py`；`infrastructure/process/test_browser_worker.py`；`providers/browser/worker.py` | Profile测试浏览器具备启动/关闭/状态和CloakBrowser进程能力 | 复用底层适配经验，不能让测试浏览器服务承担第二执行循环 |
| `infrastructure/database/session.py`、`models.py`、`migrations/versions/` | 单SQLite、SQLAlchemy、Alembic；当前head `0004_proxy_remote_controls` | 新增领域映射，迁移增量提交；不修改已存在0002分叉/0003汇合历史 |
| `application/settings/runtime.py` | QuiesceGate及mutation/process blocker | 每个新活动用例及时注册阻断，PM8做组合生命周期验收 |
| `infrastructure/credentials/system.py`、`domain/credentials.py` | 已有系统凭据抽象 | Sheets复用凭据引用；日志和业务记录不复制连接秘密 |
| `apps/backend/pyproject.toml`、`uv.lock` | 当前无Excel或Sheets库/适配器，已有httpx/keyring | PM2补Excel依赖及锁文件，PM6复用httpx传输和系统凭据，不伪报现有来源功能 |
| `renderer/app/App.tsx`、`ApplicationHeader.tsx`、`ApiProvider.tsx` | 现有全局页面与重连上下文 | 项目路由通过正式入口接入，保留同工作区重连草稿规则 |
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

主线 `.ai/decisions/2026-09-13-automation-studio-core-parity-scope.md` 已确认完整核心目标；`docs/superpowers/plans/2026-09-13-automation-studio-core-parity-milestones.md` 的M0–M7仍为计划。

项目计划消费文档保存、基础执行、变量/控制流、诊断、检查点和平台能力；不假设Studio必须全做完才允许创建项目/编辑数据。原设计R编号由里程碑正文的能力映射解释，双方各保留一个核心实现。

## 核验限制

本轮运行只读Git/源码搜索、文档链接/编号/覆盖/依赖检查。未启动应用、执行pytest/Vitest、安装依赖、操作Sheets或跑Windows/macOS验收。里程碑中的测试文件、路由与新脚本均是后续实施目标，不能把本记录当通过报告。
