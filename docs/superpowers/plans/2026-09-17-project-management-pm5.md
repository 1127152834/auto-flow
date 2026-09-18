# PM5 实施计划：登录环境持续使用与人工介入

> **状态：** 2026-09-17 按已批准总计划开工；本卡只展开实施，不改业务规则  
> **工作区：** `/Users/zhangtiancheng/Documents/projects/autoflow-project-management-pm5`  
> **分支：** `codex/project-management-pm5`  
> **基线：** `fbda6f1736b53ebf8144513c893e1bf6bc5a459b`（PM4 管理交付）  
> **技能：** 只维护本执行卡；`subagent-driven-development` 按文件所有权分包；交付前 `verification-before-completion`。

## 1. 现场核对（2026-09-17）

| 项目 | 事实 | 证据 |
|---|---|---|
| 预计路径 `autoflow-project-management-pm5` | 开工前不存在 | `ls` / `git worktree list` |
| 已有 PM5 分支 / 执行卡 / 未提交实现 | 无 | `git branch -a`、`docs/superpowers/plans`、会话检索 |
| 已批准业务规格 | 有：总里程碑 PM5 节、契约 C10–C18、HTTP §3.6、设计/原型 | `2026-09-13-project-management-milestones.md`、`contracts.md`、`api-contracts.md` |
| PM4 基线 | 管理功能 delivered / 验证 partially_verified；环境页未开放；启动只允许 `newFromProfile` | PM4 HEAD `fbda6f17`、`AVAILABILITY.environments=notImplemented`、`project_runs/rules.py` |
| 迁移 head | `pm06_project_capability_reads`；计划名 `pm05_environments` 已被 claims 占用 | 实际 head 测试 |
| 其他工作区 | 主项目、PM3/PM4 只读 | 本卡只改本 worktree |

本卡是唯一 PM5 执行卡。业务规则只引用已批准合同，不另写设计。

## 2. 目标与验证边界

PM5 交付环境身份、完整 End 保留/关联/维护、人工介入与额度竞争。保留 PM0–PM4，不进入 PM6，不改 Studio 画布/transport/bridge，不建第二套生产执行器。

**执行方式（沿用 PM4 已批准隔离测试执行器，并补真实浏览器存取）：**

- Electron 管理界面、FastAPI、SQLite、环境文件、关联、占用、Run/Operation 事实必须真实。
- 登录保存/恢复必须经过 CloakBrowser `launch_persistent_context_async` 与本地测试站，不能只验证模拟 JSON。
- 测试执行器可模拟工作流节点推进、检查点恢复与 End 编排；这些项在报告中逐条标记为模拟。
- 生产装配不因 QA 替换核心。报告区分「管理侧及实际浏览器环境存取已验证」与「真实执行核心接入待验收」。

## 3. 最近可演示目标

真实管理界面建项目与账号表 → 启动任务并在本地测试站登录 → End 保留并关联账号 → 关闭原浏览器 → 后续任务按记录关联环境恢复登录 → 环境页查看来源、关联与运行事实。

不等 PM5-C 全部完成才第一次联调。

## 4. 交付包与文件所有权

迁移实际文件为 `pm07_environments.py`，`down_revision=pm06_project_capability_reads`。计划中的 `pm05_environments` 名称不再使用。

| 包 | 交付 | 独占范围 | 主协调保留 |
|---|---|---|---|
| PM5-A | 身份、三种来源、工作副本、环境页分区、默认资源 | `domain/environments/*`、环境领域组件/页面（不含路由装配） | 迁移、bootstrap、generated.ts、availability、启动规则 |
| PM5-B | End 保存/关联/另存、部分结果、修复、维护、列表详情重命名备注删除影响 | `application/environments/retention.py`、环境维护组件 | 记录 `bindRecordEnvironment`、Operation kind、占用 CAS |
| PM5-C | 同一份人工事实、继续/结束/超时/停止唯一结果、额度 | `application/environments/manual.py`、人工详情 | Run 状态投影、调度额度、停止契约 |

