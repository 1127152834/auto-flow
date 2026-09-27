# 生产运行链真实 QA

日期：2026-09-28（Asia/Shanghai）；状态：confirmed。源码 HEAD：`33ae3aa49600840b1700c83723408c494dc201a8`。本报告只覆盖下列本机执行，未修改业务代码；审计产物由主任务统一提交。

## 结论

7 组真实运行场景、14 个持久任务全部达到各场景的预期终态：成功 8、预期失败 1、预期取消 4、崩溃后中断 1。30 项检查中 29 项通过，1 项为已批准的容量限制观察，不能计为产品缺陷。SQLite `integrity_check=ok`、外键检查无错误；2 条数据领取 lease 全部 released，12 个环境实例全部 cleaned，工作区所属进程和临时环境目录均为 0。置信：高，来源为真实 TCP API、生产 worker、实际 CloakBrowser、磁盘 SQLite 和独立停机后检查。

真实链通过不代表项目业务写入、End 保留/关联、人工检查点恢复已经实现。运行结果表节点与项目业务表有不同职责；本次明确验证并记录这一边界，不能拿运行结果表通过代替项目写回通过。

## 执行方式与数据来源

- 入口：`apps/backend/.venv/bin/python docs/qa/2026-09-28-system-audit/runtime/real_runtime_qa.py`。
- 新建专属临时工作区，`python -m autoflow --port 0 --data-dir <owned-workspace>` 启动实际 Uvicorn/FastAPI；所有命令走随机 loopback TCP HTTP。未使用 ASGITransport、fake executor、monkeypatch、替代数据库或合成 Run 事实。
- 使用已安装公开版 CloakBrowser `145.0.7632.109.2`，通过 APFS `cp -cR` 复制内核到隔离工作区。全新 headless profile，无代理、不访问用户既有浏览器会话，不读取付费 License。
- 业务数据来自当前工作树的 `package.json`、`apps/backend/pyproject.toml`、`AGENTS.md`：实际路径、字节长度、SHA-256。完整来源哈希写在 `results.json.realInputFiles`。数据写入隔离项目表，未写入任何既有用户业务表。
- 浏览器实际读取 `file://<repository>/package.json`，比对解析后的整个 JSON；公开网络只读 `https://example.com/` 并检查实际 `h1=Example Domain`。
- 表语义场景执行生产 `table_add_row → table_get_cell`，输入为实际源码文件元数据，读回 SHA-256 为 `6540097624333d15193d058972dc8ecc412d887bf021c775e881cb0e11fa7d92`。
- 失败场景用真实页面上不存在的随机 selector 产生原生浏览器超时；停止场景在实际 `wait` 节点运行期间提交普通停止；崩溃场景仅 SIGKILL 本脚本创建的 sidecar，然后重启同一个隔离工作区。
- 权限和隔离：仅创建/写入隔离 QA 工作区及本证据目录，无外发消息、无付费调用、无真实账号登录、无用户数据删除。测试进程已关闭，临时工作区保留用于复核。

最终完整运行时间：2026-09-28 01:03:43–01:04:51 +08:00（约 69 秒）。启动和浏览器执行使用本机当前环境，不是跨平台性能基线。

## 场景与结果

| 场景 | 真实验证内容 | 结果 |
|---|---|---|
| 项目数据 CRUD | 实际 3 文件元数据创建、查回；每条原 Idempotency-Key 重发；改成另一个实际文件的数据后，用旧 contentRevision 再写 | 真实值一致；不重复创建；旧版本 409 REVISION_CONFLICT 拒绝 |
| table_semantics | 两个生产任务分别添加实际文件元数据到运行结果表，再读取 SHA-256；核对项目业务表 | 两任务 succeeded；运行变量哈希正确；业务表仍为原 3 条 |
| concurrent_real_file | 用实际项目表领取输入，配置 concurrency=2/maxLiveInstances=2；两任务浏览器读取真实 package.json | 两任务 succeeded，冻结输入记录可查；采样最多 running=1；两个真实节点时间区间也无重叠 |
| 批次幂等 | 已完成批次按原 key 和相同请求再次启动 | 返回完全相同 operation/batch，无第二批次 |
| public_web | 两任务打开公开 HTTPS 网页并读取页面 h1 | 两任务 succeeded；均为 Example Domain |
| failure | 实际文件页面等待不存在元素 | failed=1/cancelled=1；成功下载真实 PNG 异常证据，1920×947 |
| stop | 已导航后在 60 秒 wait 节点普通停止 | batch=stopped；两任务 cancelled；后续读取节点未执行 |
| crash_restart | 实际 wait 节点运行时 SIGKILL sidecar；相同 SQLite 重启 | batch=interrupted；interrupted=1/cancelled=1；后续读取无输出；旧成功批次仍可读 |
| after_recovery | 重启后再创建新批次运行真实浏览器 | 两任务 succeeded；证明恢复后实际容量可复用 |
| 停机后审计 | 只读 SQLite、进程列表与环境目录 | 完整性/外键通过、无活动 lease、无残留环境进程/目录 |

