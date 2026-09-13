# 运行记录与环境原型逐图对齐

日期：2026-09-13
状态：confirmed（原图观察完成）；proposed（新系统适配与阶段映射）
来源：`docs/references/project-management-prototypes-2026-09-13/manifest.json` 的 `latest/03-runs` 21 张与 `latest/06-environments` 18 张。本文逐张以原始分辨率实际查看，不以标题替代看图。

## 已确认适配边界

- 保留 AutoFlow 当前顶部全局导航；原型左侧全局栏只作为内容与层级参考，不照搬。
- 运行记录是历史事实。任务结果、日志、输入输出、异常与证据先查询服务端事实，不从 UI 状态推断；失败任务不原地重跑。
- 数据记录的业务状态独立于 Task/Batch/环境状态，不因运行成功、失败、停止或清理而自动推进。
- 每个 Task 使用独立环境实例。临时环境默认清理；工作流 End 明确配置保存时，才保存当前环境并关联相关业务记录。保存成功但关联失败必须保留环境并提供修复路径。
- 环境清理、任务结果、数据占用分别核验，互不推导。清理请求结果不明时，只查询原命令；确认未接受后才可用原键重发。旧操作若已接受并以失败终结，则按失败事实创建显式的残留清理新操作，不能把旧操作当作未接受重发。

## 03-runs：21 张

