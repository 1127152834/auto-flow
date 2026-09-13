# Studio 改为 WebRPA 源码迁入：设计规格

> 2026-09-13 当前状态：用户要求先清除现有 Studio，再重新讨论 WebRPA 迁入。旧实现现已退出当前源码，仅保留独立空窗口；本文相关实现状态/迁入步骤留作历史，不在本轮执行。以[清除记录](../../migration/studio-removal.md)为准。

- 日期：2026-09-13。
- 状态：**方向 confirmed；具体架构 proposed，待确认后实施**。依据用户本轮要求，停止 M6 自定义录制扩展，完整迁入范围内的 WebRPA UI、前端交互和后端业务逻辑。
- 源基线：`reference/WebRPA@5ccb900e8dcf1530aae66f676d87593c416c7ebb`；目标基线：AutoFlow `c657073`，数据库 `0008_workflow_debug`。
- 本文替代“重新定义节点、状态模型、控制流和 AutoFlow 风格编辑器”的后续开发路线。历史 M1–M5 保留为已实现版本和回归证据，不再作为新 Studio 的产品行为规范。
- 用户追加授权：可以完全重构，弃用此前编写的 Studio 代码。新方案不再要求兼容旧编辑器、旧节点协议或旧执行引擎；旧源码通过 Git 归档，已有数据保留原文。
- [实施安排](../plans/2026-09-13-studio-webrpa-source-migration-implementation.md)。方案判断置信度高；迁入后的视觉、交互、浏览器兼容及跨平台结果尚未验证。

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
| `frontend/src/store/{workflowStore,layoutStore,debugStore,nodeRunStore,globalConfigStore,moduleStatsStore}.ts` | 迁入状态实现和相应依赖；不继续维护另一套相同职责的编辑历史和运行状态 |
| `frontend/src/types/`、`lib/`、`components/ui/`、`index.css` 中的工作台依赖 | 连同原类型、布局工具、控件和样式迁入，保留已有库；按真实依赖添加包 |
| `frontend/src/services/{api,socket,config}.ts` | 保留被 UI 使用的服务方法与事件语义，适配 AutoFlow 地址、鉴权、错误和工作区 |
| `backend/app/models/workflow.py`、`services/workflow_parser.py` | 保留文档字段及原图解析规则，不转换成 M4 配对控制块计划 |
| `backend/app/services/workflow_executor.py`、`executors/base.py`、范围内执行器 | 迁移执行调度、配置解释、控制流、错误策略、子流程、调试及结果逻辑 |
| `backend/app/services/variable_manager.py`、`utils/safe_expr.py` | 迁移变量和表达式语义，连同对应测试；不套用 M4“仅可视化规则、禁止表达式”的限制 |
| `backend/app/services/browser_engine.py`、`recorder.py`、`element_picker/` | 迁移页面、录制、拾取算法及会话协作，替换浏览器启动和宿主资源操作 |
| `backend/app/api/workflows.py` 及相关录制/拾取路由 | 保留调用语义，放入 AutoFlow HTTP adapters；存储与进程操作交给现有相应层 |

不直接启动整个 WebRPA 服务作为第二个后台进程，不让生产构建导入 `reference/`，也不先全面拆解、重命名原业务算法。迁入源码属于 AutoFlow 正式构建，来源许可文件与修改清单随构建保留。

## 3. 宿主与目录

前端放入 `apps/desktop/src/renderer/domains/workflows/webrpa/`，内部先保留原 `components/store/services/types/lib` 组织，使用局部 import 别名。现有 `workflows` 领域仍负责 Studio 与宿主的装配；不建立另一个原型项目。

建议同一次 renderer 构建增加独立 `studio.html` 入口，原 WebRPA CSS 只进入这个文档，主应用 CSS 不进入 Studio。两个窗口共用 main/preload 和 sidecar。调整现有固定 Studio URL/构建文件与注册窗口主 frame 校验，保留窗口复用、最小化恢复、关闭重开和工作区协调。不得通过全局覆盖 AutoFlow CSS 来追求相似，也不把所有 `@/` 导入指向宿主共享组件。

后端继续使用 `apps/backend/src/autoflow`：纯模型、解析和变量规则归 `domain/workflows`；执行调度和上下文归 `application/workflows`；网页执行器、录制拾取归 `providers/browser`；数据库、文件和 worker 归各自 infrastructure；HTTP/事件归 adapters。按源文件职责落位，必要时保留 `webrpa` 子包便于追溯。迁移路径不等于重写实现；每个内部算法的改动需要具体原因与测试。

保留 AutoFlow Profile、CloakBrowser 内核、代理凭据、工作区 SQLite、文件适配器和进程树监管。原配置面板与 Profile 的交集逐字段映射；确需替换原浏览器管理入口时，保持原对话框操作位置并明确展示实际 Profile。不得仍显示 Edge/Firefox 已选中却偷偷启动另一内核，也不得出现两套互相覆盖的启动配置。

