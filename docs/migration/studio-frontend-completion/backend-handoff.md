# Studio 正式后端交接合同

状态（2026-09-23 核销）：前端服务消费合同与真实后端迁入并行演进。正式文档、迁入执行器和 worker 已存在；Mock 只用于合同测试。下述节点槽位和项目集成证据分开记录，不能据此宣称全部后端或全部平台已完成。

## 后端迁入准备入口（2026-09-15）

本节是 Studio 后端迁入的唯一导航入口，既有前端交接合同继续有效，不复制成第二套合同。

| 文档 | 权威内容 | 当前状态 |
|---|---|---|
| [后端全局约束](../../automation-studio/BACKEND_GLOBAL_CONSTRAINTS.md) | 仅 CloakBrowser、仅批准节点、AutoFlow 分层、小助手使用 LangGraph | 用户确认，实施必须遵守 |
| [后端迁入设计规格](../../superpowers/specs/2026-09-15-studio-backend-webrpa-migration-design.md) | 架构、执行语义、合同、持久化、生命周期和数据库兼容 | 按已批准范围迁入，具体闭合状态见证据 |
| [后端迁入实施计划](../../superpowers/plans/2026-09-15-studio-backend-webrpa-migration-implementation.md) | B0–B9 任务、文件、接口、测试、退出门槛和估计 | 按依赖并行推进，不再沿用准备时的 B1 单阶段结论 |
| [213 节点能力台账](capabilities.json) | 每节点冻结源码、符号、业务字段、目标模块和三条后端验收用例 | 639 条槽位中 622 条标记已验收、17 条待真实执行；槽位不等同全部平台完成 |
| [共享后端能力映射](backend-support-mapping.json) | 文档、执行器、浏览器、运行、拾取、录制、Debug、模型/MCP、LangGraph 小助手、凭据、触发器和数据库兼容 | 13 个共享能力集中登记，按各自实际证据核销，不以节点通过代替 |
| [后端验收矩阵](../studio-backend-migration-validation.md) | 跨节点链路、故障、容量、平台与正式包验收 | 保留已有真实证据和未测平台，继续补齐剩余交付 |

已核实基线：

- 有效范围为 213 个节点，类型集合以 [范围文档](scope-database-dp-cloakbrowser.md) 为准；中文单语言，不恢复排除节点及专属配套。
- 冻结源码位于 `reference/WebRPA`，commit 为 `5ccb900e8dcf1530aae66f676d87593c416c7ebb`，产品版本 3.2.0。213 项均找到执行器入口，212 项由装饰器注册，`subflow` 手动注册。
- [上游许可证副本](../../../LICENSE.WebRPA) 与冻结仓库 LICENSE 哈希一致。项目负责人已确认在本项目范围内获准使用并迁入源码；不把该确认扩写为具体商业授权或公开发布授权。
- 准备阶段“只有 DTO、没有生产 workflows”的结论已被迁入实现替代。正式入口现有 `/api/workflows`、`/api/workflow-runs` 及项目目录 `/api/v1/workflows`；生产边界分别为 `application/workflows/documents.py`、`coordinator.py`、`runtime.py` 及数据库/worker 适配器，不能重新恢复已弃用的历史执行器。
- B0 历史记录：恢复 `f573a44` 中四个历史 revision，并以 `0011_merge_android_project_data` 合并；这个编号不是当前数据库 head 的声明。新增迁移按现有链继续。本轮仅使用隔离临时数据库，不修改真实用户数据。
- Studio 小助手按最新用户决定使用 LangGraph 管理真实多轮状态、工具、权限、取消和恢复；普通工作流仍迁入 WebRPA 确定性执行器。

当前工作为剩余节点真实验收及已批准的项目管理深度接入。项目文档入口、真实保存重开和正常关窗已具备 [macOS arm64 正式窗口证据](../studio-backend-migration/evidence/project-integration/formal-documents-electron-HMKavH/result.json)。实现、校验和明确剩余边界集中记录于 [当前会话记录](../../../.ai/sessions/2026-09-23-studio-project-integration.md)。节点聚合状态仍为 185 项已验收、28 项待验收，其中 11 项的三个槽位均已有通过记录；必须结合其平台限制核销，不能将其视为新增缺实现，也不能直接将平台限制抹掉。

