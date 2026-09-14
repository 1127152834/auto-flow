# 变量追踪服务消费与竞态保护

2026-09-14，confirmed（有界切片）；F0–F6 未整体完成。

来源：冻结 WebRPA backend/app/api/workflows.py:1294、1317 及原 VariableTrackingPanel。保留 GET/DELETE /api/workflows/{workflowId}/variable-tracking 的路径和 snake_case 记录。GET 返回 tracking 与一致的 count；DELETE 成功返回非空 message。OpenAPI 模型发布后生成前端类型，共享 API 校验记录形状、操作类型、数量及清空确认，继续使用现有鉴权/连接适配。

读取失败或畸形数据保留最后确认记录并显示错误。清空期间禁止重复提交，先取消在途读取；清空失败保留记录，成功确认后才清空。组件关闭/换流程会取消请求，迟到读取或清空响应不能写入新上下文。轮询不重叠，重新打开即读取；清空活跃 Mock 运行后仍可追加新变量变化。

浏览器实测发现对象搜索使用 String(object) 导致命中失败，改为搜索 JSON 内容；筛选零匹配单独提示，不再声称没有运行记录。更新前值为 null 也明确展示。

专项测试：16 个面板/读取契约用例，另加内存/HTTP 各 1 个活跃运行清空后继续记录用例；与现有脚本协议和消费合计 44 项通过。后端 7 项合同测试通过。Ruff 初次发现测试 dict 写法，修正后通过；未删除用例或放宽断言。全量前端152文件1821项通过；TypeScript、ESLint、renderer/main/preload构建、21脚本、OpenAPI、Ruff、mypy通过，日志见证据目录。

历史状态（已被下述2026-09-15结果替代）：此兼容端点仍按 workflowId 返回完整记录，没有独立 runId/分页/服务端筛选。导出仍是已加载记录 JSON，不能宣称完成大规模诊断及固定截止序号导出。Mock 记录仅驻留内存；未验收真实自动化后端或正式 Electron/其他平台。


## 2026-09-15：F3.3 按运行结果与诊断收口

差异归类：原表格/变量面板交互、排序过滤算法属于原版功能迁入；独立 runId、固定截止分页、大值按需加载与导出属于 F3.3 已批准增强；OpenAPI 类型与宿主原生下载属于 AutoFlow 必要适配。未新增自动化执行器。

- 结果面板默认展示所选运行的只读结果，保留原版可编辑表格作为明确的本地编辑预览。服务失败不请求全局 latest。原表格排序后仍按原行索引编辑/查看。
- 运行历史支持继续翻页，刷新保留明确选中的旧运行。切新运行当帧隐藏旧日志，不回退到旧 Store 日志。
- 变量面板使用运行级分页和服务端完整记录筛选，单页100条；可显式选择历史运行。按截止序号导出所有匹配记录，不能只导出当前页。大值摘要与真实 null 分开，完整值按序号和 side 获取。
- 清空后保留运行序号高水位，旧记录引用不能复用为新值；清空/关闭/换运行取消在途读取。Mock 运行记录与结果持久化到既有本地数据库夹具；真实后端仍需按同合同实现。

服务合同（均以现有 `/api` 为根，沿用鉴权、错误包、连接适配）：

| 方法与路径 | 请求/返回 |
|---|---|
| GET `/workflow-runs/{runId}/results` | cursor、limit(1–500)、throughSequence；返回runId/workflowId/items/total/nextCursor/throughSequence。每行sequence/nodeId/executionId/values/largeValues |
| GET `/workflow-runs/{runId}/results/{sequence}/value?key=...` | 返回runId/sequence/key/value；必须匹配请求身份 |
| GET `/workflow-runs/{runId}/results/export?throughSequence=...` | 固定截止的完整类型值JSONL，不回退其他运行 |
| GET `/workflow-runs/{runId}/variable-tracking` | 同分页/截止；query、variable、operation、valueType由服务筛选全部记录；返回tracking和总数 |
| GET `/workflow-runs/{runId}/variable-tracking/values?sequence=...&side=old_value或new_value` | 按记录身份读取完整值 |
| DELETE `/workflow-runs/{runId}/variable-tracking` | 返回相同runId和非空message；序号高水位不回退 |
| GET `/workflow-runs/{runId}/variable-tracking/export` | 同筛选，固定throughSequence，完整值JSONL |

变量记录保留原版 snake_case 字段，扩展 sequence/executionId/largeValues；摘要响应将大值槽置null并在largeValues标识，完整导出无截断。不存在运行/记录404，非法分页或截止422，服务错误不伪造成功。旧workflowId兼容端点保留，不能当运行请求失败时的兜底。

实际证据见 `evidence/f3-run-results/`：组件+内存/实际HTTP合同、原生UI操作记录和磁盘导出。此前10k日志/SSE恢复及Debug命令验收继续引用 execution-log-history-validation.md、debug-run-variable-validation.md，不重复冒充新测试。完整后端、分发包及未测平台不计通过。


末尾故障验证：存储失败最初会修改Mock运行变量但不保存诊断，新增反例复现（storage-red.log）。改为先原子持久化诊断，再提交运行变量与兼容追踪；启动初值与运行记录同次持久化，失败不占用活跃名额。两项存储故障及关联输入/调试/分页共14项通过。初值执行标识明确为runId:initial，不冒充节点首次调度。

块关闭扩大回归：303文件中301通过，3460项中3458通过。两项失败完整保留：配色审计严格计数仍写284，按已批准排除范围更新为227，逐项配色断言不变；WebDAV保存后立即离开偶发未触发关闭，单文件34项通过，尚不能宣称根因解决，登记F5.2非F3阻塞，不假称全量通过。F3相关11文件60项通过，末尾存储4文件14项通过（部分重复，不相加当唯一数）。类型/lint/构建/合同证据各按其快照保留。最后两项存储修复在原生验收之后，正式最终包需由F6再次覆盖。
