# Task 3 报告：项目交互连接恢复反馈

日期：2026-09-28

基线：`d6f9cb0f8f9dd99be6e4734641fe3144f232f336`

范围：`ProjectInteractionHost`、必要组件测试、本报告

状态：实现与定向验证完成，未 push

## 结论

`ProjectInteractionHost` 现在分别保存通信中断提示和真实操作错误。一次完整且仍属于当前连接代次的 poll 成功后，只清除通信提示；脚本执行失败或无法显示输入窗口等真实操作错误不会被成功 poll 清除。连接或 client 改变会推进本地 revision，旧请求的迟到成功和失败都不能再改写当前提示状态。

项目交互协议未改动，仍沿用原有 claim、原命令提交、未知结果查询和不重放脚本的路径。

## 代码改动

- `apps/desktop/src/renderer/domains/project-runs/components/ProjectInteractionHost.tsx`
  - 将单一 `error` 拆为 `connectionError` 与 `operationError`。
  - 当前 client/connected 变化时推进 revision；poll、输入请求、窗口显示失败和脚本异步失败都在写状态前校验同一 revision。
  - 完整 poll 成功时仅执行 `setConnectionError(undefined)`。
  - 两类提示同时存在时垂直排列，分别可关闭。
- `apps/desktop/src/renderer/domains/project-runs/components/ProjectInteractionHost.test.tsx`
  - 增加通信失败后成功 poll 清除通知的回归。
  - 增加真实脚本失败不会被后续成功 poll 清除的回归。
  - 增加连接失效后迟到成功不改变提示的回归。
  - 测试结束恢复真实计时器，避免 fake timer 泄漏。

## RED / GREEN

第一次命令误用了仓库根路径，Vitest 在 desktop workspace 中没有找到测试文件；这是测试命令路径修正，不算产品 RED：

```text
npm --workspace @autoflow/desktop test -- --run apps/desktop/src/renderer/domains/project-runs/components/ProjectInteractionHost.test.tsx
No test files found, exiting with code 1
```

修正 workspace 相对路径后，在实现前运行新增回归：

```text
npm --workspace @autoflow/desktop test -- --run src/renderer/domains/project-runs/components/ProjectInteractionHost.test.tsx
Test Files  1 failed (1)
Tests       1 failed | 4 passed (5)
```

失败点为“下一次成功 poll 后通知仍存在”，准确复现旧行为。

实现后的定向 GREEN：

```text
npm --workspace @autoflow/desktop test -- --run \
  src/renderer/domains/project-runs/components/ProjectInteractionHost.test.tsx \
  src/renderer/domains/project-runs/interactions.test.ts
Test Files  2 passed (2)
Tests       12 passed (12)
```

## 静态验证

```text
npm --workspace @autoflow/desktop run typecheck
exit 0

npm exec --workspace @autoflow/desktop -- eslint \
  src/renderer/domains/project-runs/components/ProjectInteractionHost.tsx \
  src/renderer/domains/project-runs/components/ProjectInteractionHost.test.tsx
exit 0
```

最终提交前于 14:41 再次运行同一组 12 个定向测试、typecheck、定向 eslint 与 `git diff --check`：2 个测试文件、12 个测试全部通过，其余三项均 exit 0。

## 真实原生断连/恢复验证

验证使用当前源码 Electron renderer 与基线已冻结的生产 backend 二进制。工作区、user-data 和数据库均隔离在 `/tmp/autoflow-task3-qa.j6AbYM`。没有使用 HTTP 伪成功响应。

隔离实例身份：

```text
main PID 56848
/Users/zhangtiancheng/Documents/projects/autoflow/node_modules/electron/dist/Electron.app/Contents/MacOS/Electron
sidecar PID 56855, PPID 56848
/Users/zhangtiancheng/Documents/projects/autoflow/apps/backend/dist/autoflow-backend/autoflow-backend
instanceId 56848-1790577093419
```

