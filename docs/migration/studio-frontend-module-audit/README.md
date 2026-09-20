# Studio 前端模块对照审计

日期：2026-09-13。目标代码基线：`dad1767`。参考版本：`WebRPA@5ccb900e8dcf1530aae66f676d87593c416c7ebb`。

## 最新范围约束（用户补充，2026-09-13）

本轮目标为 **Web 自动化节点及其工作台交互**，不追求 WebRPA 全部节点数量对齐，也不实施非 Web 节点差异。

- 保留：浏览器/标签页、网页导航、元素定位与拾取、页面操作与数据提取、网页截图、网页录制，以及支撑 Web 流程的条件、循环、变量、日志和 Debug。
- 不纳入：SAP、通用文件处理、Windows 桌面自动化，以及其他非 Web 自动化节点；手机自动化也不纳入本轮 Web 范围。
- 工作流保存/打开/导入导出、运行结果及网页截图文件仍属于工作台基础设施，不因排除“文件处理节点”而删除。
- 网页文件上传/下载按网页操作单独归类；本轮不据此扩展成通用文件系统处理能力。
- 本次仅收紧审计与后续实施范围，不新增、删除或隐藏业务节点。

以下 F01–F08 为此前源码发现记录，不再等同于全部待实现清单：**F03 的本地媒体能力不纳入本轮修复；F02 中 TTS、音乐、视频及本地图片节点的闭环不纳入本轮修复。** F02 的其余项按是否服务 Web 流程逐项核定。AI 面板属于已保留工作台交互的对照项，不据此增加 AI 节点能力。

## 结论

**尚不能称为已完成范围内的 WebRPA 前端功能复刻。** 主要编辑器和 Store 已迁入，缺口集中在应用入口装配、部分宿主交互、请求与事件的模拟闭环、异常场景覆盖。继续复制文件解决不了这些缺口。

本轮是源码审计，不修改业务实现。结论置信度：**高（下列直接源码证据）；完整功能等价性未知（未逐项运行全部动作表单）**。真实网页执行未接入是已授权的 Mock 阶段边界，不作为本轮“漏写执行器”问题。

## 方法与计数

1. 遍历冻结源码 `frontend/src`，逐个对应迁入清单，校验源文件哈希和目标文件存在性。
2. 对照原 App/main 与 StudioApp/入口 hook，查找丢失的应用级初始化和 UI 装配。
3. 对照全部迁入 Store 的文本差异，检查是否删掉动作或状态；对照 SocketService 的字面量事件订阅。
4. 追踪调用方 → API/事件适配器 → Mock 路由/事件生产方；查明空壳响应和实际链路缺口。
5. 逐项排除原版未接入组件、宿主替换及用户明确排除项，避免将文件差异当成功能差异。

可重复执行：`python3 docs/migration/studio-frontend-module-audit/inventory.py`。结果在同目录 `inventory.json`。

| 项目 | 本次结果 | 正确解释 |
|---|---:|---|
| 原版 src 文件 | 322 | 包括测试、CSS、图片及未使用文件 |
| manifest 映射 | 275 | 目标全存在，源哈希全部匹配；不表示修改后的语义相同 |
| 未列入 manifest | 47 | 必须分类；其中同名文件可能仍存在，见 JSON 的 sameNameTargets |
| 原 SocketService 字面量订阅 | 26 | 当前全部保留，另增 command_error |
| Mock 主文件直接生产的事件种类 | 8 | 仅统计 emitMockEvent 字面量；不含动态 AI 事件、连接事件，不能计算为覆盖率 |

检查覆盖源码入口、Store、事件适配及下表模块。未声称完成 472 个动作的逐字段/交互验收，也未把上一轮通过的测试数当作本轮完整性证明。

## 应优先补齐的缺口

路径默认相对仓库根目录。P1 表示保留功能的闭环缺失，P2 表示交互差异或范围边界未收口；不是生产事故评级。

### F01 / P1：AI 面板布局避让丢失

- 原版 `reference/WebRPA/frontend/src/App.tsx:534` 依照面板打开状态与宽度设置 `paddingRight`。
- 当前 `apps/desktop/src/renderer/app/StudioApp.tsx:41` 直接并列渲染编辑器和 AI 面板；`styles/autoflow.css:25` 无对应避让。
- `components/assistant/AIAssistantPanel.tsx:971` 仍是 `fixed top-0 right-0`。
- 后果：侧边 AI 面板覆盖原本应可见的编辑器右侧区域，宽度拖动也不会推动编辑区域。顶部 Mock 按钮替代了原浮动 AIAssistantButton，外观和交互入口也不相同。
- 修复/验收：恢复原版布局 Store 驱动的宽度避让及原入口；开关、拖宽、窄窗分别核验属性面板与 AI 面板共存。

