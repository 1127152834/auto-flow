# 系统架构与应用设计审计

- 日期：2026-09-28。
- 状态：confirmed（本页注明的源码事实）；proposed（整改及验收建议）。
- 基线：`33ae3aa49600840b1700c83723408c494dc201a8`；本次审计时存在其他任务的文档/证据工作区改动，未覆盖或修改这些内容。
- 方法：阅读项目规范、架构/目录索引、相关 ADR、生产装配/执行/数据/设备/发行代码及现有 QA 脚本；源码行号指审计基线。
- 范围：架构与产品边界、验证真实性、平台覆盖；没有修改业务代码，没有操作用户业务数据库或外部账号。运行测试结果由同目录其他报告记录。本页的静态结论不冒充已经执行过端到端验收。

## 结论

当前系统已经具备实质性的桌面应用、资源管理、项目数据与运行管理实现，不能再按“只有 Mock 页面”评价。但管理能力、Studio 节点能力和项目业务闭环之间仍有断点；现有大量回归测试也不等于所有生产链路都经过真实验证。最高优先级是打通并验收项目数据写回/环境结束/人工恢复，同时把默认 QA 入口和实际交付边界对齐。

### A-01 / P1：项目业务执行闭环尚未完成，不能用 Studio 表格节点替代项目数据库操作

**已确认，置信度高。** 项目执行已接入共享图调度器，但项目 worker 到项目数据 capability/环境 End/持久人工检查点的桥仍缺失。

证据：

- `providers/browser/project_graph.py:150` 创建的 `ExecutionContext` 接入浏览器、模型、凭据、HTTP/外部集成、代理、普通输入与表格导出；`domain/workflows/execution.py:290–319` 没有项目数据或环境 capability 端口。
- `application/workflows/dispatcher.py:782–791` 创建 worker 变量时仅合并文档变量和 `run.parameters`；已领取的项目输入快照没有在此转成执行变量或受限 capability，因此也不能把“输入快照已冻结”理解成节点已经可以读取业务记录。
- `infrastructure/process/project_workflow_worker.py:200–260` 的协议接收分支处理 `proxy:request`、事件、读凭据、交互确认与终态，没有已批准规格要求的数据/环境 capability request/result。
- `application/workflows/executors/table.py:147–153` 的 `table_add_row` 检查并追加 `context.data_rows`；它是单次运行内存表。它不会写入项目数据表、推进记录版本/状态，也不会获得项目 lease。
- `application/environments/retention.py:260` 的 `end_task` 当前调用点是环境服务/人工处理；没有从生产项目 worker 的节点执行入口调用。`rg 'end_task\(' apps/backend/src/autoflow` 可复核完整调用集。
- `bootstrap/app.py:506` 装配时直接声明 `project.data` 可用，`application/project_runs/coordinator.py:110–118` 返回“项目数据执行能力可用”。这没有区分“管理侧可领取输入”与“节点可受限写回项目表”，能力文案容易超出实际端到端边界。
- 已批准 `docs/superpowers/specs/2026-09-20-pm9-production-runtime-integration.md:18–20` 明确要求上述能力桥与恢复语义。

影响：用户可以看到项目数据、环境管理和 Studio 表格节点都存在，却不能据此完成“领取业务记录 → 浏览器真实操作 → 更新同一记录/业务状态 → 保存登录环境 → 人工介入后从检查点继续”的完整链。普通 `input_prompt` 与持久人工接管不是同一能力。

最小下一步：沿现有 PM9 R2/R3 完成明确 capability 的父进程路由；用真实生产 worker、隔离项目数据和真实浏览器做一条可核对数据库前后状态的纵向验收。不再另建执行器。

本轮运行补证：`runtime/run-hn1fvbhq/results.json` 的两个 `table_semantics` 任务均由生产 worker 成功执行，运行变量的文件 SHA256 正确，项目表仍为原 3 条。此结果验证两种表的职责边界；它不是 `table_add_row` 错误，而是不能用该节点的通过替代未接通的项目业务写回。完整边界见 [runtime/runtime-realqa.md](runtime/runtime-realqa.md)。

### A-02 / P1：默认 Studio 冒烟脚本仍验收已退役的 Mock 阶段

