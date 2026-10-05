# 安卓 S1：AI 测试工具 + 外接设备 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在安卓模块中提供基于 Google ARTEMIS 的 AI 测试工具，可对托管设备与 adb 可见的外接设备运行自然语言测试，并保存可回看的证据。

**Architecture:** ARTEMIS 运行在 AutoFlow 管理的独立 Python 3.12 环境（uv 创建），后端（3.11）只通过随包发布的 `artemis_bridge.py` 子进程调用，双方以 JSON 行协议通信。托管设备复用现有设备占用（`claim`/`connect`/`cleanup`），新增控制状态 `ai_test`；外接设备只用进程内序列号锁。运行记录落新表，前端在设备工作台加"AI 测试"标签，并新增外接设备列表。

**Tech Stack:** FastAPI、SQLAlchemy + Alembic、asyncio 子进程、psutil（已有依赖）、uv（用户机器上的外部前置条件）、React + TanStack Query、vitest、pytest。

**Spec:** [docs/superpowers/specs/2026-10-04-android-module-audit-and-ai-testing-design.md](../specs/2026-10-04-android-module-audit-and-ai-testing-design.md)（§6 为本计划范围）

## Global Constraints

- 后端 Python 保持 `>=3.11,<3.12`；ARTEMIS 不进入后端依赖，只装在 `android_runtime_root()/tools/artemis/`。
- ARTEMIS 固定到 T0 选定的提交哈希，写在 `providers/android/artemis_tool.py` 常量 `ARTEMIS_COMMIT`。
- 不运行 ARTEMIS 的 `start.sh`/`start.bat`，不启用其 Web 控制台和 MCP。
- 子进程环境必须含 `ARTEMIS_HELPER_AUTO_INSTALL=false`。
- 输入边界：`max_steps` 1–200，`timeout_seconds` 30–3600，`instruction` 1–4000 字符（去首尾空白后）。
- 模式只有 `flash`（界面"快速"，约 3–5 秒/步）与 `pro`（界面"深度"，约 15–40 秒/步）。
- 运行状态：`queued`、`running`、`succeeded`、`failed`、`cancelled`、`needs_verification`。
- 失败信息透传 stderr 末尾 50 行，写入前去除模型密钥（AGENTS 规则 2）。
- 数据库访问在事件循环外执行（`asyncio.to_thread`，规则 3）。
- 界面上每个配置项都有后端读取和测试（规则 1，`node scripts/ratchets.mjs`）。
- 界面文案不出现内部术语：generation、owner、trace、requestId、ai_test 等；"needs_verification" 显示为"结果待核实：程序中断，无法确定测试是否完成"。
- 前端只用共享控件（`shared/components`、`shared/components/ui`）和语义令牌，不向 `android.css` 新增规则。
- 迁移文件名与 revision 使用 `rm<N>_android_ai_tests`，`N` 与 `down_revision` 取实施时 `alembic heads` 的唯一 head 所在里程碑。
- 提交作者沿用仓库现有身份；提交信息结尾加 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`。

## Review Focus

1. 运行中途用户在看板点"删除/停止设备"：设备必须被策略拦截并显示"AI 测试进行中，请先停止测试"（Task 6）。
2. 同一外接设备连续点两次运行：第二次立即被拒绝，而不是两个 ARTEMIS 抢同一台设备（Task 7）。
3. 桥接进程输出了非 JSON 行或半行（崩溃时常见）：忽略坏行、不让整次运行变成 500（Task 3）。
4. 子进程拉起的孙进程（adb、scrcpy、ffmpeg）在停止/超时后残留：必须整棵进程树结束（Task 3）。
5. 产物下载接口收到 `../` 或绝对路径：必须拒绝（Task 8）。

---

## File Structure

| 文件 | 职责 |
| --- | --- |
| `apps/backend/src/autoflow/domain/android/ai_test.py`（新） | 运行状态机、输入校验、失败文本清洗 |
| `apps/backend/src/autoflow/infrastructure/database/android_ai_tests.py`（新） | ORM 行与仓储 |
| `apps/backend/src/autoflow/infrastructure/database/migrations/versions/rm<N>_android_ai_tests.py`（新） | 建表 |
| `apps/backend/src/autoflow/providers/android/artemis_bridge.py`（新） | 在 ARTEMIS 环境内运行的桥接脚本，唯一接触 ARTEMIS API |
| `apps/backend/src/autoflow/providers/android/artemis_tool.py`（新） | 工具安装、子进程运行、协议解析、进程树结束 |
| `apps/backend/src/autoflow/providers/android/external_devices.py`（新） | `adb devices -l` 解析 |
| `apps/backend/src/autoflow/application/android/ai_tests.py`（新） | 用例编排 |
| `apps/backend/src/autoflow/adapters/http/android_ai_tests.py`（新） | 路由与 schema |
| `domain/android/management_models.py`、`management_rules.py`、`infrastructure/database/android.py`、`application/android/devices.py`、`application/android/console.py`、`adapters/http/android_management.py`（改） | `ai_test` 控制状态 |
| `apps/backend/src/autoflow/bootstrap/app.py`（改） | 组装与路由注册 |
| `apps/desktop/src/renderer/domains/android/ai-test-api.ts`（新） | 前端 API |
| `apps/desktop/src/renderer/domains/android/components/AiTestPanel.tsx`（新） | AI 测试面板 |
| `apps/desktop/src/renderer/domains/android/components/ExternalDevices.tsx`（新） | 外接设备列表 |
| `DeviceConsole.tsx`、`AndroidPage.tsx`（改） | 标签与入口 |
| `.ai/knowledge/2026-10-04-artemis-interface.md`（新） | T0 结论 |

## JSON 行协议（本计划固定，桥接脚本与 `artemis_tool.py` 共同遵守）

桥接调用：`<venv-python> artemis_bridge.py run --serial <S> --mode <flash|pro> --max-steps <N> --artifacts <DIR>`，指令经 **stdin** 传入（UTF-8，读到 EOF）。辅助组件：`artemis_bridge.py helper-status --serial <S>` / `helper-install --serial <S>`。

模型配置经环境变量：`AUTOFLOW_MODEL_PROVIDER_KIND`、`AUTOFLOW_MODEL_BASE_URL`（可空）、`AUTOFLOW_MODEL_KEY`、`AUTOFLOW_MODEL_SECRET`，由桥接脚本映射到 ARTEMIS 的配置方式。

stdout 每行一个 JSON 对象：

```json
{"type": "step", "index": 1, "summary": "打开设置", "screenshot": "step-001.png"}
{"type": "result", "succeeded": true, "error": null, "traceId": "abc", "artifacts": ["report.html", "logcat.txt"]}
{"type": "helper", "installed": true}
```

`screenshot` 与 `artifacts` 为相对 `--artifacts` 目录的文件名。退出码 0 = 已输出 `result`/`helper`；非 0 = 失败，原因在 stderr。

---

### Task 0: ARTEMIS 接口核实（spike）

**Files:**
- Create: `.ai/knowledge/2026-10-04-artemis-interface.md`

**Interfaces:**
- Produces: `ARTEMIS_COMMIT` 取值；以下问题的答案（写入知识文档），供 Task 4 使用：
  1. `artemis-client` 的运行入口、`device_serial` 参数、是否有逐步回调/流式事件；
  2. 模型提供方与密钥的配置方式（环境变量名或构造参数），与 AutoFlow `provider_kind` 的对应关系（至少 OpenAI 兼容、Gemini、Anthropic）；
  3. 取消运行的方式（API 或仅能结束进程）；
  4. 辅助组件的检测与安装命令；UIAutomator2 后备是否在未装辅助组件时可用；
  5. 截图、logcat、报告在磁盘上的位置与文件名；
  6. 是否需要 scrcpy/FFmpeg 在 PATH 上，以及能否指定 adb 路径。

- [ ] **Step 1:** 克隆 `https://github.com/google/artemis` 到 scratchpad，记录 `git rev-parse HEAD` 作为候选 `ARTEMIS_COMMIT`；确认 LICENSE 为 Apache-2.0。
- [ ] **Step 2:** 只读源码回答问题 1–6，每个答案附文件路径与行号。
- [ ] **Step 3:** 在 scratchpad 中 `uv venv --python 3.12` + 安装该提交，对一台测试设备（外接 AVD 或自建 ReDroid）跑一次 `uv run artemis run "打开设置"`，记录产物目录结构。无设备时把实测项标为 `blocked`，只交付源码结论。
- [ ] **Step 4:** 写知识文档（日期、来源、状态 confirmed/blocked）；若问题 1 无逐步回调，注明 Task 4 采用"结束后从轨迹文件补出 step 行"的降级（规格 §6.7）。
- [ ] **Step 5:** 提交 `docs(android): ARTEMIS 接口核实`。

