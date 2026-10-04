# M3 Task 7：多批次公平调度

- 日期：2026-10-04；状态：confirmed（本机 Windows 测试）
- 规格：[M3 规格](../specs/2026-09-30-remediation-m3-throughput.md) R3-08

## 行为

- 批次启动时可选优先级 `high` / `normal`（默认）/ `low`，冻结在批次请求里；界面启动对话框新增"批次优先级"。
- 每个调度 tick：按优先级分组（高→普通→低），组内按创建时间排序后从"上次拿到名额的批次"之后开始轮转；
  每一轮每个批次最多启动 1 个任务，只要本轮有人启动就再来一轮，直到容量或任务用完。
- 批次自己的并发上限（`concurrency`）照旧生效；用不完的名额留给其他批次。
- 低优先级只在高、普通批次本轮都启动不了时才拿到名额（严格优先级，不做老化）。

## 行为变化

- 同一自动化的多个批次原来是"老批次占满，新批次 blocked"；现在轮流分配。
  `test_max_live_instances_and_core_capacity_apply_across_batches` 的断言改为两批各 1 个（共享上限仍是 2）。

## 证据

- `test_batch_fairness.py`：同级轮流、高优先级先得、批次上限让出名额、低优先级排后、跨 tick 从上次服务批次之后开始、非法优先级被拒。
  旧调度器上前 4 个场景失败。
- 顺带修复：`test_scheduler_dispatches_two_production_workers_with_exclusive_record_groups` 自 Task 4 起只拦截
  `on_event`，纯数据流程的过程事件改走 `on_events` 后测试超时；钩子补上批量回调。
- 前端：`start-schema.test.ts` 新用例；project-runs 191 项通过。

## 未做

- 优先级老化（低优先级长期饥饿）：规格未要求；低优先级批次被长期压住时再加等待时间加权。
