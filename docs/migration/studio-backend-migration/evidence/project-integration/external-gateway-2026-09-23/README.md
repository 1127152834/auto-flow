# 项目任务消费 Studio 外部服务适配器（2026-09-23）

状态：后端真实 worker 已验；正式 Electron 项目 UI 组合、外部供应商及其他平台未验。

项目批次原先给 `ExecutionContext.external_integrations` 留空，导致已批准的 API、邮件、SSH 等生产节点在 Studio 独立运行可用、作为项目任务却返回“外部服务不可用”。项目 worker 现在复用 Studio 已有的 `WorkflowIntegrationGateway`，并在成功、失败或取消后独立关闭；浏览器上下文清理失败也不会跳过外部连接关闭。未新增执行器或服务协议。

在独立临时工作区执行 `uv run --project apps/backend pytest -q apps/backend/tests/integration/test_project_data_worker.py`：17 项通过，包含项目任务使用真实独立 worker 向本地 HTTP 服务发送中文 JSON、SQLite 持久化输出事件、请求期间取消且无后续输出/占用。Ruff 与相关两处生产文件的 mypy 通过。测试没有读取用户数据库或启动 CloakBrowser。

这只核销项目任务的外部服务共享入口和取消清理，不核销每个外部节点在项目正式 UI 中的独有分支；自定义模块依赖、历史子流程、项目数据写回仍待完成。213 节点及 639 条节点台账数字不因本次共享适配改变。
