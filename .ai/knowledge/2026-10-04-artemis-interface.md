# ARTEMIS 接口核实（Android S1 Task 0）

- 日期：2026-10-05；状态：源码结论 confirmed；真机/模拟器实跑 blocked（本机 `adb devices` 无设备，未装 Android SDK/模拟器）
- 来源：https://github.com/google/artemis ，提交 `351ca8422f7b5b54e80a9c1ce03a222e02415b6b`（候选 `ARTEMIS_COMMIT`；浅克隆的 HEAD，未打 tag）。LICENSE 为 Apache-2.0（`LICENSE` 首部为 Apache License 2.0）。
- 验证方式：(a) 只读源码；(b) Python 3.12.10 venv 中按下文命令安装并运行 `artemis run --help`、`artemis run --standalone ...`（无设备，得到 `DeviceNotFoundError`）；(c) 对 `DataEngine` 做无设备探针：本地 TCP 监听 + `ARTEMIS_IPC_PORT`，调用 `start_session`/`record_step`，实测收到事件流与落盘文件。**没有任何一项经过真机 + 真实 LLM 的完整跑通。**
- 引用格式：`文件:行号`，路径均相对 ARTEMIS 仓库根。

## 0. 安装规格与包结构（confirmed，已实测）

- 要求 Python >=3.12（`pyproject.toml:24`）。依赖约 174 个包（含 opencv、scipy、langchain 全家、langgraph、fastapi、jupyter），体积大，必须放独立 venv。
- `artemis-client` 是同仓库的**独立包**：`packages/artemis-client`，import 名 `artemis_client`，零依赖，只是 HTTP 客户端，用来连 Artemis 守护进程（`packages/artemis-client/README.md`、`DESIGN.md`）。主包依赖它（`pyproject.toml:28`），来源是 uv workspace（`pyproject.toml:102,105`），`uv pip install` 不读 workspace，所以必须显式同时安装两者。
- **可用的安装命令（已验证，exit 0）**：先 `git clone https://github.com/google/artemis <dir>` 并 `git checkout <ARTEMIS_COMMIT>`，然后
  `uv venv --python 3.12 <venv>` →
  `uv pip install --python <venv>/Scripts/python.exe -e <dir>/packages/artemis-client -e <dir>`
  入口脚本 `<venv>/Scripts/artemis.exe`（`pyproject.toml` `[project.scripts] artemis = artemis.interfaces.cli.main:cli`）。
- **不要**用 `pip install git+https://github.com/google/artemis@<sha>`（非 editable 构建）：`setup.py:47,51` 在没有 `config/artemis.jsonc` 或已构建的 Showcase UI（`npm run build --prefix apps/showcase_ui`）时直接 `RuntimeError`；且无障碍辅助 APK 在仓库 `packages/artemis-accessibility-helper/`，`helper_manager.py:100` 按源码目录定位，不随 wheel 打包。editable 安装跳过资源拷贝（`setup.py` 的 `editable_mode` 分支）。结论：AutoFlow 需要把 ARTEMIS 固定提交的源码目录和 venv 一起管理（Task 4/安装器的事）。
- `artemis-client` 是否在 PyPI 上：未验证（本次安装全部使用本地路径）。
- 副作用提醒：`artemis run --help` 等命令会在 stdout 打印 `ℹ Activated local ADB server endpoint 127.0.0.1:5037` 之类横幅，桥接脚本不能把 ARTEMIS 的 stdout 当作干净的协议通道。

## 1. 运行入口、`device_serial`、逐步回调（confirmed：源码 + DataEngine 探针；真机 blocked）

**入口有三种**：

