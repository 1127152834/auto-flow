# PM7 设计与实施文档编写 · 2026-09-19

状态：`proposed`（设计规格与实施计划已写；未开发任何业务代码；等待用户审阅）
来源：本 worktree 源码只读核对（HEAD `309cdee1`）、`docs/superpowers/plans/2026-09-13-project-management-milestones.md`、`docs/project-management/design/functional-structure.md`、`docs/project-management/implementation/api-contracts.md`、`docs/project-management/implementation/coverage.json`、`docs/references/project-management-prototypes-2026-09-13/latest/{01-overview,04-statistics}`
给接手 agent：先读设计规格与实施计划，等用户确认后再开发。不要重开 PM6，不要进入 PM8，不要联合测试 Studio demo。

---

## 1. 本轮产出

| 文件 | 内容 |
|---|---|
| `docs/superpowers/specs/2026-09-19-project-management-pm7-design.md` | PM7 设计规格说明书（现场核对、范围、复用清单、10 条设计决策、接口、前端结构、验收方案、交付边界、待确认 3 项、自审） |
| `docs/superpowers/plans/2026-09-19-project-management-pm7.md` | PM7 实施计划（12 个包的任务卡：输入合同、可复用代码、独占文件、测试用例、通过条件、工时） |

未写业务代码；未提交。

---

## 2. 本轮最重要的两个技术发现

### 2.1 PM7 不需要新增数据库迁移（置信度：高）

原先的假设是统计需要一个“冻结结果集”表，因此需要一次追加迁移。实测推翻了这一假设：

- `domain/workflows/runtime.py:29-52`：`_TRANSITIONS` 只有 `queued/running/waiting_manual/resume_queued/finishing/stopping/reconciling` 七个键，五个终态没有出边。
- `runtime.py:438-440`：`transition_core_run` 对 `run.terminal` 直接抛 `RUN_TERMINAL`。
- `runtime.py:460`：`completed_at` 只在进入终态时写入。

因此冻结谓词 `status ∈ TERMINAL ∧ from ≤ completed_at ≤ min(to, calculatedAt)` 在时间上是**单调封闭**的：查询时刻已结束的任务此后不可改写；查询时刻未结束的任务其 `completed_at` 必大于 `calculatedAt` 而永远落在谓词之外。同一标识下的重算结果必然一致。

代价是放弃了“结果淘汰”动作与审计轨迹，只保留 TTL。升级路径（持久表 + 一次追加迁移，DTO 不变）已写入规格的 `ponytail:` 标记。

补充约束：14 个集成测试文件把 `pm08_project_sync` 断言为唯一 head，因此避免迁移的收益不只是文件数量。

### 2.2 PM7 有相当大一部分是“已经做完但没接页面”

- `list_tasks` 已支持任务编号、冻结自动化名、参数值与输入语义值搜索 —— PM7 的搜索需求**零后端改动**。
- `node-attempts` / `logs` / `outputs` / `artifacts` 四路由全部就绪。
- `TaskEvidence.tsx`（183 行）已渲染输入快照、写入、批次参数、输出、附件、错误、历史尝试。
- `TaskDetailPage.tsx` 已接 `useRunEvents`、断线补读、错误提示、终态停订阅。
- `useProjectOverview` / `api.overview` 前端 hook 已存在，只是页面没用。

真正缺的只有：概览聚合服务、统计聚合服务、失败后续批次入口、概览/统计两个页面，以及证据面板的三项补强。

命名裁决：覆盖表写的 `TaskEvidencePanel.test.tsx` 与真实代码 `TaskEvidence.test.tsx` 不一致，**沿用既有命名**，不新建 `TaskEvidencePanel`。

---

## 3. 与用户长期约束的对齐

- 顶部导航保持不变；只把原型侧栏改成顶部，其余主体布局照抄原型。
- 统一细网格表格 + 小圆角，全部新表复用 `shared/components/ui/table`。
- 不联合测试 Studio demo；使用隔离测试执行器。
- 交付声明固定为「管理侧通过，真实执行核心接入待验收」。
- 端到端 + 同视口截图比对；未执行的平台与用户手测如实标注未执行。

---

## 4. 待用户确认（写进规格 §10）

1. 契约加法式扩展：`ProjectOverview.dataChanges` 与 `ProjectStatistics.failuresByAutomation` 是否批准。
2. 概览「需要关注」本期只取已提交事实，不做资源健康探测。
3. 失败后续入口在源任务错误属“结果不明”类时，默认可见 + 二次确认。

---

## 5. 下一步

用户确认规格与上述 3 项后，按实施计划 `P0 → B1 → B2 → C1 → C2 → A1 → 前端三块 → F` 推进。每包独立提交，通过门槛后自动进入下一包；普通缺陷自行修复，只有无法自行解决的外部阻断才暂停。
