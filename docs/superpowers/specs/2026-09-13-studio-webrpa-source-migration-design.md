# Studio 改为 WebRPA 源码迁入：设计规格

> 2026-09-13 修订：用户现在要求制定迁入方案，并强调架构、技术栈和开发习惯贴合 AutoFlow。本稿替代此前“整块 webrpa 子目录 + Socket.IO”建议。产品方向和工程约束 confirmed，具体迁入设计 proposed；本轮只更新文档，当前实现仍是[独立空窗口](../../migration/studio-removal.md)。

- 日期：2026-09-13。
- 状态：**方向 confirmed；具体架构 proposed，待确认后实施**。依据用户本轮要求，停止 M6 自定义录制扩展，完整迁入范围内的 WebRPA UI、前端交互和后端业务逻辑。
- 源基线：`reference/WebRPA@5ccb900e8dcf1530aae66f676d87593c416c7ebb`；目标基线：清除旧 Studio 后的 AutoFlow `25273d5`，数据库 `0008_workflow_debug`。
- 本文替代“重新定义节点、状态模型、控制流和 AutoFlow 风格编辑器”的后续开发路线。历史 M1–M5 保留为已实现版本和回归证据，不再作为新 Studio 的产品行为规范。
- 用户追加授权：可以完全重构，弃用此前编写的 Studio 代码。新方案不再要求兼容旧编辑器、旧节点协议或旧执行引擎；旧源码通过 Git 归档，已有数据保留原文。
- [详细里程碑计划](../plans/2026-09-13-studio-webrpa-source-migration-implementation.md)采用 R0–R8，替代原粗粒度 S0–S4；操作步骤和退出条件以该计划为准，实际状态统一记在[验收台账](../../migration/studio-webrpa-migration-validation.md)。源码复用和工程归位判断置信度高；受管共享会话适配置信度中，视觉、交互、浏览器兼容及跨平台结果尚未实测。

## 1. 产品基准

新 Studio 的默认行为取自冻结源码。直接迁移组件、状态管理、配置表单和业务算法；不根据截图重新绘制，不把原节点翻译成现有少量自定义节点后再执行。

原样保留范围内的布局、样式、图标、文案、菜单位置、面板伸缩、图画布/模块条双视图、选择/拖放/连线、快捷键、撤销重做、分组便签、变量、导入导出、日志结果、录制拾取和调试交互。原有子流程、错误策略与重试不再因旧 M1–M6 排期而继续删减。品牌署名及许可文件保留来源记录；AutoFlow 宿主窗口标题可使用 AutoFlow 名称。

此前用户明确排除的企业管理、Windows 桌面/系统控件控制、发布和版本管理继续排除。远程企业协同属于排除范围；工作流文件保存/打开/导入/导出、撤销历史、运行诊断不属于版本发布管理，必须保留。Windows 上运行网页自动化仍属于目标。

原项目办公、媒体、Android、第三方平台等专项模块不能根据目录名字自动算作工作台核心，也不能被一并标成已迁入。第一批按 UI 入口和真实执行器建立逐项清单，标记“核心纳入 / 用户排除 / 专项待定”；核心纳入项不得用“后续再说”替代验收。专项未纳入时不安装其全部运行时依赖，不留下能点击却无实现的动作。

## 2. 原文件与迁入主体

以下为已静态核对的入口；实施时沿 imports 补全依赖闭包，记录每个迁入文件的源路径、源提交和有意修改。

