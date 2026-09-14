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

## PM1 实际实施基线（2026-09-13，confirmed）

前文保留 PM0 时点的核验事实。关于“尚无 projects、未执行业务测试、UI 待接入”的当前描述由本节取代，不改写历史报告。

- 实施工作区：`autoflow-project-management-pm1`，分支 `codex/project-management-pm1`。起点为正式主线 `1f80f977aac427d137bbd5a1a3afeac52f42a82c`，合入设计/PM0 `9c361f4`，文档基线提交 `dbb01f5`。未复制主目录未提交文件。
- UI 源 `1fb58e1` 仅选择实际使用的控件及测试/样式/依赖；保留主线 Studio M1、useDesktopSession 和 FormField 的现有消费者 API。Select 由系统面板改为 Radix 自有面板，保留 body 自动宽度修复，并补 disabled fieldset 对 portal 选项的保护。
- 已有项目领域、10 项 HTTP、两个持久表、真实生成 DTO、项目组件与页面。真实接口范围与错误约定见 PM1 执行卡；后续模块没有增加空 API。
- 唯一迁移 head：`pm01_projects`，父为 `0005_workflow_documents`。空库和已写入旧领域数据的 0005 数据库升级由 `test_project_migration.py` 验证；旧表行内容和外键完整性受检查。
- Studio 在本分支仍为 M1 文档编辑能力。PM1 没有实现 Run，也没有接管执行器。主目录在本轮期间推进到 `c3d6727`，这是其他任务的工作；本次没有覆盖或回滚。未来合并前需要按届时主线检查迁移和共享文件。
- 主目录、设计和 UI 目录保持只读参考。2026-09-12T20:28:52Z 的只读观测：主目录 c3d6727 / 21 个状态条目，设计 9c361f4 干净，UI 1fb58e1 干净。状态条目变化不能被解释成本任务写入。
- PM3 的核心执行与资源选择、PM8 生命周期操作仍是后续依赖。PM1 已有只读准入和全局 QuiesceGate 集成，不为未来任务预造执行框架。

实际自动测试、本机 Electron 与未运行平台分别记录于 PM1 核验报告，不以 PM0 静态结果代替。

## PM2 当前代码基线（2026-09-13，实施中）

新独立分支 codex/project-management-implementation 从 ef3178a 继续；执行卡677b60f、持久结构c1e4a6d、身份与字段规则e78b0e6、XLSX适配d915b6c、表资料API2226d19、表目录/表单组件a872db2、字段影响确认d3f76af。A2b字段/状态目录8ff3b6e完成事务和真实HTTP联调，记录写入A2d正在独立实现；五页签及文件IPC仍未接通，不能视为完整数据管理交付。

2026-09-13再次只读核对：主目录HEAD已推进9490924（Studio M2正式提交，82文件，包含0006_workflow_runs从0005派生、持久Run/日志和浏览器清理）。旧“核心全部WIP”的当前描述superseded，但该提交尚未接入此实施分支，也未证明满足项目全部XE执行契约。PM3集成前核对prepareRun共享UoW、事件补读、占用/End等实际差距，按正式提交接入并处理0006与pm02迁移分叉；不复制主目录仍未提交文件。PM1 ef3178a、设计9c361f4、UI1fb58e1工作区均干净，本任务只读。

### PM2 命令基线补充（2026-09-13，confirmed）

cc86607记录显式写入、3630e78字段编辑事务和7a2986f真实HTTP已交付。记录create/get/update/status与字段影响preview/PATCH共六个新增handler；连同之前表和目录，实际15项数据HTTP操作。670项后端全量通过，最后记录类型增量再跑33项通过；前端461项回归。详细范围见pm2-records-fields-verification.json。早期“记录写入和字段PATCH尚未接通”的当前描述由本节取代；记录列表、删除/批状态、五页签、文件IPC和实际PM2页面仍未交付。

### PM2 查询基线（2026-09-13，confirmed）

5137c1b/068d9e3交付服务端记录查询及GET集合，实际数据HTTP共16项；c5e40e4纠正缺项/null投影，beb6a3b接入字段/状态客户端，5a90c55交付状态编辑组件。698项后端、490项前端及工程检查通过；同快照分页和连接池复用异常由真实并发回归覆盖。来源见pm2-query-editor-verification.json。

前文“记录列表尚未交付”的当前描述由本节取代；删除/批状态、字段/记录编辑器与完整页面、文件IPC及Excel原子发布仍未交付。正式应用数据能力仍notImplemented，组件/接口不冒充完整PM2。下一文件接入只读盘点见.ai/knowledge/2026-09-13-project-files-baseline.md。

### PM2 编辑与前端恢复基线（2026-09-13，confirmed）