1. CLI `artemis run "<目标>"`（`artemis/interfaces/cli/commands/run.py`）。默认**经守护进程**排队（自动拉起 daemon，`run.py` 约 311–330 行区域的 `ensure_daemon_running`/`submit_task_to_daemon`）；加 `--standalone` 或环境变量 `ARTEMIS_STANDALONE=1`（`run.py:291,308`）则进程内直接跑（`asyncio.run(execute_task(...))`）。**桥接必须用 `--standalone`**，否则会起一个常驻 daemon + Web UI。
2. 守护进程 + `artemis-client`：`ArtemisClient(base_url, token=).submit(goal, profile=, device_serial=)` / `wait_for_task` / `run` / `stop`（`packages/artemis-client/src/artemis_client/client.py:175,271,348`）。走 `POST /api/run`、`GET /api/sessions/{id}`、`GET /api/status`、`POST /api/stop`（`apps/admin_console/routers/tasks.py:69,207`）。只有"轮询状态"，没有事件流；DESIGN.md 里规划的 `/api/v1/tasks/{id}/events` 尚未实现（仅为设计文档）。
3. Python SDK 进程内：`third_party/mobile_use/main.py:90 run_automation`、`artemis/sdk/agent.py` 的 `Agent(config=, device_serial=, session_id=)`，`await agent.init()` → `agent.new_task(goal)` → `agent.run_task(...)`。

**`device_serial`**：CLI `--device-serial/-s`（`run.py` 的 `device_serial` 选项）；缺省取 `settings.ADB_DEVICE_SERIAL` / 环境变量 `ADB_DEVICE_SERIAL`，再缺省 `device_pool.select_device()`（`run.py:137-151`，`config.for_device(DevicePlatform.ANDROID, serial)` 在 `run.py:151`）。SDK 侧为 `Agent(device_serial=...)`（`artemis/sdk/agent.py:85-115`）。

**CLI 常用参数（`artemis run --help` 实测）**：`--profile flash|pro`（默认 pro）、`--locked-app <包名>`、`--test-name/-n`、`--traces-path/-t`、`--output-description/-o`、`--with-video-recording-tools/--without-video-recording-tools`、`--app-path <apk>`、`--enable/disable-checker`、`--verification-level off|final|checkpoints|strict`、`--session-id <UUID>`、`--device-serial/-s`、`--standalone`。

**逐步回调/流式事件：没有"公开回调 API"，但有三条可用的逐步通道**：

- (A) **IPC 本地 TCP 事件流（推荐给桥接）**：`DataEngine._publish` 每次发布事件时，把 `{"event_type":..., "data":...}\n`（换行分隔 JSON）写到 `127.0.0.1:<ARTEMIS_IPC_PORT>`（`artemis/data_engine/engine.py:470,495`；端口读取 `artemis/config/runtime.py:41`，环境变量优先）。事件类型含 `session_started`(641)、`step_recorded`(1005)、`step_updated`、`trace_recorded`、`llm_stream`、`session_ended`(695)。**无设备探针实测**：本地监听后收到 `session_started`、若干 `trace_recorded`、`step_recorded`；`step_recorded` 的字段为 `step_id, step_number, session_id, summary, action_taken, operator_raw_thinking, last_execution_result, pre_image_name, post_image_name, generic_tools, extra_metadata, relative_time, timestamp`（可含 `token_usage`）。桥接做法：先 `listen(127.0.0.1:0)`，把端口放进子进程环境变量 `ARTEMIS_IPC_PORT`；子进程连不上时静默重试、不影响任务（`engine.py` 的 `_connect_ipc_locked` 超时 0.2s）。注意 `_ipc_port_candidates`（`engine.py:434`）还会读 `ARTEMIS_APP_DIR` 下的端口文件，所以给子进程设独立 `ARTEMIS_APP_DIR` 以免连到别人的 UI。
- (B) **SQLite 轮询**：`<traces>/data_engine.db` 的 `steps` 表（`artemis/data_engine/storage.py:138`，列：step_id, session_id, step_number, timestamp, pre_image_name, post_image_name, summary, action_taken, operator_*_thinking, last_execution_result, extra_metadata）与 `sessions` 表（`storage.py:106`，含 status、video_filepath）。可作 IPC 的兜底（步骤落盘由后台线程异步写入，略滞后于 IPC 事件）。
- (C) 进程内订阅：`DataEngine.subscribe(callback)`（`engine.py:520`），但 DataEngine 在 `run_task` 内部创建（`artemis/sdk/agent.py:314`），外部拿不到引用，除非桥接在进程内猴子补丁。另有 LangChain `graph_config_callbacks`（`run.py:153`、`third_party/mobile_use/sdk/agent.py:609`），粒度是 LangGraph 节点而非业务步，不建议用。
- `artemis/interfaces/sdk/task.py:30` 定义了 `StreamEvent`/`StreamEventType`（step_start/step_end 等），但全仓库**没有任何发射点**（`grep StreamEvent` 仅见定义与导出），不能依赖。