### Task 1: 领域规则

**Files:**
- Create: `apps/backend/src/autoflow/domain/android/ai_test.py`
- Test: `apps/backend/tests/unit/test_android_ai_test_rules.py`

**Interfaces:**
- Produces:
  - `AiTestState = Literal["queued","running","succeeded","failed","cancelled","needs_verification"]`
  - `AiTestMode = Literal["flash","pro"]`
  - `@dataclass(frozen=True) AiTestRequest(instruction: str, mode: AiTestMode, model_id: str, max_steps: int, timeout_seconds: int)`
  - `validate_request(raw: dict[str, Any]) -> AiTestRequest`（失败抛 `AndroidError(code, message, 422)`，code：`AI_TEST_INSTRUCTION_INVALID`、`AI_TEST_STEPS_INVALID`、`AI_TEST_TIMEOUT_INVALID`、`AI_TEST_MODE_INVALID`）
  - `transition(current: AiTestState, target: AiTestState) -> AiTestState`（非法迁移抛 `AndroidError("AI_TEST_STATE_CONFLICT", ..., 409)`）
  - `TERMINAL_STATES: frozenset[AiTestState]`
  - `redact(text: str, secrets: Iterable[str], max_lines: int = 50) -> str`（取末尾 `max_lines` 行，把每个非空 secret 替换为 `***`）