项目运行归属、归档等待清理及五节点真实运行已补 [正式窗口证据](../studio-backend-migration/evidence/project-integration/formal-electron-RnPj0V/result.json)：普通运行、失败调试、原生关闭中的取消/放弃停止、重开、内核缺失启动失败均覆盖。运行请求和详情包含可选 `projectId`，已存文档归属在数据库事务中校验，未保存草稿不顺带创建文档。这里的通过限 macOS arm64 开发入口；不表示项目运行读权限、资源授权、数据资产及统计已完成。

后续 [项目运行读取及事件隔离证据](../studio-backend-migration/evidence/project-integration/formal-electron-hpS5Ek/result.json) 已通过：`/api/workflow-runs` 整个路由族接受窗口绑定的 `projectId`，列表先过滤再分页，详情/日志/结果/产物/诊断和导出跨项目返回 `RUN_NOT_FOUND`；归档历史保留、已删除项目不可读。`/api/events/stream?projectId=...` 将其他项目运行变成同序号、空数据的 `studio:cursor`，前端沿用连续游标，不回放外来运行内容。原项目三次运行可查，第二项目真实 UI 列表与日志隔离；控制命令、非运行会话及完整资源权限仍单独待完成。

当前没有需要用户决定的产品冲突，源码使用授权不再是实施阻塞。正式数据库副本、跨平台机器和第三方凭据属于后续验收环境等待。

事实源：

- `service-inventory.json`：171 个前端服务方法、83 个事件、50 个直接请求、105 个 AI 动作、23 个服务族。
- `contract-matrix.md` 与 `contract-matrix-validation.md`：请求、响应、事件、错误、分页、幂等和恢复规则。
- OpenAPI 生成类型：`apps/desktop/src/renderer/shared/api/generated.ts`。
- 前端传输入口：`apps/desktop/src/renderer/domains/workflows/api/transport.ts`。

## 交接原则

1. 正式后端实现现有 operation 和事件，不要求前端增加页面、表单、Store 分支或另建传输层。
2. 命令使用客户端生成的稳定标识。相同标识和相同载荷必须幂等；相同标识和不同载荷返回冲突。
3. HTTP 接受只表示命令已登记。前端状态以可查询命令状态或带身份的服务事件为准。
4. SSE 事件带递增游标并可补读。断流不等于运行失败；重连后从最后确认位置继续，不能重复网页动作。
5. 错误沿用统一错误包，保留字段路径、节点标识、会话标识和可重试性。不能把业务冲突伪装成网络离线。
6. 所有活跃会话必须服从工作区、文档、连接代次和资源所有权。迟到响应不得写入新文档或新会话。
7. 停止、关闭和取消均需幂等。浏览器/worker/文件清理完成前不能释放占用或报告已结束。

## 服务族交接

| 服务族 | 正式后端职责 | 幂等、恢复与清理 | 前端证据 |
|---|---|---|---|
| 工作流文档 | 新建、读取、更新、列表、导入导出元数据；保留节点、连线、布局、变量和依赖 | 更新使用 revision；冲突保留草稿；保存途中继续编辑不能误标已保存 | 文档保存、结构复制、导入导出及离开保护专项 |
| 运行与调试 | 接收冻结快照和 CloakBrowser Profile，按结构化流程执行；提供运行、暂停、单步、继续、停止、断点和变量修改 | `runId`、`commandId`、`pauseId`、`controlRevision` 全链路校验；停止优先；崩溃不重放网页动作 | `f3-*`、`start-admission`、`debug-run-variable` |
| 浏览器会话 | 只消费主应用 Profile；创建临时可见/隐藏会话，管理页面、当前目标页和资源锁 | 运行、调试、拾取、录制互斥；资源清理完成后释放 Profile/内核占用 | 浏览器状态、连接恢复、正式窗口 Profile 入口 |
| 拾取与定位 | 页面列表、导航、拾取、定位测试、候选和相似元素；支持 selector、framePath 与页面身份 | `sessionId`、`requestId` 幂等；页面/字段变化使旧结果失效；取消清理注入监听 | `f4-picker-*`、`f4-selector-*`、`f4-similar-*` |
| 录制 | 会话、控制命令、步骤分页、审查修订、定位测试和生成预览 | 确认序号补读；停止后可审查，关闭后才释放资源；崩溃保留已确认步骤，不重放 | `f4-recorder-*`、`f4-recording-review` |
| 日志与结果 | 按运行和执行身份保存日志、结果、诊断与产物；支持分页、筛选、补读和导出 | 事件序号去重；大值通过引用按需读取；导出固定截止序号并校验缺失文件 | `f3-log-history`、结果/诊断专项与容量测试 |
| 交互命令 | 输入、脚本、语音、路径选择等运行期请求及回传 | 领取、回传、取消、查询均带稳定请求身份；响应丢失查询原请求；停止回收在途请求 | input/js/speech/path 系列证据 |
| 配置与资源 | 模型、MCP、WebDAV、凭据字段、网络连接、图片资源、留存策略和计划任务 | 写操作携带修订；多字段命令原子；响应丢失可查询；连接/工作区切换隔离 | `f5-*` 证据目录 |
| AI 工具 | 模型对话流、画布工具调用、权限请求、拒绝、取消和操作时间线 | 工具开关与风险策略由前端提交；后端不得绕过权限结果；排除节点始终拒绝 | `f5-supporting-settings` 与 AI 权限测试 |
| 宿主桥接 | Electron 提供工作区运行上下文、服务状态、窗口生命周期、剪贴板、文件/目录选择和下载 | 只允许已登记窗口主 frame；退出顺序为草稿处理、会话清理、sidecar 关闭、应用退出 | F6 正式 Electron 与宿主 smoke |