**对 Task 4 的结论**：桥接可以输出逐步 `step` 行（来自通道 A，B 作兜底），**不需要**"结束后从轨迹文件补出 step 行"的降级。仅当 IPC 在真机上被证伪时才退回降级（规格 §6.7）；该点在真机上未验证，状态 `blocked`（源码与 DataEngine 探针层面 confirmed）。

**任务结果判定（重要）**：CLI 在任务"失败/blocked"时**不一定以非零退出码结束**——`execute_task` 忽略 `run_task` 的返回值（`run.py:44-166`），`run_task` 对 `blocked` 只写 `end_session("failed")` 然后正常 `return output`（`third_party/mobile_use/sdk/agent.py` 约 666–685 行）；只有设备缺失、鉴权缺失等异常才抛出并以非零退出。实测无设备：stderr 打印 `Task execution failed: No device found. Exiting.` + Python 回溯（`DeviceNotFoundError`），exit 1。所以桥接应以 `sessions.status`（`completed`/`failed`/`cancelled`，`end_session`）或 `session_ended` 事件为准，并读 `<traces>/<session_id>/run_outcome.json`（`artemis/graph/checkpoints.py:59`）获取目标/断言结果，不能只看退出码。

## 2. 模型提供方与密钥配置，与 AutoFlow `provider_kind` 的对应（confirmed：源码）

**ARTEMIS 的配置面**

- 每个 agent 节点的模型由 `config/artemis.jsonc`（默认 provider=google、`gemini-3.8-flash`）决定：`default` + `nodes` 覆盖，`_expand_default_into_nodes`（`artemis/config/llm.py` 约 138–195 行）展开到全部节点（planner、operator、checker、explorer、hopper、outputter、object_detector 等共 16 个）。`parse_llm_config`（`llm.py:200`）按 `artemis.jsonc`→`artemis.json`→`llm-config.json` 的顺序找；路径解析顺序见 `artemis/config/paths.py:149-196`，其中环境变量 `ARTEMIS_ARTEMIS_JSONC=<绝对路径>`（`paths.py:159` 的拼法：`ARTEMIS_` + 文件名大写、点和横线换下划线）**优先级最高**——桥接用它指向 AutoFlow 生成的配置文件，不去改 ARTEMIS 源码目录。
- `LLM.provider` 取值：`openai|google|openrouter|xai|vertexai|anthropic|ollama|vllm|custom`（`artemis/config/constants.py:121`）。
- **密钥和 base URL 不在配置文件里**，只能走环境变量/`.env`（`artemis/config/settings.py` 的 `Settings`，`model_config={"env_file": ".env"}`）：`OPENAI_API_KEY`、`OPENAI_BASE_URL`（`settings.py:110`）、`GOOGLE_API_KEY`（别名 `GEMINI_API_KEY`/`GCP_API_KEY`）、`ANTHROPIC_API_KEY`、`OPEN_ROUTER_API_KEY`、`XAI_API_KEY`。`services/llm.py:929` 构造 `ModelEndpoint` 时从不设置 `api_key`/`api_base`，所以配置文件无法按节点指定 key/base_url。
- 启动时 `validate_providers` 要求配置里**每个节点**（含 fallback）所用 provider 的密钥都在（`third_party/mobile_use/config/llm.py:67`，缺失即 `Exception("... requires OPENAI_API_KEY in .env")`）。

**映射表**