bc3aa24/8c25641/113f0c7/d37cb1c/ad8a5d7/dc9ddf2/737ce3e已交付记录客户端、共享原命令恢复、标量/字段/记录编辑和记录表格组件。独立审查修复了NaN序列化成null、表请求漂移、字段预检校验竞态、记录脏草稿扩大写回、重复/迟到提交、错误焦点与ARIA等问题。最终564前端测试/86文件、类型/lint/build通过；OpenAPI、scripts18/structure3通过。后端源码与8556f81一致，本轮未重新运行后端全量。

主目录重新只读核对仍9490924且有其他任务WIP，未覆盖。PM0/PM1历史报告保留；coverage feature/acceptance/contract+gate entries与ef3178a一致，只有既有PM2进度元数据不同。组件未挂载正式页面，PM2整体仍在实施。删除状态的物理删除初步建议因旧行FK引用矛盾已撤回；软删除迁移与批状态持久块尚待实现，详见`.ai/knowledge/2026-09-13-project-data-deletion-batch-baseline.md`。

### PM2 删除与真实目录基线（2026-09-13，confirmed）

e58877d/2cded8e/32c3395/f4e1d08交付历史状态墓碑、删除影响/原子命令及18项数据HTTP；迁移head为pm02_status_tombstones。2813980/c1339f7及C2b接入真实数据目录、表单、筛选和五页签读取。此前“没有正式数据页”的当前描述由本节替代。最终719后端/606前端及工程检查通过；macOS arm64隔离Electron验证目录创建/编辑、真实冲突、重连草稿、200%下拉和重启持久化，另回归两工作区及已有模块入口。

详见pm2-directory-deletions-verification.json。该UI证据不覆盖字段/状态/记录编辑界面；这些仍为C2c，后续需补每次HTTP重发的动态准入。批状态、Excel文件发布、Sheets和项目运行仍未完成，PM2不完整。主线只读再次核实9490924，未复制其他任务WIP。

## 2026-09-13 修订实现检查点（confirmed）

实现工作区后端提交32e424e；迁移唯一head为pm02_excel_exports，顺序为status_tombstones→status_batches→excel_inspections→excel_imports→excel_exports。主线Studio的0006分叉未在本工作区合并。

批量状态、文件授权、Excel检查、隐藏分段导入/替换、一致快照导出和原文件结果核验已有真实HTTP与持久实现；唯一generated类型已同步。前端新表目录导入已在隔离Electron运行；详情页批量操作、重新导入、导出与来源组件接入等待原编辑任务提交。证据见pm2-backend-verification.json、pm2-frontend-verification.json，不用组件测试代替最终真实页面验收。

## PM2 最终实施基线（2026-09-13，confirmed）

用户确认原任务结束后接管页面/Hook等六处WIP。前述“详情页等待接入/完整PM2未完成”是历史检查点；当前真实页面已接通所有修订PM2能力。后端760、前端833全量及工程检查通过，详情编辑/批状态/导入替换导出/重连重启/双工作区和本机native选择取消有实际证据，见pm2-verification.json。用户里程碑验收仍pending；不把未来场景或平台标绿。当前迁移仍pm02_excel_exports，主线0006分叉待后续正式集成，不合并主线WIP。

2026-09-13最终只读核对主项目HEAD为2b5365e（Studio条件/循环/变量等已继续推进），并有其他任务WIP；此实施分支未合并这些内容。后续主线集成须重新核对实际迁移/共享类型/Studio能力，不把旧M2快照作为现状。数据能力契约最终仅data=available，其余五项未实现；修正提交d05bbe1。

## Gallery R1–R3 实际实现基线（2026-09-14，confirmed）

本节取代前文作为“当前尚未实现”的历史阶段描述；原PM0/PM1/PM2报告保持原始范围。R1 a6a0e8e与R2 a08c2fe已按原Gallery交付目录/查询和记录整页；R3 e467035、b2d1543、800fb01交付完整字段草稿、右侧抽屉、聚合预检/短事务提交、有界回填、真实状态引用、Excel来源和页内设置。恢复复用原项目Operation身份，不新增执行器。

实施分支迁移唯一head为`pm02_schema_drafts`，前置`pm02_excel_exports`。主线另有Studio工作，本阶段不合并它的迁移，PM3前必须重新核查汇合。字段删除、整表删除、Sheets和自动化配置引用仍未开放，禁用位置/说明不等于接口实现。

当前源代码800fb01；853后端、1126前端全量与工程检查通过。真实UI原子保存/409/重连/响应丢失原键、120条部分结果及完整重启、Excel源哈希和1万行分页等证据均登记`design-alignment/acceptance/gallery-r3`。记录图片/实际输入/文件选择注入、原生选择分别标注；逐图定性评价不代表用户签收。最终交付状态看machine-report.json，PM3仍未开始。

收尾只读观测：主目录2f6436f，旧仓324748a，均存在其他工作树变化。本任务未写它们，不能以现状差异推断本任务修改或删改。三个既有QA目录及独立record-grid-entry任务资产继续原样保留。
