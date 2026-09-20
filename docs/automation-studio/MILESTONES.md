# AutoFlow Automation Studio 里程碑计划

- 基线：WebRPA `5ccb900e8dcf1530aae66f676d87593c416c7ebb`
- 目标平台：Windows x64、macOS Intel、macOS Apple Silicon
- 产品边界：独立 Studio 先行，Manager 后接入；CloakBrowser 是唯一浏览器运行时
- 规则：WebRPA 只作为能力、行为和交互参考，不作为 AutoFlow 运行时 import
- 当前状态：M0 盘点已完成；自动化后端实现暂缓，主框架完成后从 Studio 前端里程碑开始

## 总体验收原则

一个里程碑只有同时满足“功能、契约、架构、测试、证据”五项，才算完成。

1. **功能**：用户路径或后端能力按定义可运行。
2. **契约**：保留 WebRPA 的 `module_type`、配置字段、输入输出、默认值和失败语义；变更必须有记录。
3. **架构**：依赖方向符合 AutoFlow 目录边界，执行器不依赖 React、Electron、FastAPI 路由或 `reference/WebRPA`。
4. **测试**：单元、契约、集成或端到端测试覆盖里程碑列出的场景。
5. **证据**：保存测试命令、结果、截图/日志、版本信息和迁移记录。

## M0：基线、实体盘点和范围冻结

### 目标

把 WebRPA 的实体、节点、配置和排除范围变成可审查的清单，防止前端开发过程中遗漏后端核心能力，也防止无计划地复制全部模块。

### 交付物

- `docs/automation-studio/WEBRPA_ENTITY_INVENTORY.md`
- `docs/automation-studio/WEBRPA_CAPABILITY_MATRIX.md`
- `docs/migration/AUTOMATION_KERNEL.md`
- P0/P1/后续/排除节点名单
- 每个迁移项的 `source_path/source_commit/target_path/action/changed_behavior/verification`

### 必须验收

- [ ] 能从固定 commit 解析出 WebRPA 的模型实体和唯一 `module_type` 清单。
- [ ] 重复注册的类型被合并标记，不能被误计为独立能力。
- [ ] 首期 P0 节点名单已冻结。
- [ ] OCR、验证码、桌面、Android、媒体、平台专用和第二浏览器运行时被明确排除。
- [ ] 文档没有把 WebRPA 目录复制当成迁移目标。
- [ ] AutoFlow 代码中不存在对 `reference/WebRPA` 的运行时 import。

### 完成证据

- 盘点脚本输出唯一类型数量和重复声明数量。
- `rg` 依赖边界检查结果。
- 范围评审记录。

### 不允许混入

- 不迁移新节点。
- 不设计 Manager 功能。
- 不引入 WebRPA 的重量级依赖集合。

## M1：Studio 前端可见骨架

### 目标

尽快得到可操作的产品表面，同时使用真实工作流文档和节点定义，不做只有截图效果的静态 Demo。

### 交付物

- Studio 页面布局。
- 模块侧栏、画布、配置面板、变量面板、运行工具栏、日志面板。
- P0 节点目录的第一版。
- React Flow 与 AutoFlow WorkflowDocument 的转换层。
- 本地 mock automation adapter。

### P0 前端节点

`open_page`、`click_element`、`input_text`、`wait`、`get_element_info`、`set_variable`、`condition`、`loop`、`screenshot`。

### 必须验收

- [ ] 可以从节点目录拖入节点。
- [ ] 可以连线、移动、选中、删除和复制节点。
- [ ] 配置面板可以编辑 P0 节点字段并显示默认值。
- [ ] 工作流可以序列化为 AutoFlow 文档，再从文档恢复画布。
- [ ] 变量引用在界面上有明确显示。
- [ ] Mock 运行会产生节点开始、成功、失败和运行结束状态。
- [ ] 失败节点能在画布和日志中定位。
- [ ] 刷新页面后可以恢复最近一次编辑文档，或明确提示未保存状态。
- [ ] 前端不直接持有浏览器 Page、Playwright 或 CloakBrowser 对象。

### 完成证据

- Vitest 组件测试。
- 一条从拖拽到保存再到 Mock 运行的浏览器测试或录屏。
- 序列化前后 JSON 快照对比。

### 不允许混入

- 不接真实浏览器。
- 不实现 Manager 项目列表。
- 不复制 WebRPA 的全部配置组件。

## M2：节点定义和前后端契约中心

### 目标

消除模块类型、配置面板、后端校验和执行器路由的多处维护，建立单一节点定义来源。

### 交付物

每个 P0 节点至少包含：

