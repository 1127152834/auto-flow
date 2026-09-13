# 项目管理视觉整改 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement task-by-task; each package has specification review followed by engineering review. Use verification-before-completion before claims.

**Goal:** 修复R1审查中的真实结构偏差，并以真实端到端流程和逐画面截图对照共同验收，再按既定顺序交付R2/R3。

**Architecture:** 复用React领域组件与现有Electron QA辅助；R1只改呈现/组合，不改HTTP/IPC/迁移。保留查询草稿、Operation恢复和工作区隔离。共享控件只补当前真实缺口。

**Tech Stack:** React/TypeScript/Tailwind/Radix/Phosphor、Vitest、Electron/CDP、FastAPI/SQLite真实测试工作区。

规格：[视觉整改规格](../specs/2026-09-13-project-management-visual-remediation.md)。基线09b56f6。状态：独立规格/可执行性审查及修正复核通过，按用户本轮授权开始VR1。本文是旧R1计划的整改增量，保留其历史记录，不重复宣称旧交付已经视觉通过。

## 文件责任与依赖

| 包 | 修改/新增文件（相对工作区） | 责任/依赖 |
|---|---|---|
| VR0 | 本规格/计划、R1执行卡附录、acceptance/r1-visual/requirements.json、manual-test.md | 主协调；先于业务代码 |
| VR1 | renderer/domains/projects/components/ProjectCard.tsx、ProjectDirectory.tsx、ProjectDirectory.test.tsx | 实现智能体；只组件，不动Workspace |
| VR2 | renderer/domains/projects/components/ProjectHeader.tsx、pages/ProjectOverviewPage.tsx；renderer/domains/project-data/components/DataTableDirectory.tsx、DataRecordsTable.tsx；pages/DataTableDirectoryPage.tsx、DataTableDetailPage.tsx；相邻.test.tsx | 主协调集成；VR1后 |
| VR3 | renderer/domains/project-data/components/RecordQueryToolbar.tsx、RecordFilterEditor.tsx及相邻.test.tsx | 实现智能体；VR2后 |
| VR4 | renderer/shared/components/Toaster.tsx/.test.tsx、实际项目通知消费者 | 主协调；VR3后 |
| VR5 | scripts/qa-project-alignment-r1.mjs、必要时新增scripts/compare-project-visuals.mjs及其.test.mjs；acceptance/r1-visual/报告、截图、对照页 | 主协调；测试可先准备，最终须对交付构建执行 |

上表 renderer 前缀均为 `apps/desktop/src/renderer/`；scripts/docs相对根。不新增页面占位。`shared/components/ui/search-input.tsx` 当前className落在input而非包装层，导致调用者flex-1未控制布局；优先在领域消费者包宽度容器解决，不在本阶段全局改API。如确需共享改动，追加所有消费者回归后再实施。

每包顺序：写可失败行为/布局断言→确认失败原因→最小实现→定向测试→规格审查→工程审查→修正复核→明确文件提交。纯样式以真实截图/几何断言为主，不以断言CSS字符串代替视觉测试。测试辅助和实现同时可推进，但不并发修改同一文件。

## VR0：冻结验收合同

- [ ] 核对HEAD、dirty及其他QA目录；读取原图、审查和现有QA实现，登记截图来源与sha。
- [ ] 将G/A/B/C/D、T01–06逐项登记到requirements.json；业务证据初始为null；未来R2/R3另列notStarted。
- [ ] 定义fixture与截图ID（见下表），保存manual-test.md的步骤/预期/异常命令。
- [ ] 独立审查规格的范围、可测试性及像素误判风险；修正后提交文档，才开始VR1。

## VR1：项目目录卡片与工具区

- [ ] 在ProjectDirectory测试保留最近过滤、更多不open、键盘、分页/模式切换断言；新增图标无误导可访问文本、长名称不影响操作及标题/动作顺序的语义断言。
- [ ] 运行 `npm test -- src/renderer/domains/projects/components/ProjectDirectory.test.tsx`，记录新行为失败。
- [ ] ProjectCard加通用Folder图标块；最近横向内容、更多右上；全部紧凑图标条目。保留全卡点击与兄弟button，不引入可配置图标业务。
- [ ] ProjectDirectory把新建移到标题下操作区，右侧搜索有明确宽度容器，去掉空白背景壳；最近区标题与查看全部相邻；2列卡片gap16，保留ScrollArea偏好恢复。
- [ ] 重跑组件及ProjectsWorkspace测试；真实E2E创建A/B→全目录打开→返回最近，采集VR-A01/A02及长文本；未拍图不得标包视觉通过。
- [ ] 独立规格/工程审查并修复；提交VR1。