**已确认，置信度高。** `package.json:21` 的 `smoke:studio` 指向 `scripts/smoke-studio-window.mjs`。后者 `34–35` 行要求 OpenAPI 不含 workflows 路由、GET workflows 返回 404；`41` 行要求画布出现“Mock 接口”。这与当前真实 Studio 后端的生产边界相反。

影响：开发者按根脚本运行 smoke，会得到过期断言失败；跳过这个失败又可能使当前 Studio 没有统一、可信的发布门禁。它不能作为本轮“所有真实测试”的入口。

最小下一步：将退役/Mock 脚本明确归档为历史验证，根入口改为当前正式主窗口 → Studio → 保存 → 真实运行 → 持久结果 → 重启恢复的同版本链，复用已有 `smoke-studio-backend-*` 脚本能力。

### A-03 / P1：若沿用 PM4–PM8 管理 QA 报告，会高估真实业务闭环覆盖

**已确认，置信度高；这是证据缺口，不是断言管理功能一定失败。**

- `scripts/qa-project-management-pm4.mjs:104` 明确声明 `executor: 'fake'`，`839` 行还断言 fake 结果标记。
- `qa-project-management-pm5.mjs:330–331` 默认选择 `tests.qa.pm5_sidecar`，该 sidecar 删除真实批次 scheduler 的 startup 回调、使 Run 一直 queued（`pm5_sidecar.py:31–43`）；其浏览器手动打开/关闭仍是真的，但不验证生产执行交接。PM7/PM8 脚本分别在 `186`/`183` 行选择专用 QA sidecar，后者复用 PM4 fake runner。
- `apps/backend/tests/qa/pm6_sidecar.py:8–16,37–38` 用 `FakeSheetsTransport`/`FakeTokenTransport` 与替代凭据存储，覆盖的是管理/协议逻辑，不能证明 Google 实网与系统凭据行为。
- `scripts/qa-pm5-browser-chain.py:54` 明确内核目录查找为 stub，即使浏览器本身是真的，也不是完整资源管理链。
- 真浏览器集成测试依赖 `AUTOFLOW_B1_CLOAK_EXECUTABLE` 或 `AUTOFLOW_TEST_CLOAKBROWSER`；未配置时 `pytest.skip`。例如 `tests/integration/test_b1_cloakbrowser_flow.py:48`、`test_environment_real_browser_chain.py:24–26`。默认 pytest 全绿并不保证真浏览器执行。

最小下一步：报告必须按“纯逻辑/真实 SQLite /生产 worker /真实浏览器 /外部实网 /原生桌面/安装包”分层记证据，保留 mock 单元测试价值，但本轮真实验收的 passed 只能来自对应真实链路。

### A-04 / P2：Android 界面承诺了当前不可用的工作流能力

**已确认，置信度高。** `apps/desktop/src/renderer/domains/android/components/DeviceDetails.tsx:12` 告知用户“在工作流工作台中选择此设备即可运行”。实际 `application/android/fleet.py:146–150` 固定返回 `ANDROID_WORKFLOW_RUNTIME_UNAVAILABLE`/409；`bootstrap/android.py:14–35` 当前运行边界也拒绝接管/启动。

本轮真实 Electron 页面证据 `ui/global-android.json` / `ui/global-android.png` 也显示首页描述“按工作流分配设备，跟踪运行与回收”及“分配工作流”入口，进一步确认这不是仅存在于未挂载组件中的旧文字。

影响：用户完成设备准备后仍会进入不存在的业务路径。这比隐藏未实现模块更容易造成错误预期。

最小下一步：设备详情明确“当前支持设备管理与手动控制”，工作流入口显示准确能力状态；待真实执行合同交付后再展示可运行说明。Android 管理优先的 ADR 允许暂不接工作流，这本身不是缺陷；界面承诺与能力不一致才是缺陷。

### A-05 / P1 发布准入：多平台构建不等于多平台完整运行/安装验收

**证据边界已确认，当前远端 CI 结果未知。** `.github/workflows/ci.yml:12–14` 有 Windows x64、macOS Intel、macOS arm64 矩阵，但未配置上述真实 CloakBrowser 测试变量、真实外部服务账号和设备资源。构建 installer 只检查文件存在，并不等于安装/升级/卸载/签名公证验证。`apps/desktop/electron-builder.yml` 声明 dmg/nsis，未见发布签名/公证验收步骤。