| AutoFlow `provider_kind` | ARTEMIS 配置 | 能否支持 |
|---|---|---|
| `openai` | `provider: "openai"`；env `OPENAI_API_KEY`（`router.py:283`） | 支持 |
| `openai-compatible` | 同样 `provider: "openai"`，加 env `OPENAI_BASE_URL=<base_url>`（`router.py:283-300`，`base_url = endpoint.api_base or settings.OPENAI_BASE_URL`）；也可用 `provider: "custom"/"ollama"/"vllm"`（`router.py:369`，读 `OPENAI_BASE_URL`，缺省 `http://localhost:8000/v1`） | 支持，限制：`OPENAI_BASE_URL` 是**进程级单值**，所有走 `openai` 的节点共用一个 base_url，不能一个节点走 OpenAI 官方、另一个走兼容网关 |
| `gemini` | `provider: "google"`；env `GOOGLE_API_KEY`（`router.py:224-252`） | 支持，限制：`ChatGoogleGenerativeAI` 构造里**没有传 base_url**，不支持自定义 Gemini 网关地址 |
| `anthropic` | `provider: "anthropic"`；env `ANTHROPIC_API_KEY`（`router.py:306-331`） | 支持，限制：`ChatAnthropic` 构造里**没有传 base_url**，不支持自定义 Anthropic 网关；AutoFlow 里 anthropic 若配了自定义 `base_url` 则无法透传 |
| `custom` | 无统一语义；仅当该网关是 OpenAI 兼容协议时按 `openai-compatible` 处理 | 部分支持（视协议） |

**额外约束（会影响可用模型）**

- `object_detector` 节点默认强制 `gemini-robotics-er-2-preview`（`config/artemis.jsonc` 77–83 行注释说明：坐标定位必须用 Gemini ER 模型，非 ER 模型会失败）。`flash` profile 的 explorer 默认 `flash` 档会委派给 `object_detector`（同文件 85–92 行）。因此**纯 OpenAI/Anthropic 配置下，Explorer 的视觉定位能力不可靠**；Task 4 应说明：未配置 Gemini 密钥时，按文件注释降级到 `explorer_mode` 非 flash 档（pro/ultra 为多轮 ReAct，可用通用模型），并在真机上验证——此点 `blocked`。
- 没有 Gemini Key 但配置里仍有 google 节点（如 hopper、planner_validation 的默认 `lightweight_judge_default`，`artemis/config/llm.py:49`）会在 `validate_providers` 或运行中报缺密钥，所以桥接生成的配置必须把**所有节点**（含 `fallback`、`hopper`、`planner_validation`、`validator_pixel_safety_net`）都改成同一 provider。
- 测试用：`ARTEMIS_FAKE_LLM=1` 返回假模型（`router.py` 的 `create_model` 开头），不发网络请求。
- 模型是否具备多模态/工具调用能力由用户选择，ARTEMIS 不做校验（`ModelEndpoint.is_multimodal` 默认 True，仅是声明）。

## 3. 取消运行（confirmed：源码；真机 blocked）

- 进程内：`Agent.stop_current_task()` 取消当前 asyncio 任务（`third_party/mobile_use/sdk/agent.py:797`），任务走 `CancelledError` 分支：`finalize(cancelled=True)`、`end_session("cancelled")`、停止录屏、整理轨迹、释放设备锁。
- 跨进程**协作式取消（不用杀进程）**：往 `get_temp_dir()/cancel-requests/session-<session_id>.cancel` 写 JSON 标记（`artemis/runtime/cancel_requests.py:39,51,89` 的 `request_cancel(session_id=..., pid=...)`），任务内的 `_watch_external_cancel`（`artemis/sdk/agent.py:179`，在 `third_party/mobile_use/sdk/agent.py:786` 启动）每 0.5 秒轮询并调用 `stop_current_task`。这要求任务启动时 `--session-id <UUID>` 已知；标记 TTL 1 小时。临时目录由 `platform.paths.temp_dir` 决定，桥接和 ARTEMIS 子进程若设了不同的 `ARTEMIS_APP_DIR` 需确认两边解析到同一目录——**未实测，blocked**；最稳妥的做法是桥接直接调用 `request_cancel(session_id=...)`（同一 venv 内 import）。
- 信号：CLI 在 `run.py:399` 注册 SIGTERM→`KeyboardInterrupt`，`run.py:432` 捕获后以 130 退出，因此 POSIX 上 SIGTERM 可优雅取消；Windows 子进程是否能收到 SIGTERM 取决于创建方式（ARTEMIS 自己对 worker 用 `CREATE_NO_WINDOW` 并明确说控制台信号到不了，见 `cancel_requests.py` 文件头注释）。
- 兜底：超时后结束进程（含子进程树：scrcpy、adb 后台命令）。结论：**有 API（同进程）和标记文件（跨进程），不是只能杀进程**；Task 4 先发标记取消，宽限期（建议 ≥15s，源码里关闭后台 adb 任务本身最长等 15s，`agent.py` 的 `shutdown_adb_background_tasks` 超时）后再杀进程树。

