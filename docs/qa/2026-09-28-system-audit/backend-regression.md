# 后端回归与测试真实性审计

- 日期：2026-09-28；状态：默认全量、静态审计、42 项真实 CloakBrowser 夹具集成及失败独立复核 completed。
- 源码基线：`33ae3aa49600840b1700c83723408c494dc201a8`。审计前已有未提交文档和历史验收资料；本次不改业务代码、不修改用户数据库或凭据；审计产物由主任务统一提交。
- 环境：macOS 26.4.1 arm64；Python 3.11.13；uv 0.10.6；pytest 9.1.1；Ruff 0.16.7；mypy 2.3.1；FastAPI 0.141.1；SQLAlchemy 2.0.52；Alembic 1.19.2；CloakBrowser 0.5.9；Playwright 1.62.0。
- 范围：执行仓库全部现有后端测试、后端静态门禁、依赖一致性检查和真实临时 SQLite 迁移核验；明确区分模拟回归、真实本地 I/O 集成与真实外部端到端验收。真实 Electron/公网/模型等场景由本次总审计的其他报告覆盖。

## 当前结果

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| 全量收集 | 4257 项，395 个 `test_*.py` 文件 | `backend/pytest-collection.log`、`backend/test-inventory.json` |
| 默认全量 pytest | 4150 passed / 64 failed / 43 skipped / 1 warning；1319.96 秒 | `backend/pytest.log`、`backend/pytest.xml`、`backend/pytest-summary.json` |
| 默认跳过的真实 CloakBrowser 用例 | 40 passed / 2 failed / 1 warning；918.27 秒；42 项全部执行 | `backend/browser-run.json`、`backend/browser-pytest.log`、`backend/browser-pytest.xml` |
| Ruff（与 CI 相同检查范围） | 失败：137 项，121 文件；src 15 项，tests 122 项 | `backend/ruff.log`、`backend/ruff.json` |
| mypy src（CI 实际命令） | 通过：502 source files | `backend/mypy.log` |
| mypy --strict src（架构承诺的门槛） | 失败：1041 errors，157 files | `backend/mypy-strict.log` |
| 锁文件与已装依赖（包括 build 组） | 通过：217 packages resolved，187 installed packages audited；不需要变更 | `backend/dependency-check-with-build.log` |
| SQLite 空库升级、重复升级 | 通过：唯一 head `0023_merge_studio_android`，82 张表 | `backend/migration.json` |
| SQLite integrity / foreign_key_check | 通过：`ok`，0 外键违规 | `backend/migration.json` |
| Alembic ORM metadata 对齐 | 失败；独立脚本再次复现 | `backend/migration-check.log`、`backend/verify_migration_metadata.py` |

测试收集分布：compatibility 3；contract 717；differential 1054；integration 1154；migration 3；unit 1326。参数化后数量不等于业务场景或节点覆盖数。现有 CI 命令不生成代码分支覆盖率；本报告不凭测试数量推算覆盖率。

对初始 4257 个唯一用例，以补跑结果替换 42 个浏览器 skip 后，为 **4190 passed / 66 failed / 1 未执行**。此合并计数没有把后续诊断变体或单项复跑作为原用例通过；唯一未执行项为真实计费模型验收。两个 pytest 批次各有一条 AnyIO `BlockingPortal` 弃用警告。

| 测试目录 | 通过 | 失败 | 跳过 |
| --- | ---: | ---: | ---: |
| compatibility | 3 | 0 | 0 |
| contract | 711 | 6 | 0 |
| differential | 1054 | 0 | 0 |
| integration | 1056 | 55 | 43 |
| migration | 2 | 1 | 0 |
| unit | 1324 | 2 | 0 |

## 64 个失败的根因分类