共享文件一次只由一人改：`project_http_routes.py`、`app.py`、`generated.ts`、迁移、`AVAILABILITY`、`project_runs/rules.py`。

## 5. 不做

不重新设计；不调用 Studio demo；不把模拟执行写成生产工作流可用；不提前释放未确认占用；凭据/Cookie/令牌不进日志、截图报告或提交；不进入 PM6。

## 6. 进度

- [x] 现场核对并建立隔离工作区
- [x] PM5-A 身份/来源/占用/目录 HTTP 与环境页（管理侧已接通；真实 CloakBrowser 存取测试待内核）
- [ ] 可演示的真实浏览器保存→关联→关闭→恢复链（helper + 本地登录夹具已就位，需 AUTOFLOW_TEST_CLOAKBROWSER）
- [x] PM5-B 保存/关联/部分结果/修复/维护打开/删除影响查询（删除命令仍属 PM8）
- [ ] PM5-C 人工继续/结束/超时唯一结果已有后端与目录；额度与现场进入浏览器未完
- [ ] 11 项真实验收、视觉同视口、手测、覆盖账本

## 7. 验证命令

```bash
uv run --directory apps/backend pytest tests/unit/test_project_environment_rules.py tests/contract/test_project_environments.py tests/integration/test_project_environment_retention.py tests/integration/test_project_manual_actions.py -q
npm --workspace @autoflow/desktop test -- src/renderer/domains/environments
npm run openapi:generate && npm run openapi:check
```

阶段退出再跑原计划全量检查。Windows/其他架构/打包/用户手测未执行时保持未验收。

## 8. 接手续做检查点（2026-09-17 04:06 +08）

状态：进行中；工作树未提交，基线仍为 `fbda6f17`。本节覆盖旧交接中关于 persist 未复跑和 QA 进程仍运行的结论，历史失败记录保留。

| 交付目标 | 本次事实 / 剩余阻断 | 负责人及文件范围 | 完成证据 | 依赖 |
|---|---|---|---|---|
| 真实浏览器保存 / 恢复 | CloakBrowser 登录、完全关闭 context、保存目录、恢复新实例、重新访问 `/me` 已通过；不是 UI 全链 | 主协调：persistent_context、登录集成夹具、environment_store | `test_environment_persist_restore.py`；本轮最终定向命令通过 | 已安装公开内核 145.0.7632.109.2 |
| Task 和环境预约同事务 | 参数和数据领取均将实例 / 环境占用写入 Task/Run 所在 Session；预约失败不吞掉 | 主协调：coordinator、scheduler、EnvironmentService、SqlAlchemyEnvironments | 参数额度真实 SQLite 反例、数据领取故障反例、成功 / 同键重发回归 | 目录准备、完整恢复与资源派发仍待闭合 |
| 管理 UI 首链 | 最新构建已运行；界面新建真实 profile，201；旧保存环境仍引用占位 profile，validation 阻断正确 | 主协调：只在标记 QA 工作区操作 | `qa-runs/resume-profile-blocked.png`、`resume-start-rejection.json` | 真实环境实例 opener、Run 工作目录装配 |
| 浏览器打开 / 关闭与 End | `opener=None`、目录参数未接；保存前真实进程关闭与人工恢复仍未验收 | 主协调：后续按既有服务 / provider / bootstrap 落点收口 | 无完成证据；不把状态变更当浏览器已打开 | 受控进程与失败恢复 |
| 工程及独立审查 | 限定 Ruff 与 diff 检查通过；最新 mypy 17 个错误未闭合；独立审查未取得有效结论 | 主协调；审查独立只读范围 | mypy 当前运行输出，不能引用历史报告全绿 | PM5 既有 retention/schema/repository 类型问题 |

### 本轮根因与修复