## 4. 辅助组件（无障碍辅助 APK）检测、安装与 UIAutomator2 后备（confirmed：源码；真机 blocked）

- 辅助组件是设备端 APK `packages/artemis-accessibility-helper/ArtemisAccessibilityHelper.apk`（带 `helper_manifest.json`），`helper_manager.py:100 BUNDLED_APK_PATH`。
- 检测：`artemis helper status [--serial S] [--json]`（`artemis/interfaces/cli/commands/helper.py:71`）。安装：`artemis helper install [--serial S] [--force] [--all]`（`helper.py:135`）；卸载 `artemis helper uninstall`。
- **任务会自动安装/升级**：`ARTEMIS_HELPER_AUTO_INSTALL`（默认 true，`settings.py:121`）为 true 时，任务占用设备后 `helper_manager.provision(...)`（`helper_manager.py:666`）用 `adb install -r -g` 装 APK（`helper_manager.py` 约 755 行）。设为 `false` 则只连接用户已手工装好的。AutoFlow 若不想让第三方 APK 被静默装进用户手机，要显式设 `ARTEMIS_HELPER_AUTO_INSTALL=false` 并在 UI 里做"一键安装"按钮调用 `artemis helper install`（产品决策，非本任务范围）。
- **UIAutomator2 后备**：由 `ARTEMIS_HIERARCHY_BACKEND` 控制（`settings.py:118`，值 `auto|helper|uiautomator`，`artemis/clients/screen_client_factory.py:14-22` 文档）。`auto`（默认）= 辅助组件优先，失败逐次调用降级到 UIAutomator2（`screen_client_factory.py:220 _degrade`、`:242 _call`）；`uiautomator` = 完全不用辅助组件。结论：**未装辅助组件时 UIAutomator2 后备可用**（`auto` 在 helper 报 `RuntimeError/OSError/...` 时降级；设为 `uiautomator` 则直接用它）。UIAutomator2 本身会向设备推送自己的 APK（`screen_client_factory.py` 文档第 21 行说明 `u2.connect` 会推 APK），所以"完全不改动手机"的路径不存在。设备掉线/未授权时不降级，直接抛 `DeviceOfflineError`（`screen_client_factory.py` 约 52 行）。
- 整体体检：`artemis doctor`（`artemis/interfaces/cli/commands/doctor.py:418`），可作 Task 4 的环境检测来源（未实跑其全部输出）。

## 5. 截图、logcat、报告落盘位置与文件名（源码 + DataEngine 探针 confirmed；真机 blocked）

根目录由 `ARTEMIS_TRACES_DIR`（`constants.py:27`，`paths.py:86 get_default_traces_path` 优先读取）决定；缺省：源码 checkout 下为 `<repo>/traces`，设了 `ARTEMIS_APP_DIR`/用户目录模式则为 `<APP_DIR>/traces`（`paths.py:59,86-100`）。桥接应显式设置 `ARTEMIS_TRACES_DIR=<AutoFlow 运行目录>` 与独立 `ARTEMIS_APP_DIR`。`Agent` 以它作为 `_tmp_traces_dir`（`artemis/sdk/agent.py:125`）。