| 原路径（相对于 reference/WebRPA） | 处理方式 |
| --- | --- |
| `frontend/src/components/workflow/WorkflowEditor.tsx`、`ModuleNode.tsx`、`ModuleSidebar.tsx`、`ConfigPanel.tsx` | 迁入原组件和范围内配置面板，保持事件处理及原视觉；不套用现有 NodeInspector 表单 |
| `BlockFlowView.tsx`、`blockFlowModel.ts`、`GroupNode.tsx`、`NoteNode.tsx`、`QuickModulePicker.tsx` | 保留双视图及原编辑模型，不重做控制块算法 |
| `Toolbar.tsx`、`LogPanel.tsx`、`DebugBar.tsx`、`RecorderPanel.tsx`、`LocalWorkflowDialog.tsx` | 保留原操作流程，通过服务边界接入真实后端；仅移除明确排除入口 |
| `frontend/src/store/{workflowStore,layoutStore,debugStore,nodeRunStore,globalConfigStore,moduleStatsStore}.ts` | 迁入编辑/布局算法及需要的运行投影；globalConfigStore 筛选范围内工作台行为/视图设置，宿主资源与凭据由 AutoFlow 提供；不维护两套编辑历史 |
| `frontend/src/types/`、`lib/`、`components/ui/`、`index.css` 中的工作台依赖 | 连同原类型、布局工具、控件和样式迁入，保留已有库；按真实依赖添加包 |
| `frontend/src/services/{api,socket,config}.ts` | 保留被 UI 使用的服务方法与事件语义，适配 AutoFlow 地址、鉴权、错误和工作区 |
| `backend/app/models/workflow.py`、`services/workflow_parser.py` | 保留文档字段及原图解析规则，不转换成 M4 配对控制块计划 |
| `backend/app/services/workflow_executor.py`、`executors/base.py`、范围内执行器 | 迁移执行调度、配置解释、控制流、错误策略、子流程、调试及结果逻辑 |
| `backend/app/services/variable_manager.py`、`utils/safe_expr.py` | 迁移变量和表达式语义，连同对应测试；不套用 M4“仅可视化规则、禁止表达式”的限制 |
| `backend/app/services/browser_engine.py`、`recorder.py`、`element_picker/` | 迁移页面、录制、拾取算法及会话协作，替换浏览器启动和宿主资源操作 |
| `backend/app/api/workflows.py` 及相关录制/拾取路由 | 保留调用语义，放入 AutoFlow HTTP adapters；存储与进程操作交给现有相应层 |

不直接启动整个 WebRPA 服务作为第二个后台进程，不让生产构建导入 `reference/`，也不先全面拆解、重命名原业务算法。迁入源码属于 AutoFlow 正式构建，来源许可文件与修改清单随构建保留。

## 3. 宿主与目录

前端直接放入 `apps/desktop/src/renderer/domains/workflows/`，按现有 `components/`、`hooks/`、`pages/`、`tests/` 落位。原工作台专用控件归 `components/controls/`，节点表单归 `components/config-panels/`；编辑 Store、纯模型和请求分别使用领域内 `editor-store.ts`、`model.ts`、`api.ts`、`events.ts`。按实际职责拆分，不预建无消费者的框架层。来源通过文件署名和迁移清单记录，不保留 `workflows/webrpa` 平行应用，也不复制原全局 App/store/services。

保留原编辑 Store 的图操作、选择、复制粘贴、双视图和历史算法，使用领域内 Zustand；不重写成一套 hooks 历史实现。服务端列表、Profile、历史运行和分页结果进入现有 TanStack Query，打开文档时显式建立编辑草稿，查询刷新不能覆盖草稿。实时状态只有一个事件接收入口，Store 只维护界面所需投影，不与 Query 同时维护两份权威数据。切工作区才重建编辑会话；同工作区服务重连不销毁草稿。

不整份迁入原 globalConfigStore，它包含浏览器及其他模块的凭据/配置。保留范围内的工作台行为配置和视图偏好；宿主资源和凭据经 AutoFlow 服务取得。自动保存、覆盖确认/副本保存、自定义快捷键、运行后关闭浏览器等逐项登记目标配置归属，不能因不是视觉设置而删除。原 autoCloseBrowser 并非现有 Profile 字段，应保留为工作台会话策略；原文件副本保存映射到 SQLite 文档副本时需核对同名、标识及脏状态行为。原 Store 中直接导入 socket 等 IO 副作用移到 hook/api/events 装配，原编辑动作本身尽量不改。

