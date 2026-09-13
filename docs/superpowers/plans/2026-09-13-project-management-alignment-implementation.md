# 项目管理原型对齐 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 保留顶部导航及已验证PM2能力，按已确认原型完成项目入口、数据页面和字段统一保存的前后端纠偏，再满足条件后恢复PM3。

**Architecture:** 继续当前Electron + React领域组件、FastAPI应用服务和SQLite仓储。先确认对应画板，再完成组件、真实接口和页面组合；复用控件、命令恢复、文件授权与现有数据模型，不复制旧应用壳或第二执行器。

**Tech Stack:** React、TypeScript、Tailwind、shadcn/Radix、React Hook Form/Zod、TanStack Query、Electron、FastAPI、SQLAlchemy、Alembic、SQLite、Vitest、pytest。

---

## 1. 授权、基线与范围

- 日期：2026-09-13。状态：**planned / 本轮只编写计划，所有实施证据为空**。
- 用户已确认提交 `4688353be07e06d08aa2319c3195086983768ad0` 的[完整对齐规格](../specs/2026-09-13-project-management-prototype-alignment-design.md)，包括Studio参数定义权威和字段聚合保存的有界回填取舍；不再重复要求选择。
- 写入工作区 `/Users/zhangtiancheng/Documents/projects/autoflow-project-management-implementation`，分支 `codex/project-management-implementation`；执行前重新核对HEAD及文件责任。
- 主项目只读观察HEAD `25273d57ee50aeaf2b3861636a222428b673a181`；旧仓只读 `324748abe7095f085b4ffb9467be9cb5c8851a5c`，源码前缀`autoflow-desktop/`。主线仍有其他任务，计划不合并或修改其WIP。
- 三个既有未跟踪QA目录 `run-577a57`、`run-VoRvWR`、`run-W6Td3i` 不属于新交付，原样保留，不扫入提交。
- 本轮交付三份有界实施子计划和一份总控。R1–R3均是真实可验收的软件切片；R4仅列恢复PM3的明确前置交付，不凭过期Studio基线编写未来实现代码。
- 不实施字段/整表删除、工作流表写入、环境操作、Sheets同步、统计计算或项目生命周期；旧原型包含这些入口，不等于本轮应提前实现。

## 2. 执行顺序与文件所有权

| 包 | 计划与交付 | 负责人 / 可并行范围 | 退出点 |
|---|---|---|---|
| B0 | 本文件任务B0：基线、图稿和验收映射 | 主协调；图像生成按模块顺序 | 对应画板已确认才组装业务页 |
| R1 | [页面层级与目录](2026-09-13-project-management-alignment-r1.md) | 前端；主协调管理共享页头、Toaster及ProjectsWorkspace装配 | 项目与数据目录、顶部导航及紧凑工具栏真实验收 |
| R2 | [记录详情、编辑与返回](2026-09-13-project-management-alignment-r2.md) | 前端记录组件与主进程外链适配可并行；主协调管理路由/共享Hook | 独立记录页面、CRUD、草稿/恢复与列表往返 |
| R3 | [字段聚合保存与数据闭环](2026-09-13-project-management-alignment-r3.md) | 后端聚合与前端草稿组件在冻结DTO后并行 | 原子结构提交、状态引用、来源/设置、Excel/批状态完整回归 |
| R4准入 | 本文件任务G1：核心/参数合同及PM3计划重编 | 主协调；Studio所有者提供真实核心基线 | 条件全部满足再另开PM3实施，不自动跨阶段 |

迁移、`bootstrap/app.py`、`project_schemas.py`、生成类型、`app/navigation.ts`、`ProjectsWorkspace.tsx`、共享控件和覆盖资产由主协调单一修改。边界明确的实现可以使用用户已授权的gpt-5.6-sol子智能体；每包先规格审查再工程审查，不让两个智能体同时编辑同一文件。本轮计划自审由主协调完成，没有把“计划审查”冒充代码审查。

## 3. B0：冻结基线与视觉验收资产

**Files:**
- Read: `docs/project-management/design-alignment/coverage.json`、`review-resolution.md`、三个逐图清单及`automation-management-supplement.md`。
- Create: `docs/project-management/design-alignment/prototype-briefs.md`。
- Create: `docs/project-management/design-alignment/prototypes/manifest.json`。
- Create: `docs/project-management/design-alignment/prototypes/r1-directory-overview.png`、`r2-record-pages.png`、`r2-record-states.png`、`r3-schema-draft.png`、`r3-file-and-batch-states.png`。
- Create: `docs/project-management/design-alignment/implementation-ledger.json`。

- [ ] B0.1 记录实际提交、已跟踪改动、迁移head和未跟踪文件归属；检查本目录AGENTS/.ai/PROJECT_STRUCTURE。运行以下只读命令，预期实施分支仍独立，不能依赖固定输出提交号：

```bash
git status --short
git log -1 --format='%H %s'
git worktree list
uv run --directory apps/backend alembic -c src/autoflow/infrastructure/database/alembic.ini heads
python3 docs/project-management/design-alignment/verify-alignment.py
```