| 产物 | 位置 / 文件名 | 说明 |
|---|---|---|
| 截图 | `<traces>/images/<sha256>.jpg`（`engine.py:832`；探针实测生成两个 `.jpg`） | 以内容哈希命名；步骤里的 `pre_image_name`/`post_image_name` 就是该哈希（不含扩展名）。前后图相同则 post 为空 |
| 数据库 | `<traces>/data_engine.db`（SQLite；`constants.py` `DATA_ENGINE_DB_FILENAME`） | 表 `sessions`、`steps`、`images`（含 ui_tree/ocr）、`traces`、`video_recordings`、`history_chunks`、`background_tasks` |
| 会话目录 | `<traces>/<session_id>/`（探针实测创建） | 内含 `run_outcome.json`（`checkpoints.py:59`）、`check_ledger.jsonl`、`check_streams.jsonl`（检查器台账）等（文件名常量见 `checkpoints.py:57-59`） |
| 轨迹包（仅 `--test-name` 时） | `<--traces-path>/<test_name>_<PASS\|FAIL\|TESTFAIL>_<YYYY-MM-DDTHH-MM-SS>/`（`third_party/mobile_use/sdk/agent.py:913-915`） | 内含 `trace.gif`（`utils/media.py:181`）、`steps.json`、`recording.mp4`（有录屏时，`agent.py:931`）；原始 `.jpeg` 与逐步 `.json` 在汇总后删除（`agent.py:920-925`） |
| 最终输出 | 环境变量 `RESULTS_OUTPUT_PATH=<含扩展名的文件>`（`third_party/mobile_use/main.py:123`、`config/output.py:136` 要求路径带后缀，否则报"像目录"并忽略） | 写入 outputter 的结构化结果（`record_events`）；`EVENTS_OUTPUT_PATH` 仅在 `output.py` 解析，实际只写 outputter 结果，不是逐步事件，勿当步骤日志用 |
| 录屏 | scrcpy 录到临时目录（`get_temp_dir("recordings")`），结束后合入轨迹包 | 依赖 scrcpy+ffmpeg，见第 6 节 |
| logcat | **ARTEMIS 没有固定的 logcat 落盘文件。** logcat 只在 Operator 通过 adb 命令工具按需抓取（`artemis/tools/command_tool.py`、`log_analyzer` 节点），结果进入 `traces` 表的 trace payload，不是独立文件 | 若 AutoFlow 需要 logcat，应由 Task 4 在任务前后自行 `adb -s <serial> logcat -d` 落盘；此项真机 blocked |

ARTEMIS 自身日志（loguru 风格）写 stdout/stderr（含 ANSI/emoji 与横幅，见第 0 节），桥接需自行落盘并过滤。

## 6. scrcpy / FFmpeg / adb（confirmed：源码；真机 blocked）

- **scrcpy 与 FFmpeg 不是必需**：仅用于录屏与视频分析。`detect_video_tools_enabled()` = 两者都可用才启用（`artemis/utils/video.py:567`；`ExecutionSetup`/`AgentConfigBuilder` 默认值都取它），缺任一则自动关闭视频功能；也可显式 `--without-video-recording-tools`。FFmpeg 有回退：`imageio-ffmpeg` 自带二进制（已在依赖里，`toolchain/descriptors.py` 的 `_get_embedded_ffmpeg`），所以通常只缺 scrcpy。显式 `--with-video-recording-tools` 且缺 ffmpeg 会直接失败（`main.py` 的 `ensure_video_recording_available`）。
- scrcpy 的发现：`resolver.resolve("scrcpy")` 依次看 `ARTEMIS_SCRCPY_PATH`、系统常见路径、PATH（`toolchain/resolver.py:65` 起，`descriptors.py:80`）；但 `unified_controller.py:342,451` 在分段录制时直接用字面量 `"scrcpy"`（走 PATH），所以要用录屏就应把 scrcpy 所在目录放进子进程 PATH，而不是只设 `ARTEMIS_SCRCPY_PATH`。
- **adb 路径**：解析器支持 `ARTEMIS_ADB_PATH` > `ANDROID_HOME/ANDROID_SDK_ROOT/platform-tools` > 常见路径 > PATH > adbutils 自带 adb（`resolver.py:65-115`），**但是** `Agent._init_internal` 在第一步硬检查 `shutil.which("adb")`，没有则抛 `ExecutableNotFoundError`（`third_party/mobile_use/sdk/agent.py:142`；`ARTEMIS_CLOUD_MODE=1` 才跳过）。所以桥接必须把 AutoFlow 管理的 adb 所在目录**前置到子进程 PATH**，仅设 `ARTEMIS_ADB_PATH` 不够。远程/非默认 adb server：`ADB_HOST`、`ADB_PORT`（`settings.py`、`runtime/adb_endpoint.py:111` 设置 `ADB_SERVER_SOCKET`）。
- 其余：ARTEMIS 的 `uv` 描述符只是工具发现，不要求安装。

