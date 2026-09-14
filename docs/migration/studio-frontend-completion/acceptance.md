# 前端完整交付：实际验收记录

日期：2026-09-13。当前为 F0 进行中；F1–F6 未完成。

## 已执行

| ID | 前置/操作 | 预期与实际 | 测试层级/证据 |
|---|---|---|---|
| F0-CATALOG-001 | 运行 inventory-studio-completion.mjs，从当前分类和 AST 取证 | 284 个唯一保留入口，全部找到直接条件/case 源码候选；通过 | 静态结构检查；capabilities.json |
| F0-ROUNDTRIP-节点类型 | 对每个节点调用实际 addNode→export→clear→import | 284 个节点创建的配置、位置、ID 均保留；通过 | Store 规则；catalog-roundtrip.test.ts；不是 UI 保存重开 E2E |
| F0-AI-001 | 已有 open_page，AI 请求仅添加 excel_create | 请求拒绝，原节点不变；通过 | excluded-assistant-nodes.test.ts |
| F0-AI-002 | AI 批量添加 open_page/qq_send_message，并连接两者 | 仅保留 open_page，删除悬空边；通过 | 同上 |
| F0-AI-003 | AI 请求已移除 Excel 工具/资源面板 | 明确拒绝且不切面板；通过 | 同上 |
| F0-UI-001 | 独立 localhost 预览→更多操作→全局配置 | QQ、飞书标签不存在；模型/数据库/凭据等保留；实点通过 | CUA 浏览器 AX 观察；见 evidence/browser-check.md |
| F0-UI-002 | 刷新独立预览，检查底栏及动作库 | 284 入口；无 Excel 资源页签；数据表格/全局变量/图像资源保留；实点通过 | CUA 浏览器；不是正式 Electron E2E |

## 台账边界

capabilities.json 和 test-cases.json 由 scripts/inventory-studio-completion.mjs 生成。1,988 条是逐节点的初始用例模板，尚需展开实际字段分支、工具与期望合同，状态为“待细化”。**不能将模板数当成已执行用例数。** 源码 AST 字段/组件是候选依赖，不是人工确认的完整调用闭包。

## F0 尚未关闭的事项

- 逐节点实际字段、共享工具、动态分发与全部分支的人工核对。
- 非节点能力逐项注册与具体用例展开。
- 排除能力的剩余 AI 工具描述、Mock 路由与无引用源码清理。
- 旧文档顶层排除节点闭环已通过；自定义模块内部的递归检查仍需核对。
- 现存数据/图像资源共享消费者审计；不得误删保留节点的配套功能。

## 未验收

全部 HTTP/SSE 契约一致性、运行/Debug/录制复杂闭环、正式 Electron 用户端到端、正式包及 macOS Intel/Windows。本轮浏览器实点不能替代这些验证。真实后端执行也未实现。

## 工程回归

- 全桌面单元/组件测试：79 个文件、765 项通过，见 evidence/unit-tests.txt。
- 首次全量检查发现 3 条新增中文缺少英文翻译；已补充 uiI18nDict 并完整重跑通过，没有放宽断言。
- 这些测试包含旧系统、源测试和新增用例；数量不代表 765 个端到端业务场景。
- TypeScript、ESLint、renderer/main/preload 构建通过；构建输出见 evidence/build.txt。依赖的 Rollup 注释警告保留在输出中，不影响构建成功。

## F0 第二批：旧节点与入口保护

- F0-LEGACY-API-001：保存含 excel_create 的旧文档，GET 保留原字段，execute 返回 422，活跃运行仍为空，再次 GET 无损；mock-transport.test.ts 通过。
- F0-AI-004～006：版本提交、发布和屏保动作不再执行；excluded-assistant-nodes.test.ts 通过。删除相应实际分支及权限元数据，保留已确认范围内的定时任务能力。
- F0-UI-003：宽窗口通过“导入整包”选择独立测试文件，选择旧节点显示原配置；F5 明确拒绝运行；保存→刷新→打开→选中，path=/original.xlsx、custom=preserve 保持。CUA 真实浏览器操作通过，接口为 Mock，不能计作正式 Electron E2E。
- 旧节点专属表单改为配置 JSON 预览；通用备注与高级设置仍可编辑，不声称整个文档只读。
- 284 个入口分类提取为纯 lib/moduleCatalog.ts，AI/Mock 不再反向依赖 React 侧栏组件。component-tools.json 增加函数式组件依赖候选，未解析项仍需核对，不能作为完整覆盖证明。
- 当前全量回归：79 个测试文件、769 项通过；TypeScript、ESLint 通过。renderer/main/preload 构建通过，见 evidence/f0-legacy-build.txt；测试输出见 evidence/f0-legacy-tests.txt。

