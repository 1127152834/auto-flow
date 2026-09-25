# 工作流代理控制实施与验证

日期：2026-09-25。状态：confirmed（本地实现/测试）；真实供应商、Windows、打包：pending。
来源：当前分支源码、实际命令输出、独立代码审查及 RED→GREEN 回归；没有真实供应商写入。

## 交付范围

隔离工作树 `codex/workflow-proxy-control`，基线 `0f9884522d052a427d130f5157ac5f0df99ca215`。原主工作区已有修改未纳入。
新增三个节点、共用配置组件、Studio/项目 worker 私有请求协议、身份绑定与使用登记、按操作预算及新连接出口验证。复用 proxy_operations 和现有远程服务；没有新表、依赖或调度器。
节点默认 10 秒/5 轮/30 秒，支持变量、捕获失败、原操作查询、可取消等待。未知操作保留数据库阻断。保留浏览器/页面/Cookie，不刷新或重启。
使用说明：`docs/workflow-proxy-control.md`；设计/实施计划：`docs/superpowers/{specs,plans}/2026-09-25-workflow-proxy-control-*.md`。

## 独立审查及修复

一次全分支独立审查；3 项 P1、1 项 P2 均接受并修复，无延期 minor：

1. 节点结束后远端预检可能晚到 POST：增加 prepared token 身份、节点访问有效性、截止时间检查；取消 pending RPC；取消 prepare 释放 claim。
2. 原操作在两轮之间完成可能重复 POST：记录已交付状态，未交付成功时继续读取原操作；按持久 write_started 去重统计实际请求。
3. 旧浏览器节点未声明 requires_browser：补声明，使已有并行保护覆盖旧节点；用真实运行时并行分支验证。
4. 第二次预检冷却误判 fatal：保留可重试的 PROXY_COOLDOWN/PROXY_BUSY 分类。

每项新增测试均观察到修复前失败；修复组 58 项通过。补查探测抛错漏记请求次数，增加 `test_failed_post_switch_probe_preserves_operation_and_sent_count`：先观察 requestsSent 为 0 的失败，修复后统计 1，下一轮查询原操作并成功，POST 总数仍为 1。

## 最终验证

命令从隔离工作树根目录运行。Python 子进程使用显式 PYTHONPATH，防止共享虚拟环境的 editable 安装把子进程导向原工作区。

```sh
PYTHONPATH="$PWD/apps/backend/src" apps/backend/.venv/bin/python -m pytest -q -c apps/backend/pyproject.toml \
  apps/backend/tests/contract/test_proxy_remote_controls.py \
  apps/backend/tests/contract/test_proxy_runtime.py \
  apps/backend/tests/contract/test_proxy_api.py \
  apps/backend/tests/integration/test_proxy_management.py \
  apps/backend/tests/integration/test_proxy_concurrency_review.py \
  apps/backend/tests/unit/test_workflow_proxy_control.py \
  apps/backend/tests/unit/test_proxy_worker_requests.py \
  apps/backend/tests/unit/test_browser_proxy_relay.py \
  apps/backend/tests/integration/test_workflow_proxy_workers.py \
  apps/backend/tests/unit/workflows/test_scope_preflight.py \
  apps/backend/tests/unit/test_project_graph_executor.py \
  apps/backend/tests/integration/test_workflow_worker_protocol.py \
  apps/backend/tests/integration/test_workflow_worker_process.py

npm test -- catalog-field-contract.test.ts catalog-roundtrip.test.ts catalog-panel-registration.test.tsx ProxyControlConfig.test.tsx ProxyRetryCountdown.test.tsx
apps/backend/.venv/bin/mypy apps/backend/src
npm run typecheck
npm run lint
npm run build
npm run openapi:check
npm run test:structure
git diff --check
```

| 验证 | 实际结果 |
| --- | --- |
| 审查修复后的前一轮定向后端集合 | 273 passed，1 条 Starlette 弃用警告 |
| 最终补充后的上述后端组合 | 232 passed，1 failed，1 条同类警告，77.31 秒 |
| 前端 5 个定向文件 | 1271 passed，6.32 秒 |
| Ruff：相对基线所有 37 个改动 Python 文件 | All checks passed |
| mypy 全后端 | 496 source files，无错误；既有 untyped-body 提示 |
| 前端 typecheck / lint | exit 0 |
| 前端 build | exit 0，30.08 秒；依赖 pure annotation 和动态/静态 import 混用警告 |
| OpenAPI check | exit 0 |
| 结构测试 | 4 passed |
| git diff --check | 无空白错误 |

未把重复测试次数相加作为覆盖数量。没有声称整个仓库全套测试或全仓 Ruff 通过；全仓 Ruff 的其他既有问题未纳入本功能修改。

唯一失败是 `test_proxy_runtime.py::test_runtime_mounts_proxies_but_never_publishes_host_contract` 的“所有 OpenAPI schema 都不能有 password 属性”断言。将基线提交的 `apps/backend/src` 通过 git archive 提取至临时目录，用 PYTHONPATH 和 pytest `-o pythonpath=<基线源码>` 运行同一测试，得到相同失败（1 failed，7 deselected）。本次未修改该测试或相关既有模型，保留为基线问题；不能报告所有测试全绿。
临时原始输出：`/tmp/autoflow-proxy-delivery.txt`、`/tmp/autoflow-proxy-runtime-baseline.txt`、`/tmp/autoflow-proxy-ui-final.txt`、`/tmp/autoflow-proxy-mypy-delivery.txt`；这些是本机临时证据，不作为仓库依赖。

## 决策与剩余验证

- 确认读取失败或仍忙时保留 unknown；证据不足时继续查询，不能强制解锁后重复写入。
- 遗留 worker 无可靠代理身份且清理未确认时阻断工作区全部代理；代价是其他代理也等待清理。未来具备持久可信绑定后可缩小阻断范围。
- 管理 API 限流与冷却分类独立；缺少真实剩余时间字段时保持 null。Studio 重试倒计时不代表供应商冷却倒计时。
- 实网切换 IP/地点、真实冷却响应、新连接出口与登录态保持未执行；需要选择明确允许中断且有操作能力的代理。合成测试不提升供应商字段证据等级。
- Windows、安装包/打包后 worker、真实 CloakBrowser 页面与外部供应商变更行为未验证。本机 worker/SQLite/转发器集成测试不替代这些验收。
- 实施交付时本分支与提交保留供审查，未合并主工作区，未推送或发布。后续用户授权合并见 `2026-09-26-workflow-proxy-control-merge.md`。