| 原因 | 数量 | 定性与验证 |
| --- | ---: | --- |
| 迁移 head 常量过期 | 47 | 45 项仍期望 `0020_recording_project_scope`，2 项仍期望 `0015_workflow_mcp`；当前真实唯一 head 为 `0023_merge_studio_android`。这是测试维护问题，不代表 47 次数据损坏。 |
| 敏感结果事件契约不一致 | 6 | 测试期望 `output.value=None`，实现对敏感变量完全不发 output。独立重跑 6 failed / 4 passed；运行成功，凭据时序断言通过。 |
| BrowserStatus 旧精确快照 | 4 | 未纳入新增的 5 个状态字段；独立重现。 |
| proxy schema 旧全局断言 | 1 | 禁止所有 schema 出现 password，与 WebDAV 输入 schema 冲突；不证明泄密。 |
| 来源台账测试旧数量 | 1 | 台账已为 216 项，测试仍期望 213。 |
| 执行器注册表旧集合 | 1 | 断言遗漏新增的 3 个代理节点。 |
| 关停测试调用了错误 handler | 1 | `await app.router.on_shutdown[-1]()` 实际选中后来新增的同步 `LayaRuntime.close`，出现 await None。完整 HTTP/SSE 关停四种组合通过。 |
| Excel 测试夹具缓存没有写入 | 1 | 原正则只匹配 `<v/>`，当前 openpyxl 生成 `<v></v>`，替换次数为零；修正独立副本后真实读取/公式元数据/第 23 行值全部正确。 |
| 代理节点必填字段元数据确实缺失 | 1 | 后端批准集合 216，实际元数据 213，缺 3 个代理节点；见下一节。 |
| 成功 worker 的退出等待超时 | 1 | project/proxy_change_location 在 `project_workflow_worker.py:186` 等进程退出超过测试配置的 0.5 秒，抛 TimeoutError；单项独立重跑 1 passed / 2.39 秒。生产默认 3 秒，当前不能据此断定生产必现，根因仍待确认。 |

针对 Android 四种历史起点，还只读检查了失败后留下的真实测试数据库：run hash、artifact、相关 Android device 都保留，integrity 为 ok、无 FK 违规，见 `backend/legacy-migration-postcheck.json`。这不替代其余 43 项被过期断言提前截断的后续验证。

针对凭据事件，保存了本轮真实 worker 写入 SQLite 的脱敏事实，见 `backend/credential-failure-events.json`。Excel 夹具原因与有效副本核验见 `backend/excel-fixture-postcheck.json`。原始失败结果不因诊断或单项重跑通过而改写为全量通过。

## 已确认缺口

### 0. 新增代理节点未接入必填字段元数据（高置信）

`APPROVED_NODE_TYPES` 当前有 216 项，已含 `proxy_query`、`proxy_change_ip`、`proxy_change_location`，实际 `/api/system/module-required-fields` 仍为 213 项，缺这三项。`test_real_required_fields_route_preserves_frozen_rules_and_approved_scope` 已在全量和单独运行中失败。前端 `ConfigPanel.tsx:1545` 对不在 `coveredModules` 的节点显示“此节点尚未提供必填字段规则，请核对配置”。这是新功能接入不完整，不只是测试里旧数量常量的问题。后端执行器是否已经独立验证其参数，需结合代理功能审计判断；本结论不声称后端可以因此绕过校验。

另有两类已单独复现的旧测试断言未更新：四个 `StudioBrowserStatus` 精确字典比较未包含新增的 phase/projectId/sessionId/profileId/pickerSessionId；proxy runtime 测试要求所有 OpenAPI schema 均无 `password`，与新的 `WebDavConfig` 输入字段冲突。WebDAV 实现读取配置时回空 password，实际密码使用 CredentialStore；这个失败本身不能证明密码泄漏。证据见 `backend/repro-studio-contracts.log` 和 `backend/repro-proxy-runtime.log`。

### 1. ORM 与真实迁移后的数据库不同步（高置信）

`project_run_models.py:123` 仍声明 cursor 的唯一键为 `(task_id, lease_id)`，但 `pm10_shared_sheet_cursors.py:15` 已迁移为 `(task_id, record_ref)`。`command.check` 在全新临时数据库上明确提出删除当前约束、重新添加旧约束。这是可复现的架构维护缺陷：后续自动生成迁移可能误回滚约束，使用 ORM `create_all` 的测试也可能验证不同结构。当前测试没有证明真实生产数据库发生写入失败，因此不把它夸大为已发生的数据损坏。

此外，Alembic `env.py` 未完整注册 proxy ORM 表，并存在纯迁移维护的历史表、缺少对应 ORM 字段的 `project_sheets_bindings.identity_verification`、未映射索引、约束命名及 `studio_credentials.description` 类型差异。部分对象可能有意仅通过 SQL 管理，但当前缺少显式排除，导致统一元数据校验无法成为可靠门禁。检查同时报告 `project_data_generations` 与 `project_data_tables` 的循环外键排序警告。

### 2. 声明的 strict 类型门槛实际上未执行（高置信）