- [ ] **Step 1: 写失败测试**

```python
def test_instruction_trimmed_and_bounded():
    assert validate_request(ok(instruction="  打开设置  ")).instruction == "打开设置"
    with pytest.raises(AndroidError, match="AI_TEST_INSTRUCTION_INVALID"): validate_request(ok(instruction="   "))
    with pytest.raises(AndroidError): validate_request(ok(instruction="a" * 4001))

@pytest.mark.parametrize("steps,valid", [(0, False), (1, True), (200, True), (201, False)])
def test_max_steps_bounds(steps, valid): ...

@pytest.mark.parametrize("seconds,valid", [(29, False), (30, True), (3600, True), (3601, False)])
def test_timeout_bounds(seconds, valid): ...

def test_transitions():
    assert transition("queued", "running") == "running"
    assert transition("running", "needs_verification") == "needs_verification"
    for terminal in TERMINAL_STATES:
        with pytest.raises(AndroidError, match="AI_TEST_STATE_CONFLICT"): transition(terminal, "running")

def test_redact_tail_and_secret():
    text = "\n".join(f"line{i}" for i in range(60)) + "\nkey=sk-123"
    out = redact(text, ["sk-123", ""])
    assert "sk-123" not in out and "***" in out and "line0" not in out and len(out.splitlines()) == 50
```

允许的迁移：`queued→running|cancelled|failed`，`running→succeeded|failed|cancelled|needs_verification`；其他全部非法。

- [ ] **Step 2:** `cd apps/backend && uv run pytest tests/unit/test_android_ai_test_rules.py -q` → FAIL（模块不存在）。
- [ ] **Step 3:** 实现上述接口。
- [ ] **Step 4:** 同命令 → PASS。
- [ ] **Step 5:** 提交 `feat(android): AI 测试运行的领域规则`。

### Task 2: 持久化

**Files:**
- Create: `apps/backend/src/autoflow/infrastructure/database/android_ai_tests.py`
- Create: `apps/backend/src/autoflow/infrastructure/database/migrations/versions/rm<N>_android_ai_tests.py`
- Modify: `apps/backend/src/autoflow/infrastructure/database/migrations/env.py`（若需导入新模型以被 autogenerate/检查识别，按现有 android 模型的导入方式）
- Test: `apps/backend/tests/integration/test_android_ai_tests_repository.py`；迁移由现有 `tests/migration` 检查覆盖

**Interfaces:**
- Produces:
  - `AndroidAiTestRow`（表 `android_ai_test_runs`）：`id` str36 PK；`request_id` str128 UNIQUE；`device_kind` str16；`device_id` str36 可空；`serial` str128 可空；`state` str32；`created_at`/`started_at`/`finished_at` DateTime(tz)；`payload` JSON。索引 `ix_android_ai_test_runs_device_created(device_kind, device_id, serial, created_at)`。
  - `payload` 键：`instruction`、`mode`、`modelId`、`modelKey`、`maxSteps`、`timeoutSeconds`、`steps`（列表，最多保留最近 200 个）、`artifactsDir`、`artifacts`、`traceId`、`succeeded`、`errorCode`、`errorMessage`、`toolVersion`。
  - `class AiTestRepository(sessions: sessionmaker[Session])`，全部同步方法（应用层用 `asyncio.to_thread` 调用）：
    - `create(run: dict[str, Any]) -> dict[str, Any]`（`request_id` 冲突时返回已有记录，且仅当请求摘要相同；不同则抛 `AndroidError("ANDROID_REQUEST_CONFLICT", ..., 409)`）
    - `get(run_id: str) -> dict[str, Any]`（不存在 404 `AI_TEST_NOT_FOUND`）
    - `update(run_id: str, **changes: Any) -> dict[str, Any]`
    - `append_step(run_id: str, step: dict[str, Any]) -> None`
    - `list(device_kind: str, device_id: str | None, serial: str | None, cursor: str | None, limit: int = 20) -> tuple[list[dict[str, Any]], str | None]`（按 `created_at` 倒序）
    - `active_for(device_kind: str, device_id: str | None, serial: str | None) -> dict[str, Any] | None`（状态 queued/running）
    - `unfinished() -> list[dict[str, Any]]`
    - `delete(run_id: str) -> dict[str, Any]`
  - 记录对外字典形状（camelCase）：`id, requestId, deviceKind, deviceId, serial, state, createdAt, startedAt, finishedAt` + payload 各键。

