# AutoFlow Automation Studio 规划与迁移计划

> 从 WebRPA 的功能模块和源码依赖倒推的从零开发顺序，以 [REVERSE_ENGINEERED_DEVELOPMENT_PLAN.md](./REVERSE_ENGINEERED_DEVELOPMENT_PLAN.md) 为当前实施顺序和验收依据；本文继续保存产品形态、架构边界与长期约束。

- 状态：实体盘点完成；等待 AutoFlow 主框架完成后，先复刻 Studio 前端，自动化后端暂缓
- 日期：2026-09-11
- 目标平台：Windows x64、macOS Intel、macOS Apple Silicon
- 产品形态：AutoFlow 中可独立运行的工作流创作桌面应用
- 参考来源：WebRPA 主分支审查基线 `5ccb900e8dcf1530aae66f676d87593c416c7ebb`
- 旧项目：`/Users/zhangtiancheng/Documents/projects/browser-automation/autoflow-desktop`

## 1. 目标和边界

Automation Studio 是 AutoFlow 的自动化创作与执行工作台。它可以在没有项目管理模块的情况下独立启动，创建基础 Web 自动化流程，并通过 CloakBrowser 执行流程。

项目管理模块是自动化的管理能力。它负责项目、自动化关系、资源配置、运行分析和数据支撑；自动化内核不依赖项目管理。项目管理完成后，Studio 可以在管理窗口中停靠，也可以重新弹出为独立窗口，底层工作流和执行器保持同一套代码。

### 第一阶段包含

- 工作流画布和节点配置；
- 当前工作流的保存和加载；
- 基础流程控制：变量、条件、循环、子流程；
- CloakBrowser 网页自动化；
- 页面导航、元素定位、点击、输入、等待、文本/属性读取、截图；
- 标签页和 iframe 基础操作；
- 运行、停止、超时、节点状态和日志；
- Windows 和 macOS 的启动、执行、关闭验证。

### 第一阶段明确排除

- 工作流版本历史、快照、对比和恢复；
- 工作流市场、发布系统和 WebDAV；
- OCR、验证码、媒体处理、文档转换；
- Windows 桌面自动化、macOS 桌面自动化和 Android 自动化；
- AI 自愈和自动生成工作流；
- WebRPA 运行时集成、协议兼容、文件格式兼容和外部进程调用；
- 复制 WebRPA 全部 573 个唯一 `module_type`。

## 2. 核心设计原则

1. **自动化核心独立。** 自动化可以独立编辑和执行，不 import 项目管理代码。
2. **管理端是上层组合。** 项目管理通过 application API 调用自动化能力，不进入执行器内部。
3. **CloakBrowser 是唯一浏览器运行时。** 所有网页节点必须通过 `CloakBrowserRuntime`，不能直接创建 Playwright 或其他浏览器实例。
4. **画布不是领域模型。** React Flow 只负责交互，后端使用 AutoFlow 自己的工作流文档模型。
5. **窗口不是业务边界。** Manager 和 Studio 是同一应用中的两个界面宿主，共享后端和契约，不复制业务实现。
6. **先做少量可验证能力。** 先实现基础 Web 节点的完整闭环，再扩大节点数量。
7. **平台差异显式化。** 第一阶段只实现跨平台网页能力；暂不支持的平台能力返回结构化不可用状态。
8. **没有产品级版本管理。** 只保存当前工作流和运行记录；内部格式字段只有在序列化确实需要时才增加。

## 3. 桌面应用形态

### 3.1 一个应用、两个窗口

```text
AutoFlow Desktop
├── Manager Window
│   ├── 项目和自动化列表
│   ├── 资源配置
│   ├── 运行记录
│   └── 分析和数据
├── Studio Window
│   ├── 工作流画布
│   ├── 节点目录
│   ├── 配置检查器
│   ├── 运行控制
│   └── 日志面板
└── 一个 FastAPI sidecar
    ├── 自动化应用服务
    ├── CloakBrowserRuntime
    ├── 执行器注册表
    └── 运行事件
```

第一阶段先实现独立 Studio Window。Manager Window 可以先只有打开 Studio 的入口和运行状态占位，项目管理功能不阻塞自动化内核。

### 3.2 停靠和弹出

Studio 支持两种展示模式：

```text
presentationMode = "window" | "docked"
```

- `window`：Studio 路由挂载在独立 BrowserWindow；
- `docked`：Studio 组件挂载在 Manager Window 的内容区域；
- 切换模式前保存当前编辑会话状态；
- 每个 `automationId` 同时只允许一个 Studio 会话；
- Manager 和 Studio 不直接同步完整 React state，而是通过后端工作流数据和运行事件同步；
- 第一版不物理重挂载 BrowserWindow，也不使用 iframe；切换模式时复用同一套 Studio React 组件并重新挂载。