`docs/architecture/README.md:271` 要求 mypy strict；`.github/workflows/ci.yml:104` 只运行 `mypy src`，`apps/backend/pyproject.toml` 没有启用 strict。实际普通检查通过，但日志提醒未标注函数体默认不检查；严格检查出现 1041 个错误。错误主要反映类型覆盖缺口，不等于 1041 个运行时故障。

### 3. 当前 lint 门禁不通过（高置信）

137 个问题包括 I001 112、RUF100 17、S110 4、DTZ005 2、UP035 1、RUF007 1。多数是导入排列或旧 noqa；S110 包含被吞掉的 IMAP 异常，DTZ005 涉及没有时区的时间戳。此次只记录，不自动修复或把每条 lint 都当安全漏洞。

### 4. 集成命名不能证明真实端到端覆盖（高置信）

148 个 integration 测试文件中，42 个包含 `monkeypatch`、11 个包含 `Fake`、16 个包含 `TestClient`；这些只是文本统计，不能直接算成不真实测试，修改环境变量或观察器并不等于替换执行器。相反，真实 worker、SQLite、临时文件或本地 TCP 服务即便输入是夹具，也确实执行了相应基础设施。

1054 项 differential 回归的通过证明其断言覆盖的行为与冻结来源相符；它们不能替代独立业务需求验收，也不能证明上游行为本身没有缺陷。

例如 `tests/contract/conftest.py` 明确替换 kernel、license、operations；`test_proxy_runtime.py` 自称 synthetic 并使用内存凭据与 SyntheticProvider。`test_b6_text_to_speech_worker.py` 手工回送 tts_result，只能证明 worker 协议；`test_b6_printer_worker.py` 检验空路径拒绝，不能证明打印机成功输出；gesture worker 测试检验不存在手势的错误，不能证明摄像头识别。

真实 Cloak 测试由 `AUTOFLOW_TEST_CLOAKBROWSER` / `AUTOFLOW_B1_CLOAK_EXECUTABLE` 开关控制，真实计费模型测试由 `AUTOFLOW_LIVE_MODEL_TEST=1` 控制。当前 CI 的 pytest 步骤没有设置这些开关，所以默认绿灯不代表这些路径通过。本轮默认回归显式移除这些开关，随后从 JUnit 的实际跳过原因选择全部 42 个 Cloak 用例补跑：15 项由 B1 开关触发、27 项由 TEST 开关触发；没有凭文件名猜测覆盖范围。

补跑使用公开内核 `chromium-145.0.7632.109.2/Chromium.app/Contents/MacOS/Chromium`，两环境变量均设置为该本机已安装可执行文件；`CLOAKBROWSER_CACHE_DIR` 和 pytest basetemp 均属于新临时目录，每个 browser context/profile 独立。覆盖网页动作、iframe/选择器、网络监听、录制、文件产物、环境保存恢复、项目批次成功/停止/超时/失败等。实际运行的仍是仓库合成 HTML、登录站点和受控数据，有些外围 provider 依然替换为 Fake；这是**真实浏览器加夹具的集成测试**，不冒充用户要求的真实业务数据端到端验收。真实公网和真实仓库输入的执行证据由同次审计的 runtime 报告单独提供。

### 5. 环境恢复 QA 脚本报告成功后无法退出（高置信）

真实浏览器补跑中，`test_environment_real_browser_chain.py` 调用的 `scripts/qa-pm5-browser-chain.py` 已完成登录、End 保存、环境恢复、二次保存及第三次读取，并写出 `passed=true`。但其子进程持续不退出。系统采样明确停在 `Py_FinalizeEx -> wait_for_thread_shutdown`，见 `backend/browser-chain-hang-sample.txt`。

代码在 `scripts/qa-pm5-browser-chain.py:221` 手动调用 `TestClient.__enter__()`，`finally` 只关闭本地站点，未调用 `__exit__()`。本次另建临时 workspace，仅给内存中的脚本加上该关闭调用，同样的真实浏览器完整链在 9.574 秒内正常退出 0。原脚本与业务源码完全未改；诊断变体不替换原用例结果。可复跑探针为 `backend/probe_browser_chain_cleanup.py`，命令及结果为 `backend/browser-chain-cleanup-probe-run.json`。

