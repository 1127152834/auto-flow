# 项目默认模型真实验收（2026-09-23）

- 入口：`apps/backend/tests/integration/test_studio_project_model_live.py`。
- 命令：在 `apps/backend` 执行 `AUTOFLOW_LIVE_MODEL_TEST=1 .venv/bin/pytest -q --tb=short tests/integration/test_studio_project_model_live.py`。
- 默认运行该测试会跳过；启用后会访问真实付费模型。本次只进行一次请求，没有自动重试和第二模型调用。
- 实测链路：临时项目默认提供商 → 正式 bootstrap/协调器 → 主应用 ModelService/SystemCredentialStore → 私有 worker 启动通道 → 真实 worker/HttpModelProvider → OpenRouter 的 `aion-labs/aion-2.0` → SQLite 事件 → 进程清理。
- 主应用模型数据库所有连接都使用 SQLite URI `mode=ro`，并逐连接设置/核验 `query_only=ON`；不启动主应用 bootstrap、不执行迁移和凭据维护。项目、文档、运行、事件及产物目录均使用独立临时工作区。
- 本用例是纯 AI 节点，不打开浏览器；Profile 仅使用已有测试元数据夹具，不声称验证真实浏览器/真实 Profile 启动。
- 返回精确文本“项目默认模型验收成功”；运行及清理均完成，剩余 worker PID 和服务阻塞列表均为空。保存文档和原始运行快照中的 `modelId` 仍为空，仅执行副本继承默认模型。
- `real-model.json` 仅记录非秘密结果、模型 ID、提供商主机、原样 usage、计时及清理断言；不复制系统凭据、连接密钥或私有启动报文。供应商 usage 数值原样保留，不额外推断计费币种或矛盾字段含义。
- 本证据是实际外部模型与真实 worker 验收；不包含正式 Electron UI。显式模型覆盖已有独立组装测试，本次不为重复证明而再产生外部请求。
- 实际测试：1 passed（8.38 秒）；详细结果见 `real-model.json` 和 `pytest.log`。