- [ ] **Step 1:** 写失败测试：建临时 SQLite（沿用 `tests/integration` 现有 android 仓储测试的 fixture 方式），断言 create 幂等/冲突、`append_step` 超过 200 条只保留最后 200 条、`list` 倒序分页、`active_for` 只返回进行中、`unfinished` 返回 queued/running。
- [ ] **Step 2:** `uv run pytest tests/integration/test_android_ai_tests_repository.py -q` → FAIL。
- [ ] **Step 3:** 实现行、仓储、迁移（`upgrade` 建表与索引，`downgrade` 删表）。
- [ ] **Step 4:** 同命令 PASS；`uv run pytest tests/migration -q` PASS（单一 head）。
- [ ] **Step 5:** 提交 `feat(android): AI 测试运行记录表`。

### Task 3: 工具提供者（安装、运行、协议、进程树）

**Files:**
- Create: `apps/backend/src/autoflow/providers/android/artemis_tool.py`
- Test: `apps/backend/tests/unit/test_android_artemis_tool.py`（使用 `tests/fixtures/fake_artemis_bridge.py`，新建）

**Interfaces:**
- Consumes: `android_runtime_root()`；Task 1 `redact`。
- Produces:
  - `ARTEMIS_COMMIT: str`（Task 0 值）
  - `@dataclass(frozen=True) ToolStatus(state: Literal["missing_prerequisite","not_installed","installing","ready","failed"], version: str | None, message: str | None)`
  - `@dataclass(frozen=True) ModelEnv(provider_kind: str, base_url: str | None, model_key: str, secret: str = field(repr=False))`
  - `class ArtemisTool(root: Path, bridge: Path = <artemis_bridge.py 路径>, uv: str | None = None)`：
    - `status() -> ToolStatus`（`uv` 由参数、`AUTOFLOW_UV_PATH`、`shutil.which("uv")` 依次解析；找不到为 `missing_prerequisite`，message"需要先安装 uv（Python 工具管理器）"；环境目录存在且记录的提交等于 `ARTEMIS_COMMIT` 为 `ready`）
    - `async install(on_output: Callable[[str], None]) -> ToolStatus`（`uv venv --python 3.12 <root>/tools/artemis/.venv`，再 `uv pip install "git+https://github.com/google/artemis@<ARTEMIS_COMMIT>"`；成功后写 `<root>/tools/artemis/installed.json` `{"commit": ...}`；失败抛 `AndroidError("AI_TOOL_INSTALL_FAILED", redact(output), 502)`）
    - `async run(*, serial: str, instruction: str, mode: str, max_steps: int, timeout_seconds: int, artifacts: Path, model: ModelEnv, on_event: Callable[[dict[str, Any]], Awaitable[None]], cancel: asyncio.Event) -> dict[str, Any]`：返回 `result` 事件；超时抛 `AndroidError("AI_TEST_TIMEOUT", ...)`；`cancel` 置位抛 `AndroidError("AI_TEST_CANCELLED", ...)`；非 0 退出或无 `result` 抛 `AndroidError("AI_TEST_PROCESS_FAILED", redact(stderr, [model.secret]))`
    - `async helper(serial: str, *, install: bool) -> bool`
  - 子进程环境：继承 `os.environ`，加 `ARTEMIS_HELPER_AUTO_INSTALL=false`、`AUTOFLOW_MODEL_*`、`PYTHONIOENCODING=utf-8`，PATH 前置 AutoFlow 自带 adb 所在目录（沿用 `shutil.which("adb")` 的结果目录）。
  - 进程树结束：`psutil.Process(pid).children(recursive=True)` 全部 `kill()` 后结束父进程；POSIX 用 `start_new_session=True` 启动。

- [ ] **Step 1: 写失败测试**（假桥接脚本按环境变量 `FAKE_MODE` 选择行为：`ok`、`garbage`、`crash`、`hang`、`child`）

```python
async def test_run_streams_steps_and_returns_result(tool, tmp_path):
    events = []
    result = await tool.run(**args(tmp_path), on_event=collect(events), cancel=asyncio.Event())
    assert [e["type"] for e in events] == ["step", "step"] and result["succeeded"] is True

async def test_garbage_lines_ignored(tool, tmp_path):  # FAKE_MODE=garbage: 非 JSON 与半行混在正常行之间
    result = await tool.run(...); assert result["succeeded"] is True

async def test_crash_reports_redacted_stderr(tool, tmp_path):  # stderr 含 secret
    with pytest.raises(AndroidError) as err: await tool.run(...)
    assert err.value.code == "AI_TEST_PROCESS_FAILED" and SECRET not in err.value.message

async def test_timeout_kills_process_tree(tool, tmp_path):  # FAKE_MODE=child: 父进程再拉起一个 sleep 子进程并写出其 pid
    with pytest.raises(AndroidError, match="AI_TEST_TIMEOUT"): await tool.run(..., timeout_seconds=1)
    assert not psutil.pid_exists(child_pid_from_file(tmp_path))

async def test_cancel_kills_and_raises(tool, tmp_path): ...

def test_env_contains_flags_and_secret_only_in_env(tool, tmp_path):
    # 假桥接把收到的环境变量写到文件；断言 ARTEMIS_HELPER_AUTO_INSTALL=false、AUTOFLOW_MODEL_SECRET 存在，
    # 且 secret 不出现在 argv（桥接写出的 sys.argv）中

def test_status_missing_uv(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: None); monkeypatch.delenv("AUTOFLOW_UV_PATH", raising=False)
    assert ArtemisTool(tmp_path).status().state == "missing_prerequisite"
```