## 鉴权与敏感数据

- 所有 HTTP/SSE 请求复用 sidecar 启动时下发的本机 token；服务须验证工作区实例和连接代次。
- License、代理密码、模型密钥和凭据秘密不得进入日志、SSE、运行快照或诊断导出。
- 凭据字段管理前端已提供独立改名、批量改名/删除、原子命令、修订冲突和响应丢失恢复；正式秘密存储仍由后端负责。
- 文件与产物读取必须验证其登记归属，不能接受任意路径穿越。

## 正式后端剩余交付边界

本节替代准备阶段“仓库没有真实后端”的旧清单。当前剩余要求继续沿用既有能力台账及矩阵，不能重新笼统判定整族未实现：

- 17 个节点的待真实执行槽位，以及对应平台、凭据、硬件环境；用户删除的 14 个通知节点保持排除。
- Studio 与项目执行/权限/资源、数据资产、统计、活动及导航的完整接入；项目管理的原运行表与 Studio 运行表尚未统一消费，目录可读不代表项目批次可运行全部迁入节点。
- 项目范围内 Debug、拾取、录制和宿主切换的完整生命周期矩阵；文档正常关闭证据不能代替其他活跃会话验收。
- 必填字段规则404已由完整213源规则及真实HTTP/正式包证据核销；全局快捷键404已由受控Electron原生注册核销；两条旧启动命令501已由每连接日志投递及受控宿主目标替代核销，不能以文档保存成功掩盖。
- 真实模型、秘密存储、外部集成与跨平台正式包各自独立记账，以对应能力证据为准。

所有缺口按实际入口追踪；不能将未实现的前端业务归入真实后端外部等待，也不能使用 Mock 通过关闭真实执行槽位。

## 接入退出条件

- memory 与 HTTP/SSE 合同套件对同一 operation 得到一致状态转换。
- OpenAPI 生成文件无差异；错误和事件通过运行时 schema 校验。
- 响应丢失、断流补读、重复命令、停止竞争、工作区切换和 sidecar 异常均有真实集成证据。
- 正式 Electron 使用真实 CloakBrowser 完成运行、Debug、拾取、录制闭环，并确认无遗留进程和资源锁。


### 项目范围的运行命令合同（2026-09-23）

运行/Debug/输入、JS、语音及平台交互请求使用宿主 `projectId` 查询参数。服务在分发前验证对应 run/request 的持久归属；外项目返回 404，不执行命令、不改变在途状态。原 `commandId`/暂停修订/请求负载及响应丢失查询保持不变，查询回执也验证归属。旧流程级变量追踪先按项目选择运行，不能读或清空另一项目记录。

证据：`../studio-backend-migration/evidence/project-integration/run-controls-2026-09-23/result.json` 及 `formal-electron-GS1ler/result.json`。这关闭当前运行控制消费边界，不等同于项目全部权限、资源授权、拾取/录制/助手接入完成。