```text
Manager 点击编辑
    ↓
获取或创建 StudioSession
    ↓
打开 Studio Window
    ↓
编辑 / 运行
    ↓
Manager 通过 API 和事件看到运行状态
```

停靠和弹出属于桌面壳能力，不进入自动化领域模型。

## 4. 目标代码结构

```text
apps/
├── desktop/
│   └── src/
│       ├── main/
│       │   ├── bootstrap/
│       │   ├── lifecycle/
│       │   ├── windows/
│       │   │   ├── window-manager.ts
│       │   │   ├── manager-window.ts
│       │   │   ├── studio-window.ts
│       │   │   └── studio-session-store.ts
│       │   ├── sidecar/
│       │   └── platform/
│       │       ├── windows/
│       │       └── macos/
│       ├── preload/
│       └── renderer/
│           ├── app/
│           ├── domains/
│           │   ├── management/
│           │   └── automation/
│           │       ├── studio/
│           │       ├── canvas/
│           │       ├── node-catalog/
│           │       ├── inspector/
│           │       ├── execution/
│           │       └── logs/
│           └── shared/
│
└── backend/
    └── src/autoflow/
        ├── bootstrap/
        ├── domain/
        │   └── automation/
        ├── application/
        │   └── automation/
        ├── executors/
        │   ├── registry.py
        │   ├── base.py
        │   ├── core/
        │   └── browser/
        ├── infrastructure/
        │   ├── automation/
        │   └── cloakbrowser/
        └── adapters/
            └── http/
                └── automation/
```

目录只在对应能力开始实现时创建。不会先创建完整的空模块树。

## 5. 自动化领域模型

### 5.1 当前工作流

```text
WorkflowDocument
├── workflowId
├── name
├── nodes[]
│   ├── id
│   ├── type
│   ├── config
│   └── platformRequirements[]
├── edges[]
├── variables
└── updatedAt
```

`WorkflowDocument` 表示当前可编辑内容。系统不建立 revision、snapshot、publish 或 compare 表。

### 5.2 执行模型

```text
Run
├── runId
├── workflowId
├── status: queued | running | succeeded | failed | cancelled | timed_out
├── startedAt
├── finishedAt
├── error
└── nodeResults[]
```

```text
RunEvent
├── runId
├── sequence
├── nodeId
├── type: run_started | node_started | node_progress | node_succeeded |
│        node_failed | node_cancelled | run_succeeded | run_failed | run_cancelled
├── timestamp
└── payload
```

事件序号只保证单次运行内的顺序，不引入事件溯源或历史版本系统。

### 5.3 执行器

```python
class ModuleExecutor(Protocol):
    module_type: str

    def validate(self, config: object) -> list[ValidationIssue]: ...

    def capabilities(self) -> CapabilityDescriptor: ...

    async def execute(
        self,
        config: object,
        context: ExecutionContext,
    ) -> ModuleResult: ...
```

AutoFlow 可以在内部使用 `NodeExecutor` 作为别名，但迁移层保留 WebRPA 的 `ModuleExecutor`、`module_type`、配置字段和结果字段，避免没有证据的契约改名。

第一批执行器：

```text
core.variables
core.condition
core.loop
core.subflow
browser.navigate
browser.click
browser.input
browser.wait
browser.get_text
browser.get_attribute
browser.screenshot
browser.tabs
browser.iframe
```

## 6. CloakBrowser 强绑定设计

```text
CloakBrowserRuntime
├── start_session(profile, proxy)
├── open_page(url)
├── locate(selector)
├── click(target)
├── input(target, value)
├── wait(condition)
├── read_text(target)
├── read_attribute(target, name)
├── screenshot(path)
├── switch_tab(tab_id)
├── enter_iframe(frame)
└── close_session()
```

执行器依赖 `CloakBrowserRuntime`，不依赖具体启动命令、数据目录或 Electron。CloakBrowser 的 profile、代理、指纹和关闭逻辑统一由 runtime 管理。

现有旧项目中的 `cloakbrowser` 依赖、内核管理和 profile 资源会先做能力迁移审查，再接入 runtime。旧项目中的 Windows-only 凭据实现不能直接作为跨平台实现；凭据在资源迁移计划中通过 Windows Credential Manager 和 macOS Keychain 分别实现。

CloakBrowser 启动验收：

- 可在 Windows 和 macOS 创建会话；
- 可以加载本地测试页面；
- 可以执行一个完整节点链；
- 节点失败会关闭页面和浏览器上下文；
- 用户取消后在限定时间内关闭会话；
- sidecar 退出不会遗留 CloakBrowser 子进程。

## 7. WebRPA 能力复刻策略