| 原图 | 实际看到的结构与动作 | 禁用、错误、恢复与返回 | 新系统适配 / PM阶段 |
| --- | --- | --- | --- |
| `PMUI-2cd367411306` `latest/03-runs/001-run-records-v1-approved-2cd367.png` | 项目内运行记录，批次/任务/等待人工三级页签；搜索、自动化与时间筛选；批次表显示开始、状态、成功/失败数，进入记录或异常。 | 分页边界禁用；页脚明确任务结果数不等于数据新增量。 | 顶部导航承载项目上下文；PM3提供参数型Batch列表，PM4补数据执行结果。 |
| `PMUI-9a81f19297bf` `latest/03-runs/002-task-list-approved-9a81f1.png` | 任务表按批次、输入标识、状态、节点、最近状态时间查询；等待人工进入事项，失败进入日志，成功进入任务。 | 明示任务记录只读、输入快照不随业务表变化。 | PM3交付Task/CoreRun查询与稳定输入快照；PM5开放人工入口。 |
| `PMUI-09ab4db96ce3` `latest/03-runs/003-manual-list-selected-v2-09ab4d.png` | 等待人工列表显示原因、任务、批次、输入、剩余保留时间，支持搜索、按剩余时间排序及进入事项。 | 倒计时是展示；说明等待人工不暂停整批次。 | PM5；PM3不得展示可操作的假人工入口。 |
| `PMUI-459f2512d622` `latest/03-runs/004-batch-detail-approved-459f25.png` | 批次头部、起止/耗时/原因、成功失败汇总、任务筛选分页、只读配置快照。 | 黄色提示批次结束不代表全部成功；返回批次列表。 | PM3基础详情；PM4补数据型任务及实际计数。 |
| `PMUI-510347fcb949` `latest/03-runs/005-task-log-510347.png` | 失败任务详情；节点与尝试时间线、分级日志搜索，错误日志直达异常证据。 | 未执行节点明确；每次尝试独立保留，失败记录不可重写；返回批次。 | PM3真实事件日志、补读与只读事实。 |
| `PMUI-7af0aa5dbf06` `latest/03-runs/006-task-input-output-approved-7af0aa.png` | 左侧固定参数和本任务数据输入快照；右侧最终输出缺失、中间节点输出、证据附件。 | 当前记录可能变化；中间输出不代表任务成功；附件与业务结果分别保留。 | PM3参数输入/产物；PM4加入Data RecordRef快照与互查。 |
| `PMUI-559ddf21e9c4` `latest/03-runs/007-task-exception-evidence-approved-559ddf.png` | 异常摘要含错误码、节点、尝试、时间、说明；失败截图、错误文本和历史尝试。 | 可定位对应日志；证据属于本次任务，不随当前页面或数据表变化。 | PM3受控artifact与错误证据。 |
| `PMUI-d5f491b409df` `latest/03-runs/008-manual-detail-v2-approved-d5f491.png` | 人工事项详情：冻结现场截图/输入/资源、剩余时间；继续节点、完成、失败三种处理。 | 未接入环境时“打开环境”和提交禁用；处理回写原任务，不创建新任务；返回等待人工。 | PM5。End保存环境与记录关联按新语义实现，不增加独立Bind步骤。 |
| `PMUI-cfe619a5fc06` `latest/03-runs/009-task-filter-cfe619.png` | 任务状态下拉、筛选chip与清除；失败结果保留日志入口。 | 时间按最近状态时间；分页禁用态可见。 | PM3通用查询状态。 |
| `PMUI-7c122b5f3cb6` `latest/03-runs/010-capability-unavailable-7c122b.png` | 保留页签和筛选框架，但中央说明能力未接入，提供返回自动化和能力说明。 | 控件整体禁用；明确“不代表没有运行记录”。 | 当前至PM3接通前的诚实不可用态。 |
| `PMUI-a916def01912` `latest/03-runs/011-empty-a916de.png` | 查询完成、0批次空态，主动作查看自动化。 | 与能力未接入态严格区分。 | PM3。 |
| `PMUI-8f158b0e642b` `latest/03-runs/012-no-results-8f158b.png` | 保留表头与筛选条件，中央无匹配；动作清除搜索、扩大时间范围。 | 显示当前筛选结果0，不混同全库空。 | PM3。 |
| `PMUI-b84d0ee17963` `latest/03-runs/013-loading-b84d0e.png` | 筛选框保留、表格骨架、读取提示。 | 分页禁用并标“页码待查询”；切筛选以最新查询结果为准。 | PM3，需scope/请求epoch隔离。 |
| `PMUI-28344b2ccafd` `latest/03-runs/014-refresh-error-28344b.png` | 旧列表仍可见，上方显示刷新失败、旧数据时间、重试与展开错误。 | 标识“非最新状态”；不清空已知事实。 | PM3，保留旧投影并显式刷新。 |
| `PMUI-e79f810a29f4` `latest/03-runs/015-stop-confirm-e79f81.png` | 运行批次停止确认；说明停止领新数据、活动任务安全结束、等待人工自然超时，历史不受影响。 | 强调停止不可从这里恢复；确认前未提交。 | PM3-C交付安全停止请求、未知结果查询和旧worker撤权；PM4补领取/lease与数据边界。 |
| `PMUI-00d61e05c305` `latest/03-runs/016-force-stop-confirm-00d61e.png` | 停止中批次的强制停止确认；要求输入批次编号。 | 警告活动上下文和未提交中间内容可能丢失，服务端确认优先。 | PM3-C交付强停请求、未知结果查询和旧worker撤权；PM8只补完整生命周期收口。 |
| `PMUI-d5287cb18c62` `latest/03-runs/017-running-task-logs-d5287c.png` | 执行中任务的节点时间线和实时日志；跟随滚动暂停时提示新日志并可跳到最新。 | 未结束、待执行节点明确；尚无最终业务输出。 | PM3事件流、断线补读与游标恢复。 |
| `PMUI-85b8b563e5b4` `latest/03-runs/018-manual-check-failed-85b8b5.png` | 人工详情仍保留现场；环境检查失败，提供重新检查。 | 继续工作流禁用，保留时间不重置；只检查原快照，不换成最新工作流。 | PM5。 |
| `PMUI-919ab528c908` `latest/03-runs/019-manual-complete-confirm-919ab5.png` | 标记完成人工事项的确认弹窗；可填说明并必须勾选知情确认。 | 明确完成不等于资料已保存或自动写入业务数据，处理回原任务。 | PM5；若End要求保存，保存与关联必须报告各自结果。 |
| `PMUI-98016b070643` `latest/03-runs/020-manual-expired-98016b.png` | 人工保留时间到期，任务失败；历史现场与任务日志可查，资源清理单列待确认。 | 不再允许提交人工处理；刷新状态只查询事实。 | PM5人工超时，PM8补完整清理核验。 |
| `PMUI-f523b7905fd4` `latest/03-runs/021-evidence-missing-f523b7.png` | 异常证据页缺截图，但错误文本、错误码、历史尝试仍在。 | 明确缺截图不影响其他证据；不是整页失败。 | PM3基础artifact unavailable，PM5/PM8补现场生命周期。 |