SSH 五节点已通过 [正式 UI 闭环](../studio-backend-migration/evidence/b6/formal-ssh-electron-nUEoTd/result.json)，配套 [真实 worker 失败/停止证据](../studio-backend-migration/evidence/b6/ssh-local-worker-2026-09-23/result.json)。此批核销 5 个真实执行槽位；外部主机、Intel/Windows 和冻结入口仍按族证据的 remaining 保留。

### 项目运行数据与删除合同（2026-09-23）

`GET /api/v1/projects/{projectId}/run-assets` 以 kind、runId、nodeId、cursor/limit 查询现有索引投影，返回元数据、total/nextCursor，不包含完整值或磁盘路径。`GET /api/workflow-runs/{runId}/results/{sequence}` 按已登记事件读取完整结果；文件仍用原 artifact 地址，均带宿主 projectId。新文件有真实 registeredAt，旧文件无登记/事件时间时返回 null。数据目录可预览、下载并读取对应执行日志。

证据：[数据入口及完整正式 UI](../studio-backend-migration/evidence/project-integration/data-assets-2026-09-23/result.json)、[项目删除清理集成](../studio-backend-migration/evidence/project-integration/delete-cleanup-2026-09-23/result.json)。永久删除先清受管运行目录，成功后清该项目运行/索引/文档/保存回执；失败保留 deleting 和重试责任，其他项目、共享资源及用户外部输出不删除。正式 UI 删除、业务数据表写入、统计与录制归属尚未在这两份证据中关闭。

### Studio 统计事实与下钻（2026-09-23）

`GET /api/v1/projects/{projectId}/statistics/studio` 复用项目统计服务，按 from/to（运行启动时间）、workflowId、status、cursor/limit 在数据库过滤和聚合。成功为 completed、取消为 stopped；成功率分母只计 completed+failed，时长包含暂停/清理。节点执行按真实 execution:node_start 事件统计，结果次数不是业务记录数，文件与诊断独立计数。计划来源按已登记执行关联，缺证据返回 unknown。结果包含有界运行列表和下一游标；前端从统计读取原运行日志及原项目资产，无假任务ID。活跃状态刷新后可能变化，不冒充原任务冻结结果集。

[统计及正式 UI 证据](../studio-backend-migration/evidence/project-integration/statistics-2026-09-23/result.json)。录制归属尚缺，因此 recordingCount=null，接口和页面给出真实原因；录制统计仍待后续归属接入，不将 null 算通过。正式包和其他平台未在此项核销。


### 项目拾取／录制合同补齐（2026-09-23）

上节录制归属缺口由此项替代。`/api/browser`、`/api/element-picker`、`/api/recorder` 请求统一携带宿主 `projectId`；外项目或省略项目不能读取/控制有归属的会话和录制资源。开始录制额外传当前（可未保存）`documentId`，同 sessionId 不可改绑定。审查、已确认步骤和幂等回执均独立验证持久归属。停止/关闭/读取在 closing 允许，新采集/恢复和审查修改禁止。

`0020_recording_project_scope` 为新数据冻结项目/文档归属，历史无归属保持 null；不会猜测归属或批量改库。项目占用在浏览器异步启动前登记，与归档写事务互斥；清理失败保留占用和重试，启动中关闭可取消等待。永久删除沿用现有 project_id 清理和事件级联。

统计 recordingCount 现在来自已登记项目归属的真实录制 session，按文档和创建时间筛选；运行 status 过滤不适用于录制时为 null+原因。历史无归属不计入且页面说明。最近活动包括录制更新时间。

[专项及边界](../studio-backend-migration/evidence/project-integration/inspection-recording-2026-09-23/result.json) · [正式录制、重开、独立重放和项目统计](../studio-backend-migration/evidence/project-integration/formal-recording-electron-eUd5nT/result.json)。仅 macOS arm64 开发构建实测，未替代正式包、其他平台、项目资源权限或任务/业务表桥接验收。

### 项目自动化调用 Studio 五节点（2026-09-23）

项目文档目录、自动化校验和批次准备现准入 `open_page/input_text/click_element/get_element_info/screenshot`。旧项目四节点协议保持兼容；Studio 格式使用现有迁入图执行器及同一 CloakBrowser 当前页，冻结完整文档和主应用 Profile。截图复用工作区产物存储和原事件 SQL 事务，结果/失败用途分别展示；回执不确定时保留文件，停止及父通道断开可中断启动/节点，清理后才终态。

