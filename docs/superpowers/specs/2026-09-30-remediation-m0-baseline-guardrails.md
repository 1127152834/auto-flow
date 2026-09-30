# M0 基准与守门 设计规格

- 日期：2026-09-30；修订：r2；状态：in_progress（Task1–4已实现；其余任务及阶段验收未完成，证据见.ai/sessions/2026-09-30-remediation-m0-implementation.md）
- 总纲：[整改里程碑总纲](2026-09-30-remediation-roadmap.md)；对应整改方案"验收基准"一节与 N3、N4、N5
- 实施计划：[M0 实施计划](../plans/2026-09-30-remediation-m0-baseline-guardrails.md)

## 1. 结论

M0 不改变任何用户可见行为，只做两件事：**让系统可测量**（基准与主循环延迟监测），**让问题不再增加**（守门检查）。后续里程碑的"完成"都以 M0 产出的数字为准。

## 2. 背景

评审中的关键结论（单次领取 2 秒、失败原因丢失、并发写死为 2 等）目前只能靠一次性脚本复现。仓库没有持续记录这些指标的机制，也没有阻止"前端新增后端不读的配置项""新增写死颜色""新增截图证据进仓库"的检查。

本规格编写时已用原型脚本在 ea2cc5b 上实测（Linux，临时目录 SQLite），作为预期量级参考：

| 指标 | 实测 |
| --- | --- |
| 领取 500 行（按记录键 / 按字段排序） | 76 / 66 毫秒；1 万行 2.0–2.6 秒（评审实测） |
| G4 框架开销（无数据库、无浏览器） | 0.19 毫秒 / 节点 |
| G4 每节点事件数 | 5.0（nodeAttempt 2、log 2、output 1） |
| 单次事件提交 p50 / p99（现配置） | 4.1 / 8.3 毫秒 |
| 同上，开启 WAL + synchronous=NORMAL | 1.4 / 3.8 毫秒 |
| 守门计数：未读取配置键 / 写死调色类 / phosphor 文件 / docs PNG | 127 / 2,008 / 80 / 3,247 |

结论：G4 的真实开销主要来自"每节点 5 个事件 × 每个事件一次同步提交"，而不是运行时本身；M0 的三个离线基准分别盯住这三个量。

## 3. 目标与非目标

**目标**

- G-1 离线基准：不需要真实浏览器即可在 CI 中运行，输出结构化指标。
- G-2 浏览器黄金场景：在装有 CloakBrowser 的机器上可选运行，记录端到端现状。
- G-3 主循环延迟监测：服务内常驻，记录事件循环被阻塞的时长。
- G-4 守门检查：存量只减不增，新增问题在 CI 失败。
- G-5 协作规则：把整改方案 N4 的 AI 协作规则写入 `AGENTS.md`。

**非目标**

- 不修复任何问题（修复从 M1 开始）。
- 历史 QA 图片迁出与历史改写属于独立维护任务，不是 M0 的交付项或退出门槛（见总纲第 6 节）。
- G1 多账号身份场景推迟到 M4（依赖身份模型）；M0 只建立 G2、G3、G4。
- 不引入节点配置 schema（M2 A1 正式实现时引入）；M0 的配置键守门是文本扫描下限。

## 4. 需求