## VR2：数据目录和记录层级

- [ ] 新增/保留唯一h1、归档只读、表来源/数量、身份类型不混同、字段值语义和打开/编辑事件测试。
- [ ] 紧凑ProjectHeader合并一行；数据目录搜索并入标题工具区，保留来源/排序；卡片按B01–03结构重组，不额外逐卡请求字段数量。
- [ ] 表标题、来源、次操作就近；记录表身份列112px、完整身份仍可读；状态改为已有Badge视觉。保留项目与表页签和全部PM2入口。
- [ ] 运行Header、DataTableDirectory、DataRecordsTable、DataTableDetailPage测试与typecheck。E2E创建本地表/记录→打开→返回；测记录表头y≤380、全页不横向溢出；截图VR-B01/C01。
- [ ] 双审并提交VR2。来源设置/字段整页不在本包顺手重写。

## VR3：查询浮层

- [ ] 用已有Toolbar测试扩展标题/关闭、切换丢弃草稿；保留复杂条件、过滤+搜索组合与选列无读取断言。
- [ ] Panel加入标题和有名称的X，图标触发和应用状态；filter/sort/columns分宽度。复用原受控编辑器；仅改表达标签与间距，不新写查询语言。
- [ ] 工具栏顺序和primary新增对齐C02；通过组件测试后真实点击筛选/排序/列的取消与应用，各拍图；嵌套Select Esc两次及200%关闭/focus单独验收。
- [ ] 真实搜索“温室”叠加状态，清空搜索保留状态；拦截只读网络记录验证选列不请求及export最终过滤一致，不得用mock成功响应。
- [ ] 双审并提交VR3。

## VR4：通知与交互收尾

- [ ] 保留去重/3条上限/2600+150ms/卸载/StrictMode测试。只改位置、图标及项目消费者能确认的业务语义。
- [ ] UI创建/编辑项目拍真实Toast；提交丢响应注入后原操作查询恢复，只有一个成功事实；跨工作区迟到响应无误导通知。
- [ ] 回归其他模块通知、菜单焦点与loading宽度；双审并提交VR4。

## VR5：端到端、截图对照与用户手测

- [ ] 扩展原QA脚本，使用有标记临时工作区；记录UI操作与API准备区分，增加fixed fixture、每步断言、截图ID及几何测量。不要另建通用自动化框架。
- [ ] 如需应用金图差分，先检查已装图像工具；只新增一个最小比较脚本，输入两图和显式掩码、输出diff/比例/尺寸，不自动更新基线。原型合成图只作坐标化并排审查，禁止当应用金图。
- [ ] 执行下列完整矩阵；失败先修复再复验，不删业务断言。保存每次失败及最后通过的构建provenance。
- [ ] 用电脑工具抽查交付构建的最近/全部/记录/三个浮层；检查并排图，逐条填强制项和评分。E2E通过但视觉不通过时继续整改。
- [ ] 独立规格审查→工程审查；记录问题和修复提交，最终运行工程检查。
- [ ] 更新执行卡/结构职责/.ai与手测方案；提交版本、截图、原图对应和未执行平台；停在R1用户验收点。

### 必须执行的E2E与截图矩阵

| ID | 前置与实际UI步骤 | 必须断言 | 截图/原型 |
|---|---|---|---|
| E01 | 空工作区→项目→创建内容采集/客户跟进→返回全部先开A再开B→返回最近 | 真实保存；B先于A；更多编辑不open；未访问排除在E02 fixture建立后复核 | VR-A00空、A01最近、A02全部 / R1-A |
| E02 | fixture52项目→搜索→排序→第二页→打开→返回→重启再打开 | 同会话返回/sidecar重连恢复查询/页码/滚动；50/2分页；完整重启仅验项目与访问持久 | VR-A03分页、A04无匹配 / R1-A |
| E03 | UI创建资料库→编辑描述→新字段/新记录→返回 | 卡片事实真实，来源/操作正常；主h1唯一 | VR-B01 / R1-B |
| E04 | 打开记录→修改筛选后取消/Esc/外点→再应用；排序/选列重复 | 取消无变化；应用才变化；选列不查后端；导出最终查询一致 | VR-C01列表、C02筛选、C03排序、C04列 / R1-C |
| E05 | 指定标题搜索温室→叠加状态→清空搜索 | AND语义、状态保留，空/null/布尔/数值正确 | VR-C05生效、C06无匹配 / R1-C |
| E06 | 读取失败注入→重试；竞争编辑→保存；提交后丢响应→核验 | 旧内容/草稿保留，真实冲突，原键找回不重复 | VR-A05错误、C07冲突、D01成功 / 常见状态+B0 |
| E07 | 服务重连→换B工作区→返回A→重启 | 无串数据/旧通知；相同工作区草稿不丢；偏好独立 | VR-I01/02，行为证据为主 |
| E08 | 1440/100%和200%，长名长字段，Tab/Enter/Esc嵌套Select | 主宽变化≤1；仅表格横滚；表头y≤380仅100%；焦点恢复 | VR-Z01–04 / 对应画板 |
| E09（集成回归） | 记录编辑、批状态、Excel导入/重导/导出及其他模块入口 | PM2 smoke所有原业务断言保留，不以入口存在代替闭环 | 保留PM2实测图及结果 |