### F02 / P1：交互型运行事件没有 Mock 请求—响应闭环

- `events.ts:608–673` 保留输入提示、TTS、JS、音乐、视频和图片请求消费者；`events.ts:86–121` 保留结果回传。
- `api/mock-server.ts:71` 的 tick 只发开始、日志、完成及少量结果事件，没有产生上述请求或等待其结果。
- 同文件 `:141` 的 `/events/commands` 除停止之外，对所有事件直接返回 success。没有校验待处理 requestId，也没有应用用户输入/JS/媒体结果。
- 后果：界面组件存在，但“运行节点 → 弹窗 → 用户操作 → 回传 → 后续运行”的交互无法通过正常 Mock 运行验证；未知事件也被确认成功。
- 修复/验收：增加有限的场景状态机和明确的命令允许列表，模拟成功/取消/失败/迟到结果；不需要实现真实浏览器执行器或真实 TTS。

### F03 / P1：媒体资源请求绕过注入传输，Mock 不能提供对应资源

- `components/ImageViewerDialog.tsx:36` 与 `VideoPlayerDialog.tsx:96` 将 `/api/system/local-file?...` 拼成媒体地址；DOM 的 src 请求不会经过 studioFetch。
- `api/config.ts` 指向 `http://autoflow-studio.mock`。它是传输识别用的虚拟域名，没有真实媒体服务器。
- 转换音频/视频/图片调用虽已换成 studioFetch，但 Mock 没有 convert-audio、convert-video、convert-image 路由。
- 后果：保留的本地媒体展示/转换流程无法完成，且虚拟 URL 会进入浏览器原生资源请求。
- 修复/验收：Mock 返回 Blob/Object URL 或已登记的内联资源；提供转换成功与失败样本。先补 F02 的请求触发，再验证播放、关闭、失败回传与 URL 清理。

### F04 / P2：自定义快捷键事件只剩前半段

- 原版 `App.tsx:505` 下发自定义全局热键并在重连时重发；`:524` 消费 `hotkey:custom_action`。
- 当前 `events.ts:819` 仍转发这个 DOM 事件，但 `hooks/useStudioIntegration.ts:25` 只处理窗口 keydown，没有订阅该事件或下发注册。
- 后果：编辑器聚焦时的自定义快捷键可走本地路径；后端/宿主发来的自定义热键事件没有动作消费者。不能把这两者算成同一个已完成能力。
- 修复/验收：恢复事件消费，宿主注册通过 AutoFlow 边界适配；Mock 注入事件验证动作仅触发一次，重连不重复注册。Windows 专属桌面动作仍按排除范围处理。

### F05 / P2：断线提示事件没有接收方

- `api.ts:52` 网络错误改为分发 `studio:connection-error`；全 renderer 搜索只有这一处，没有事件消费者。
- `api/event-client.ts` 有重连，不能替代操作失败提示。部分调用方有自己的错误 UI，因此不是“所有错误都不可见”。
- 后果：原统一连接提示被移除后，新的统一提示链路未完成；依赖这个回调的请求没有对应恢复入口。
- 修复/验收：接入 Studio 连接状态与非破坏性重试提示；离线保存、初次加载离线、SSE 断线分别验证，草稿不刷新丢失。

### F06 / P2：全局 Tooltip 行为没有迁入

- 原版 `main.tsx:10` 调用 installGlobalTooltip，`lib/globalTooltip.ts` 将 title 转为主题化提示并提供全局监听。
- 当前没有这个源模块/入口调用，普通 title 回到浏览器原生提示。
- 后果：全局提示的延迟、布局和视觉与 WebRPA 不一致。不是“完全没提示”。
- 修复/验收：迁入原逻辑并作用于 Studio 根区域；检查动态节点、悬浮工具栏与弹窗，避免跨主窗口污染。

### F07 / P1：Mock 缺少验证复杂编辑/调试交互所需的场景

- `api/mock-server.ts:71` 按节点数组推进；`:206` 只复制初值，`:207` 仅生成初始变量记录。
- 定位测试 `:242` 将所有非空选择器判为单匹配；相似元素 `:241` 永远返回空数组。
- 后果：可以展示基本开始/完成/暂停，但无法核验条件未选路径、循环重复节点、运行变量变化、零/多匹配、无效选择器、框架失败等前端状态。现有“断点能暂停”不代表 Debug 的完整交互已覆盖。
- 修复/验收：增加可选的确定性事件脚本与定位结果样本，覆盖这些 UI 分支；无需在 Mock 中重写 WebRPA 的业务执行引擎。