## 4. 浏览器与执行会话：明确替换旧约束

源码证据：`executors/basic.py` 的打开页面逻辑优先复用 `browser_engine` 的共享 context；`services/recorder.py` 同样读取共享 context。因此，“每次运行必开独立浏览器、录制/拾取必须关闭后才允许运行”不能继续作为新 Studio 的固定产品规则。

建议一个工作区 Studio 会话持有一个受监管 worker，原引擎的共享浏览器状态局限在该 worker 内。打开浏览器、拾取、录制、执行和 Debug 使用原前端/后端的状态转换；浏览器是否复用、执行后是否自动关闭按已核实的原配置处理。运行任务仍串行占用工作区，不并行操作同一浏览器；共享会话不代表可以边录制边并发运行。

父进程管理资源锁、工作区归属和清理。浏览器保持打开期间继续持有 Profile/内核使用锁；执行停止与浏览器关闭分别按原行为完成，关闭会话/退出/换区最终必须清理受管进程后释放占用。原进程全局变量不得跨工作区复用；崩溃后不得自动重放动作。凭据仅通过受控启动通道提供，不进入文档、日志或录制文件。

保留“先处理未保存文档，保存成功才离开；取消或保存失败保留现场”的保护。不得为了移植原 Toolbar 直接调用 reload/close 而绕开宿主的离开协调。

## 5. 数据和服务兼容

采用原前端保存/导出模型及其原有后端转换，保留 `moduleType`、`data`、端口、组关系、配置名和变量语法。前端 React Flow `type` 与后端执行类型不一定相同，必须复用原转换代码，不能直接混用两种模型。新格式使用明确的来源/格式标识与存储元数据包装，原 payload 不强塞进 M1–M5 的 schemaVersion 2 模型。

新文档写入当前工作区 SQLite，使用增量迁移；文档原文、标识、名称、修改时间及 revision 可在仓储包装层维护。继续提供原子保存和并发冲突保护，禁止覆盖写文件取代工作区存储。导入/导出是原工作台能力，与工作区内实际存储方式分开。

现有 M1–M5 文档和历史运行保持原始数据，不强制新编辑器兼容它们，不为旧 `timeoutSeconds`、`framePath` 或配对控制图编写双引擎适配。源格式标识隔离新文档；旧数据在迁移前提供可核验的备份/导出，不能伪装为可直接导入 WebRPA 的文件。旧版本可通过 Git 检查点找回；新产品只保留一套 Studio。将来确实需要迁移某条旧流程时，再单独验证转换，不作为本次源码迁入的前置门槛。

保留原 Socket.IO 调用和事件名，作为同一 sidecar 中的迁移协议适配层，复用 AutoFlow 鉴权；不另起无鉴权端口。将确认事件持久化、断线补读和诊断索引接在事件边界，避免直接重写所有原 Store 订阅。旧 SSE 保留历史兼容，不能让两个通道同时驱动同一新运行造成重复动作或日志。

HTTP 服务方法优先沿用原调用语义；命名空间放入现有 workflows API 范围，在动态文档路由前注册。具体 DTO 和路由清单在第一切片按真实调用闭包冻结，使用 OpenAPI 生成类型。宿主鉴权、停写、并发校验等新增语义在 adapter 中处理，不要求 UI 组件理解资源锁和数据库事务。

## 6. 允许的优化和验收依据

迁入阶段允许：导入路径/包边界调整、宿主浏览器与存储适配、明确排除功能裁剪、有复现证据的缺陷修复。其他交互、默认值、流程语义修改先记录差异，不以“更干净”作为重写依据。

已静态核实的例子：原 `workflow_executor.py` 找不到执行器时返回成功并跳过。新版本必须明确报不支持，不把此行为当成熟能力复制。原 `workflowStore.ts` 的 `HistorySnapshot` 仅包含 nodes/edges/name；涉及变量的撤销是否丢状态，需要用原操作路径复现后确定修复。原测试 README 说明部分外部浏览器依赖使用 mock/skip，不能据此宣称全部真实场景已验证。

每条验收对照同一冻结版本、同一流程输入和受控网页。视觉对照固定视口、缩放、面板状态和字体，核对截图；动态时间等非确定内容单独屏蔽，排除入口变更逐项记录。交互核对鼠标/键盘操作轨迹、文档前后状态及撤销结果。执行核对节点顺序、分支、变量、网页副作用、错误和资源归属，不只看按钮状态。

最终交付必须包含：原 UI 的正式窗口、真实存储、手动编排运行、原录制生成并独立重放、Debug/日志/结果、全部核心清单通过、无占位执行器，以及宿主保存/离开/工作区/进程回收回归。旧 Studio 自定义行为不再作为必须通过的产品回归项；数据保全与宿主其他功能仍须回归。macOS arm64、Intel、Windows 分别记录真实证据，未测不标通过。
