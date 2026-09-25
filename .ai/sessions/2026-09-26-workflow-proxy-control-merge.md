# 工作流代理控制本地合并

日期：2026-09-26。状态：confirmed。来源：用户明确要求“合并”，Git 状态、文件摘要及合并后实际测试。

- 目标：原工作区的 `codex/project-management-pm9`。
- 执行：`git merge --ff-only codex/workflow-proxy-control`，从 `0f988452` 快进到 `56d06a09`，包含全部 5 个功能提交，无冲突。
- 合并前记录 103 个已有修改/未跟踪文件的 SHA-256；合并后逐个相等，Git porcelain 状态完全相同。未暂存、覆盖或提交其他任务的修改。
- 未推送、发布或操作真实代理。功能分支及工作树保留，未做清理。

## 合并后验证

- pytest：代理远程契约、节点执行、worker 请求、转发器、项目图、真实 worker 管道，共 90 项，89 passed / 1 failed。唯一失败为 `test_proxy_nodes_over_real_owned_worker_pipes[project-proxy_change_location]` 的进程退出等待超过测试配置 0.5 秒，进程记录 returncode=0。
- 随后单独执行完整 `tests/integration/test_workflow_proxy_workers.py`：6 passed，15.15 秒。不隐去首次超时，也不把复查次数相加；没有修改生产代码或放宽测试时间。
- 前端原 5 文件定向组合：1240 passed / 31 failed。全部失败位于 `catalog-field-contract.test.ts` 的组件清单映射断言，涉及已有 AI/network_capture 字段，没有代理节点失败。
- 用测试相同映射判据分别读取已提交和原有未提交的 `docs/migration/studio-frontend-completion/component-tools.json`：提交版本缺失 0 个映射，本地修改版本缺失 31 个，准确解释失败。该文件没有本功能变更，合并前后字节摘要相同；保留其他任务修改，不擅自回滚清单或改测试。
- `npm run openapi:check`、`npm run typecheck`、功能提交范围 `git diff --check` 均通过。
- 真实供应商、Windows、打包验收仍未执行；此前记录的后端 OpenAPI password 断言基线失败仍未处理。

命令与本机临时输出：

```sh
PYTHONPATH="$PWD/apps/backend/src" apps/backend/.venv/bin/python -m pytest -q -c apps/backend/pyproject.toml apps/backend/tests/contract/test_proxy_remote_controls.py apps/backend/tests/unit/test_workflow_proxy_control.py apps/backend/tests/unit/test_proxy_worker_requests.py apps/backend/tests/unit/test_browser_proxy_relay.py apps/backend/tests/unit/test_project_graph_executor.py apps/backend/tests/integration/test_workflow_proxy_workers.py
PYTHONPATH="$PWD/apps/backend/src" apps/backend/.venv/bin/python -m pytest -q -c apps/backend/pyproject.toml apps/backend/tests/integration/test_workflow_proxy_workers.py
npm test -- catalog-field-contract.test.ts catalog-roundtrip.test.ts catalog-panel-registration.test.tsx ProxyControlConfig.test.tsx ProxyRetryCountdown.test.tsx
npm run openapi:check
npm run typecheck
```

输出保存在 `/tmp/autoflow-proxy-merged-backend.txt`、`/tmp/autoflow-proxy-merged-workers-recheck.txt`、`/tmp/autoflow-proxy-merged-frontend.txt`；文件保留校验基准为 `/tmp/autoflow-proxy-premerge.json`。临时路径不是仓库运行依赖。
