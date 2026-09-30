# M3 吞吐与性能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **本计划为任务级。** M2 通过退出评审后细化为步骤级并经用户确认再执行。每个任务都必须先扩展 M0 基准、记录改动前数字，再改代码（`AGENTS.md` 整改期规则 4）。

**Goal:** E4 性能预算全部达标：领取 < 20 毫秒（10 万行）、主循环 p99 < 50 毫秒、框架开销 < 5 毫秒 / 节点、首节点延迟达标、环境占用受控。

**Architecture:** 领取改为基于 `record_index` 表的索引查询 + 候选预取 + 部分唯一索引抢占租约；所有写事务经单一 `DatabaseWriter` 线程；worker 协议 v2 支持过程事件批量发送；worker 进程池与三种会话模式；环境存储排除缓存、清单摘要、写时复制与代次清理。

**Tech Stack:** Python 3.11、SQLite（部分索引、`json_extract`）、asyncio + 线程、CloakBrowser；M0 基准框架。

**Spec:** [docs/superpowers/specs/2026-09-30-remediation-m3-throughput.md](../specs/2026-09-30-remediation-m3-throughput.md)

## Global Constraints

- 状态事件（数据写回、环境保存、End、人工检查点、运行终态、产物登记）保持同步提交与 ACK、执行代次校验与幂等；只有过程事件可以批量。
- worker 协议 v1 与 v2 共存一个版本。
- `pool` 会话模式只允许与临时身份 / 无登录采集组合。
- 缓存排除列表集中维护，可按环境覆盖。
- 迁移文件前缀 `rm3_`；大表不做 ALTER 重建，筛选索引放在 `record_index` 表。

## Review Focus

1. **记录在领取与抢占之间被修改**：预取的候选在抢占时重新校验，冲突跳过而不是领取旧版本（Task 2 随机化测试）。
2. **写线程队列积压**：队列长度超过阈值记警告，关闭时排空（Task 3 测试）。
3. **worker 在批量发送前被杀**：只丢最后一批过程事件，状态事件完整（Task 4 崩溃注入测试）。
4. **会话复用时上一任务的 Cookie 残留**：`pool` 模式任务间清理后校验 Cookie 为空（Task 6 测试）。
5. **排除缓存后网站登录失效**：G1（M4）验证登录保持；本里程碑用夹具站点的 Service Worker 登录样例测试可覆盖（Task 8）。

---

### Task 1: 基准扩展与目标阈值

- 扩展 `bench_claims`（100,000 行、字段筛选）、新增 `bench_first_node_latency`、`bench_environment_roundtrip`；CI 基准步骤开始对 M3 指标设置"不回退 20%"阈值。
- Files: `apps/backend/tests/benchmarks/*`、`.github/workflows/ci.yml`。

### Task 2: 领取下推与抢占

- Files: `rm3_record_index.py`、`infrastructure/database/record_index.py`（写记录时同步维护）、`infrastructure/database/project_claims.py`（WHERE 下推、预取 并发×4、部分唯一索引抢占、租约索引查询）、筛选翻译器 `domain/project_data/filter_sql.py`、自动化预检"无法下推"提示。
- Interfaces: `translate_filter(filter, fields) -> SqlPredicate | Unpushable`；`claim_candidates(session, automation, limit) -> list[Candidate]`。
- Tests: `test_filter_sql.py`（每种运算符）、`test_claim_pushdown.py`、随机化测试 `test_claim_randomized.py`（1,000 次随机筛选 / 并发：不重复、不遗漏、不死循环）、`bench_claims` 100,000 行 < 20 毫秒。

### Task 3: 单一数据库写线程

- Files: `infrastructure/database/writer.py`（`DatabaseWriter.submit(fn) -> Future`、关闭排空、队列长度指标）、调度器 / 派发器 / 事件提交改走写线程。
- Tests: 写顺序保持、异常传播、关闭排空、主循环延迟 p99（G2 运行中）< 50 毫秒。

### Task 4: 事件分级与 worker 协议 v2

- Files: `providers/browser/project_workflow_worker.py`（worker 侧缓冲，200 毫秒 / 100 条）、`infrastructure/process/project_workflow_worker.py`（`eventBatch`）、`application/workflows/dispatcher.py`（批量写入）、日志 JSONL 存储与保留清理 `infrastructure/filesystem/run_logs.py`。
- Tests: 协议 v1/v2 契约测试、崩溃注入、G4 框架开销 < 5 毫秒 / 节点。

### Task 5: worker 进程池

- Files: `infrastructure/process/worker_pool.py`（预热、回收：N 个任务或 RSS 阈值）、worker 输入事件驱动（去掉 10 毫秒轮询）、`bootstrap/workflows.py`。
- Tests: 池大小随容量设置变化；回收后执行代次撤权仍然有效；首节点延迟（新浏览器）< 3 秒。

### Task 6: 会话模式

- Files: `domain/project_automations/rules.py`（`sessionMode`）、`application/workflows/browser_resources.py`（租借 / 归还）、worker 侧"清理标签页 / 清理存储"命令、自动化运行设置界面。
- Tests: perIdentity 连续多行复用同一浏览器；pool 模式任务间 Cookie 为空；撤权时浏览器被关闭而不是归还；复用会话首节点延迟 < 300 毫秒。

### Task 7: 多批次公平调度

- Files: `scheduler.py`（优先级、同级轮转、批次自有并发上限）、批次启动接口与界面。
- Tests: 两个同优先级批次交替获得名额；高优先级先得；单批次上限生效。

### Task 8: 环境存储瘦身与清理

- Files: `providers/browser/environment_store.py`（排除列表、清单摘要、clonefile / 块克隆 / 增量同步）、`application/environments/retention.py`（保留 3 个代次、孤儿清理后台任务）、设置页磁盘占用。
- Tests: 恢复 + 保存 < 2 秒（典型环境夹具）；100 次运行后总占用 ≤ 单环境 × 4；Service Worker 登录样例在排除列表覆盖后保持登录。

### Task 9: 里程碑验收

- 全部基准与黄金场景（G2 会话池模式吞吐 ≥ M0 基线 × 5）；AC3-01 至 AC3-08 逐条勾选；更新 `.ai` 与目录文档；独立退出评审。