| 编号 | 需求 |
| --- | --- |
| R0-01 | 领取基准：给定行数 N（默认 2,000，可配 10,000、100,000），测量 `SqlAlchemyProjectInputGroups.select_required` 单次耗时，覆盖"按记录键排序"和"按字段排序"。 |
| R0-02 | 执行开销基准（G4）：用 `ProjectGraphExecutor` 在无浏览器条件下执行"循环 1,000 次 × 5 个 set_variable 节点"，输出 `framework_ms_per_node` 和 `events_per_node`。 |
| R0-03 | 事件提交基准：在真实 SQLite 上调用 `SqlAlchemyWorkflowRuntimeRepository.append_event` 并提交 1,000 次，输出 `event_commit_ms_p50`、`event_commit_ms_p99`。 |
| R0-04 | 所有基准输出同一 JSON 结构：`{"schemaVersion":1,"commit":"<sha>","platform":"<os-arch>","metrics":{"<name>":{"value":<number|null>,"unit":"ms|count|per_node|ratio|rows_per_min|tasks_per_min"}}}`，写入 `apps/backend/tests/benchmarks/results/`（不入库），并打印一行摘要。同目录每次运行写 manifest（scenarioVersion、executionProfile、数据集/故障种子、硬件、内核、并发、重复次数、报告文件列表、commit）；缺任何比较维度的旧结果只作为观察，不计算提升比例。 |
| R0-05 | `LoopLagMonitor`：每 50 毫秒调度一次心跳，记录实际延迟；超过 100 毫秒写一条 warning 日志（含"event loop lag"与毫秒数）；提供最近 5 分钟 p50/p99/max 的只读快照。sidecar 创建它挂到 `app.state.loop_lag`，启动时开始、关闭时停止。 |
| R0-06 | G2/G3 使用真实 HTTP、SQLite、worker 和 CloakBrowser；浏览器 fixture 在 golden/conftest.py 显式注册，未设置 AUTOFLOW_TEST_CLOAKBROWSER 时 skip。M0 的 executionProfile=controlled-one-row-batches-v1：枚举完整输入身份，通过公开调试预检取得 debugSelection，每行启动一次 maxTasks=1/concurrency=1 的批次，最多两个批次并行；等待所有终态，不按 createdTaskCount 停止。G2 打开并提取五字段，G3 点击提交。记录 tasks_attempted、distinct_rows_processed、rows_succeeded、tasks_failed、throughput_rows_per_min、attempts_per_min、failure_reason_ratio、loop_lag_p99_ms。成功吞吐只计具有正确输出/站点回执的唯一成功行；空错误不算有原因，无失败时覆盖率记 null。默认 30 行，夜间 G2=10000/G3=1000 可配置。M2 的原生多行台账场景另建 native-batch-v1，不与此口径混算。 |
| R0-07 | 守门检查 `scripts/ratchets.mjs`，四项计数与 `scripts/ratchets-baseline.json` 比较：任一项大于基线即失败并指出具体项，小于基线时提示收紧基线：①前端配置面板写入、但后端源码中不存在的配置键（保存键名列表）；②`domains/workflows` 下写死的 Tailwind 调色类数量；③从第二套图标库（`@phosphor-icons/react`）导入的文件数，lucide 为保留库；④`docs/` 下 PNG 数量。 |
| R0-08 | CI：每次 push 运行离线基准（只记录、不设阈值，结果 JSON 作为构件上传）和守门检查；新增 `golden.yml`：手动触发 + 每晚一次，在 macOS 上安装固定版本 CloakBrowser 后运行黄金场景并上传指标。 |
| R0-09 | `AGENTS.md` 增加"整改期硬性规则"一节（整改方案 N4 的 6 条），并在"完成定义"中要求批量执行相关改动附基准对比。 |

## 5. 设计

### 5.1 目录

```text
apps/backend/tests/benchmarks/
├── __init__.py
├── report.py                  # 统一 JSON 结构与摘要输出（R0-04）
├── bench_claims.py            # R0-01
├── bench_runtime_overhead.py  # R0-02
├── bench_event_commit.py      # R0-03
├── test_offline_benchmarks.py # pytest 入口（benchmark 标记）
└── results/                   # .gitignore
apps/backend/src/autoflow/infrastructure/observability/
├── __init__.py
└── loop_lag.py                # R0-05
apps/backend/tests/golden/
├── __init__.py
├── site.py                    # 本地站点与故障注入
├── harness.py                 # 建项目、建表、存流程、建自动化、启动批次、收集指标
├── test_golden_site.py        # 站点自身的单元测试（不需要浏览器）
├── test_g2_scrape.py          # R0-06
└── test_g3_form_entry.py      # R0-06
scripts/ratchets.mjs, scripts/ratchets.test.mjs, scripts/ratchets-baseline.json
.github/workflows/golden.yml
```

### 5.2 基准运行方式

- 基准放在 `tests/benchmarks/` 下，以直接复用 `tests/fixtures/workflow_runs.create_queued_run` 与 `tests/integration/test_project_input_groups.py` 的建表辅助函数，不在生产包里引入测试依赖。
- 离线基准为普通 Python 模块：`uv run --directory apps/backend python -m tests.benchmarks.bench_claims --rows 10000`。
- pytest 入口 `tests/benchmarks/test_offline_benchmarks.py`（标记 `benchmark`，小规模参数，证明可运行且结构正确）。`benchmark`、`golden` 两个标记在 `pyproject.toml` 注册；默认 `addopts = -m "not benchmark and not golden"`，CI 基准步骤用 `-m benchmark`、黄金场景用 `-m golden` 显式选择。

### 5.3 LoopLagMonitor

- 纯 asyncio，无第三方依赖；样本存在定长 `collections.deque`（容量 6,000 = 5 分钟 × 每秒 20 次）。
- 快照：`LoopLagSnapshot(p50_ms: float, p99_ms: float, max_ms: float, samples: int)`；另有 `reset()` 供基准分段测量。
- 在 `bootstrap/app.py` 用现有 `add_event_handler("startup", ...)` 启动，在现有 `shutdown()` 的最外层 `finally` 中停止；不新增 HTTP 接口（避免 OpenAPI 变化）。

### 5.4 黄金场景站点