### 命令与结果记录

工作目录为implementation根。先运行：

```bash
npm test
npm run openapi:check
npm run typecheck
npm run lint
npm run build
npm run test:scripts
npm run test:structure
node scripts/qa-project-alignment-r1.mjs
node scripts/smoke-project-data.mjs
node scripts/smoke-pm2-detail-flows.mjs
git diff --check
```

后端定向运行 `uv run --directory apps/backend pytest tests/contract/test_projects.py tests/unit/test_project_data_query.py`；不声称前端改版证明全后端。自动工具结束后 `node scripts/qa-project-alignment-r1.mjs --manual` 给用户留隔离应用，记录当前构建/路径。用户手测E01–09逐项填写通过/失败/未执行。清理必须验证所有权标记，只清工具目录。

## 后续里程碑接口

R1用户验收后才执行原 [R2计划](2026-09-13-project-management-alignment-r2.md)，补充记录每个状态截图和本规格双门槛；R2用户验收后执行 [R3计划](2026-09-13-project-management-alignment-r3.md)，补齐Excel每一步/批部分结果截图。各阶段开工重新核对实现/迁移，不以本计划预先标通过。没有用户验收不得自动继续。

QA审查补充：每个动作/截图按规格证据分级登记；UI主流程清除直接hash/preload导航捷径。像素比较不替代结构和人工审查。

技能已通过允许文件读取加载，实际路径：`/Users/zhangtiancheng/.claude/plugins/cache/superpowers-marketplace/superpowers/5.0.7/skills/subagent-driven-development/SKILL.md` 与同skills根下 `verification-before-completion/SKILL.md`。不可用工具名不影响已读取的技能工作流；使用本环境子智能体/exec工具执行。

工程交付门槛与用户验收分开：自动E1路径、E2/E4对应集成/故障回归、内部人工逐图审查全部通过后可交付；用户M01–09仍pending，等待用户验收，不因此虚称全部用户用例通过。

## 本轮执行记录

- VR0：759b815，规格/计划/27项清单/手测文档；独立审查及修复复核通过。
- VR1组件：3bc17f1、7b22b25；图标/横向卡片/搜索工具区/长名省略。定向28项测试、typecheck/build通过。
- VR1有界目录E2E：run-8BvVYs，通过真实UI创建A/B、打开/返回顺序、菜单不导航、无匹配恢复、未访问fixture排除、200%长名真实尾省略。记录原构建失败run-wUVDJP与后续取证校准失败；run-3tG4Kd虽然行为passed，但zoom重复应用导致实际400%，不得作为200%合格证据；最终run已硬断言720×512/DPR2。
- 截图初审与 [对照页](../../project-management/design-alignment/acceptance/r1-visual/vr1-comparison.html)已形成；只覆盖正常目录与长名，未把A05全状态或完整R1标通过。
- 当前：第一组件包已开始实施并有有界证据，VR2–VR5尚待执行；完整R1/userAcceptance仍pending，未进入R2。

## 连续实施授权（当前，2026-09-13）

用户明确要求从b93823f连续完成R1→R2→R3，不再等待各阶段用户确认。此授权替代前文及R2/R3子计划中“等待用户验收再进入下一阶段”的执行安排；每阶段仍必须完整通过工程/E2E/逐图/独立双审并保存手测文档才能推进。用户手测未执行仍pending。仅无法自行修复的阻断汇报，普通失败自行修复复验。最终R3统一交付，不进入PM3。