建议同一次 renderer 构建增加独立 `studio.html` 入口，原 WebRPA CSS 只进入这个文档，主应用 CSS 不进入 Studio。两个窗口共用 main/preload 和 sidecar。调整现有固定 Studio URL/构建文件与注册窗口主 frame 校验，保留窗口复用、最小化恢复、关闭重开和工作区协调。不得通过全局覆盖 AutoFlow CSS 来追求相似，也不把所有 `@/` 导入指向宿主共享组件。

后端继续使用 `apps/backend/src/autoflow`：纯模型、解析和变量规则归 `domain/workflows`；执行调度和上下文归 `application/workflows`；网页执行器、录制拾取归 `providers/browser`；数据库、文件和 worker 归各自 infrastructure；HTTP/事件归 adapters。按源文件职责落位，不把整份 WebRPA app 包塞进某一层。迁移路径不等于重写实现；每个内部算法的改动需要具体原因与测试。

保留 AutoFlow Profile、CloakBrowser 内核、代理凭据、工作区 SQLite、文件适配器和进程树监管。原配置面板与 Profile 的交集逐字段映射；确需替换原浏览器管理入口时，保持原对话框操作位置并明确展示实际 Profile。不得仍显示 Edge/Firefox 已选中却偷偷启动另一内核，也不得出现两套互相覆盖的启动配置。


### 技术栈与控件复用

| 部分 | 迁入规则 |
| --- | --- |
| Electron / React / TypeScript / Vite / Tailwind | 继续当前工程及锁文件版本，不复制原 package.json，不降级或另建构建系统 |
| React Flow / Zustand / ELK | 原画布、编辑状态和布局算法有直接消费者时加入；限定 workflows 领域，不替换主应用现有状态层 |
| shadcn / Radix / 共享 UI | 现有控件视觉和行为等价时复用；原 VariableInput、NumberInput、菜单交互等保留为工作台领域控件，复用 Radix primitive 和共享工具。不能用当前 h-10 黏土色 Button 机械替换原 h-8 功能色 Button |
| RHF / Zod | 新增宿主配置对话框按现有提交模式使用；原节点表单的即时更新、补全和撤销粒度保留，不统一改为 submit/blur，不另定义一套节点默认值 |
| 图标与其他依赖 | Studio 可局部保留原 Lucide 以保证形状一致；宿主保留 Phosphor。其他包按真实调用闭包引入，不装整套办公/AI/企业依赖 |
| 前端服务数据 | 使用现有 ApiProvider / TanStack Query / 共享客户端；不复制 axios、localStorage token、自建全局重连弹窗 |
| 后端与存储 | Python 3.11 / FastAPI / Pydantic / SQLAlchemy / SQLite / Alembic / PyInstaller 沿现有工程；CloakBrowser 使用现有 Profile 与启动参数适配 |

一致性要求作用于代码职责、接口、依赖与验证；Studio 的可见 UI 仍以 WebRPA 为基准。共享组件与原控件不等价时，保留领域控件并记录原因，不顺手重画页面。

### 后端拆分边界

原 parser、变量解释、分支/循环/子流程和错误策略保留实际调用链，不恢复已删除的配对控制块编译器，也不把原图强行限制成顺序链。工作区单次活跃运行与原图内部调度是不同层面的约束。

原 ExecutionContext 混合运行变量、控制信号和 Page/Frame 操作：变量与控制状态归 application，页面定位/操作归 provider；仅在真实 IO 边界注入端口。原 API 内存字典、源码相对路径、直接写文件、反向 import app.main/app.api 的调用分别移到仓储、文件、受控 UI 请求和事件适配。不要给每个纯函数建立接口或搭通用插件平台。

原变量管理类和 ExecutionContext.resolve_value 不因名字相似就合并；先用原测试和真实调用路径固定不同的解释行为。缺省参数与显式输入继续按原配置契约处理，不在迁移中任意改名、改单位或统一默认值。

## 4. 浏览器与执行会话：明确替换旧约束

源码证据：`executors/basic.py` 的打开页面逻辑优先复用 `browser_engine` 的共享 context；`services/recorder.py` 同样读取共享 context。因此，“每次运行必开独立浏览器、录制/拾取必须关闭后才允许运行”不能继续作为新 Studio 的固定产品规则。