1. CloakBrowser 官方 persistent API 自己传 `executable_path`，helper 再传一次会抛 TypeError；移除重复参数，真实测试以官方 `CLOAKBROWSER_BINARY_PATH` 选择明确内核。
2. 真实浏览器集成夹具曾调用 `_closed_instance`，向 `Default/Cookies` 写入占位字节，破坏 SQLite Cookie 文件。改用真实空实例；仍执行原登录 / 关闭 / 保存 / 新目录恢复 / 已登录断言，没有替换为 mock。
3. 目录复制排除 Chromium runtime locks 后，digest 同样排除这些临时文件，避免源 / 副本不一致。现有摘要仅比较路径和大小，不能据此宣称内容校验已完备。
4. 原参数启动 commit 后才 attach，`newFromProfile` 失败被吞；数据调度同样吞掉 attach 错误。先补失败反例，再将预约纳入调用者 Session；实际目录准备仍在提交后。未声称已完成所有文件与 Run 恢复竞态。

### 本次验证范围

- 真实 CloakBrowser 集成及环境 / 参数启动 / PM4 调度相关回归：58 passed；2 项依赖弃用警告。它证明列出的测试行为，不等于完整 PM5。
- 限定文件 Ruff、`git diff --check` 通过。`npm run build` 通过，保留依赖注释和 chunk 警告。
- `uv run --directory apps/backend mypy src`：17 errors / 5 files，未通过。完整工程退出检查未执行。
- 原 QA PID 已不存在，无需 kill；重新启动固定 9333 的隔离 Electron。浏览器配置 `PM5 真实登录测试` 由 UI 创建，id `2c1fa094-63d8-4bb4-a895-82d48682d6b9`。旧自动化未被悄悄改成真实保存环境。
- 对旧自动化直接 POST batches 得到 422 RESOURCE_UNAVAILABLE / PROFILE_NOT_FOUND，前后批次数均为 0；单独登记为直接 HTTP 负向验证，不是 UI E2E。
- UI 完整链、原型评分、Windows、其它架构、打包、用户手测、真实执行核心接入：未执行 / 未完成。

### 后续定向修复与审查（同日）

- 已补真实 SQLite Run 派发→WorkflowBrowserResources.acquire 集成反例，修复租约缺少 userDataDir：通过进程内注入的目录解析器以 run_request_id 查询权威 Run/Task/instance；不是把 run_request_id 当 active_run_id。仅运行态、单一活动实例、适用占用有效、目录实际存在时返回工作目录。bootstrap 已注入，停止态拒绝获取。该证据模拟 profile/kernel 与浏览器 worker，不表示生产工作流验收。
- 独立审查已返回有效报告，取代本节先前“无审查结论”的临时状态。其范围扩大到了既有 End 生命周期：关联事务 CAS 缺失、保存执行代次信任请求自身、End 未真实关闭浏览器、opener 未装配、End 子操作随机键与重启阶段恢复不足。不得因历史 PM5-B 打勾忽略这些问题。
- CAS 修复：bind_records 在短写事务内重读并比较 linkRevision 及 previous_environment_id，包括无变化结果。两记录反例证明后一记录并发关联导致整组回滚，前一记录不部分保存。仍须补当前合同的 lease、关联证据与幂等提交整体审查，不声称整个 XE-C10 已完成。
- 真实浏览器主动关闭后的 persist/restore 仍通过。完整管理端 End 保存、关联、恢复链没有通过，opener/closer、权威保存代次、阶段恢复仍是下一阻断。
- 修改后限定生产文件 Ruff 通过；扩展到原环境合同测试文件发现原有三处 BLE001，尚未宣称全量 lint 通过。mypy 未全绿；最终视觉和端到端尚未执行。
- 最终相关回归 77 passed / 2 warnings（24.74s），含真实 CloakBrowser 主动关闭后的恢复；不是完整 PM5。随后执行单独真实浏览器→管理 HTTP End 探针，登录成功，但 End 抛 Error，浏览器未被关闭，恢复未执行，结果 failed，证据 `qa-runs/resume-real-end-probe.json`。该探针使用合成 Task/Run 身份准备环境与真实浏览器，不能声称真实 Task 运行或 Electron E2E 已通过。