WebRPA 只提供源码和能力参考，不作为 AutoFlow 依赖。重点审查以下来源：

```text
backend/app/executors/
backend/app/services/workflow_*.py
backend/app/models/workflow.py
frontend/src/components/workflow/
frontend/src/store/
frontend/src/types/workflow.ts
```

来源主分支审查基线为 `5ccb900e8dcf1530aae66f676d87593c416c7ebb`。

每个能力按以下流程移植：

1. 写出 AutoFlow 节点行为和输入输出测试；
2. 读取来源文件及直接依赖；
3. 删除全局 store、启动器、Windows-only 代码和不需要的重量级依赖；
4. 将纯算法、节点 schema 或浏览器动作重构进 AutoFlow 模块；
5. 让浏览器动作全部经过 CloakBrowserRuntime；
6. 在本地固定测试页面上验证；
7. 在 Windows 和 macOS 验证；
8. 记录来源 commit、文件、许可证、改动和剩余依赖。

首批只复刻 WebRPA 的基础网页自动化能力。OCR、桌面、Android、媒体、文档和高级 AI 能力不进入首期计划。

WebRPA 仓库的 LICENSE 声明 AGPL-3.0 与商业授权双授权，并列出额外的非商业或 GPL 依赖。直接复制文件前必须完成许可证记录和发布策略决策；未完成记录的代码只能作为参考。

## 8. 分期路线

### Phase 0：主线架构完成

前置条件：AutoFlow 主聊天中的跨平台基础架构、Electron shell、FastAPI sidecar、路径服务和 OpenAPI 约定完成并通过验证。

交付：将 Automation Studio 的目录、命名和工具链接入主线，不创建第二套桌面基础设施。

### Phase 1：独立 Studio 壳

交付：

- 独立 Studio Window；
- React Flow 空画布；
- 节点目录和配置区域占位；
- FastAPI automation 路由；
- 当前工作流保存和加载；
- CloakBrowserRuntime 启动/关闭；
- 基础运行日志。

验收：不依赖项目管理即可创建一个空流程并启动/关闭浏览器。

### Phase 2：工作流内核

交付：WorkflowDocument、节点注册表、配置校验、变量、条件、循环、子流程、Run、RunEvent、取消和超时。

验收：控制流节点可以在没有网页的情况下通过单元测试和最小运行测试。

### Phase 3：基础 Web 节点

按以下顺序迁移：

1. navigate；
2. wait；
3. click；
4. input；
5. get_text；
6. get_attribute；
7. screenshot；
8. tabs；
9. iframe。

验收：使用仓库内本地测试页面完成“打开页面 → 输入 → 点击 → 读取结果 → 截图”的完整流程。

### Phase 4：Studio 编辑和运行体验

交付：节点配置表单、配置错误提示、节点状态、运行/停止按钮、日志过滤、失败节点定位、浏览器会话状态。

验收：用户可以不打开开发者工具完成流程创建、运行、停止和错误定位。

### Phase 5：双窗口模式

交付：Manager Window、Studio Window、StudioSession、窗口聚焦、单 Studio 会话、停靠和弹出。

验收：同一自动化在独立窗口和管理窗口中切换后，当前编辑内容、运行状态和日志不丢失。

### Phase 6：项目管理接入

建立：

```text
ProjectAutomationBinding
├── projectId
├── automationId
├── resourceDefaults
└── executionPolicy
```

管理端调用：

```python
validate_automation(automation_id)
run_automation(automation_id, execution_context)
cancel_run(run_id)
stream_run_events(run_id)
```

验收：项目可以选择自动化、提供 CloakBrowser profile/proxy 等资源、启动运行并查看运行数据；自动化核心测试不需要项目管理 fixture。

## 9. 评估体系

### 9.1 能力等级

```text
0 = 未实现
1 = 原型可运行
2 = 功能完成，有单元测试和错误测试
3 = Windows/macOS 验证，有集成、取消、清理和日志测试
```

基础 Web 节点进入 Studio 正式使用前必须达到 3。实验节点可以暂时停留在 1 或 2，但必须在界面上标记不可用于正式运行。

### 9.2 每个节点的验收矩阵

| 维度 | 必测内容 |
|---|---|
| 正常行为 | 合法配置在本地测试页面产生预期输出 |
| 配置校验 | 缺少必要字段、类型错误、无效 selector |
| 页面异常 | 元素不存在、页面加载失败、iframe 不存在 |
| 运行控制 | 超时、取消、重复点击运行按钮 |
| 资源清理 | 浏览器上下文、页面、临时文件、子进程关闭 |
| 事件顺序 | 节点开始、进度、完成/失败和运行结束顺序正确 |
| 跨平台 | Windows 和 macOS 结果明确，未支持能力返回结构化状态 |
| 可维护性 | 执行器不直接依赖 HTTP、Electron 或 React |