建议一个工作区 Studio 会话持有一个受监管 worker，原引擎的共享浏览器状态局限在该 worker 内。打开浏览器、拾取、录制、执行和 Debug 使用原前端/后端的状态转换；浏览器是否复用、执行后是否自动关闭按已核实的原配置处理。工作区不同时接受两次流程运行；同一次流程内部保留原调度和并行能力，录制/拾取与运行按核验后的会话状态协调。共享会话不代表可以边录制边并发运行。先核实原浏览器生命周期选项和停止后的实际行为，再固定会话状态表；不得为适配 worker 擅自改变这些选项。

父进程管理资源锁、工作区归属和清理。浏览器保持打开期间继续持有 Profile/内核使用锁；执行停止与浏览器关闭分别按原行为完成，关闭会话/退出/换区最终必须清理受管进程后释放占用。原进程全局变量不得跨工作区复用；崩溃后不得自动重放动作。凭据仅通过受控启动通道提供，不进入文档、日志或录制文件。

重新接入“先处理未保存文档，保存成功才离开；取消或保存失败保留现场”的保护。清空时旧 Studio 握手已经移除，需要在现有窗口/设置/工作区机制上按新文档和会话接入，不能写成现成能力已具备。不得照搬原 Toolbar 的 reload/close 绕开这些保护。

## 5. 数据和服务兼容

采用原前端保存/导出模型及其原有后端转换，保留 `moduleType`、`data`、端口、组关系、配置名和变量语法。前端 React Flow `type` 与后端执行类型不一定相同，必须复用原转换代码，不能直接混用两种模型。新格式使用明确的来源/格式标识与存储元数据包装，原 payload 不强塞进 M1–M5 的 schemaVersion 2 模型。

持久化采用明确字段投影，不直接把原 `exportWorkflow()` 的 `...node` 全部写库。保留节点配置、连线/端口、分组、尺寸、位置、便签及恢复所需信息；排除 selected、dragging、DOM 测量缓存和运行高亮等瞬态。服务 DTO 从 OpenAPI 生成，本地仅补编辑投影类型，不再手写第二份 wire contract。

**不能假设所有位置都是执行无关数据。** 原 `workflow_executor.py` 在分组/子流程处理中用位置、宽高识别成员，部分无入口情况还按 y/x 排序。迁入必须保存这些必要几何，并在执行快照中固定；可在边界用原算法解析为明确成员和入口，但不得改变用户观察到的分组语义。对应测试覆盖移动组/节点、尺寸、显式连线与无入口回退。将布局与文档分开存储不等于可以删除布局的业务含义。

原 Toolbar 的运行路径先 create/update 执行文档。须按原真实调用区分“提交执行快照”与“用户文档保存”的关系；不能把废弃 M2 的“运行必不保存”规则自动带入。保存按钮、运行按钮和未保存状态需要原版操作轨迹验收。

新文档写入当前工作区 SQLite，使用增量迁移；文档原文、标识、名称、修改时间及 revision 可在仓储包装层维护。继续提供原子保存和并发冲突保护，禁止覆盖写文件取代工作区存储。导入/导出是原工作台能力，与工作区内实际存储方式分开。

现有 M1–M5 文档和历史运行保持原始数据，不强制新编辑器兼容它们，不为旧 `timeoutSeconds`、`framePath` 或配对控制图编写双引擎适配。源格式标识隔离新文档；旧数据在迁移前提供可核验的备份/导出，不能伪装为可直接导入 WebRPA 的文件。旧版本可通过 Git 检查点找回；新产品只保留一套 Studio。将来确实需要迁移某条旧流程时，再单独验证转换，不作为本次源码迁入的前置门槛。

采用 AutoFlow 已有的认证 HTTP 命令和 SSE 事件模式，不默认引入 Socket.IO。保留原事件含义和 UI 响应，把服务边界替换为 `shared/api/client.ts`、生成类型和领域 `events.ts`。原 Debug 的 resume/step/breakpoints 已是 HTTP，执行器也有事件回调，因此网络协议替换无需重写调试算法。涉及输入提示、脚本结果等反向交互，逐项登记为有类型的 HTTP 确认命令，不遗漏双向动作。