- `module_type`
- `display_name`
- `category`
- `config_schema`
- `input_schema`
- `output_schema`
- `runtime_requirements`
- `ui_metadata`
- `executor`
- `status`

### 必须验收

- [ ] 前端节点目录可以从节点定义生成或校验。
- [ ] 后端注册表中的 P0 执行器都有节点定义。
- [ ] 节点定义中的字段与 WebRPA 基线字段逐项对照。
- [ ] 缺少必填字段、字段类型错误和非法值能在保存前被发现。
- [ ] 变量引用规则在前端和后端一致。
- [ ] 同一 `module_type` 只能注册一个规范执行器。
- [ ] 未实现节点在前端显示不可运行状态，不能被伪装成已完成。

### 完成证据

- 节点定义快照。
- 配置校验测试。
- 注册表重复类型测试。
- 前端目录与后端节点定义数量对照报告。

### 不允许混入

- 不为了新命名而改动 WebRPA 的 `module_type`。
- 不允许前端单独增加后端不存在的配置字段。

## M3：Automation Kernel 和 Mock-to-Real 替换

### 目标

用真实后端替换 Mock，建立可独立运行的自动化执行内核，但暂时可以使用测试浏览器适配器。

### 交付物

- WorkflowDocument 校验。
- `ModuleExecutor` 协议。
- `ExecutionContext`。
- `ExecutorRegistry`。
- `AutomationKernel`。
- Run、RunEvent、NodeResult/ModuleResult。
- 取消、超时、失败停止和节点结果。

### 必须验收

- [ ] `open_page → click_element → input_text → wait → get_element_info` 可顺序执行。
- [ ] 变量可以从工作流定义进入执行上下文，并被后续节点读取。
- [ ] 节点失败会停止后续节点，结果包含节点 ID、类型和错误。
- [ ] 超时会产生明确的 timed-out 结果。
- [ ] 用户取消不会留下运行中的任务。
- [ ] 单次运行的事件序号严格递增。
- [ ] 运行结束后上下文和临时资源可以释放。
- [ ] Kernel 单元测试不依赖 FastAPI、Electron 或 reference/WebRPA。

### 完成证据

- Kernel 单元测试。
- Mock browser golden flow。
- 取消、超时、未知节点和配置错误测试。
- 事件序列快照。

### 不允许混入

- 不在执行器里创建浏览器。
- 不在 Kernel 里放项目管理逻辑。
- 不实现分布式调度。

## M4：FastAPI Automation API

### 目标

将 Kernel 通过稳定 HTTP 契约提供给 Studio，并保持 HTTP 层与执行器分离。

### 交付物

- 工作流创建、读取、更新接口。
- 节点定义接口。
- 工作流校验接口。
- 运行、取消、查询运行状态接口。
- RunEvent 拉取或流式接口。
- 结构化错误响应。

### 必须验收

- [ ] 未认证请求不能访问受保护的自动化 API。
- [ ] 无效工作流返回字段级校验错误。
- [ ] 运行接口返回 run ID，而不是阻塞到整个流程结束。
- [ ] 状态接口能观察 queued/running/succeeded/failed/cancelled/timed_out。
- [ ] 事件接口保持单次运行内顺序。
- [ ] 重复取消是幂等的。
- [ ] API 层不 import 具体浏览器实现。
- [ ] OpenAPI 可生成前端类型或被契约测试校验。

### 完成证据

- FastAPI contract tests。
- OpenAPI 快照。
- 错误响应样例。
- 运行、取消和事件流测试。

## M5：CloakBrowser 运行时和 P0 浏览器能力

### 目标

将测试浏览器适配器替换为真实 CloakBrowser，并完成首期浏览器能力。

### 实施顺序

1. session 启动、profile、代理和关闭。
2. 页面打开、复用、关闭、刷新、前进、后退。
3. selector 格式化、等待和元素诊断。
4. 点击、输入、悬停、下拉、复选框、滚动。
5. 标签页切换和新标签页跟进。
6. iframe 进入和返回主页面。
7. 对话框、上传、下载和截图。

### 必须验收

- [ ] 所有 P0 浏览器执行器只调用 `CloakBrowserRuntime`。
- [ ] 执行器不直接 import Playwright。
- [ ] CloakBrowser profile 和代理配置由 runtime 统一管理。
- [ ] 浏览器异常退出后状态被清理。
- [ ] 页面、标签页和 iframe 状态不会泄漏到下一次运行。
- [ ] 元素不存在、不可见、selector 错误和页面加载失败有可行动诊断。
- [ ] 上传、下载和截图路径符合 Windows/macOS 规则。
- [ ] Windows 和 macOS 完成启动、运行、取消、关闭冒烟测试。

