# F3 输入请求、回传与后续调度协议

2026-09-14。按冻结 WebRPA app/main.py 的 execution:input_prompt 请求字段和 executors/basic.py 的输入结果行为接入前端协议夹具。真实自动化后端未新增运行器。

## 请求与状态

input_prompt 节点开始后生成独立 requestId，发送 execution:input_prompt，然后保持运行占用，不完成当前节点或调度后续节点。事件带 variableName、title、message、defaultValue、inputMode、范围/长度/必填/候选项，以及夹具的 workflowId/nodeId。源码 promptTitle/promptMessage 映射到事件 title/message。

13种输入模式及结果包络由 StudioInputPromptRequest/StudioInputPromptResult 发布到既有 OpenAPI。事件消费者和输入组件共同引用生成类型；旧事件缺少可选约束时由显式可选字段映射兼容，nullable 数值约束映射为原生输入属性的 undefined。没有第二套 contracts 包。

POST /api/events/commands 的 input_prompt_result 命令包含 commandId 与 data:{requestId,value}，value 只能为字符串或 null。正确请求先消费 pending requestId，再更新运行变量并完成节点/继续调度。同commandId同内容返回原结果；新commandId回答已消费请求、未知请求或已停止运行返回409；非法结果类型返回422，不推进。GET原commandId仍可查询成功或拒绝结果。

null 按源逻辑表示用户取消本次输入：原变量不变，后续节点继续。数字、整数、复选框、列表及多选按既有原文编码转换；不执行表达式，不修改草稿初值。停止清除等待责任，迟到结果不能重新调度。请求等待的真实超时、完整运行身份和资源清理另按运行契约完成。

命令夹具不再为未知事件泛化返回成功：未实现命令501，拒绝结果可按原ID查询。set_verbose_log 和 set_current_workflow 检查布尔/非空字符串字段并记录夹具配置；它们不冒充正式宿主的客户端过滤与热键能力。

## 验收

新增26个内存/真实HTTP协议用例：初始20项全部失败；修复后补充未知命令与错误元数据，新增6项修复前失败。输入与命令相关99项通过。新增25个Python schema用例，加导出回归28项通过；后端全量467通过，Ruff、mypy通过。前端全量129文件/1572项通过，类型、lint、构建、OpenAPI和21脚本检查通过。

真实UI完成导入→运行→等待弹窗→填值→提交→后续节点完成→保存，证据 evidence/f3-input-protocol/browser-ui.md。原始普通JSON误用整包入口被拒绝，修正夹具后通过，未放宽产品校验。输入后的提取为Mock事件，不是真实网页操作。

更正：上一批 input-prompt-validation 的测试与构建通过，但其类型检查确实失败，原文“类型通过”已更正，初始失败日志保留。本批通过统一生成类型、修复测试库参数和nullable原生属性，重新运行类型检查并确认退出码0。

## 后续缺口

输入提交回执、响应丢失查询、历史输入事件过滤及匹配工作流停止后的弹窗回收已在 input-recovery-validation.md 补齐。输入队列、完整独立运行身份、JS等其他交互命令、跨服务重启恢复仍未验收。F1/F3未完成。