## 工作台装配修复（F0 审计发现，F2.1 局部实施）

- INT-HOTKEY-001：挂载、配置修改、重连均下发当前快捷键；卸载后不重复处理；studio-integration.test.tsx 通过。
- INT-HOTKEY-002：服务触发已登记 action 恰好一次，未知/原型属性名拒绝；卸载后不触发；同上通过。
- INT-HOTKEY-003：富文本后代输入和按键长按不启动流程，普通快捷键阻止默认动作并触发一次；同上通过。
- INT-CONNECTION-001：错误可重复提示，失败重试保留提示、成功清除；connection-notice.test.tsx 通过。
- INT-CONNECTION-002：并发重试只发一次，旧成功响应不隐藏新错误；同上通过。
- INT-TRANSPORT-001/002：直接传输调用也通知网络异常；主动取消/409 业务错误不误报离线；transport-errors.test.ts 通过。
- INT-UI-001：CUA 打开 AI 面板，截图核实主编辑区和顶部场景区让出右侧 440px；工具栏按编辑区宽度使用折叠菜单；关闭按钮可明确访问。小画布内搜索/视图控件仍拥挤，容量布局用例未通过，不计 F2.1 完成。
- INT-UI-002：在线导入一节点测试包并确认节点可见，修改名称为 F0 离线节点草稿；服务离线→保存，记录 Mock network offline，节点保留；恢复连接→重试→保存，提示工作流已保存: F0 离线节点草稿.json。真实浏览器 UI + Mock，不是原生 Electron/后端执行。首次尝试导入时仍离线而失败、空流程保存被拒绝，这些失败没有记作通过。

全量回归 82 文件/776 项通过，TypeScript/ESLint/renderer-main-preload 构建通过。见 evidence/f0-integration-tests.txt 和 f0-integration-build.txt。全局 Tooltip、原浮动 AI 入口、全局热键真实宿主注册及其它 F2.1 项仍待完成。

## F0 注册和服务调用台账扩展

- service-inventory.json：当前 187 个 API 方法、83 个事件、105 个 AI 动作、62 处直接请求候选；记录源/目标路径和具体调用代码。数量包含死代码和未实现服务，不是完成数。移除无人消费的版本/屏保 API 前为 197 个方法。
- component-tools.json 现在包括箭头函数、memo/forwardRef 声明及 value/checked/onChange 等绑定。动态别名与同名组件可能有候选歧义，不能当完全人工核对过的合同。
- catalog-panel-registration.test.tsx：284 个真实 ConfigPanel 挂载，类型显示正确，无错误空态/排除提示。首次运行 284 项通过。该测试不包含每个表单的全部分支，不替代 F2 配置验收。
- verified-cases.json：将 284 个注册、284 个 Store 往返及 11 个配套规则测试写成有前置、步骤、UI/IO/状态断言和证据路径的窄范围用例。原 test-cases.json 仍是待细化模板。
- global-tooltip.test.ts：动态标题、安全文本展示、可访问名称、清理与重挂载通过；不伪称已完成全部鼠标/键盘 E2E。
- assistant-ui-delivery.test.ts：无消费者/同步异常返回失败，有消费者只调用一次，卸载不继续接收。
- excluded-assistant-nodes.test.ts：新增手机/桌面残留拒绝、替换/单项/批量排除类型阻止、合法替换保持 moduleNode/配置并可撤销。

新增测试曾发现测试存储环境缺失、keydown 的 Window target 不支持 closest、beforeEach 误返回 mock、源 Tooltip 短路表达式不符合 lint；分别修正测试设施或代码，没有放宽功能断言。