用 CUA 在隔离实例中创建项目 `Task3 连接恢复实测`、关联真实工作流并启动一个任务。工作流的真实 `js_script` 在 dedicated worker 中运行 20 秒，将 `count` 从 0 增为 1，返回 `task3-original-result`，随后由 `print_log` 输出变量与返回值。

在 API 已返回同一请求为 `status=claimed` 后，只对已核验的 sidecar PID 56855 执行 `SIGSTOP`。`ps` 显示 `T+`；2026-09-28T14:38:22+0800 仍确认该 PID/PPID/命令一致。CUA 随后真实读取到：

```text
项目交互连接中断，正在查询原请求；未重新执行脚本
```

2026-09-28T14:38:45+0800 对同一 PID 执行 `SIGCONT`。下一次完整 poll 后 CUA 的 AX diff 删除了通知节点；同一刷新中批次变为“已完成”，成功 1、进行中 0。

任务详情由 CUA 显示：

```text
真实断连脚本 14:38:16 尝试 1 成功
JS脚本执行成功，返回值: task3-original-result
1:task3-original-result
```

SQLite 读取 `project_workflow_run_events` 和 `project_workflow_runs`：

```json
{"distinct_script_attempts":1,"script_outputs":1,"result":"task3-original-result"}
```

间隔两秒的两次稳定性读取完全一致：

```json
{"status":"succeeded","execution_generation":1,"last_sequence":15,"script_attempt_events":2,"script_outputs":1,"result":"task3-original-result"}
```

这里 `script_attempt_events=2` 是同一 `attempt=1` 的开始/完成生命周期事件；`COUNT(DISTINCT attempt)=1`。输出事件只有一条，结果未被恢复 poll 重写。隔离 main/sidecar 已退出。用户原有 `autoflow-android-handoff` PID 26110 在清理后仍运行，未被操作。

### 可审查原始证据

证据清单与精确身份记录在 [`docs/qa/2026-09-28-remediation/interaction-notice/README.md`](../../../docs/qa/2026-09-28-remediation/interaction-notice/README.md)。同目录包含：

- `query-interaction-notice.sh`：以 `sqlite3 -readonly` 和 `PRAGMA query_only=ON` 复跑身份、事件与单次执行查询。
- `sqlite-readonly-results.txt`：上述脚本对保留数据库的实际原始输出。
- `instance-exit-readonly.txt`：隔离实例退出、原用户实例仍运行、测试目录/SQLite 仍存在及 SQLite SHA-256 的只读核验。

真实测试目录 `/tmp/autoflow-task3-qa.j6AbYM` 和原 SQLite 保留供复查。实时 CUA 期间没有把截图或 AX dump 保存成文件，因此证据目录没有重建或补造这类资产。

## AOCI 会话记录

按仓库约束先调用 `aoci_rules`，再建立 Whole-Index。前两条全新 Overview 链分别在继续游标时失败；两次原始返回完全相同：

```text
[cognition_snapshot_unavailable] Overview组装期间正式认知资产发生变化；未交付混合快照
建议: 认知资产并发变化停止后，重试显式Overview
```

两次失败响应本身没有返回时间戳，调用侧当时也没有单独记录墙钟时间，因此不能虚构精确时间。它们均发生在 2026-09-28 最终成功链开始前：第一次已交付 ordinal 1–128 后失败，第二次从新链 chunk 1 后失败。两次可核验 receipt 身份均为：

```text
index_sha256=8d03add9c0cdf5cb207f320eefcddc3c831698afdea9ed2ba9d7c6b65d3e6545
entry_count=280
chunk_tokens=8000
```

根任务停止其他 AOCI 调用并给出独占窗口后，只再执行一条全新完整链。该链在约 2026-09-28T14:15:17+0800 至 14:18:29+0800 完成 5 chunks、280 entries、约 31,829 tokens；Host delivery confirmed，challenge 10/10。投影为 `model_cognition_usable=true`、`governance_aligned=false`，正式索引仍 dirty/stale 且有 semantic-threshold pending。本任务据此只做 source-bound 修改，没有调用 maintain/update/report，也没有修改 AOCI 资产。