## 对 Task 3 / Task 4 的要点汇总

1. 桥接用 `artemis run --standalone -s <serial> --profile <flash|pro> --session-id <uuid> [--without-video-recording-tools] "<目标>"`（或同 venv 内 `run_automation`），**不要**走 daemon / `artemis-client`（后者只能轮询、需常驻服务、无事件流）。
2. 逐步事件：桥接监听本地 TCP，传 `ARTEMIS_IPC_PORT`；解析 `step_recorded`（`step_number, summary, action_taken, pre/post_image_name`）；截图读 `<ARTEMIS_TRACES_DIR>/images/<name>.jpg`；`data_engine.db` 作兜底。
3. 最终结果以 `session_ended`/`sessions.status` + `run_outcome.json` 为准，不依赖退出码。
4. 环境变量集合：`ARTEMIS_APP_DIR`、`ARTEMIS_TRACES_DIR`、`ARTEMIS_ARTEMIS_JSONC`（AutoFlow 生成的全节点同 provider 配置）、`OPENAI_API_KEY`+`OPENAI_BASE_URL` / `GOOGLE_API_KEY` / `ANTHROPIC_API_KEY`、`ADB_DEVICE_SERIAL`（可选）、`ARTEMIS_HELPER_AUTO_INSTALL`、`ARTEMIS_HIERARCHY_BACKEND`、`ARTEMIS_IPC_PORT`、`PATH`（前置 adb 目录）、`PYTHONIOENCODING=utf-8`。密钥只经环境变量传，不写入配置/日志。
5. `anthropic`/`gemini` 自定义 base_url 无法透传；`openai-compatible` 只有一个全局 base_url；纯非 Gemini 配置下 Explorer 视觉定位待真机验证。

## 状态汇总

| 项 | 状态 | 依据 |
|---|---|---|
| 提交 / LICENSE | confirmed | git rev-parse、LICENSE |
| 安装规格 | confirmed | 实际安装成功，`artemis run --help` 可运行 |
| 1 入口 / device_serial | confirmed | 源码 + `--help` |
| 1 逐步事件（IPC） | confirmed（DataEngine 探针）/ blocked（真机整链路） | 探针收到 `step_recorded` |
| 2 provider 映射 | confirmed（源码） | `router.py`、`settings.py`；未用真实密钥发请求 |
| 3 取消 | confirmed（源码） / blocked（真机） | `cancel_requests.py` |
| 4 辅助组件 / U2 后备 | confirmed（源码） / blocked（真机） | `screen_client_factory.py`、`helper_manager.py` |
| 5 落盘位置 | confirmed（DataEngine 探针 + 源码） / blocked（完整一次真机运行的目录） | 探针落盘；`--test-name` 轨迹包仅源码 |
| 6 scrcpy/FFmpeg/adb | confirmed（源码） | `resolver.py`、`agent.py:142` |
| 真机 `artemis run "打开设置"` | blocked | 本机无设备，不装 SDK/模拟器（已决定） |