本批工程结果：85 文件、1,071 项测试通过，TypeScript/ESLint/构建通过，见 evidence/f0-registry-tests.txt、evidence/f0-registry-build.txt。类型/构建在删除无消费者 API 后再次通过。

AST 核对发现早期扫描将查询回调中的 open_page 比较扩展为整个 ConfigPanel，错误地拉入所有表单依赖。已在函数边界停止扩展，区分 reference 与 branch，并重新生成。没有使用旧候选图作为删除依据。共享 UrlInputDialog/SimilarSelectorDialog/CustomModuleConfig 在专属节点分支之外，仍需单独注册，不能因节点候选未引用而删除。

## Excel 配套清理与真实 HTTP 层验证

- 四个 Excel 专属组件、旧 dataAssetApi 及其分发已删除；checksum/消费者依据见 excluded-source-files.json 和 excluded-capabilities.md。
- mock-transport.test.ts：Excel GET/上传/删除返回 410，已有存储字节原样保留；图像资源正常；嵌套自定义模块包含排除节点时返回 422，模块/文档无损。
- excluded-custom-modules.test.ts：循环引用不重复检查，不修改内容；它不代表循环执行合法。
- HTTP-DOC/CMD/SSE/CLIENT 四场景分别通过 memory/http，共 8 项；完整数据/操作/边界见 http-fixture.md。
- 全量 87 文件、1,082 项测试通过，TypeScript/ESLint/renderer-main-preload 构建通过，见 evidence/f0-http-tests.txt 和 evidence/f0-http-build.txt。
- 284 属性面板和既有保存/编辑测试通过。F0 仍有其它专属配置源码/字段用例未关闭；F1 只有局部 HTTP 夹具，不能标完整合同已冻结。

## F0 专属配置与媒体服务清理

- 通过导入关系与 284 个保留节点分发逐项核对，移除 16 个已排除类别的专属配置文件；删除 ConfigPanel 的排除分支及桌面拾取状态/轮询。共享网页定位、相似元素、自定义模块配置保留。
- 移除六个专属音乐/视频/图片播放容器及弹窗。旧媒体执行事件返回失败回执，不启动播放器、不发转换请求；保留 text_to_speech 及停止时语音清理，图片资源不变。
- 删除的源文件路径、冻结 checksum、原因保留于 excluded-source-files.json；已有工作流及资源数据未删除。源注册表现在为 250 文件。
- 284 面板注册与 284 保存往返通过；新增三个过期媒体事件回执及一个语音取消测试通过。
- 首次全量回归发现新增失败文案缺英文词条，补入原字典后重跑，未削弱断言。逐字段交互、Electron 原生 E2E 尚未据此宣称通过。
- 重跑全量结果：88 文件、1,086 项通过；TypeScript、ESLint、renderer/main/preload 构建通过。证据：evidence/f0-exclusive-tests.txt 与 evidence/f0-exclusive-build.txt。

## 保留计划任务配套迁入

八个源 UI/Store 文件、Toolbar/AI 消费者及 Mock 协议已接通，详见 scheduled-tasks.md。新增任务协议五项、组件两项、memory/http各一项；全量 90 文件、1,095 项通过。真实浏览器实测创建、重载、修改触发器及422失败提示；不计原生 Electron 或后台调度通过。源列表错误不显示及源 Store 误判成功已修复。首次组件断言错用英文错误而运行器返回既有中文错误，已改为断言规范中文，不放宽错误语义。
TypeScript、ESLint、renderer/main/preload 构建通过；证据 f0-scheduled-tests.txt、f0-scheduled-build.txt。日志仅规范尾部空白。类型检查发现测试误用 Playwright exact 选项，已移除并沿用 RTL 默认精确匹配；lint 的多余 let 已修复。

## 2026-09-14 范围调整

用户明确取消界面国际化；历史 i18n 记录保留，但不再构成后续门槛。中文单语言实现及测试见 [中文单语言验收](chinese-only.md)。完整回归 99 文件 / 1,167 项通过；F0–F6 全量验收仍未完成。

## 2026-09-14 连续实施增量

本轮已经完成画布脏状态、SSE完整帧补读、命令响应身份、图片资源受控读取/上传/重命名，以及确定执行轨迹的局部修复与验收。详见 graph-dirty-validation.md、sse-framing-validation.md、command-identity-validation.md、image-resource-validation.md、image-command-validation.md、execution-order-validation.md。