### F08 / P2：宿主设置边界没有统一处理，保留了无效按钮

- `components/GlobalConfigDialog.tsx:617` 仍展示“安全”；`:125/:129` 调用启用令牌与重新生成。
- `api.ts:488` 保留 securityApi，但 Mock 仅实现 `/security/status`（关闭状态），其余两个路由到 501；getAuthToken/setAuthToken 已因 AutoFlow 接管鉴权而置空/无操作。
- 后果：UI 仍承诺 WebRPA 独立服务的令牌管理，实际既未模拟也未映射到 AutoFlow。
- 修复/验收：明确其为 AutoFlow 管理，展示受控入口/说明；若要保留视觉交互样本，隔离为 Mock 设置，不能制造已修改正式鉴权的提示。这是宿主融合缺口，不能机械复制旧鉴权实现。

## 范围差异，需要单独记账

以下不是本轮自动认定要恢复的功能：

- 企业、发布、版本、工作流市场/打包以及 Windows 桌面控制：符合此前排除方向；不进入核心迁入缺陷。
- 手机自动化、SAP：`ModuleSidebar.tsx:1803` 一并隐藏。依照最新“只需要 Web 自动化节点”约束，不纳入本轮，不再作为待确认缺口。
- 计划任务及监控 URL 自动加载：原 App 包含 workflow/task_id 参数加载与补日志；新入口没有迁入。属于编排之外的调度/宿主入口差异，不能写成“原版没有”。
- AssistantWindow：原版支持独立助手入口；现在只有 Studio 内面板。是否需要独立窗口应单列范围；AI 面板布局缺失则已明确列 F01。

## 模块对照矩阵

| 模块 | 当前证据 | 状态/下一步 |
|---|---|---|
| 主画布、块视图、布局算法 | WorkflowEditor、BlockFlow、ELK 等源模块已映射 | 已迁入；未做全部动作实机等价声明 |
| 分组、便签、子流程及复制历史 | 核心 editor-store 与相关组件保留 | 已迁入；Store 未发现源动作整体删除 |
| 动作库、搜索、收藏/统计 | ModuleSidebar、moduleStatsStore 保留；分类过滤 | 已迁入；范围差异独立记账 |
| 属性表单及默认值/必填规则 | ConfigPanel、config-panels、lib 已映射 | 已迁入；472 项逐字段验收待做 |
| 保存、打开、导入导出 | Toolbar、API、Mock 本地持久化 | 基本接通；虚拟目录不是正式工作区 |
| Debug、断点、单步 | debugStore/nodeRunStore、Toolbar、事件保留 | 基本接通；F07 场景不足 |
| 日志、运行数据、变量追踪 | 消费器与组件保留 | 基本接通；批量及变化事件需补场景 |
| 浏览器、定位拾取 | 调用及 Mock 路由存在 | 基本接通；F07 定位分支不足 |
| 网页录制、生成节点 | 原录制组件及事件入口保留 | 基本 Mock 接通；不等于真实采集 |
| 输入提示、JS、媒体 | 组件、消费者、结果上报保留 | F02/F03 未闭环 |
| 自定义模块、资源库 | Store、CRUD、上传与 bundle Mock | 基本接通；Excel 正文解析为明确占位 |
| AI 对话、工具/权限/会话 | 相关 Store、组件、API 保留 | F01 布局差异；真实工具与模型未接入 |
| 设置、偏好、主题 | globalConfigStore/layoutStore 保留 | F04/F06/F08 待收口 |
| HTTP/SSE | 独立传输、序号补读、源订阅保留 | F02/F05；不能仅按事件名称算覆盖 |
| Electron/服务/工作区 | 独立 Studio HTML，主应用服务边界保留 | 工作区绑定仍是后续正式适配，Mock 存储不隔离正式工作区 |

## 已排除的误报

- 原版 DebugPanel、VariablePanel、DataPreviewPanel、ExecutionDetailsPanel 在源码中未找到其他生产模块的导入/渲染引用。不能要求仅因同名文件缺失就重新迁入；实际 UI 应以 Toolbar/日志等活跃链路核验。
- 源 scheduledTaskStore 是唯一未迁入的生产 Store。其余 11 个生产 Store 均有映射；逐个文本差异未发现动作整体删除。workflowStore 有迁移期历史修正，仍需独立回归，不能视为字节级复刻。
- 目录/浏览器配置并未彻底丢失同步：GlobalConfigDialog 中仍有未依赖 isOpen 的同步 effect。原 App 初始同步与重连顺序虽不同，本轮不凭入口删行将其列为确定缺陷。
- AI cancel Mock 本身只确认，但面板还会 abort 当前请求，Mock chat 检查信号。不能仅看 cancel 路由就宣称停止按钮无效。
- 所有 26 个原字面量 SocketService 订阅保留。真正的缺口在部分生产方及响应处理，不是接收器大面积漏拷。