- `http.server.ThreadingHTTPServer`，随机端口，守护线程运行，`GoldenSite` 作为上下文管理器。
- `/item/<id>`：5 个字段（`#title`、`#price`、`#sku`、`#stock`、`#seller`）。id 以 `timeout-` 开头：该 id 第一次请求延迟 20 秒后才响应，之后正常；以 `gone-` 开头：固定 404。
- `/form?name=<v>[&lose=1]`：表单（`#name` 输入框、`#submit` 按钮，`method=post`，action 带上同样的查询串），回车与点击都会提交。
- `/submit`：记录一次提交（按 name 计数）；`lose=1` 时保持连接 30 秒后直接断开、不返回响应；否则返回 `<p id=result>ok:<name></p>`。
- `site.hits(path_prefix)`、`site.submissions(name)` 供断言。

### 5.5 守门检查的计数规则

- 配置键：扫描 `apps/desktop/src/renderer/domains/workflows/components/ConfigPanel.tsx` 与 `components/config-panels/*.tsx`（不含测试）中的 `handleChange('<key>'` 与 `onChange('<key>'`；若后端 `apps/backend/src/autoflow/**/*.py` 中既不含 `'<key>'` 也不含 `"<key>"`，计为"未读取"。基线保存键名列表，新增任何一个键名即失败。
- 调色类：正则 `\b(bg|text|border|ring|from|to|via)-(gray|slate|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-(50|[1-9]00|950)\b`，统计 `domains/workflows` 下 `.ts/.tsx/.css`。
- 图标：统计 `apps/desktop/src` 中含 `from '@phosphor-icons/react'` 的文件数。
- PNG：统计 `docs/**/*.png`（不区分大小写）。
- 这是文本扫描，是下限而非证明：配置键的精确校验由 M2 的节点配置 schema 取代。

## 6. 验收标准

| 编号 | 验收 |
| --- | --- |
| AC0-01 | `python -m tests.benchmarks.bench_claims --rows 2000` 输出符合 R0-04 的 JSON，含 `claim_ms_key_order` 与 `claim_ms_field_order`。 |
| AC0-02 | `bench_runtime_overhead` 输出 `framework_ms_per_node` 与 `events_per_node`；`events_per_node` 在当前代码上 ≥ 4（记录现状）。 |
| AC0-03 | `bench_event_commit` 输出 `event_commit_ms_p50` 与 `event_commit_ms_p99`，且 p99 ≥ p50 > 0。 |
| AC0-04 | 单元测试：同步阻塞事件循环 300 毫秒后，`snapshot().max_ms` ≥ 250，且有含"event loop lag"的 warning 日志；sidecar 应用对象上存在 `app.state.loop_lag` 且已注册启动钩子。 |
| AC0-05 | 无浏览器按预期 skip；配置浏览器时输入完整身份集合恰好覆盖、无重复，每条正常行提取/提交结果正确，每个故障样本确实访问，lose 行恰好提交一次。未知结果状态缺口独立 xfail(strict=True)，不得包住上述断言。30 次同一行失败且原因空：distinct_rows=1、rows_succeeded=0、成功吞吐=0、failure_reason_ratio=0；无失败覆盖率=null。 |
| AC0-06 | `node scripts/ratchets.mjs` 在基线上通过；测试中分别新增一个未读取配置键、一个写死调色类、一个 phosphor 导入、一张 PNG，各自导致失败并指出具体项；减少时不失败、提示收紧。 |
| AC0-07 | CI 在 push 时运行离线基准与守门检查，并把基准 JSON 作为构件上传；`golden.yml` 可手动触发。 |
| AC0-08 | `AGENTS.md` 含"整改期硬性规则"一节。 |

## 7. 风险

- CI 机器上离线基准绝对值不稳定：M0 只记录不设阈值；阈值从 M1 起按"相对基线不回退 20% 以上"设置。
- 配置键扫描有误报（键名恰好出现在无关字符串）或漏报：它是守门下限，不代替 M2 的节点配置 schema；schema 中存在键也不证明运行时读取，仍须行为测试。
- 黄金场景依赖本机 CloakBrowser：只在夜间与手动触发时运行，不阻塞普通 push。

## 8. r2 基准口径

- controlled-one-row-batches-v1 只借现有 debugSelection 固定输入，不改生产领取器，不绕过真实派发器。另保留“重复领取同一行”的已知缺陷诊断，它不作为行吞吐成绩。
- 原始数值 JSON 沿用 schemaVersion=1，Unit 扩展 ratio/rows_per_min/tasks_per_min，value 可为 null（仅无失败分母）。manifest 作为每次运行的必备伴随文件，与报告一起上传。
- 正常样本、首次超时、永久 404、响应丢失都按完整身份列明预期；强制核对站点计数与真实 Task 结果。G3 的缺失状态只在独立用例标 xfail，基准有效性断言始终严格。
- M1 保留点击版 G3 并新增按键版；M2 增加写回版/native 版。场景升级后保留原场景或在同一候选/硬件上重跑比较基线，不能将更换场景的指标拼成趋势。