测试为 `run` 注入可执行：`ArtemisTool` 增加仅测试用参数 `python: str | None`（默认指向 venv 的 python），测试传 `sys.executable`、`bridge` 传假脚本。`timeout_seconds` 的 30 秒下限只在领域层校验，提供者不重复校验。

- [ ] **Step 2:** `uv run pytest tests/unit/test_android_artemis_tool.py -q` → FAIL。
- [ ] **Step 3:** 实现。逐行读取 stdout，`json.loads` 失败或缺 `type` 的行跳过；stderr 并行读取保留最后 50 行。
- [ ] **Step 4:** 同命令 PASS（Windows 与 Mac 本机各跑一次进程树用例）。
- [ ] **Step 5:** 提交 `feat(android): ARTEMIS 工具提供者与 JSON 行协议`。

### Task 4: 桥接脚本

**Files:**
- Create: `apps/backend/src/autoflow/providers/android/artemis_bridge.py`
- Modify: 后端打包脚本 `scripts/build-backend.mjs` 或其 spec（确保该文件作为数据文件随包发布，按现有打包对非 Python 资源的处理方式）
- Test: `apps/backend/tests/unit/test_android_artemis_bridge.py`

**Interfaces:**
- Consumes: Task 0 结论；上文 JSON 行协议。
- Produces: 命令 `run`、`helper-status`、`helper-install`，行为与协议一致。脚本只用 3.11 也可解析的语法（测试在后端 3.11 环境 import 它）；对 ARTEMIS 的 import 放在函数内部。

- [ ] **Step 1:** 写失败测试：向 `sys.modules` 注入假的 ARTEMIS 客户端模块（模拟 Task 0 确认的 API：成功两步、失败、抛异常），调用 `artemis_bridge.main([...])`，捕获 stdout，断言输出的 step/result 行符合协议、`screenshot` 为相对文件名、模型环境变量被映射到 Task 0 记录的 ARTEMIS 配置位置、异常时退出码非 0 且 stderr 含异常信息。
- [ ] **Step 2:** `uv run pytest tests/unit/test_android_artemis_bridge.py -q` → FAIL。
- [ ] **Step 3:** 实现；无逐步回调时按 Task 0 的降级从轨迹补出 step 行。
- [ ] **Step 4:** 同命令 PASS；`npm run backend:build` 后确认产物中包含 `artemis_bridge.py`。
- [ ] **Step 5:** 提交 `feat(android): ARTEMIS 桥接脚本`。

### Task 5: 外接设备发现

**Files:**
- Create: `apps/backend/src/autoflow/providers/android/external_devices.py`
- Test: `apps/backend/tests/unit/test_android_external_devices.py`

**Interfaces:**
- Produces:
  - `parse_adb_devices(output: str) -> list[dict[str, str | None]]`：每项 `{"serial", "state", "model", "product"}`；`state` 取 `device`/`offline`/`unauthorized` 原值。
  - `async list_external_devices(managed_serials: set[str], adb: str | None = None) -> list[dict[str, str | None]]`：运行 `adb devices -l`（超时 5 秒），排除 `managed_serials`；adb 不存在抛 `AndroidError("ANDROID_ADB_MISSING", "未找到 adb", 503)`。

- [ ] **Step 1:** 写失败测试：解析包含 `emulator-5554 device product:sdk_gphone64 model:sdk_gphone64_arm64`、`127.0.0.1:5556 device ...`、`R58M unauthorized`、空行与表头的样例；排除托管序列号 `127.0.0.1:5556`。
- [ ] **Step 2:** 运行 → FAIL。
- [ ] **Step 3:** 实现。
- [ ] **Step 4:** 运行 → PASS。
- [ ] **Step 5:** 提交 `feat(android): 外接设备发现`。

### Task 6: 托管设备的 `ai_test` 控制状态

**Files:**
- Modify: `apps/backend/src/autoflow/domain/android/management_models.py`（`OwnerKind` 加 `"aiTest"`；`ControlState` 加 `"ai_test"`）
- Modify: `apps/backend/src/autoflow/domain/android/management_rules.py`（`display_state`、`policy_for`）
- Modify: `apps/backend/src/autoflow/infrastructure/database/android.py:33`（`claim(device_id, run_id, control: str = "workflow")`）
- Modify: `apps/backend/src/autoflow/application/android/devices.py:81`（`claim(device_id, run_id, control: str = "workflow")` 透传）
- Modify: `apps/backend/src/autoflow/adapters/http/android_management.py:126`（`control == "ai_test"` → `owner_kind="aiTest"`）
- Modify: `apps/backend/src/autoflow/application/android/console.py:92`（创建会话前若设备 `control == "ai_test"` 抛 `AndroidError("ANDROID_AI_TEST_OWNS_DEVICE", "AI 测试正在使用设备，请先停止测试")`；新增 `connected_serials() -> set[str]`：返回未关闭会话的 `session["context"].runtime.serial` 非空值）
- Test: `tests/unit/test_android_management_state.py`、`tests/unit/test_android_console_lifecycle.py`、`tests/contract/test_android_management_devices.py`（追加用例）