### 9.3 端到端基线

仓库提供固定本地测试页面，不依赖外部网站。第一条端到端流程固定为：

```text
navigate
→ wait for selector
→ input
→ click
→ get_text
→ screenshot
→ close session
```

每个平台记录：应用版本、Python/Electron 版本、CloakBrowser 版本、流程耗时、取消耗时、退出码和日志路径。

## 10. 工程质量门槛

每个阶段都必须通过：

- Ruff、mypy strict、pytest；
- ESLint、TypeScript、Vitest；
- OpenAPI 导出与前端生成类型检查；
- 本地测试页面端到端测试；
- Windows/macOS 的 sidecar、CloakBrowser 启动和关闭冒烟测试；
- 未保存编辑、失败运行、取消运行和浏览器异常退出测试。

任何新依赖都必须说明：使用场景、平台 wheel、打包影响、许可证和删除方案。不能因为迁移一个节点而复制 WebRPA 的全部 `requirements.txt`。

## 11. 后续执行顺序

主线架构完成后，按以下顺序开工：

1. 将本计划拆成独立实现计划：Studio 壳、自动化内核、CloakBrowser、基础 Web 节点、双窗口、项目接入；
2. 先完成 Studio 壳和 CloakBrowser 最小闭环；
3. 再迁移一个节点并完成 Windows/macOS 证据；
4. 以节点为单位持续扩展，不批量复制 WebRPA；
5. 完成基础 Web 能力后，再开始项目管理接入；
6. 项目管理接入完成后，再评估是否需要其他 WebRPA 能力。

本计划的成功标准不是复制 WebRPA 的目录或模块数量，而是用 AutoFlow 自己的架构稳定提供一组可测试、可停止、可跨平台运行的 CloakBrowser Web 自动化能力。

## 12. 当前实施计划（实体盘点后的执行顺序）

### 阶段 A：契约冻结

交付：`WEBRPA_ENTITY_INVENTORY.md`、节点迁移表、P0 配置快照、错误和日志事件约定。

规则：保留 WebRPA 的 `module_type`、配置字段、输入输出和默认值；只允许改变包边界、浏览器适配层和已确认排除能力。任何字段变更必须有源代码位置、行为差异和测试证据。

退出条件：P0 节点名单和首期排除名单冻结；不存在“先改名、以后兼容”的未记录决定。

### 阶段 B：Kernel 可运行闭环

交付：Workflow、Node、Edge、Variable、ModuleResult、ExecutionContext、ExecutorRegistry、AutomationKernel，以及 `open_page → click_element → input_text → wait → get_element_info` 黄金流程。

退出条件：不导入 `reference/WebRPA`；执行器只通过 `CloakBrowserRuntime`；节点失败、超时和变量传递有测试；注册表重复类型直接失败。

### 阶段 C：运行事件与 API

交付：Run、RunEvent、取消、超时、节点状态、日志和截图附件；FastAPI 工作流保存、加载、校验、运行和事件接口。

退出条件：一次运行内事件序号稳定；运行结束后资源清理；HTTP 层不包含执行器逻辑；内核测试不依赖 FastAPI fixture。

### 阶段 D：CloakBrowser 适配与 P0 浏览器节点

顺序：页面生命周期 → 元素定位/等待 → 输入与点击 → 下拉框/复选框/滚动 → 标签页 → iframe → 对话框 → 上传/下载 → 截图。

退出条件：固定本地测试页面覆盖导航、表单、异步元素、新标签页和 iframe；Windows 与 macOS 均完成启动、取消、关闭和异常退出证据。

### 阶段 E：Studio 编辑器

交付：React Flow 画布、P0 节点目录、配置面板、变量面板、运行控制、节点状态和日志面板。前端类型由同一份节点元数据生成或校验，不能再出现多处手工维护的节点列表。

退出条件：可以创建、保存、加载并运行一个 P0 黄金流程；编辑器不直接持有浏览器状态；运行状态来自后端契约。

### 阶段 F：录制、拾取与选择器测试

交付：元素拾取、选择器预览/测试、click/input/select/navigate 录制、selector hints 和可观测的自愈日志。

退出条件：录制结果能直接生成现有 P0 节点配置；自愈不会静默改变工作流；用户可以看到原选择器、候选选择器和采用原因。

### 阶段 G：P1 能力与 Manager 接入

只有阶段 A-F 全部通过后，才按清单逐项迁移数据处理、HTTP、文件、表格、数据库、触发器和调度能力。Manager 通过 application API 调用 Studio，不把项目、资源和分析逻辑放进执行器。

每个 P1 能力单独提交、单独记录来源和行为差异，并重新运行黄金流程；不进行“整目录搬迁”。
