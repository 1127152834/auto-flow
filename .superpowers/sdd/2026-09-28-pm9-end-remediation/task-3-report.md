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