最近前端全量125文件/1453用例通过；其后公共命令schema接入的定向前端36通过、后端全量421通过，类型/lint/构建与OpenAPI、17脚本检查通过。浏览器实际链路分别有记录，全部明确Mock边界。正式Electron、各平台打包及F0–F6完整退出门槛仍未完成。不要用这些通过数量代替全部能力覆盖。

## 2026-09-14 输入、调试与参数链路增量

- 输入13种模式验证、稳定命令回执、丢响应查询、历史输入请求状态核验、停止回收：input-command-protocol.md、input-recovery-validation.md。
- 文件/目录配套选择的取消兼容、错误显示和迟到结果保护：input-path-validation.md。
- 调试条等待事件确认、停止优先、拒绝/未知提示和其他工作流事件过滤：debug-bar-validation.md。
- 单条/批量日志原始时间及重放：log-timestamps-validation.md。
- 数字原文保留、错误提示与等待节点保存重开：number-input-validation.md。

最新全量136文件1648项通过，类型/lint、renderer/main/preload构建与21脚本通过。输入状态schema30项、Ruff/mypy/OpenAPI在对应批次通过。实际浏览器操作证据已分别记录，全部保留Mock边界。

F0仍需完整字段/动态工具依赖核对；F1仍需全部操作schema和独立运行/会话合同；F2仍需全图预检与全部284节点分支；F3仍缺服务端暂停身份、命令幂等、运行历史与其它交互命令；F4仍缺全局拾取/录制会话所有权与完整生命周期；F5宿主与权限/离开协调未收口；F6正式Electron及打包/跨平台未验收。没有任何整批因此标为完成。

## 定位协议增量

定位测试成功响应运行时校验、生成schema和显式Mock场景已接通，详见 selector-protocol-validation.md。新增前端28、后端18项通过，正式页面组件的预览点击已记录；全量138文件1690项、类型/lint、Ruff/mypy、构建、21脚本及OpenAPI通过。F0–F6整体缺口仍按上述清单保留。

## 写回与运行事件归属增量

修复建议绑定启动源文档，确认期间校验旧字段，整批可撤销；见selector-healing-validation.md。外来终态/节点/数据事件不污染当前流程，输入请求按自身身份回收；见event-ownership-validation.md。最新全量141文件1706项通过，类型/lint/构建通过。独立runId、会话所有权、原生宿主和F0–F6整体门槛仍未完成。

## 相似元素服务闭环增量

已打通显式Mock相似元素审查、索引命名、整批应用/撤销/重做和保存重开，响应使用生成schema并有运行时检查。见similar-picker-validation.md。前端全量142文件1715项、后端502项、工程检查通过，仍不计真实网页识别或正式Electron验收。

## 2026-09-14：脚本回传与连接恢复补齐

浏览器状态严格校验与停止期间迟到结果失效见browser-status-validation.md；快捷键/拾取错误及连接恢复见service-recovery-validation.md（146文件1749项全量通过）。JavaScript领取、Worker、回传、取消及变量追踪见js-script-validation.md（151文件1799项全量通过，后增边界用例另记专项结果）。真实浏览器发现并修复横幅残留、无初值占位与诊断记录缺失。F0–F6仍未整体完成，Mock及平台边界保持原标注。

## 2026-09-14：变量追踪服务确认与上下文保护

GET/DELETE合同、错误保留、清空确认、迟到请求、活跃运行清空后继续记录及对象搜索已补齐，见variable-tracking-validation.md。152文件1821项前端全量通过，正式窗口及容量/服务端分页仍未完成。

## 2026-09-14：代码编辑器补全与事件上下文

三种编辑器补全范围/释放，重复和外来开始/日志事件，以及日志缓冲离开保护已修复。153文件1829项全量通过，见editor-event-context-validation.md。独立runId和正式宿主等原有缺口仍在。

## 2026-09-14：零值滑块与保存回显

文本朗读音量和声音触发阈值0不再被默认值替代，原生滑块具备对应标签；浏览器保存重开通过。新增10项、数字输入联合36项、面板/输入弹窗327项回归及工程检查通过，见zero-slider-validation.md。