宿主按 workflowId 打开已保存文档时，保存使用更新合同；新建仍创建新身份。正式开发入口已完成项目绑定→五节点→PNG、长导航停止、失败截图、恢复后成功和进程清理。证据：[`project-task-bridge-2026-09-23/result.json`](../studio-backend-migration/evidence/project-integration/project-task-bridge-2026-09-23/result.json)。同一链路已在本次 macOS arm64 本地 unsigned 包完成，记录具体 app.asar/后端哈希；Intel/Windows 未测。其余项目节点族、业务表写入、权限资源及已登记404/501不因此关闭；213节点槽位仍622/17。

### 完整源字段元数据（2026-09-23）

`GET /api/system/module-required-fields` 使用现有严格DTO、共享鉴权与错误包，返回冻结WebRPA最终合并的213节点规则；生产不读reference或development目录。已有导出器遗漏后续AUTOFIX/人工覆盖的根因已修正，旧69覆盖结论由源逐项差分替代。源摘要、许可与改动见 required-field-source-coverage.json；全部映射过滤排除节点，不恢复14通知。

正式开发入口及本地unsigned包实际点击验证空URL、填写、wait三模式及原未覆盖邮件字段；仅配置提示测试、不发送邮件。共享加载/失败/重试/连接隔离原测试保留。证据：[`required-fields-2026-09-23/result.json`](../studio-backend-migration/evidence/shared-services/required-fields-2026-09-23/result.json)。规则元数据完整不等于全部节点执行器行为已验收。

### Studio 自定义快捷键原生接入（2026-09-23 confirmed）

保留原版九项动作及配置持久化，生产Electron经已登记Studio主frame注册到globalShortcut，窗口/sidecar身份变化注销；同宿主修改原子替换，失败保留旧映射。回调只发给当前就绪窗口，不写入可续读SSE。前端确认原生注册后抑制同组合本地重复处理。计划任务快捷键注册不受影响。

78项关联测试、类型/lint/构建通过。开发和本地unsigned正式包实际系统按键分别在Studio及主窗口前台保存一次；AXClose注销、重开恢复不重放、实际清除后注销均通过，并回归项目五节点/停止/失败/恢复。证据：[native-hotkeys-2026-09-23/result.json](../studio-backend-migration/evidence/shared-services/native-hotkeys-2026-09-23/result.json)。这是Studio配置能力，不核销hotkey_trigger节点槽位；Intel/Windows未测。

### 实时日志投递接入（2026-09-23 confirmed）

冻结原版 `make_execution_callbacks.on_log` 的简洁模式保留用户/系统/警告/错误日志。AutoFlow 使用现有 `GET /api/events/stream` 的 `verboseLog` 参数表达每连接偏好；缺省 true 保持旧消费者兼容。切换只重连此流并保留 afterSeq，不能取消输入/脚本等正在确认的命令；被抑制帧仍发送空 `studio:cursor`，不删除共享事件或持久历史。项目隔离先于日志过滤。原版 Socket 全局 `set_current_workflow` 已由上节受控宿主目标替代，生产不再发送 `current` 哨兵或两个旧命令，没有返回伪造成功回执。

节点事件按冻结源码重要节点/触发器集合与批准节点集的交集带分类标记，协调器保留节点明确给出的日志级别和用户/系统标志；普通成功节点仍沿既有 success 查询合同。独立 worker 警告统一到实际前端消费的 log 信封。类型经 OpenAPI 更新，Mock 仅对照连接投递合同、不执行节点。

关联失败与修复：真实 HTTP 测试显式禁用外部代理避免本机请求502；保留原 success 导出断言，未更改测试期望。复核以同一个网络 chunk 的取消场景复现旧帧推进游标，现取消后不消费余帧。实际 UI 测试只修正节点遮挡、原版 tooltip 改写及读取 DOM 返回 boolean，保存/重开/真实执行断言保留。

历史发现（已由下节实际耗时修复替代）：`application/workflows/runtime.py` 曾转发 `ModuleResult.duration` 但未实际计时；冻结源 `workflow_executor.py:1195` 使用实际毫秒。来源为本次日志只读审查，影响节点耗时诊断的准确性；后续在既有调度边界补计时，不能把默认0作为真实测量。它不影响本块的模式切换、日志内容、分类及事件身份验收。