- [ ] B0.2 使用imagegen前读取其SKILL.md并说明使用；引用真实原图、现有暖灰/黏土棕tokens与顶部导航。每页以1440×1024逻辑viewport为构图基准；同一模块多状态可成总览，但保留可单独放大的画板，不把二十个小窗塞成不可读缩略图。不生成HTML替代图。
- [ ] B0.3 按R1→R2→R3生成上述5组PNG。brief逐项写明：原PMUI ID、标题、信息顺序、真实按钮、加载/空/错误/只读、保存/冲突/核验状态、返回目标。R2占用稿只作PM4未来状态标注，不能在R2页面伪造占用。R3文件与批状态必须保留PM2完整能力。
- [ ] B0.4 记录每份输出hash、原图ID、对应交互和审阅结果；逐张看实际图片，核对中文、无多余侧栏、无虚构入口/数值。向用户展示对应切片的具体图稿，得到图稿确认后再开始该切片页面实现；已经确认的业务规格无需重问。
- [ ] B0.5 将六组原缺图映射：ALIGN-DATA-01→R2两图，ALIGN-DATA-02→R3字段图，ALIGN-DATA-03→R3文件/批状态图；ALIGN-AUTO-01/02在G1后、PM3-A前补，ALIGN-ENV-01在PM8前补。R1额外补当前顶部导航下目录画板，不宣称是原图库新增历史稿。
- [ ] B0.6 只提交本包实际生成且已检查的资产和记录：`git commit -m "docs: freeze project alignment visual acceptance baseline"`。没有图时不得勾选B0完成。

账本每个任务使用以下结构，测试证据未运行保持null：

```json
{"taskId":"R2-03","status":"notStarted","owner":"record-frontend","dependsOn":["B0","R2-01","R2-02"],"sourceIds":["PMUI-d3f6c5774ec4"],"evidence":{"automatic":null,"electron":null,"windows":null},"commit":null}
```

## 4. 所有实现任务的执行约定

每个任务按勾选步骤执行，重用已有fixture但不只验证实现返回的同一常量。行为变化先写反例测试并确认因缺能力失败，再实现；純样式调整以已有交互测试与真实截图为主，不增加只检查className的测试。计划内代码是目标合同/关键实现与反例，生产改动只在执行阶段写入。

每个任务检查通过后提交具体文件：`git add -- <该任务Files列的实际变更>`；禁止`git add .`，提交信息见各任务。单包提交不等于整阶段验收。失败修复只复跑相关测试；阶段集成再跑完整套件。

## 5. 真实应用与阶段集成门槛

每个R包新增截图到 `docs/project-management/design-alignment/acceptance/{r1,r2,r3}/`（拟新增）。记录同一数据、窗口内容宽高、缩放、平台、主题、HEAD、画板ID、动作和截图。源码测试和当前小样本不能证明大表/跨平台。截图允许顶部导航这一已批准差异，不允许把整页改弹窗后仍判一致。

最终执行（均在实施工作区）：

```bash
uv run --directory apps/backend pytest
uv run --directory apps/backend ruff check .
uv run --directory apps/backend mypy src
npm test
npm run openapi:check
npm run typecheck
npm run lint
npm run build
npm run test:scripts
npm run test:structure
node scripts/smoke-project-data.mjs
node scripts/smoke-pm2-detail-flows.mjs
node scripts/smoke-pm2-native-picker.mjs
git diff --check
```

运行smoke前检查脚本采用临时user-data目录；原生文件选择脚本必须实际操作面板，不注入选择结果冒充手工。需要测试注入的断线/响应丢失用例单列。浏览器/代理/模型/设置/Studio入口沿用既有隔离回归方法，主项目实例不参与。保存新的 `docs/project-management/design-alignment/acceptance/verification.json` 和审查记录，不覆盖PM2历史核验。

退出要求：R1/R2/R3真实页面全部可操作；原始记录身份、业务状态、文件源不变和恢复路径无退化；图稿/组件/页面三者对应；Windows、其他架构与打包未运行明确标记未执行。然后停在纠偏验收点。

## 6. G1：恢复PM3前必须完成的交接

- [ ] G1.1 重新读取主线正式提交中Studio文档/Run/开窗桥、迁移head及测试；制作当前→需要的能力差表，不使用本轮`25273d5`作为未来永久基线。
- [ ] G1.2 将用户确认的参数权威写入PM0合同勘误：工作流文档有稳定parameterId和版本，自动化只保存绑定/覆盖，本次启动值独立冻结；false、0、空字符串、null、未提供分开，不能通过改document.variables初值传参。同步18契约中受影响的输入/准备/快照与错误引用，保留旧报告。
- [ ] G1.3 核心所有者明确`prepareRun`参与调用者事务、不自行commit、提交后dispatch、停止/强停/旧worker撤权与序号恢复的真实能力。若缺失，排前置核心任务，不增加项目执行器或HTTP拼事务。
- [ ] G1.4 在隔离集成分支解决当前PM2迁移分叉与正式Studio迁移，使用追加merge revision，不改历史迁移；验证空库和两种既有库升级及PM2数据保留。
- [ ] G1.5 补ALIGN-AUTO-01/02高保真图，保留四页签同一草稿、统一resolve/save、明确保存后预览、资源修复往返、Studio定位；按旧324748a能力复用。
- [ ] G1.6 更新paused PM3规格的已批准参数结论和最新依赖，再由writing-plans编写PM3-A、B、C细化计划。默认有限1次，数据调度PM4、End/人工PM5、完整诊断PM7；PM3-C不可推迟停止安全。

G1是交接清单，不是已经完成的核心集成计划；本次规划并未授权执行G1中的业务修改。