## 自审与边界

- 成功只清通信提示，不会清脚本/窗口操作错误。
- poll 串行运行；revision 额外阻断 client 或连接代次变化后的迟到结果。
- 卸载仍通过原 AbortController 取消 poll 和已领取脚本，旧用例保留。
- `interactions.ts` 未改；未知结果仍查询同一 command，不会重发动作或重跑脚本。
- 没有后端源码或后端测试改动，没有修改 remediation README、`packaged-end-realqa.mjs`、最终构建/日志资产或第三方 WIP。
- 当前仓库存在其他任务/AOCI 的大量未提交文件；提交必须只显式暂存本报告和上述两个组件文件。

置信度：高。真实故障注入、界面恢复、单次执行和 SQLite 稳定结果均已直接验证。

---

## Review fix round 1（基线 `489224c5`，2026-09-28）

### 复核结论与改动

Reviewer 指出的 Important 问题成立：`pending` 列表成功之后，`executeProjectScript` 内部的 request 读取仍可能发生瞬态失败；旧 Host 已经登记 `scripts` key，并把该失败写成 `operationError`，因此恢复后不会重试读取。此前“完整 poll 成功”也只覆盖了 pending 列表，不覆盖执行脚本所必需的 request/claim 读取。

本轮将脚本路径分成三个显式阶段：

1. `readProjectScript` 在 claim 前读取并校验原 request。瞬态失败仍属于 poll transport failure，不登记 key，下一次 poll 可以安全重读。
2. request 成功后先登记原 identity key，再由 `claimProjectScript` 使用原 target、单一 command key 和未知结果查询完成 claim。从该边界开始不允许重放。
3. `executeClaimedProjectScript` 才启动原 dedicated Worker，并以同一 identity 和 claimId 确认 result。

Host 只有在 pending 列表、request 读取和 claim 所需读取全部完成后才清除 `connectionError`。真实 request/claim/worker/result 错误仍写入 `operationError`。原 `executeProjectScript` 保留为上述三个阶段的组合，因此 `interactions.test.ts` 的原命令提交、未知结果查询和 claim 后不重放契约继续适用。

### RED / GREEN 原始命令

新增回归先在旧实现上执行：

```text
npm --workspace @autoflow/desktop test -- --run src/renderer/domains/project-runs/components/ProjectInteractionHost.test.tsx -t "retries a transient JS request read before claim and executes the script once"
exit 1
Test Files  1 failed (1)
Tests       1 failed | 7 skipped (8)
TestingLibraryElementError: Unable to find an element with the text: /项目交互连接中断/
Duration 18.98s
```

旧实现把 `TypeError('offline')` 显示为真实操作错误 `offline`，并没有显示可恢复的 transport notice，准确命中 review finding。

实现后的同一聚焦回归：

```text
npm --workspace @autoflow/desktop test -- --run src/renderer/domains/project-runs/components/ProjectInteractionHost.test.tsx -t "retries a transient JS request read before claim and executes the script once"
exit 0
Test Files  1 passed (1)
Tests       1 passed | 7 skipped (8)
Duration 7.17s
```

第一次运行两个完整文件时，新用例读取到了前一用例遗留的模块 mock 调用历史，结果为 13 个测试中 1 failed。回归中增加 `runJsScript.mockReset()` 后，最终完整运行如下：

```text
npm --workspace @autoflow/desktop test -- --run src/renderer/domains/project-runs/components/ProjectInteractionHost.test.tsx src/renderer/domains/project-runs/interactions.test.ts
exit 0
Test Files  2 passed (2)
Tests       13 passed (13)
Duration 14.23s
```

这 13 个测试同时覆盖本轮新增的 pre-claim request 恢复、真实 operation error 保留、stale/unmount，以及原有 submit/query/no-replay 协议。

### 静态检查

最终源码状态运行：