本块97项后端、46项前端及类型/lint/OpenAPI/结构/构建通过。开发入口与本次macOS arm64 unsigned正式包均实际切换日志模式、执行六节点、保存重开、读取同次历史，并确认CloakBrowser清理；PyInstaller与冻结启动通过。证据：[log-delivery-2026-09-23/result.json](../studio-backend-migration/evidence/shared-services/log-delivery-2026-09-23/result.json)。诊断耗时与其余项目集成仍保留，不核销任何未测节点/平台。

### 节点真实耗时（2026-09-23 confirmed）

冻结源以毫秒记录节点执行；迁入调度器现使用单调时钟，在节点自身断点结束后计时，执行完成/失败结果透传到事件、持久日志和既有毫秒显示。不改整次运行墙钟时长，不制造取消/抛错节点的完成事件。

嵌套等待通过现有任务上下文关联调用祖先，只扣本调用链的调试边界等待；重叠等待计一次，不存逐次计时历史。非等待子流程在原 worker 后台入口分离计时祖先，仍保留原取消/调试和调用深度保护。最初共享 worker 暂停累计方案会误扣无关并行分支，已由真实控制器及嵌套 Runtime 回归替代。

证据：[node-duration-2026-09-23/result.json](../studio-backend-migration/evidence/shared-services/node-duration-2026-09-23/result.json)。78项关联回归、Ruff/mypy通过；开发入口真实五网页动作及用户日志的非零毫秒、持久恢复和进程清理已验证。最终后台调用细化后，PyInstaller171秒、冻结启动和本次macOS arm64本地unsigned包真实六节点、持久毫秒及关窗恢复均通过；其他平台与全项目集成不因此核销。

## 凭据真实消费闭环（2026-09-23）

[凭据运行证据](../studio-backend-migration/evidence/shared-services/credential-runtime-2026-09-23/result.json) 已完成：原生凭据UI保存→真实CloakBrowser输入引用→页面验证→日志重开→UI删除，开发V7sWWS及最终本地unsigned包ZMGYx6通过。共享系统存储按字段经所属worker私有管道读取，不进入日志/SSE；缺失/空字段保留源占位符，读取等待可停止且迟到响应丢弃。8项真实worker/5项管道保护补充82项关联回归。此闭环不代表所有集成或项目凭据ACL已完成；213节点622/17槽位不变，Intel/Windows未实测。

## 项目资源默认规则（2026-09-23，用户确认）

Studio 的 Profile／模型沿用项目 `defaultResources`，允许任务显式覆盖，不新增资源白名单。该产品选择已经确认，后续按已有主应用资源边界接入。历史文字中的“权限资源／凭据ACL待确认”不代表获准新增ACL；项目归属与跨项目数据隔离仍继续校验。

## 高级数据项目任务桥（2026-09-23，开发及正式包通过）

[本批证据](../studio-backend-migration/evidence/project-integration/advanced-data-2026-09-23/result.json)集中记录26个既有高级列表／字典／CSV执行器的项目准入、字段保留及输出登记。复用现有图执行器，不重写数据算法；旧四节点和五节点桥保留。纯数据冻结计划不要求Profile或内核，不预留浏览器环境；停止和重启仍经过受管worker清理，JSON null产出仍作为有效结果登记。

开发正式UI已经完成CSV解析→列表扁平化→反转→CSV生成的项目批次链，保存及原生关闭重开后运行，四份持久输出可查。正式包状态由本批证据记录，不借用前一包结果。26入口共享桥接通过不等同项目控制流／业务表／全部公共运行上下文已完成：项目worker凭据读取及模型端口仍单列；普通Studio的凭据证据不能替代项目任务凭据消费。

该链路随后通过最终macOS arm64 unsigned包 `V8a98L`；同包 `7k2XEy` 实际回归原五节点、PNG、导航停止、失败和恢复成功。最终177项关联回归、Ruff/mypy/OpenAPI/目录检查、PyInstaller及冻结启动通过。仅此批项目顺序数据桥核销，不替代其他节点族、凭据/模型上下文或平台验收。

### 项目默认浏览器配置与显式覆盖（2026-09-23）

按用户确认，Studio读取项目 `defaultResources.profileId`，允许从全部主应用Profile显式覆盖；不增加资源白名单。覆盖按工作区/项目保存在编辑会话，同工作区重连保留，新窗口重新读取项目默认。项目没有默认时要求选择；失效默认不静默回退。已有计划任务明确保存的Profile继续优先；新建任务采用项目默认后允许覆盖。普通非项目窗口沿用现有全局选择与首项行为。