**Interfaces:**
- Produces: `AndroidConsole.connected_serials() -> set[str]`；`policy_for(DeviceFacts(owner_kind="aiTest", control="ai_test", runtime_state="ready"))` → `ActionPolicy(("view_ai_test",), {a: "AI 测试进行中，请先停止测试" for a in ("start","stop","restart","delete","restore","open","backup")})`；`display_state` → `"AI 测试中"`。

- [ ] **Step 1:** 写失败测试：上述策略与显示；`connected_serials()` 只含未关闭会话；`repository.claim(..., control="ai_test")` 后 payload `control == "ai_test"`；控制台对 `ai_test` 设备创建会话返回 `ANDROID_AI_TEST_OWNS_DEVICE`；管理设备列表接口返回 `owner.kind == "aiTest"`。
- [ ] **Step 2:** 运行这三个测试文件 → 新用例 FAIL。
- [ ] **Step 3:** 实现。
- [ ] **Step 4:** `uv run pytest tests -q -k android` PASS（不回归已有安卓用例）。
- [ ] **Step 5:** 提交 `feat(android): 设备新增 AI 测试占用状态`。

### Task 7: 应用服务

**Files:**
- Create: `apps/backend/src/autoflow/application/android/ai_tests.py`
- Test: `apps/backend/tests/unit/test_android_ai_tests_service.py`

**Interfaces:**
- Consumes: Task 1–3、5、6；`AndroidDeviceService.context(device_id)`、`.claim(device_id, run_id, control="ai_test")`、`await .connect()`、`.runtime.serial`、`await .cleanup()`；`ModelService.execution_binding(model_id) -> ModelExecutionBinding(model_id, model_key, connection(provider_kind, base_url), secret)`；`AndroidConsole.connected_serials()`（托管设备的 adb 序列号不落库，只在连接期间存在，形如 `127.0.0.1:<随机端口>`）。
- Produces: `class AiTestService(repository: AiTestRepository, tool: ArtemisTool, devices: AndroidDeviceService, models: ModelService, console_serials: Callable[[], set[str]], artifacts_root: Path)`：
  - 托管序列号集合 = `console_serials()` ∪ 本服务正在运行的托管设备序列号；传给 `list_external_devices` 排除，并在外接路径 `start` 时再次校验，命中则抛 `AI_TEST_DEVICE_MANAGED` 409（"该设备由 AutoFlow 管理，请从设备工作台运行"）。
  - `async tool_status() -> ToolStatus`
  - `async install_tool(request_id: str) -> dict[str, Any]`（同一时间只允许一次安装；返回当前状态）
  - `async external_devices() -> list[dict[str, Any]]`
  - `async start(request: dict[str, Any]) -> dict[str, Any]`：`request` 含 `requestId`、`deviceKind`（`managed`/`external`）、`deviceId` 或 `serial`、Task 1 的字段。顺序：校验 → 工具 `ready`（否则 `AI_TOOL_NOT_READY` 409）→ 模型绑定（`ModelError` 原样转为 409/503 并保留消息）→ 设备检查（托管：`claim(control="ai_test")` 失败转 `ANDROID_BUSY` 原因；外接：序列号须在 `external_devices()` 且 `state=="device"`，并获取进程内锁，已被占用抛 `AI_TEST_DEVICE_BUSY` 409）→ 辅助组件已装（否则 `AI_TEST_HELPER_REQUIRED` 409，由界面引导安装）→ 落库 `queued` → 后台任务执行并立即返回 202 记录。
  - `async install_helper(device_kind: str, device_id: str | None, serial: str | None) -> bool`
  - `async cancel(run_id: str) -> dict[str, Any]`
  - `async recover() -> None`：启动时把 `unfinished()` 标为 `needs_verification`（`errorMessage`="程序中断，无法确定测试是否完成"），并把 `control == "ai_test"` 的托管设备复位为 `idle`、`ownerRunId=None`。
  - `async shutdown() -> None`：取消全部运行中任务并等待。
  - 后台任务：`running` → `tool.run(...)`（每个 step 事件 `append_step`）→ `succeeded`/`failed`（`result.succeeded`）；`AI_TEST_TIMEOUT`/`AI_TEST_PROCESS_FAILED` → `failed` 并记 `errorCode/errorMessage`；`AI_TEST_CANCELLED` → `cancelled`；`finally` 中托管设备 `await context.cleanup()`、外接设备释放锁。仓储调用全部 `await asyncio.to_thread(...)`。