## 建议下一轮修复顺序与验收门槛

1. 修入口装配：F01/F04/F05/F06/F08；每个问题一条可重复交互测试，不重构源组件。
2. 补 Web 范围内的交互协议：F02 中保留的输入/取消/JS 交互必须有 requestId 对应，未知命令不能成功；排除本地媒体节点及 F03，不为审计差异补写非 Web 能力。
3. 补 Mock 场景：F07；重点是模拟后端契约与事件序列，不写第二个完整执行器。
4. 再按动作类别验收表单字段、默认值、显隐、序列化及变量引用。保留原目录模型，用差异表逐项销账。

本轮没有运行真实浏览器/打包验收，没有复用上一轮测试结果宣称上述缺口已修复。完成标准应是每个保留模块具有入口、Store 动作、请求/事件、成功和失败场景，以及独立的可重复证据。

## 附：未映射文件清单（47 项）

此表只列迁入清单差异，不自动认定为遗漏；同名存在也不代表语义相同。

| 源路径（frontend/src/） | 当前同名文件 |
|---|---|
| `App.tsx` | 无 |
| `AssistantWindow.tsx` | 无 |
| `assets/icons/gesture-icon.svg` | 无 |
| `assets/icons/variable-tracking.svg` | 无 |
| `assets/react.svg` | 无 |
| `components/ai-assistant/AIAssistantButton.tsx` | 无 |
| `components/scheduled-tasks/NotificationConfigEditor.tsx` | 无 |
| `components/scheduled-tasks/ScheduledTasksDialog.tsx` | 无 |
| `components/scheduled-tasks/ScheduledTasksPage.tsx` | 无 |
| `components/scheduled-tasks/StatisticsPanel.tsx` | 无 |
| `components/scheduled-tasks/TaskCreateDialog.tsx` | 无 |
| `components/scheduled-tasks/TaskEditDialog.tsx` | 无 |
| `components/scheduled-tasks/TaskLogsDialog.tsx` | 无 |
| `components/ui/card.tsx` | 无 |
| `components/ui/color-field.tsx` | 无 |
| `components/ui/hierarchical-image-selector.tsx` | 无 |
| `components/ui/progress.tsx` | 无 |
| `components/ui/table.tsx` | 无 |
| `components/ui/tabs.tsx` | 无 |
| `components/workflow/DataPreviewPanel.tsx` | 无 |
| `components/workflow/DebugPanel.tsx` | 无 |
| `components/workflow/DesktopRecorderPanel.tsx` | 无 |
| `components/workflow/EnterpriseDialog.tsx` | 无 |
| `components/workflow/ExeUiDesigner.tsx` | 无 |
| `components/workflow/ExecutionDetailsPanel.tsx` | 无 |
| `components/workflow/MouseCoordinateOverlay.tsx` | 无 |
| `components/workflow/PackageDialog.tsx` | 无 |
| `components/workflow/PhoneMirrorDialog.tsx` | 无 |
| `components/workflow/PhoneScreenshotCropper.tsx` | 无 |
| `components/workflow/PluginMarketPanel.tsx` | 无 |
| `components/workflow/ScreensaverDialog.tsx` | 无 |
| `components/workflow/ScreenshotSelector.tsx` | 无 |
| `components/workflow/SponsorDialog.tsx` | 无 |
| `components/workflow/UpdateDialog.tsx` | 无 |
| `components/workflow/VariablePanel.tsx` | 无 |
| `components/workflow/VersionHistoryPanel.tsx` | 无 |
| `components/workflow/WorkflowErrorBoundary.tsx` | 无 |
| `components/workflow/WorkflowHubDialog.tsx` | 无 |
| `components/workflow/config-panels/IframeModuleConfigs.tsx` | 无 |
| `hooks/use-toast.ts` | 无 |
| `lib/__tests__/helpers/addNodeParserBaseline.json` | 有，详见 inventory.json |
| `lib/globalTooltip.ts` | 无 |
| `lib/moduleSearchAudit.ts` | 无 |
| `lib/motion.ts` | 无 |
| `main.tsx` | 无 |
| `services/version.ts` | 无 |
| `store/scheduledTaskStore.ts` | 无 |