工具栏、交互浏览器及拾取启动复用同一解析入口，实际请求仍发送明确profileId。类型沿现有项目/浏览器OpenAPI，无新传输框架或数据库迁移。60项关联测试与最终开发正式UI通过（含真实交互浏览器、五节点、PNG、正常关窗、停止/失败/恢复与跨项目隔离）。正式包最新结果与所有失败尝试见 [Profile默认验收汇总](../studio-backend-migration/evidence/project-integration/profile-defaults-2026-09-23/result.json)。该证据不核销模型默认、项目worker秘密/模型上下文及其他平台。

### 运行重试的资源冻结（2026-09-23）

同一runId按原始文档、布局、Profile ID及运行选项校验；已接受请求复用原资源/模块快照，Profile或模型随后修改/停用不会引发重启。不同请求仍409。51项真实SQLite及协议回归见 `../studio-backend-migration/evidence/project-integration/resource-retry-2026-09-23/result.json`；真实模型与正式入口组合验收另计。

## 项目默认模型与显式覆盖（2026-09-23 confirmed）

按已确认资源规则，Studio AI节点空`modelId`继承项目默认提供商中按主应用既有排序返回的首个启用模型；显式ID优先，不设白名单。缺失/禁用默认、无可用模型和无效显式ID明确失败，不回退全局第一项。根文档、子流程、自定义模块只修改本次执行副本，保存文档及原运行快照保持原始配置；非秘密解析模型ID记入运行资源快照。稳定runId重试沿前节已冻结资源处理，不重读秘密或重放动作。

节点面板显示继承值，保留原版备用模型机制；小助手沿真实LangGraph和主应用模型服务，选择覆盖仅限当前工作区/项目会话。请求代际变化隔离迟到结果，默认失效仍可显式选择其他可用模型。未添加新的服务端模型管理接口。

[专项与正式UI证据](../studio-backend-migration/evidence/project-integration/model-defaults-2026-09-23/result.json)：开发`tBtjEa`与本次unsigned包`2pmiUF`实际创建14节点，继承/覆盖、保存、AXClose重开、运行、媒体产物、CloakBrowser视觉点击和小助手切换通过。同包`RjFuGN`回归五节点、Profile默认/覆盖、失败Debug、正常关窗取消/保存/停止及清理。真实外部模型另有[一次OpenRouter调用](../studio-backend-migration/evidence/project-integration/model-defaults-live-2026-09-23/real-model.json)，主模型库仅只读、凭据仅经系统存储及私有worker通道；受控HTTP模型UI测试不替代该证据。

前端74项关联、后端分组52/45/33项（组间有重叠，不能累加）、Ruff/mypy/TypeScript/ESLint、OpenAPI/目录及构建/冻结/打包通过。macOS arm64实测，Intel/Windows未测。此批采集时项目任务worker模型/凭据与助手会话后端项目归属仍未关闭；worker端口由下方后续证据分别核销。213节点及622/17槽位不变。

## 项目任务凭据消费（2026-09-23 confirmed）

项目worker现通过现有StudioCredentialService与系统秘密存储读取字段，复用普通Studio同步读取器及原版变量解析。请求仅走所属worker私有管道，绑定run/generation/request，不进入持久事件、HTTP/SSE或公共结果。stdin唯一线程直接唤醒同步等待，停止/EOF及时解除；父侧每个运行最多一个未返回的原生读取，清理/停止/归属变化后写锁内丢弃迟到值。无新增凭据管理体系或项目白名单。旧项目chain/v1行为保留。

真实复核修复两项：空name/field仍保留原占位符，不变为协议失联；同步读取加入任务局部节点预算，超时不继续动作。共享节点完成消息透传安全的`isTimeout`布尔值，使凭据错误内容隐藏后仍能准确分类为WORKFLOW_NODE_TIMEOUT。不会为此公开凭据派生值。