```text
npm --workspace @autoflow/desktop run typecheck
exit 0

npm exec --workspace @autoflow/desktop -- eslint \
  src/renderer/domains/project-runs/interactions.ts \
  src/renderer/domains/project-runs/interactions.test.ts \
  src/renderer/domains/project-runs/components/ProjectInteractionHost.tsx \
  src/renderer/domains/project-runs/components/ProjectInteractionHost.test.tsx
exit 0

git diff --check -- <Task 3 owned files>
exit 0
```

没有运行全量 frontend/build/package。为真实 UI 验收执行过源码 Electron build；main/preload 完成，renderer 输出更新至 2026-09-28T15:27:10+0800，但命令承载工具在最终退出状态返回前超时，因此不把它计为正式 build gate。最终 build/package 仍由 root 执行。

### Review fix 真实 UI 验收

验收使用新的独立复制工作区 `/tmp/autoflow-task3-round1-qa.UlhnXI`、当前源码 renderer 和冻结生产 backend。复制前源库与新库 SHA-256 同为 `08f06a3b429bcab97a10362461ea491fb6685cb6878c1e8daa6fb52b5bb8189e`；运行后新库 SHA-256 为 `492a09bfe9eb0e2f5c967590b1870d464e7125184bfed54390cf48bb1046a192`，因此本轮新行与旧 Task 3 行可区分。

本轮独立成功运行身份：batch `2c82d320-47a6-457e-89e6-8dd462f6ce7a`、task `84908701-ce45-4571-8763-d97c02afb4d5`、run `70bae1a2-f936-455d-86fd-41ac6330f709`。SQLite 显示 `execution_generation=1`、`last_sequence=15`、一个 distinct script attempt、一个 output，结果为 `task3-original-result`。

运行中断连使用 batch `c05fd0df-484e-4d4d-b5c4-be4e2e018560`、task `9c94e341-2071-447a-a24a-f5c7fa2b54ce`、run `d25462ec-6c04-4bd9-9f21-c7c987ac4762`。只对已核验的专属 sidecar PID `55301`（PPID `55287`，instance `55287-1790580512419`）在 `15:46:32+0800` 执行 `SIGSTOP`。任务仍显示运行中时，实际 CUA screenshot 与 AX 均出现：

```text
项目交互连接中断，正在查询原请求；未重新执行脚本
```

`15:47:12+0800` 对同一 PID 执行 `SIGCONT` 后，实际 screenshot/AX 显示 transport notice 消失，同时真实 operation error `交互命令不存在` 保留。40 秒暂停超过 backend interaction lifetime，SQLite 将 request `c0d1d0be-b921-44c2-a131-b9980a00bdb7` 记录为 `expired`，该 run 因此失败；这次运行只证明 notice 恢复和真实 operation error 保留，不计为成功执行。pre-claim 瞬态失败后的单次执行由确定性回归证明，真实单次成功由上述独立成功 run 证明，没有伪造 HTTP 成功。

专属 Electron PID `55287` 与 sidecar PID `55301` 已退出；用户原有 android-handoff app PID `26110` 仍运行且未被控制。原 SQLite 保留。可审查截图、AX、进程身份、只读 SQL 脚本与原始结果见 [`interaction-notice-round1/README.md`](../../../docs/qa/2026-09-28-remediation/interaction-notice-round1/README.md)。

### 边界与 AOCI

- 本轮仅修改 desktop renderer 源码/测试、本报告及 Task 3 证据目录；没有后端/Python改动，也没有触碰 root 的最终构建、package、native End 资产。
- 当前 AOCI 为 `recovery_pending` 且无正文；依照协调要求未接管 recovery、未调用 maintain/update、未修改 AOCI 资产。该限制不影响本轮 source-bound 修复与验证。
- 置信度：高。代码级边界由 13 个测试覆盖，真实 UI 的 interrupted/recovered 状态有本轮实际 PNG、AX 和 SQLite 证据；真实故障持续时间导致过期这一限制已明确保留。