## 9. 接续实施检查点（2026-09-18 12:12 +08）

状态：进行中；工作树未提交，基线 HEAD 仍为 `fbda6f17`。本节取代 §8 中"管理端 End 保存未通过""opener 未装配""UI 未用新构建验收"等结论，历史失败证据保留。

| 当前交付目标 | 具体阻断 | 负责人及文件范围 | 完成证据 | 依赖 |
|---|---|---|---|---|
| 管理侧首链：建项目→配置→自动化→启动→进入浏览器→End 保留→真实关闭 | 无（本机连续两次通过） | 主协调：`application/environments/service.py`、`providers/browser/environment_browser.py`、`tests/qa/pm5_sidecar.py`、`scripts/qa-project-management-pm5.mjs`、`src/main/index.ts`、`src/main/sidecar/supervisor.ts` | `qa-runs/2026-09-18/ui-result.json`（status=passed，13 检查点，20 截图） | 已安装内核 `chromium-145.0.7632.109.2` |
| 真实浏览器保存/恢复/内容代次 | 无（HTTP + 真实浏览器层通过） | 主协调：`providers/browser/persistent_context.py`、`scripts/qa-pm5-browser-chain.py` | `qa-runs/2026-09-18/browser-chain.json` | 同上 |
| 工程退出检查 | 全量 pytest / Ruff / mypy 已通过；前端命令见 §10 | 主协调 | §10 表格 | — |
| **视觉对齐（06-environments）** | 通过：PM5 范围内 6 个画板 ≥85；`100-rename-validation-conflict` 与已批准设计冲突待产品确认；范围外画板已登记 | 主协调：`domains/environments/**` | `docs/project-management/implementation/pm5/ui-verification.md` | 需先确认 006 默认资源编辑归属 |
| **人工详情（PM5-C）** | 未实现：见 §12；后端 `GET /manual-items/{id}` 与 resume/finish 已就绪，前端缺「一份人工详情」与运行记录侧入口 | 主协调：`domains/environments/**`、`domains/project-runs/**`、路由装配 | 无 | `GET /manual-items`、`allowedTargets` |
| 真实执行核心接入 | 未验收（本阶段允许隔离执行器） | 核心侧 | 无 | Studio/核心里程碑 |

### 本轮根因与修复

1. **`openInstance` 永久停在 `running`（真实缺陷）**：`open_instance` 原先只捕获 `ProjectError`，launcher 抛出的 Chromium/OS 异常会绕过收口，用户只能轮询一个永不完成的请求。已把整个 `with self._lifecycle_lock(...)` 段纳入收口，新增 `_fail_operation()`，非域异常写 `INSTANCE_OPEN_FAILED`（details 含 `domainCode/retryable/cause`）。失败反例先写先红：`tests/contract/test_project_environments.py::test_open_records_an_unexpected_launch_failure_instead_of_leaving_it_running`。
2. **End 保存 410 `EXECUTION_GENERATION_REVOKED` 的根因是"真实执行器与人工接管抢同一个 `userDataDir`"**：sidecar 日志显示 `TargetClosedError` + `正在现有的浏览器会话中打开` + playwright 杀进程 EPERM；真实执行器被人工接管打断后进入 `reconciling`，撤权 `execution_generation` 1→2，End 按旧代次保存被拒。这不是 End 保存逻辑缺陷，而是 PM5 明示的"人工接管 vs 真实执行核心"语义冲突。本阶段按已批准边界改用隔离测试执行器，让任务在整个链里保持 `queued`。
3. **诊断能力**：侧车 stdout/stderr 原先被丢弃，失败无法解释。`supervisor.ts` 新增 `attachLog()`，把侧车输出写到 `<dataDir>/logs/sidecar.log`（失败静默、不阻塞服务）；`developmentModule` 改为优先读 `AUTOFLOW_QA_SIDECAR_MODULE`，**仍以 `!app.isPackaged` 为前提**，打包应用不受影响。