## 已确认的设计边界及缺口

### R1：项目数据能力与 End 生产节点接入尚未完成（高置信）

已批准 `docs/superpowers/specs/2026-09-20-pm9-production-runtime-integration.md:18–20` 要求受限项目 capability 消息和 End 调用。当前实际代码：

- `apps/backend/src/autoflow/providers/browser/project_graph.py:150` 构造 ExecutionContext 时没有项目数据能力或 End 环境能力；现有 command bus 接 input prompts、browser scripts、webhook 等。
- `apps/backend/src/autoflow/application/workflows/dispatcher.py:782–791` 构造 worker 变量仅合并文档变量与 `run.parameters`。项目输入快照虽真实领取和保存，却未在此传成执行变量或受限项目能力。
- `apps/backend/src/autoflow/infrastructure/process/project_workflow_worker.py:160–165` start 消息携带 executionPlan/parameters/variables/browser/modelBindings；不是项目数据 capability RPC。
- `apps/backend/src/autoflow/application/workflows/executors/table.py:125–164` 的 `table_add_row` 操作 `context.data_rows`。本轮真实执行证实运行结果有数据、项目表没有新增。此行为本身符合 `docs/project-management/design/data-flow-and-contracts.md:48–70` 的“项目记录与运行结果集分开”；缺口是没有接通明确的项目写入动作，不能把这个节点视为项目写回实现。
- 环境终结现有入口在 `apps/backend/src/autoflow/adapters/http/project_environments.py:185–200`，调用 `EnvironmentService.end`（`application/environments/service.py:518–520`）；未发现生产图节点调用它。

本轮未猜造变量语法、节点类型或直接调用 capability 用例冒充生产节点验收。项目数据写入→业务状态推进→End 环境保留/关联→后续自动化复用闭环依然不能签字。此处为批准范围与当前接线的缺口，非 table_add_row 算法错误。

### R2：配置并发上限与实际执行容量应明确区分（已批准限制）

数据型配置允许 concurrency/maxLiveInstances 1–100（`domain/project_automations/rules.py:576–578`）；参数型配置明确只允许 1（`:570–574`）。生产 dispatcher.capacity 固定 1（`application/workflows/dispatcher.py:128–131`），scheduler 将配置上限与真实核心容量取最小值。因此真实数据批次接受 concurrency=2，但任务串行，符合单活动 worker 的批准设计。

本次最初的“必须观察到 running=2”断言基于不完整前提，交叉审查批准规格后重分类为 `observed_limitation`。保留原始断言、采样数据和重分类理由；不作为失败缺陷。产品界面若把该上限呈现为当前保证并行数量，才构成需另行核实的误导。

## 证据索引及复现边界

- [最终完整结果](run-hn1fvbhq/results.json)：30 检查、7 批次、14 任务、输入快照、节点尝试、输出、日志、产物。
- [TCP 请求/响应证据](run-hn1fvbhq/http.jsonl)：未包含认证 header/token。
- [停机后完整性与资源审计](run-hn1fvbhq/post-run-integrity.json)。
- [执行脚本](real_runtime_qa.py)；[本次运行输出](runner.log)。脚本最后按 failed/fatalError 返回非零；observed_limitation 不算失败。
- `run-j08v4our`、`run-wz8ot63l`、`run-tqhr5x51`、`run-f59lirkf`、`run-lmdc6yn1` 是 harness 校准记录：分别涉及健康路径、必填字段默认值、recordKey base64url、无变化 PATCH 不增加版本、参数型并发准入。它们不是产品失败清单；最终完整运行是 `run-hn1fvbhq`。
- 原始完整运行完成后仅对测试报告做容量语义重分类，并对脚本退出码增加按失败项返回非零；未改业务代码、未改原始 HTTP、输入、任务或节点事实。

## 未执行或尚不能验收

Windows/macOS Intel、安装包、Electron 真实 UI（其他负责人）、现有自动化测试套件（其他负责人）、长时间压力/内存增长、多 sidecar 争用同工作区、断网/磁盘满/系统休眠、强停宽限、持久 cron 调度准确性、远端 Sheets/账号/付费模型和代理写操作、项目数据节点生产写回、End 保留/关联与业务人工恢复均不由本报告宣称通过。真实 browser smoke 和本次 14 任务不能等价“所有模块所有场景完成”。
