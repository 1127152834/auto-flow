# 项目临时执行器退役验证

日期：2026-09-24。状态：confirmed（本地清理范围）。来源：本记录命令的实际输出、生产调用链与差异检查。关联决策：`../decisions/2026-09-24-retire-project-browser-legacy.md`。

基线：669c01c0；隔离分支：`codex/remove-project-legacy-executor`。未修改并行 PM9 / Studio 工作区，未合并、推送或更改发行验收状态。

## 实现与行为

- 删除 `providers/browser/workflow_executor.py` 及 `_LegacyBrowserNode`。四个节点类型保留，项目注册表直接取得 `build_production_executor_registry()` 的实现；不再保留独立浏览器动作或线性执行循环。
- 项目和 Studio 使用同一正式会话语义；失败截图从该会话获取。保留项目事件提交门禁、取消、整体超时、数据/End/人工能力及 chain/v1 文档转换。
- 移除临时行为预期：非逐字输入遵循正式 `fill` 行为，变量遵循共享解析器，缺少当前页面时遵循正式错误行为。测试改用正式入口，未删除超时、停止、截图及业务结果断言。
- 新增同一文档经两入口执行的对照测试，比较四节点动作、页面、变量及输出。删除前失败于项目动作没有在正式会话登记当前页面；删除后通过。

## 实际验证

命令均从隔离工作区执行；本地原始日志在 `.tmp-tests/legacy-cleanup/`（忽略目录）。

| 检查 | 结果 |
| --- | --- |
| `uv run --directory apps/backend pytest -q tests/unit/test_workflow_worker.py tests/unit/test_project_graph_executor.py` | 43 passed；随后进一步收紧关闭页面断言，由下述全量回归复核 |
| `uv run --directory apps/backend pytest -q tests/differential/workflows/test_b1_executor_parity.py tests/differential/workflows/test_variable_parity.py` | 51 passed；使用冻结 WebRPA 5ccb900e8dcf1530aae66f676d87593c416c7ebb |
| 设置 `AUTOFLOW_TEST_CLOAKBROWSER` 后运行 `test_workflow_real_cloakbrowser.py`、`test_project_batch_real_cloakbrowser.py`、`test_project_sheets_real_cloakbrowser.py` | 46 passed，658.15 秒；真实原生浏览器/worker，Sheets 传输为测试替身 |
| `uv run --directory apps/backend pytest -q --maxfail=20` | 3487 passed、79 skipped、2 warnings，894.77 秒；包含最终收紧的关闭页面断言。默认跳过的真实浏览器场景另以上述显式环境运行 |
| `uv run --directory apps/backend ruff check src` 及四个修改测试文件 | passed |
| `uv run --directory apps/backend mypy src` | passed，407 source files |
| `node scripts/verify-pm9-coverage.mjs` | 251 条引用有效；未提升任何覆盖状态 |
| `node scripts/build-backend.mjs` | passed，macOS arm64 后端打包成功 |
| `node scripts/smoke-sidecar.mjs --executable apps/backend/dist/autoflow-backend/autoflow-backend` | 首次 15 秒 readiness 超时；后续原命令复核通过。未改超时或健康判定，首次原因未确认 |
| `node scripts/smoke-project-management.mjs --executable apps/backend/dist/autoflow-backend/autoflow-backend --runtime-kernel /tmp/autoflow-pm9-public-browser/chromium-145.0.7632.109.2/Chromium.app/Contents/MacOS/Chromium --output-dir .tmp-tests/legacy-cleanup/packaged` | passed；生产 HTTP、打包 worker、真实浏览器、UUID 参数、人工继续、End/关联修复、子流程权限/取消、并行分支、登录态恢复等现有断言通过 |
| 源码引用检索、`git diff --check` | 旧临时执行器无生产引用，差异检查通过 |

本轮未重跑三平台 CI / 安装包实机验收，也未执行 Google Sheets 实网授权或 OAuth 验收。打包验证仅代表本地 macOS arm64 后端生产链，不能据此认定整个 PM9 完成；`releaseAccepted` 不变。