这说明原 QA 的业务 JSON 成功并不代表生命周期验收成功。该问题属于 QA harness 资源清理，不构成浏览器登录状态未保存的证据。原用例保留其 600 秒超时设置执行，最终在 600.031 秒以 `subprocess.TimeoutExpired` 失败；完整证据为 `backend/browser-pytest.xml`。父测试自然回收其超时子进程，本次没有手动提前终止该测试。

### 6. 原生浏览器持久化用例的关停回调调用错误（高置信）

另一项真实浏览器失败是 `test_workflow_real_cloakbrowser.py::test_real_cloakbrowser_persisted_dispatch_and_service_recreation`。原测试首次执行的 run 已成功，参数快照、输出值、事件连续序列、终态及 dispatcher 无阻塞等断言均通过；随后第 185 行的 `await app.router.on_shutdown[-1]()` 选中同步 `LayaRuntime.close`，触发 `TypeError: object NoneType can't be used in 'await' expression`。正常的完整应用关停由多个回调共同完成，不能假设最后一个回调是异步主关停函数。这与默认回归的 `test_sidecar_shutdown.py` 失败属于同一测试维护问题。

原样独立重跑仍为 1 failed / 12.33 秒，见 `backend/repro-service-recreation.log`。原失败发生在进入服务重建阶段之前，所以不能从原测试声称服务重建成功。为区分测试、环境和产品故障，另用新临时目录执行原测试的内存变体，仅把两处手动关停改为按注册顺序执行所有回调，并等待可 await 的结果。真实浏览器执行和 SQLite 持久化仍使用生产实现，原来的全部断言（含服务重建后 run 相等、worker 非 busy）通过，完整子进程 12.978 秒退出 0，见 `backend/service-recreation-cleanup-probe-run.json` 和 `backend/service-recreation-cleanup-probe.log`。

可复跑探针为 `backend/probe_service_recreation_cleanup.py`；原测试与业务源码未改，诊断通过不覆盖原始失败。探针第一次误用了当前 FastAPI 已不存在的公共 `router.shutdown()`，相应失败单列保存在 `backend/initial-service-recreation-cleanup-probe*`；校正后按实际注册回调语义运行。以上证据将本项定性为 **QA 生命周期调用错误**，没有观察到持久化产品故障或环境不兼容。

## 执行命令与隔离

工作目录均为仓库根目录。使用现有锁定环境，`--frozen --no-sync` 防止在回归过程中安装或改动依赖。pytest 的 `--basetemp` 为此次通过 `tempfile.mkdtemp` 创建的专属目录；完整路径、起止时间和退出码保存在 `backend/pytest-run.json`。模型计费和浏览器实跑开关不在此默认回归中启用。

```sh
uv run --frozen --no-sync --directory apps/backend pytest --collect-only -q
uv run --frozen --no-sync --directory apps/backend pytest -q -ra --durations=30 --junitxml=<本报告目录>/backend/pytest.xml --basetemp=<此次新建临时目录>
uv run --frozen --no-sync --directory apps/backend ruff check .
uv run --frozen --no-sync --directory apps/backend mypy src
uv run --frozen --no-sync --directory apps/backend mypy --strict src
uv sync --directory apps/backend --check --locked --group build --offline
apps/backend/.venv/bin/python docs/qa/2026-09-28-system-audit/backend/verify_migration_metadata.py
```

另执行不含 `--group build` 的依赖只读检查时，uv 只提示需移除四个已经存在的构建包（PyInstaller 及依赖）；加入项目声明的 build 组后检查通过。没有执行安装、卸载或同步。

原生浏览器补跑的完整 42 个节点命令、环境路径、起止时间、退出码、数据来源保存在 `backend/browser-run.json`。独立失败复跑及两个生命周期诊断均另外保存命令和结果，不与全量计数混算。收尾按本轮 basetemp、内核副本路径及其子进程检查浏览器/worker 残留，结果为 `backend/owned-process-cleanup-check.json`；原始测试数据库保留以便复核。

## 尚未验证

本报告不提供 Windows、macOS Intel、安装器签名/公证、真实外部收费模型、真实 Google Sheets 写入、真实邮件发送、真实 Telegram 消息、物理打印、摄像头/麦克风或长时间 soak 的通过结论。本次全量回归和全部 42 项 CloakBrowser 补跑已结束；失败、跳过、警告、耗时及诊断证据均已记录。真实外部依赖、长时间运行与跨平台验收仍须单独补齐，不能用本轮夹具集成通过代替。