- [ ] **Step 1:** 写失败测试（假 tool、假 devices、假 models、真实仓储或内存仓储）：
  - 成功路径：状态 queued→running→succeeded，步骤落库，结束后 `cleanup` 被调用一次；
  - tool 抛超时：`failed` + `AI_TEST_TIMEOUT`，`cleanup` 仍被调用；
  - 取消：`cancelled`；
  - 同一外接序列号第二次 `start` 抛 `AI_TEST_DEVICE_BUSY`，第一次结束后可再次运行；
  - 以外接方式提交托管设备正在使用的序列号抛 `AI_TEST_DEVICE_MANAGED`；
  - 工具未就绪、模型停用、辅助组件缺失分别得到对应错误码，且不留下 queued 记录、不占用设备；
  - `recover()` 把 running 改为 needs_verification 并复位 `ai_test` 设备；
  - 模型 secret 不出现在任何仓储写入的值中（遍历 payload 断言）。
- [ ] **Step 2:** 运行 → FAIL。
- [ ] **Step 3:** 实现。
- [ ] **Step 4:** 运行 → PASS。
- [ ] **Step 5:** 提交 `feat(android): AI 测试应用服务`。

### Task 8: HTTP 接口与组装

**Files:**
- Create: `apps/backend/src/autoflow/adapters/http/android_ai_tests.py`
- Modify: `apps/backend/src/autoflow/bootstrap/app.py`（构造 `ArtemisTool(android_runtime_root())`、`AiTestService(...)`，lifespan 中 `recover()`/`shutdown()`，注册路由，前缀 `/api/v1/android/ai-tests`，与现有安卓路由同一方式）
- Modify: `apps/desktop/src/renderer/shared/api/generated.ts`（`npm run openapi:generate`）
- Test: `apps/backend/tests/contract/test_android_ai_tests_api.py`

**Interfaces:**
- Consumes: Task 7 `AiTestService`。
- Produces（schema 名称供前端使用）：`AiToolStatusRead`、`AiTestRunCreate`、`AiTestRunRead`、`AiTestRunPageRead`、`ExternalDeviceRead`、`AiTestHelperInstall`。路由与规格 §6.5 一致：
  - `GET /tool`、`POST /tool/install`（body `{requestId}`）
  - `GET /external-devices`
  - `POST /runs`（202）、`GET /runs`（query `deviceKind`、`deviceId`、`serial`、`cursor`）、`GET /runs/{id}`、`POST /runs/{id}/cancel`、`DELETE /runs/{id}`（运行中拒绝 409 `AI_TEST_STATE_CONFLICT`；删除记录并删除运行目录）
  - `POST /helper`（body `AiTestHelperInstall{deviceKind, deviceId?, serial?}`）
  - `GET /runs/{id}/artifacts/{name}`：`name` 解析后必须位于该运行目录内（`resolve()` 后 `is_relative_to`），否则 404 `AI_TEST_ARTIFACT_NOT_FOUND`。
  - `AndroidError` 沿用 `adapters/http/errors.py` 的映射。

- [ ] **Step 1:** 写失败契约测试：各路由的状态码与 schema；产物名 `../x`、`/etc/passwd`、`..%2Fx` 均 404；删除运行中记录 409。
- [ ] **Step 2:** 运行 → FAIL。
- [ ] **Step 3:** 实现并组装；`npm run openapi:generate`。
- [ ] **Step 4:** 契约测试 PASS；`npm run openapi:check` 通过；`uv run pytest tests -q -k "android or openapi"` PASS。
- [ ] **Step 5:** 提交 `feat(android): AI 测试 HTTP 接口`。

### Task 9: 前端 AI 测试面板

**Files:**
- Create: `apps/desktop/src/renderer/domains/android/ai-test-api.ts`
- Create: `apps/desktop/src/renderer/domains/android/components/AiTestPanel.tsx`
- Modify: `apps/desktop/src/renderer/domains/android/components/DeviceConsole.tsx:373`（标签数组加 `'AI 测试'`，渲染 `AiTestPanel`，`target={{ deviceKind: 'managed', deviceId }}`）
- Test: `apps/desktop/src/renderer/domains/android/tests/AiTestPanel.test.tsx`

**Interfaces:**
- Consumes: Task 8 schema；`androidManagementApi` 的写法（`client.request` + `components['schemas']`）；模型列表沿用模型管理现有前端 API（实施时用其已有查询函数，不新建接口）。
- Produces: `aiTestApi(client)` 含 `tool`、`installTool`、`externalDevices`、`installHelper`、`start`、`runs`、`run`、`cancel`、`remove`、`artifactUrl`；`AiTestPanel({ api, target, onTakeOver? }: { api: AiTestApi; target: { deviceKind: 'managed' | 'external'; deviceId?: string; serial?: string }; onTakeOver?: () => void })`。