## 06-environments：18 张

| 原图 | 实际看到的结构与动作 | 禁用、错误、恢复与返回 | 新系统适配 / PM阶段 |
| --- | --- | --- | --- |
| `PMUI-f757d2d1a115` `latest/06-environments/001-environment-main-v1-approved-f757d2.png` | 环境页分运行环境、等待人工、持久环境、项目默认资源；当前现场按人工和自动运行分组，右侧默认资源/持久环境摘要。 | 页面说明当前执行能力未接入，现场仅示意。 | PM3只开放真实临时实例读态；PM5完成全部页签。 |
| `PMUI-9ff896ee6a9f` `latest/06-environments/002-running-environment-detail-9ff896.png` | 临时环境详情含最新截图、当前节点/事件、任务入口、浏览器和代理快照、生命周期。 | 截图非实时；任务结束后清理，未声明保存不自动保留。 | PM3临时实例及清理账本；PM4补数据占用。 |
| `PMUI-3a0ed24d0238` `latest/06-environments/003-manual-environment-list-3a0ed2.png` | 等待人工现场列表显示缩略图、任务/批次/输入、原因和剩余时间，可查看现场或进入处理。 | 明示执行槽已释放，但保留浏览器、输入和租约。 | PM5。 |
| `PMUI-9f9960189c44` `latest/06-environments/004-persistent-list-9f9960.png` | 持久环境可搜索、按状态筛选、刷新；显示来源Task/Batch、保存时间、引用数和更多菜单。 | 保存中、失败、已过期分别展示；陈旧读取提示立即刷新。 | PM5；引用数必须真实查询，不伪造。 |
| `PMUI-70a735e4d748` `latest/06-environments/005-persistent-environment-detail-70a735.png` | 持久环境基本信息、来源任务、保存原因、资源快照和截图。 | 强调后续任务只把它作为创建来源，每任务仍创建独立环境。 | PM5。 |
| `PMUI-4455876cef6d` `latest/06-environments/006-resource-defaults-445587.png` | 项目默认浏览器/代理选择，管理全局资源入口；底部先核对影响、取消、保存。 | 未核对时保存禁用；保存只改默认，不创建环境或运行。 | PM3-A资源配置适配；保留End保存关联语义。 |
| `PMUI-b6a666548c7a` `latest/06-environments/007-resource-impact-and-invalid-b6a666.png` | 默认资源影响预览列出继承方案；浏览器引用失效，提供去全局配置修复和重新核对。 | 引用失效不自动换源或直连，保存禁用。 | PM3-A，稳定资源ID、revision与candidate。 |
| `PMUI-8598c1dcd25f` `latest/06-environments/008-resource-version-conflict-8598c1.png` | 后台配置变化冲突弹窗并排“我的修改/最新内容”。 | 可继续编辑或采用最新版本并保留我的修改；不自动覆盖。 | PM3-A CAS与显式rebase。 |
| `PMUI-47ae56bb3331` `latest/06-environments/009-resource-unsaved-leave-47ae56.png` | 未保存离开确认显示当前浏览器/代理草稿。 | 未完成影响核对时“保存后离开”禁用；可继续编辑或放弃本次草稿。 | PM3-A统一leave guard。 |
| `PMUI-8eb31da6c89c` `latest/06-environments/010-runtime-availability-states-8eb31d.png` | 同页并列未开放、确实无现场、读取失败三种状态及对应动作。 | 三者不可混用；读取失败提供重新读取。 | 当前/PM3能力门控的权威状态规范。 |
| `PMUI-ea61357bb97a` `latest/06-environments/100-rename-validation-conflict-ea6135.png` | 持久环境行内重命名示例；名称唯一、最多36字符。 | 同名校验错误、并发更新提示保留草稿，保存禁用直到解决。 | PM5，稳定environmentId不随名称改变。 |
| `PMUI-3a2ef6f57afe` `latest/06-environments/100-delete-impact-preview-3a2ef6.png` | 实际画面是“持久环境已删除”的结果页：删除环境记录，保留运行记录、历史快照、数据和全局模板，带操作编号。 | 删除不可撤销，返回环境。manifest标题称“删除环境影响预览”与画面不符，应以画面事实记录。 | PM8删除结果；实施前仍需独立影响预检状态。 |
| `PMUI-b15079893dbc` `latest/06-environments/100-rename-drawer-b15079.png` | 持久环境详情右侧重命名抽屉，实时名称可用校验；说明ID和任务引用不变。 | 取消/保存名称，关闭抽屉返回详情。 | PM5。 |
| `PMUI-b144be36f3ca` `latest/06-environments/100-save-with-warning-b144be.png` | 默认资源核对结果：引用有效但代理连接检测超时；列出每个方案实际浏览器/代理变化。 | 可带警告保存；不会启动任务或自动直连。 | PM3-A。 |
| `PMUI-eaa49aead521` `latest/06-environments/100-invalid-reference-eaa49a.png` | 默认浏览器引用不存在；旧影响仅作参考，方案待重新核对。 | 必须重新选择浏览器，保存禁用；不静默替换。 | PM3-A。 |
| `PMUI-da12148a156c` `latest/06-environments/100-cleanup-unknown-da1214.png` | 临时环境任务已结束，清理请求无响应；事件表和关联任务/批次/输入可查。 | “核验清理结果”可用，“重试清理”禁用；先确认上次请求避免重复。 | PM3-C按原命令身份查询；确认未接受后才用原键重发，已接受的旧操作不得重发。PM8补完整生命周期收口。 |
| `PMUI-6a82d660e25b` `latest/06-environments/100-cleanup-failed-6a82d6.png` | 已核验清理失败，显示浏览器退出但目录因占用残留；事件链完整。 | 核验后才开放重试；重试只处理残留环境，不重跑任务。 | PM3-C保留终态失败账本，并为残留清理创建新操作；不能把已接受且失败的旧操作当作未接受重发。PM8补运维生命周期收口。 |
| `PMUI-6c0606a45f0f` `latest/06-environments/100-cleanup-completed-6c0606.png` | 清理完成，浏览器退出、临时目录移除；历史事件仍保留。 | 任务结果仍失败、清理结果完成、数据占用待确认，三者不互相推导。 | PM3清理完成事实；PM4提供数据占用独立核验。 |