### 隔离测试执行器边界（报告口径）

`tests/qa/pm5_sidecar.py` 调用生产 `create_app(settings)`，只从 `app.router.on_startup` 摘掉 `project_run_scheduler.startup`（停用批次派发），其余装配、路由、事务、SQLite、文件存储全部真实。因此：

- **管理侧及实际浏览器环境存取已验证**：界面点击、FastAPI、SQLite、环境目录副本、CloakBrowser 145 真实启动/关闭、保存/恢复登录态。
- **真实执行核心接入待验收**：生产工作流执行器跑完整节点链、任务内真实浏览器执行、检查点恢复与 End 编排。

### 本轮证据

- `node scripts/qa-project-management-pm5.mjs` 连续两次 `passed`（`/tmp/pm5-qa-5.log`、`/tmp/pm5-qa-6.log`，EXIT=0），10 检查点全过；关键事实 `sidecarModule=tests.qa.pm5_sidecar`、`taskStatus=queued`、`runStatusBeforeEnd=queued`、`runGenerationBeforeEnd=0`、`savedEnvironments=1`、`closedAfterEnd=true`、`browserKernel` 指向工作区内 `chromium-145.0.7632.109.2`。
- `qa-runs/2026-09-18/`：`ui-result.json` + 20 张 1440×1024 截图（`scrollWidth<=1440` 有断言），覆盖环境页四分区、重命名抽屉与校验态、等待人工现场与目录、读取失败与重试恢复。历史 `99-failure.png`（12:58 失败构建）已移到 `/tmp/pm5-superseded-99-failure.png`，未删除。
- `qa-runs/2026-09-18/browser-chain.json`：真实内核启动 → 登录 → End 保留+关联 → `browserClosedByEnd=true`、实例 `cleaned` → 恢复 `/me` 得"已登录" → 写标记 v2 → 二次 End `contentGeneration=2` → 三次打开读到"已登录"+v2。
- 无 `autoflow-pm5-ui-qa*` 与 `Chromium.*environments/instances` 残留进程；遗留的 `crossloop_probe`（pid 62664/62666）已终止。

### 视觉验收结论（06-environments 范围通过；范围外缺口已登记）

`ui-verification.md` 复验版逐画面评分：`001`=88、`003`=88、`004`=88、`005`=87、`100-rename-drawer`=90、`010`=90（PM5 触达的可用性状态）全部达到 ≥85 且强制结构项通过；唯一被批准的差异仍是顶部导航。`100-rename-validation-conflict`=62，原因是原型要求项目内名称唯一、与已批准设计 `execution-and-environment.md:277`「名称不是身份」冲突，需产品确认，本轮未擅自加唯一约束。范围外缺口（`002` 属 PM3/PM4、`006` 与 `007`–`009` 属 PM3-A、`100-delete-impact-preview` 与 `100-cleanup-*` 属 PM8/PM3-C）已在报告第 5 节登记。旧版低分结论（`001`=40 等）对应当日 12:00 前构建，历史保留、未删除，但不再代表当前状态。

### 清理与未执行

- 隔离工作区只清 `autoflow-pm5-ui-qa-*`（须带 `.pm5-qa.json` 的 `kind=pm5-project-management-qa` 标记）；清理方法见 `manual-test.md` §6。
- 未执行：Windows、其他架构、打包应用、用户手测、真实执行核心接入、视觉修复后的复验。

## 10. 本轮自动检查结果