界面行为：
- 工具 `missing_prerequisite`/`not_installed`/`failed`：显示原因和"安装测试工具"按钮（`missing_prerequisite` 时按钮禁用并显示 message）；`installing` 显示进度状态。
- 表单：指令（多行，必填）、模式（快速/深度，附每步耗时说明）、模型（必选）、步数上限（默认 30）、超时秒数（默认 600）。客户端按 Global Constraints 的边界禁用提交，后端仍是最终校验。
- 运行中（每 2 秒轮询 `run`，页面隐藏时暂停，沿用现有隐藏页暂停做法）：步骤时间线（序号、摘要、缩略图）、"停止"；`onTakeOver` 存在时显示"停止并接管"（先 `cancel`，状态终止后调用 `onTakeOver`）。
- 错误码 `AI_TEST_HELPER_REQUIRED`：确认对话框"需要在该设备安装测试辅助组件"，确认后 `installHelper` 再重试同一请求（新 requestId）。
- 结果与历史：状态文案（通过/失败/已停止/结果待核实：程序中断，无法确定测试是否完成）、耗时、步数、模型、失败原因原文；产物链接；"用相同指令重跑"；删除需确认。

- [ ] **Step 1:** 写失败测试：工具未安装→安装按钮；边界外步数禁用提交；运行中显示步骤并可停止；`AI_TEST_HELPER_REQUIRED` 弹确认后调用 `installHelper` 再 `start`；`needs_verification` 文案；"停止并接管"在终止后才调用 `onTakeOver`；页面不出现 `requestId`/`trace`/`ai_test` 字样。
- [ ] **Step 2:** `npm --workspace @autoflow/desktop test -- AiTestPanel` → FAIL。
- [ ] **Step 3:** 实现，只用共享控件与语义令牌。
- [ ] **Step 4:** 测试 PASS；`npm run typecheck && npm run lint` 通过。
- [ ] **Step 5:** 提交 `feat(android): 设备工作台 AI 测试面板`。

### Task 10: 外接设备列表

**Files:**
- Create: `apps/desktop/src/renderer/domains/android/components/ExternalDevices.tsx`
- Modify: `apps/desktop/src/renderer/domains/android/pages/AndroidPage.tsx`（看板页头增加"外接设备"入口，页面状态加 `'external'`；选中设备后渲染 `AiTestPanel` 且不传 `onTakeOver`）
- Test: `apps/desktop/src/renderer/domains/android/tests/ExternalDevices.test.tsx`、`AndroidPage.test.tsx`（追加）

**Interfaces:**
- Consumes: Task 9 `aiTestApi.externalDevices`、`AiTestPanel`。
- Produces: `ExternalDevices({ api, onSelect }: { api: AiTestApi; onSelect: (serial: string) => void })`。

界面行为：列表显示型号、序列号、状态（可用/离线/未授权，未授权提示"请在设备上允许 USB 调试"）；只有"可用"可选；"刷新"；空态说明"启动模拟器或连接设备后点击刷新；由 AutoFlow 创建的设备不在此列出"；页头注明"外接设备可能同时被其他程序操作"。

- [ ] **Step 1:** 写失败测试：三种状态渲染与可选性、空态、选中后显示 AI 测试面板且无"停止并接管"。
- [ ] **Step 2:** 运行 → FAIL。
- [ ] **Step 3:** 实现。
- [ ] **Step 4:** 测试 PASS；typecheck、lint 通过。
- [ ] **Step 5:** 提交 `feat(android): 外接设备入口`。

### Task 11: 验收与记录

**Files:**
- Create: `docs/qa/android-ai-testing/2026-10-xx-s1-acceptance.md`（只放汇总与 CI 产物链接，截图不入库，规则 7）
- Modify: `.ai/memory/project-context.md`、`.ai/decisions/2026-10-04-android-testing-platform-and-artemis.md`（状态更新）、`docs/research/android-manager-2026-09-30/open-source-references.md`（加入 ARTEMIS 行）

- [ ] **Step 1:** 全量门禁：`cd apps/backend && uv run pytest -q`；根目录 `npm test`、`npm run typecheck`、`npm run lint`、`npm run openapi:check`、`npm run build`、`npm run test:structure`、`npm run test:scripts`、`node scripts/ratchets.mjs`。全部 exit 0（AC-S1-5）。
- [ ] **Step 2:** 密钥检查（AC-S1-4）：以测试密钥跑 Task 7 的成功与崩溃用例后，在数据库文件、运行目录、后端日志中 grep 该密钥，结果为空。
- [ ] **Step 3:** 真实设备验收（需用户单独授权）：AC-S1-1（Windows + 外接 AVD）、AC-S1-2（Mac + 托管 ReDroid）、AC-S1-3（停止、超时、强杀子进程、重启 AutoFlow）。指令："打开设置搜索 Wi-Fi，然后打开浏览器访问 example.com"。条件不足的项标 `blocked`，不得记为通过。
- [ ] **Step 4:** 更新 `.ai` 记录与 AOCI 条目（`aoci_maintain` → `aoci_update_entry`）。
- [ ] **Step 5:** 提交 `docs(android): S1 验收记录`。