### 必须通过的黄金流程

- 页面导航和页面加载等待。
- 普通输入框和密码输入框。
- 点击后打开新标签页并切换。
- iframe 内元素操作并返回主页面。
- 异步元素等待。
- 读取文本、value、href、src 和自定义属性。
- 失败时记录节点、selector、URL、截图和错误原因。

## M6：真实 Studio 运行控制和调试

### 目标

让 Studio 连接真实 API，形成“编辑、运行、观察、停止、诊断”的完整产品闭环。

### 必须验收

- [ ] Studio 可以保存并加载真实工作流。
- [ ] 点击运行后显示 run ID 和实时节点状态。
- [ ] 当前执行节点在画布中高亮。
- [ ] 日志面板显示系统日志、节点日志和错误详情。
- [ ] 可以取消运行，并在 UI 中看到 cancelled 状态。
- [ ] 运行失败时可以定位到节点和配置字段。
- [ ] 重复点击运行不会创建意外的并发运行。
- [ ] 浏览器关闭或 sidecar 退出时，UI 显示结构化失败状态。

### 完成证据

- Studio-to-FastAPI integration test。
- 真实黄金流程录屏或截图。
- 失败、取消、重试和 sidecar 异常证据。

## M7：录制器、元素拾取和选择器测试

### 目标

在手工流程稳定后，迁移录制和拾取能力，并确保其输出直接生成 P0 节点配置。

### 必须验收

- [ ] 元素拾取能返回 selector、tag、文本、属性、矩形和 selector hints。
- [ ] 拾取结果能直接填充 click/input/select 节点配置。
- [ ] 录制至少支持 click、input、select、check、navigate。
- [ ] 连续重复事件会被合理合并，不生成不可执行节点。
- [ ] 选择器测试能显示命中数量和目标摘要。
- [ ] 选择器自愈记录原 selector、候选 selector、采用原因和节点 ID。
- [ ] 自愈可以关闭，且不会静默修改用户工作流。
- [ ] 录制和拾取失败不会破坏当前编辑内容。

## M8：P1 能力迁移

### 目标

在 P0 稳定后按能力域扩展，而不是按 WebRPA 文件目录批量复制。

### 推荐顺序

1. 数据结构和字符串补充。
2. HTTP 请求和文件操作。
3. 表格和数据提取。
4. 数据库。
5. 触发器和调度。
6. 自定义模块。

### 每个 P1 能力域必须验收

- [ ] 独立节点定义和配置校验。
- [ ] 独立执行器和运行时依赖说明。
- [ ] 独立迁移记录。
- [ ] 正常、错误、超时、取消测试。
- [ ] Windows/macOS 依赖和打包检查。
- [ ] 不会把排除能力或第二浏览器运行时带入核心包。

## M9：Manager 双窗口接入和跨平台发布验收

### 目标

在 Studio 独立运行稳定后接入 Manager，而不是让 Manager 反向侵入 Kernel。

### 必须验收

- [ ] Manager 可以创建或打开 Studio 会话。
- [ ] Studio 可以独立窗口运行。
- [ ] Manager 可以看到运行状态、日志摘要和最近结果。
- [ ] Manager 与 Studio 通过后端契约同步，不共享完整 React state。
- [ ] 同一 automation 同时只有一个有效 Studio 会话。
- [ ] 窗口关闭、sidecar 关闭和浏览器关闭都能正确清理。
- [ ] Windows 和 macOS 完成安装包、启动、升级前后的数据目录和退出测试。
- [ ] 首期排除能力在 UI 和 API 中返回结构化 unsupported 状态。

## 里程碑之间的硬门槛

- M0 未完成：不能扩展节点。
- M1 未完成：不能接真实浏览器。
- M2 未完成：不能继续增加前端配置面板。
- M3 未完成：不能开始 Manager 接入。
- M5 未完成：不能宣称首期网页自动化可用。
- M6 未完成：不能开始批量迁移 P1 节点。
- M7 未完成：不能宣称录制器或选择器自愈可用。

## 最终首期发布门槛

首期 Automation Studio 必须同时满足：

- P0 黄金流程全部通过。
- Windows 和 macOS 均完成启动、运行、取消和关闭验证。
- `reference/WebRPA` 不在运行时依赖图中。
- CloakBrowser 是唯一浏览器运行时。
- 工作流、运行、日志和错误契约稳定。
- Studio 可以独立运行，Manager 接入不影响自动化核心。
- 所有首期未实现能力都能被准确识别为 unsupported，而不是静默失败。