[证据](../studio-backend-migration/evidence/project-integration/credential-runtime-2026-09-23/result.json)：95项关联测试、Ruff/mypy/OpenAPI/目录、98项脚本通过；正式开发Cy7fmp和最终unsigned macOS arm64包vBd3bn通过实际凭据UI保存→项目文档五节点→原生关闭重开→绑定任务→CloakBrowser密码输入及页面校验→PNG/日志持久化→停止/失败/恢复→UI删除临时凭据。失败1iu9Wz保留，原因是测试点击中心被画布工具遮挡，改用实际可见内部点，未改产品或业务断言。

最终冻结166秒；测试只使用临时工作区与本次临时系统凭据，结束清理，无用户数据库写入。此项替代“项目worker缺凭据端口”；模型端口、助手会话归属和其他项目节点族/业务数据桥仍保留。213节点622/17不变，Intel/Windows未测。

## 项目任务模型消费（2026-09-23 后端链路）

按已确认的“项目默认值＋显式覆盖”规则，项目任务的无浏览器资源请求也冻结有效`modelProviderId`；纯数据任务不因未使用的模型默认值失效。15个已批准AI入口进入项目目录，并逐项核对批准范围与真实执行器注册。节点显式`modelId`优先；缺省时由主应用`ModelService`按冻结提供方解析。模型凭据只在派发时读取，经受控父子进程消息传入原有`WorkflowModelGateway`，不写入Batch、PreparedContent、CoreRun、日志或公开事件。解析失败以明确错误终止，未启动浏览器或worker。

[项目模型端口证据](../studio-backend-migration/evidence/project-integration/project-task-model-2026-09-23/result.json)覆盖正式项目启动的真实SQLite资源冻结、无浏览器AI节点的实际worker/HTTP模型调用、继承与显式覆盖、输出持久化、无秘密落库、缺默认与非法ID失败，以及原项目任务、AI worker回归。正式Electron开发入口和本次macOS arm64本地unsigned包从项目页真实编排AI摘要、保存、关联自动化并启动两次批次：先继承项目默认模型，再从节点显式覆盖；任务日志、输出及worker清理通过，冻结包哈希见证据。受控本地模型不算外部真实模型验收；其余项目节点族/数据桥、Intel/Windows仍未关闭。Studio 213节点和622/17执行槽位不因项目桥接测试重标。

## 小助手会话项目归属（2026-09-23）

新增0021增量迁移为小助手会话保存可空项目标识，历史会话仍归独立入口。项目甲、项目乙与独立入口的会话读取、修改、聊天、附件下载、工具命令确认和查询均按归属隔离；共享SSE保留连续游标，跨项目帧不含原数据。小助手运行或等待工具确认时，项目归档预检报告活跃会话，结束后解除。前端沿用现有项目URL边界，切换项目时清空会话状态、取消待审批动作并中止旧请求。

[本批专项证据](../studio-backend-migration/evidence/project-integration/assistant-project-2026-09-23/result.json)包含真实SQLite迁移、HTTP命令及产物、生命周期和前端请求测试。正式Electron开发入口与本次macOS arm64本地unsigned包均从项目页真实操作小助手、保存及正常关窗重开，独立入口不显示项目会话；PyInstaller和包内后端实际启动通过。项目默认模型由公开接口作为测试前置数据设置，本批模型服务是受控本地夹具；外部真实模型效果及Intel/Windows仍单列，不据此核销节点执行槽位。

## 项目任务基础控制流（2026-09-23）

[本批证据](../studio-backend-migration/evidence/project-integration/control-project-2026-09-23/result.json)把已迁入的WebRPA图调度和控制执行器接入项目预检：v3图文档保留条件、循环端口与真实拓扑，旧链式文档继续使用原顺序合同。项目目录登记九个已批准且已有执行器的控制／变量节点，不增加第二套调度器或数据库迁移。无入口的纯环在启动前拒绝。

正式Electron开发入口与本次macOS arm64本地unsigned包均从项目页编排、保存并启动三个批次。真实受管worker完成三轮增减与条件真分支，列表／字典各两轮遍历、列表体内嵌条件的真假分支、无限循环退出和两轮跳过；未选分支与被跳过节点无副作用。第三个批次在画布分组子流程内设置变量并以CloakBrowser打开受控网页，调用后尾节点取得42；任务输出、尝试记录及浏览器清理可查。项目预检保留定义分组，拒绝分组／便签连线和空执行图。历史`subflow_header`定义、其他嵌套组合、自定义模块依赖与业务数据写回仍按集成台账保留；Intel/Windows和17个实际环境槽位亦未核销。
