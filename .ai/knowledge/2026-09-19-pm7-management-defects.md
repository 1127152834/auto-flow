# PM7 端到端才暴露的真实缺陷（2026-09-19）

- 日期：2026-09-19。
- 状态：confirmed（每个缺陷都由真实 Electron + FastAPI + SQLite + 隔离 QA 执行器复现，修复前有失败用例）。
- 来源：`docs/project-management/implementation/pm7/qa-runs/20260918203625/report.json` 及其前序运行（含失败运行 20260918202945、20260918203241）；相关提交 `6e26c6bd`、`5ad992de`、`5144079c`，以及 D0/D15 修复提交。
- 验证方式：先写失败用例并确认失败，再最小修复，最后重跑定向用例与真实端到端。

## 1. 按幂等键找回 `followUpBatch` 操作返回 500

`ProjectOperationView.kind` 与 `projects.py` 的 operations 只读列表都没有 `followUpBatch`。`POST .../follow-up-batches`
能正常写入该类型的 Operation，但用 `GET /operations/by-idempotency-key/{key}` 读回时 FastAPI 响应校验失败 → 500。

后果：后续批次「提交成功但响应丢失」之后，用户按原操作身份核对的唯一通道失效——IPC 缺失不是显示问题，而是恢复路径不存在。

修复：`6e26c6bd` 把 `followUpBatch` 加进 Literal 与 operations 列表，重新生成 `generated.ts`。
新增 `test_operation_lookup_accepts_every_kind_the_runs_router_can_write`，断言「路由能写的每种 kind 都能被操作查询读回」，
防止同类漏登记再次发生。

## 2. 回到概览页签不重新取数

`useProjectOverview` 只在 `ProjectsWorkspace` 挂载时查询一次。用户先建表/自动化/批次，再切到概览页签，拿到的是首次查询的缓存：
计数 0/0/0/0、今日变化 0、活动为空——页面显示的是「已确认的过期事实」。

修复：`5ad992de` 给 hook 增加 `visible` 参数，`enabled: Boolean(projectId) && visible`，由 `route.tab === 'overview'` 驱动。
测试 `refetches the overview every time the user comes back to the overview tab`。

## 3. 统计刷新失败丢失上次已确认的范围与数值

`StatisticsPage` 每次挂载都用「当前时间」生成时间窗口，查询键随之变化，React Query 视作全新查询。
切走再切回而服务失败时，页面只剩「统计读取失败」，既没有上次数值也没有上次的范围标题。

修复：`5144079c` 按工作区+项目把最后一次成功快照写入 `sessionStorage`（`${key}:snapshot`），
渲染用 `stats.data ?? snapshot?.data`，`shownWindow` 与快照同源，成功后立刻覆盖。
测试 `keeps the last confirmed numbers and window after the page is remounted`。

## 共同模式

三个缺陷的共性是**「显示的是已确认事实」这条规则在状态与缓存层被绕过**：一个是恢复通道缺 kind，
一个是挂载期缓存被当成当前事实，一个是时间窗口参与查询键导致无法保留上次结果。
三者都没有被单元测试拦住，因为替身不校验路由响应模型、也不模拟「切走再切回 + 服务失败」的时序。

## 4. 统计下钻做成统计页里的内联卡片（原型为独立页面）

原型 `04-statistics/007` 的下钻是运行记录下的独立页面：面包屑 `项目 / 项目名 / 运行记录 / 任务`、运行记录页签高亮、
批次/任务/等待人工子页签、筛选胶囊、统计快照条、六列表格、页脚说明与分页。实现里只是统计页内的一张卡片，
视觉评分 62，属阻断项。

修复：新增 `RunFrozen` 路由字段（`#/projects/{id}/runs/frozen/{resultSetId}/{result}[/{intervalStart}[/{automationId}]]`）
与 `StatisticsDrillPage`，复用现有项目页头、运行记录子页签和任务表格（`TaskDirectory` 新增 `frozen` 上下文：
隐藏筛选工具栏、六列布局、`查看日志` 动作、冻结空态文案）。`StatisticsPage` 只负责解出冻结集合身份后导航。

## 5. 冻结结果集标识被按短标识校验

冻结结果集标识是服务端 HMAC 签名的不透明令牌（base64url 载荷 + 签名），实测约 340 字符。
第一版路由校验限制「不超过 200 字符」，于是点击下钻直接落到「项目地址无效」。失败运行 `20260918202945/99-failure.png` 保留了该画面。

修复：去掉长度猜测，只保留非空与上限 4096 的防御；`navigation.test.tsx` 改用与后端同形状的 340 字符签名令牌做回归。

## 6. 冻结集合过期文案被二次兜底吞掉

`TaskDirectory` 内部用 `presentRunFailure(error)` 做白名单翻译；下钻页把 `presentStatisticsError` 预格式化的字符串传进去，
字符串不在白名单里 → 显示「操作失败，请重试」，用户看不到「统计结果已过期，请刷新后重试」。
失败运行 `20260918203241/99-failure.png` 保留了该画面。

修复：`TaskDirectory` 的 `error` 改为接收原始错误，由它统一翻译；`apiFailureMessages` 补 `STATISTICS_RESULT_EXPIRED` 映射。
`RunDirectories.test.tsx` 增加反例，断言该画面不得退化成通用失败文案。