CI 已配置源码和 packaged 的项目管理、desktop、browser smoke；不能说 CI 完全没有运行测试。这里的缺口是当前 CI 结果尚未读取、完整生产执行链与实际安装/升级/签名等验收仍需要独立证据。

Android 实际运行环境也只支持 Apple Silicon Mac：`providers/android/mac_runtime.py:88–104` 检查 Darwin + arm64、Lima/ADB/ssh、固定 scrcpy 和 Binder；这应作为模块级平台能力公开，而不是从“应用支持 Windows/macOS”推导 Android 全平台可用。

本机是 Darwin arm64，存在 node/uv/adb/limactl/ssh/scrcpy/codesign/xcrun 命令。生产 `MacAndroidRuntime.environment()` 基础依赖探测返回 `available=true`、固定镜像 1 个、VM 6 核/7,921 MiB，见 [android-environment.json](android-environment.json)。但随后真实创建/启动 QA 专属设备时，两次均因 VM 缺少 `docker0` 启动失败；因此这项 available 探测不能作为设备可启动证据，详见 A-10。原有设备与数据未修改，QA 设备/卷均已清理。本架构子任务未访问 Keychain 内容，系统凭据真实隔离测试见独立安全报告。

最小下一步：同一源码版本形成三平台可审查证据：真实安装启动、sidecar/浏览器子进程清理、原生文件面板、凭据、工作区切换、执行与崩溃恢复。账号/硬件功能缺条件时保持 blocked，不能折算为通过。

### A-06 / P2：当前状态文档与代码长期交叉覆盖，容易误导后续实施

**审计时已确认，置信度高；收尾时部分已由另一任务修正。** `.ai/README.md:5` 和审计时的 `docs/PROJECT_STRUCTURE.md:4,263–265` 把当前 Studio 描述成前端/Mock 边界；`docs/architecture/README.md:3` 还写“仅保留独立空窗口”和“proposed，未实现”。正文追加后续阶段，但入口当前态不一致。2026-09-28 收尾复核时，另一任务已在 `docs/PROJECT_STRUCTURE.md` 顶部标明旧 Mock 结论 superseded 并链接新项目地图；该文件的入口误导已得到修正，不再计作当前未修复项。`.ai/README.md` 的旧表述仍在。

最小下一步：只维护一份简洁的当前能力/平台/验收状态索引，其余历史记录标明基线与 superseded；无需新建复杂文档系统。

**本轮纠正两条旧评价：**

- 9/24 评价的“两套独立执行循环、项目仅四节点”已过时。`project_workflow_worker.py:16,190` 与 `project_graph.py:169–180` 使用共享 `WorkflowRuntime`；四节点 `_LegacyBrowserNode` 只为历史 chain/v1 文档动作兼容，新图走 production registry。不要再以旧结论要求重建引擎。
- 9/24 评价的“全局资源删除没有静态引用保护”已过时。`application/profiles/service.py:98–107` 已检查 `ensure_unreferenced`；models provider、kernel、proxy pool/connection 也已有守卫，`bootstrap/app.py:232` 装配真实 `SqlAlchemyProjectResourceReferences`。是否存在更细粒度遗漏仍需针对场景验证，不能泛称保护完全不存在。
- `packages/ui` 空目录不是必须立即修复的缺陷：`docs/architecture/README.md` 已有 9/12 补充，明确现阶段共享组件在 renderer/shared，独立包等有真实消费者再建立；本轮不建议为满足空目录形式而搬包。

### A-07 / P2 风险：大数据查询与执行表格的复杂度需用真实负载定上限

**实现机制高置信，本轮已测 1,000/8,504 行后端性能，未证明更大规模存在超预算故障。** `infrastructure/database/project_data_queries.py:96–143,152–176` 将业务筛选实现为 SQLite Python UDF，业务排序通过 JSON 投影 + 自定义 collation；这不能像普通列索引一样直接跳过所有无关记录。`table.py:82–97,147` 每次增加内存表格行时遍历当前全部行重新累计容量，循环添加 N 行会出现累计二次扫描。

本轮真实仓库 8,504 个文件记录通过正式 TCP API/SQLite 批量写入、筛选排序与 43 页完整回读；默认首页 P95 32.826 ms，字节数降序 P95 139.781 ms（每类 10 次，P95 为该组最大值）。86 个批写入 HTTP 耗时合计 5,034.169 ms。此规模没有出现必须立即换数据库的证据；详见 [performance.md](performance.md)。运行内存表格的二次扫描、大数据 UI、10 万行和长时负载仍未实测。