工作流事件需要自己的序号、持久化补读和去重；结果/诊断的大值使用文件引用与分页，不能把整个变量表反复放进 SSE 或进程消息；复用 SSE 读取和鉴权，不直接复用容量为 1、会覆盖旧快照的 KernelEventBroker 作为日志队列。当前旧工作流 SSE 已删除，无兼容接口需要维持。后端应用层只调用事件回调，HTTP/SSE 传输留在 adapters；所有控制命令使用稳定 ID，响应丢失查询原命令，不能自动重复单步或网页动作。

HTTP 服务方法优先沿用原调用语义；命名空间放入现有 workflows API 范围，在动态文档路由前注册。具体 DTO 和路由清单在第一切片按真实调用闭包冻结，使用 OpenAPI 生成类型。鉴权、DTO 和错误序列化由 adapter 处理；revision 比较、保存事务和命令去重由 application/仓储原子保障；停写复用现有 bootstrap middleware/QuiesceGate。不要求 UI 组件理解资源锁和数据库事务。

## 6. 允许的优化和验收依据

迁入阶段允许：导入路径/包边界调整、宿主浏览器与存储适配、明确排除功能裁剪、有复现证据的缺陷修复。其他交互、默认值、流程语义修改先记录差异，不以“更干净”作为重写依据。

已静态核实的例子：原 `workflow_executor.py` 找不到执行器时返回成功并跳过。新版本必须明确报不支持，不把此行为当成熟能力复制。原 `workflowStore.ts` 的 `HistorySnapshot` 仅包含 nodes/edges/name；涉及变量的撤销是否丢状态，需要用原操作路径复现后确定修复。原测试 README 说明部分外部浏览器依赖使用 mock/skip，不能据此宣称全部真实场景已验证。

每条验收对照同一冻结版本、同一流程输入和受控网页。视觉对照固定视口、缩放、面板状态和字体，核对截图；动态时间等非确定内容单独屏蔽，排除入口变更逐项记录。交互核对鼠标/键盘操作轨迹、文档前后状态及撤销结果。执行核对节点顺序、分支、变量、网页副作用、错误和资源归属，不只看按钮状态。

最终交付必须包含：原 UI 的正式窗口、真实存储、手动编排运行、原录制生成并独立重放、Debug/日志/结果、全部核心清单通过、无占位执行器，以及宿主保存/离开/工作区/进程回收回归。旧 Studio 自定义行为不再作为必须通过的产品回归项；数据保全与宿主其他功能仍须回归。macOS arm64、Intel、Windows 分别记录真实证据，未测不标通过。

## 7. 开发方式与完成门槛

每个能力按“源文件/调用路径 → 原行为样例 → AutoFlow 目标位置 → 最小适配 → 对照验收”推进。迁移清单记录来源 commit、许可、改动原因和验证结果；每个任务一个清晰提交，不混入其他 UI/模型修改。

组件先于页面，契约先于联调；原组件及其测试与专用控件先归位，再组合页面。服务参数和事件字段核实后生成类型。第一项交付为原 UI 与真实保存/打开，同时尽早验证一个原 parser/executor + CloakBrowser + HTTP/SSE + 暂停/停止的执行样例，避免先做完全部页面才发现执行链不兼容。

不用统一重命名、全面格式重写或关闭全局 strict/lint 规则掩盖迁移问题；必要类型修复在具体边界完成。先完成行为对齐，再基于具体问题局部优化。所有纳入的可用按钮必须有真实调用，失败明确展示，不返回假成功。

每个切片运行匹配范围的原特征测试与 AutoFlow 新适配测试。最终运行后端 pytest/Ruff/mypy、前端 Vitest/TypeScript/ESLint、OpenAPI、目录/脚本检查，及 renderer/main/preload、PyInstaller、正式 Electron 入口。实际 UI 和网页行为在临时工作区及受控页面验证，平台实测与模拟测试分开记录。
