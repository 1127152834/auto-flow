# Studio 改为 WebRPA 源码迁入

- 日期：2026-09-13；状态：产品方向和 AutoFlow 工程约束 confirmed，具体迁入架构 proposed。
- 来源：用户要求照搬 WebRPA UI、交互和后端业务，允许弃用旧 Studio；清除完成后追加“架构，技术栈和开发习惯要贴合 autoflow 的模式”。本轮要求说明迁入方式，仅更新设计，不写业务代码。
- 当前代码：`25273d5` 已清除旧 Studio，仅保留独立空窗口；数据库 head `0008_workflow_debug`，旧数据保留。[清除记录](../../docs/migration/studio-removal.md)不被本设计替代为“迁入完成”。
- 正文唯一来源：[设计规格](../../docs/superpowers/specs/2026-09-13-studio-webrpa-source-migration-design.md)及[实施安排](../../docs/superpowers/plans/2026-09-13-studio-webrpa-source-migration-implementation.md)。

## 已确认方向

原 UI、交互、文档语义、解析/执行、录制拾取和 Debug 是产品基准；不再继续旧 M6 自定义实现或恢复 M1–M5 少量节点、配对图和强制独立会话约束。企业管理、Windows 桌面控制、发布/版本管理仍排除；工作台核心完整迁入。专项模块逐项列出范围，不借裁剪删除核心，也不自动带入全部外部依赖。

旧源码已有 Git 归档，旧数据库和产物保持原文；不建设旧引擎、双编辑器或旧格式自动转换。用户其他领域的未提交改动保留。

## 本次修订与依据

1. **superseded：整块 webrpa 子目录及复制全局 Store/services。** 改为正式 workflows 领域目录，迁原组件/编辑算法，源头由清单记录。Zustand 限编辑/界面投影，Query 管服务端事实；globalConfigStore 含宿主配置/凭据，保留范围内行为/视图设置，宿主资源/凭据走 AutoFlow。自动保存、覆盖/副本、自定义快捷键、autoCloseBrowser 均需保留并映射，不因非视觉设置而删除。
2. **superseded：默认引入 Socket.IO。** AutoFlow 已有 HTTP/SSE；原 Debug 继续/单步/断点是 HTTP，executor 提供事件回调。保留事件语义，在 API 边界替换传输；输入提示/脚本结果等反向交互需有类型的确认命令。KernelEventBroker 为容量 1 的覆盖快照，不能充当持久日志总线。
3. **proposed：同构建独立 studio.html。** 避免宿主 CSS 改变原 UI及 Radix portal。保留同一 Electron/main/preload/sidecar；原控件不等价时作为领域控件保留，不机械替换成现有黏土色 h-10 Button，不改原即时表单/撤销粒度。
4. **proposed：工作区会话 worker。** 原 basic.py 和 recorder 复用 browser_engine context，迁入需保留已核实的浏览器协作；Profile/内核锁和进程监护由宿主承担。方案置信度中，第一批真实验证原引擎/共享页/事件/调试/停止后再扩展，不先做完整 UI。
5. **confirmed 源码事实：几何可能影响执行。** 原 workflow_executor.py 用组位置/尺寸识别子流程成员，部分无入口情况按 y/x 排序。必须保存并冻结必要几何，保留原解析算法；只排除 selected/dragging 等瞬态。
6. **confirmed 当前边界：旧握手已删除。** 新文档保存/离开、会话清理与 Studio 连接权限需要重新接入现有窗口、设置和工作区机制，不能宣称现成可用。
7. **proposed：保留实现、调整真实 IO 边界。** domain 保持纯规则，application 接调度/会话，browser provider 做网页 IO，infrastructure 做数据库/文件/进程，adapters 做传输；反向 import app.main/app.api 改为窄端口/回调，不新增通用 RPC/插件框架。

迁入不代表复制已知缺陷：原未知执行器静默成功需要明确失败并补回归；原变量撤销和录制尾部可靠性需用实际操作复现。原测试存在 mock/skip，不能据数量认定所有行为成熟。

本次静态核对及前后端独立复审支撑分层判断，尚无迁入后的真实 UI/运行证据。第一项交付为原编辑器+真实保存/打开，并提前通过原引擎+CloakBrowser+HTTP/SSE+暂停/单步/停止探路。

## 详细里程碑补充

- 2026-09-13；状态 proposed；来源用户“给我一个详细的里程碑计划，要求方便测试，稳步前行”。
- 既有实施文档细化为 R0–R8，取代 S0–S4 的粗粒度安排；不另建第二份路线正文，不沿用旧 M1–M6 完成状态。增加 60 组可编号复测用例和[唯一验收台账](../../docs/migration/studio-webrpa-migration-validation.md)，全部待验收。
- R1即通过原编辑保存与原引擎真实执行、原断点/单步/停止、持久事件、命令去重、离开清理、数据迁移和本机冻结/包入口；大规模组件及执行器迁入在此之后。
- R2完整编辑，R3网页动作，R4控制流/变量/子流程及通用数据/脚本/I/O，R5拾取，R6录制重放，R7完整原Debug/诊断，R8最终对照和平台组合验收。每批有短用户脚本及深层工程测试，未通过不进入依赖阶段。
- 源码复核后明确：R1以原节点断点触发暂停；不默认带回旧M5变量批量修改/failed_paused。R6沿原等待/框架生成语义，独立重放关浏览器是测试方法。R4首个输入提示/脚本消费者即接双向命令，R7完成调试组合验证。
- 录制步骤确认以工作区持久提交为准，失败未确认尾部单列，使用已有事件/文件边界。容量阈值按现有配置和首次实测固定后才验收，不临时放宽。各平台实测分别记录。