| 检查 | 结果 | 关键数字 |
|---|---|---|
| `uv run --directory apps/backend pytest -q -p no:randomly`（带 `AUTOFLOW_TEST_CLOAKBROWSER`） | 通过 | 1656 passed / 2 warnings / 308.04s |
| `uv run --directory apps/backend ruff check .` | 通过 | 修掉 `tests/contract/test_project_environments.py` 两处 `I001` 后 `All checks passed!` |
| `uv run --directory apps/backend mypy src` | 通过 | `Success: no issues found in 274 source files`（§8 记录的 17 errors 已闭合） |
| 前端与结构检查 | 见 `verification.json` | `npm test` / `openapi:check` / `typecheck` / `lint` / `test:structure` / `test:scripts` / `git diff --check` |

## 11. 退出条件对照

| PM5 退出条件 | 现状 |
|---|---|
| 环境身份/来源/工作副本（PM5-A） | 管理侧通过；真实执行核心未验收 |
| End 完整保留与关联（PM5-B） | 管理侧通过（含真实关闭原浏览器）；阶段与逐目标结果未逐条截图 |
| 人工/额度/竞争（PM5-C） | 环境页等待人工列表（06-env `003`）与后端合同通过；运行记录侧等待人工列表、「一份人工详情」（03-runs `003`/`008`/`019`/`020）与任务列表人工入口（002）已交付并截图，见 §13；`018`（检查失败→重新检查）与 `021`（证据缺失）按缺口登记 |
| 逐图审查通过 | `06-environments` 内 PM5 画板 6/6 通过；`03-runs` 内 5 个画面（002/003/008/019/020）通过，`018`/`021` 无实图并登记为缺口，见 §13 与 `pm5/ui-verification.md` 附录 |
| 全量工程检查 | 通过 |
| 手测方案 | 已交付 `manual-test.md`，用户未执行 |
| 未执行平台 | Windows、其他架构、打包、用户手测 |

**结论：PM5 停在验收点。管理侧及真实浏览器环境存取可作为管理侧交付；`06-environments` 与 `03-runs` 范围内的视觉对照通过（11 个画面），§12 的继续实施项已由 §13 收尾；`03-runs/018`（依赖真实执行核心的上下文校验）与 `021` 仍按缺口登记，`100-rename-validation-conflict` 的唯一性规则待产品确认；真实执行核心接入待验收。**

## 12. 新发现的 PM5 范围缺口与继续实施（2026-09-18 接续）

现状：管理侧首链、真实浏览器存取、`06-environments` 视觉对照已完成。核对对齐账本 `docs/project-management/design-alignment/runs-environments.json` 后确认：**PM5 的范围不止 `06-environments` 目录**，还包括 `03-runs` 的人工类画板，而这一组此前没有被对照，也没有实现。

| 画板 | 账本 pmPhases | 账本要求 | 当前事实 |
|---|---|---|---|
| `03-runs/002-task-list-approved` | PM3, PM5 | 「PM5 开放人工入口」 | 任务列表只有状态筛选，没有人工入口 |
| `03-runs/003-manual-list-selected-v2` | PM5 | 运行记录第三页签「等待人工」：等待原因 / 所属任务 / 剩余保留时间 / 操作，可搜索、按剩余时间排序 | 运行记录只有批次、任务两个页签 |
| `03-runs/008-manual-detail-v2-approved` | PM5 | 「一份人工详情供运行/环境入口使用」：冻结现场与输入、剩余时间；继续工作流（选继续节点）/ 标记完成 / 标记失败；处理写回原任务 | 无人工详情页面；环境页「进入人工处理」直接开浏览器 |
| `03-runs/018-manual-check-failed` | PM5 | 检查失败时保留现场、提供重新检查、继续禁用、保留时间不重置 | 未实现 |
| `03-runs/019-manual-complete-confirm` | PM5 | 「标记完成」二次确认：处理说明 + 已知情勾选；完成不等于资料已保存 | 未实现；现有「明确结束」硬编码 `outcome=failed` |
| `03-runs/020-manual-expired` | PM5, PM8 | 保留时间到期后的状态与处置 | 列表有「已超过保留时间」文案，无独立到期页 |
| `03-runs/021-evidence-missing` | PM3, PM5, PM8 | 证据缺失时的说明与处置 | 未实现 |

里程碑正文 §PM5-C 的原文是「**一份人工详情**供运行/环境入口使用；浏览器处理后校验并继续同一任务；人工结束、超期、取消、窗口关闭和现场失联按核心唯一转换处理」。执行卡 §4 也把「人工详情」列在 PM5-C 的独占范围内。因此这是**计划内未交付项**，不是新增范围。

### 本轮继续实施顺序

1. **人工详情（008）**：新增 `domains/project-runs/pages/ManualDetailPage`（或等价落点），使用既有 `GET /manual-items/{manualItemId}`、`resume`、`finish`；继续工作流走 `allowedTargets` 选择继续节点，标记完成/失败分别提交 `outcome` 与处理说明；「打开环境」复用 `POST /environment-instances/{id}/open`。
2. **运行记录「等待人工」页签（003）**：在 `RunDirectoryPage` 增加第三页签，列 等待原因 / 所属任务 / 剩余保留时间 / 操作，接入搜索与剩余时间排序；行操作进入人工详情。
3. **完成确认（019）** 与失败/到期/证据缺失（018/020/021）按能力如实呈现：已实现的后端事实才显示为可操作，缺失能力显示为不可用并说明原因，不显示假操作。
4. **两个入口**：环境页「进入人工处理」改为进入同一份人工详情；详情内「打开环境」才启动浏览器。
5. 证据：定向 Vitest + 导航/路由测试 + QA 脚本新增检查点与截图 + `ui-verification.md` 追加 `03-runs` 逐画面评分。

完成后重跑阶段全量检查与 QA，更新覆盖表与 `.ai`。不进入 PM6，不改 Studio。

## 13. 第二轮补交付检查点（2026-09-18 13:40 +08）

状态：§12 的五项继续实施已完成；工作树未提交，基线 HEAD 仍为 `fbda6f17`。本轮修掉四处真实缺陷，并把 `03-runs` 的人工链接到真实页面与真实接口。

| 当前交付目标 | 具体阻断 | 负责人及文件范围 | 完成证据 | 依赖 |
|---|---|---|---|---|
| 运行记录「等待人工」页签（003） | 无 | 主协调：`domains/project-runs/pages/RunDirectoryPage.tsx`、`components/ManualItemDirectory.tsx` | `qa-runs/2026-09-18/20-manual-list-tab.png`、`components/ManualItemDirectory.test.tsx` | `GET /manual-items` |
| 一份人工详情（008/018/019/020） | 无（提交前必须知情确认、失败必填原因在弹窗内校验） | 主协调：`domains/project-runs/pages/ManualDetailPage.tsx`、`components/ManualItemDirectory.tsx` | `21`/`22`/`23` 截图、`ManualDetailPage.test.tsx`（6 例） | `resume`/`finish`、`allowedTargets` |
| 任务列表人工入口（002） | 无 | 主协调：`application/project_runs/queries.py`、`adapters/http/project_run_schemas.py`、`components/TaskDirectory.tsx` | `24` 截图、`tests/contract/test_project_runs.py` | `manual_item_id` 仅对未结束事项返回 |
| 任务列表列结构对齐 002 | 无（本轮补齐） | 同上 | `24` 截图、`RunDirectories.test.tsx` 两条列断言 | `lastStatusAt` 由服务端事实计算 |
| 超时终态（020） | 无（本轮补截图与检查点） | 主协调：`ManualDetailPage.tsx`、`scripts/qa-project-management-pm5.mjs` | `25`/`26` 截图、`ManualDetailPage.test.tsx` 终态用例 | 注入的 `expired` 资料脚本内删除并还原运行状态 |
| 真实执行核心接入 | 未验收（本阶段允许隔离执行器） | 核心侧 | 无 | Studio/核心里程碑 |

### 本轮根因与修复

1. **「标记完成」永远无法提交（真实缺陷）**：`canSubmit` 要求 `chosen === 'complete'` 时 `agreed` 已勾选，而 `agreed` 只能在确认弹窗内勾选，页面级按钮因此永久禁用。改为页面级只校验选择，知情勾选在弹窗内校验。
2. **人工详情路由永远进不去（真实缺陷）**：`ProjectsWorkspace` 的 runs 分支写成 `route.taskId ? (route.manualItemId ? …)`，人工事项没有 `taskId`，因此被短路。改为 `manualItemId` 优先。
3. **等待人工目录空态误报（真实缺陷）**：默认为 `waiting` 的状态筛选被当成用户施加的筛选条件，空库时显示「没有匹配」。改为只认用户明确设置的搜索或非默认状态。
4. **终态仍显示不可用表单（真实缺陷）**：`expired`/`resolved` 等终态仍渲染「继续/完成/失败」表单。按原型 018/020 改为「处理结果」+「历史现场」，隐藏「打开环境」，并提供「查看任务日志」「刷新状态」，同时写明管理侧只登记已确认事实，不按倒计时推断清理结果。

### 本轮补充：002 任务列表列结构

原型 `03-runs/002` 的任务表列是 任务/自动化 · 所属批次 · 输入标识 · 任务状态 · 当前或结束节点 · 时间（最近状态时间）· 操作。此前实现只有 任务 · 自动化 · 输入标识 · 任务状态 · 结束时间 · 操作。

- 新增服务端 `lastStatusAt`：取任务创建、最近一次节点尝试、运行开始与运行结束四个真实事实中的最新者；排队任务因此等于创建时间，**不按客户端时钟或剩余时间推断**。合同测试覆盖「排队任务＝创建时间」与「有节点尝试时＝最近尝试时间」两个反例。
- 目录上下文的「所属批次」使用已加载的批次选项名，缺失时退回 `自动化名 · 批次开始时间`，不显示内部 ID；「当前或结束节点」使用已有 `endNodeName`，未结束时如实写「尚未结束」。

### 本轮证据

- QA：`node scripts/qa-project-management-pm5.mjs` → `qa-runs/2026-09-18/ui-result.json`（status=passed，16 检查点，27 截图，1440×1024 / DPR 1，逐图断言 `scrollWidth <= 1441`）。本轮新增检查点：等待人工任务行的人工入口、超时终态处理结果。
- 视觉对照：`docs/project-management/implementation/pm5/ui-verification.md`（06-environments 6 个画面 + 03-runs 人工类画面逐画面评分）。
- 定向回归：`project-runs` + `environments` + `navigation` 26 文件 / 166 项通过；后端 `tests/contract/test_project_runs.py` 16 项通过（含 `lastStatusAt` 的「排队＝创建时间」与「有节点尝试＝最近尝试时间」两个反例）。
- 阶段全量检查（本轮实跑）：后端 `pytest -q -p no:randomly` **1659 passed**（290.13s）、`ruff check .` All checks passed、`mypy src` 274 文件无问题；前端 `npm test` 307 文件 / 3305 项通过、`openapi:check`、`typecheck`、`lint`、`build`、`test:scripts` 64/64、`test:structure` 3/3、`git diff --check` 全部通过。

### 未执行与边界（不得写成通过）

- 真实生产执行核心接入、任务内真实浏览器执行、Studio 联合运行。
- Windows、其他架构、打包应用。
- 用户手测（`manual-test.md` 未执行）。
- `03-runs/021-evidence-missing`：本阶段无证据缺失的独立画面与处置入口，按账本归属 PM3/PM5/PM8 登记为缺口。