## 诊断阶段边界补充

以上日志、输入输出、异常、实时日志原型展示的是最终完整形态。PM3只验基础节点日志、错误/截图与序号恢复；完整attempt/变量快照/输入与当前数据及输出互查按PM7。对应逐图JSON已单独补齐PM7依赖，不能因画面放在PM3参考集而视为PM3全交付。

## 实施顺序

1. **PM3-A**：复用现有自动化配置，交付项目默认资源的resolve/impact/save、稳定引用、版本冲突和离开保护。
2. **PM3-B/C**：真实Batch、Task、CoreRun、输入快照、日志事件补读、基础产物、临时环境实例、清理账本、安全停止、强制停止、未知结果查询及旧worker撤权；参数型任务首次可用。
3. **PM4**：数据型任务、RecordRef领取与lease、写入结果和数据占用独立核验。
4. **PM5**：等待人工、现场恢复、持久环境及End保存当前环境并关联业务记录；部分成功必须保留环境并允许修复关联。
5. **PM8**：环境删除影响及跨项目关闭、归档、删除等完整生命周期收口；不延后PM3-C已包含的停止与强停能力。

截图只能证明可见结构和文案，不能证明键盘顺序、焦点圈、读屏名称、实时更新、请求幂等或服务端状态机；这些需要组件测试、契约测试和真实运行验收。
