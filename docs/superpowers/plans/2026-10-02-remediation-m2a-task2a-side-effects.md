# M2A Task 2a：副作用边界与失败分类 步骤级计划

- 日期：2026-10-02；状态：执行中。上位：[M2 规格](../specs/2026-09-30-remediation-m2-business-model-reliability.md) R2-10、R2-13；[任务级计划](2026-09-30-remediation-m2-business-model-reliability.md) Task 2。
- Task 2 拆分：**2a（本文）** 副作用声明、持久边界事实、失败分类；**2b** 统一 errorPolicy 模型、旧配置候选迁移与显式启用、节点级重试/goto 执行、前端"出错时"控件（R2-08/09/11/12）。2a 不改变任何重试行为，只产出可信的分类事实，供 Task 3 投影与 Task 4 领取使用。

## 代码事实（2026-10-02）

- 项目 worker 在每个节点执行前发出 `nodeAttempt {status:'started'}`，父进程持久化为 `project_workflow_run_events` 并 ACK 后才继续（`providers/browser/project_workflow_worker.py::send_event` 等待 `event_committed`）。嵌套子流程、自定义模块内的节点同样经 `publish` 发出。
- 因此"已进入可能有副作用的区域"不需要新协议：让 started 事件携带节点的副作用声明即可，ACK 语义已满足 R2-10 的"动作前同步持久化"。
- 运行终态：`succeeded/failed/cancelled/timed_out/interrupted`；结果不明为 `interrupted + WORKFLOW_RESULT_UNKNOWN`。

## 设计

1. `domain/workflows/side_effects.py`：`node_side_effect(module_type, config) -> 'none'|'possible'`。**默认 possible**；只把纯计算、流程控制、等待与读取类节点列入只读白名单。`project_data` 按操作判定（inputs/readRecord/queryRecords/queryTableSchema 为 none，其余为 possible）。容器节点（子流程、自定义模块、循环、分组）本身为 none，其内部节点各自上报。`refresh_page`、`handle_dialog`、各类点击输入、脚本、外部请求、通知、SSH、End、人工节点均为 possible。
2. 项目图 started 事件增加 `sideEffect`；完成事件已有 `status`。
3. `domain/project_runs/failure_category.py::classify(status, error, attempts)`，attempts 为按顺序的 (visit, status, sideEffect) 事实；缺 `sideEffect` 的历史事件按 possible 处理：
   - succeeded → None；
   - 没有任何节点开始（启动、浏览器、代理预检失败或开始前失联）→ `infrastructure`（确定未开始）；
   - cancelled：存在已开始未完成的 possible 节点 → `unknown`，否则 `cancelled`；
   - failed/timed_out/interrupted：任一 possible 节点已开始 → `unknown`（整 Task 重做不安全，证据缺失默认人工核实）；否则 → `page`（只读路径可安全再做）。
   - `business` 由 End 的业务结果决定，留在 Task 3（R2-14）。
4. 暴露：任务详情返回 `failureCategory`（按运行事件即时计算，只读）；Task 3 改为终态同事务投影后由台账提供。

## 步骤

1. 副作用声明与单元测试（白名单、默认 possible、project_data 按操作）。
2. 分类纯函数与单元测试（覆盖上面每一条及历史事件缺字段）。
3. 项目图 started 事件带 `sideEffect`；单元测试经 `ProjectGraphExecutor` 断言事件。
4. 任务详情 `failureCategory`：查询运行事件计算；契约测试 + OpenAPI 生成。
5. ruff/mypy/严格类型、受影响回归、`.ai` 记录。

## 风险

- 保守默认会让"点击后才失败"的任务归为 unknown，接入领取（Task 4）后需要人工核实。执行器以后可在能证明动作未发出时（如定位元素超时）声明"未执行"以降级为 page，留作 2b/后续优化，不在 2a 放宽。