最小下一步：在本轮 1 千/8,504 行后端测量基础上，取得足量真实数据再扩展到 1 万/10 万行，并补导出、运行结果表批量增加、UI 首次渲染；同时测 1,000 logs/min 和长时运行的 RSS/SQLite/产物增长。记录 P50/P95、取消延迟、失败恢复与资源上限。不复制数据凑样本量，也不在缺性能证据时先换数据库或引入缓存。

### A-08 / P2 可维护性：迁入边界集中在少量巨大模块，修改后需要跨层回归

**代码规模已确认，维护成本为架构判断，置信度中。** 当前 `application/workflows/coordinator.py` 2,254 行、`providers/browser/workflow_worker.py` 2,164 行、`infrastructure/database/project_capabilities.py` 1,811 行。这里同时涉及停止、交互、凭据、事件与资源回收；一个局部修补容易只验证其中一个入口。

最小下一步：每次修复先列 Studio/项目/历史文档/嵌套运行调用方并跑真实共享边界回归；只在明确改动时抽取已形成独立职责的协议或资源清理逻辑。无需立即重写或再加抽象层。

### A-09 / P2：真实场景 QA 脚本仍明显绑定开发者本机

**已确认，置信度高。** 枚举 `scripts/*.mjs` 得到 37 个文件含开发者绝对 `/Users/...` 路径，34 个文件使用 `cp -cR`。例如 `smoke-studio-backend-b5-ai-tasks.mjs:13–14,44` 默认读取个人 macOS 内核目录并调用 macOS clone-copy 选项。

影响：这些脚本即便本机通过，也不能直接成为 Windows/macOS Intel 的同版真实场景门禁；换机器容易先在准备阶段失败，妨碍区分环境不满足与产品行为失败。

最小下一步：真实内核路径成为显式可验证参数，文件复制复用 Node 标准库；测试准备步骤与断言结果分开记录。不要复制一套 Windows 脚本维护第二份场景。

### A-10 / P2：Android 环境诊断给出可用结论，但缺少启动所需网络依赖核验与可操作错误

**真实重现两次，置信度高。** 本轮环境诊断两次返回 `available=true`，自有 QA 设备创建与幂等重发成功，随后 start 均在约 0.8–0.9 秒失败，进入 `recovery_required`。只读容器错误和 `ip link` 复核确认 VM 缺少默认 Docker bridge 对应的 `docker0`，不是凭空归因于 AutoFlow。

应用层缺口：`providers/android/mac_runtime.py:89–100` 只检查工具、Docker info、架构、Binder 与 scrcpy；没有检查实际启动所依赖的网络。`mac_runtime.py:43–45` 丢弃 stderr，仅返回通用 `ANDROID_COMMAND_FAILED`；错误在界面/API 中不能指出网络、容量还是镜像问题。管理层正确记录失败并要求恢复，这部分没有假成功。

最小下一步：在不暴露任意原始命令输出的前提下，提供依赖级诊断和可操作的稳定错误；修复共享 VM 网络需作为独立变更处理，之后重跑 start→真实 PNG→正常 stop。此次只通过自有设备创建/recover/delete 与无误删核对，截图和运行中停止没有通过。完整证据见 [Android 真实 QA](android/android-realqa.md)。

## 规模与真实性基线

2026-09-28 使用文件枚举获得：生产 Python 502 个文件；后端 `test_*.py` 395 个（unit 119、contract 79、integration 148、differential 47、migration 1、compatibility 1）；desktop `*.test.ts[x]` 428 个；根 `scripts/*.test.mjs` 23 个。它们是**文件数量，不是本轮执行通过数量**。

对 `domain/workflows/scope.py` AST 读取获得 `APPROVED_NODE_TYPES` 的唯一类型数为 216。前端入口数量、唯一 node type 数、生产 executor 数和实测节点数是不同口径，不能用旧“227 入口”或“216 类型”推导全覆盖。

详细真实场景、测试替代边界和外部先决条件见 [coverage-matrix.md](coverage-matrix.md)。本页不给出未经执行支持的总体通过率。
