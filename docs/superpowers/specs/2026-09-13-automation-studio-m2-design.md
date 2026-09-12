# Automation Studio M2 规格

- 日期：2026-09-13
- 状态：confirmed；用户明确要求实施本轮 M2 计划。
- 基准：正式 M1、WebRPA 冻结源码；实现目录遵守 docs/PROJECT_STRUCTURE.md。

## 产品约束

运行当前未保存草稿快照，不自动保存；运行期间可继续编辑和手动保存。每工作区一个活跃运行，无队列。每次使用所选 Profile 的临时独立 CloakBrowser context，尊重 headless、内核、指纹、代理等参数，不访问 Profile.start_url、不接管测试浏览器、不继承登录态。所有终态在清理浏览器进程树后确认。

六节点沿 M1 字段与默认值：open_page、click_element、input_text、wait_element、get_element_info、screenshot。timeoutSeconds 默认 60，正小数合法；节点只使用一个总预算。单条连通顺序链，按连线执行；无重试、控制流、Debug、录制、拾取。允许保存未完成稿，运行须通过结构、配置、初值、引用顺序、资源校验；重复输出仅警告并顺序覆盖。

CSS/xpath= 取首个匹配。输入支持替换/追加/空文本及容器内可编辑元素，不向不明焦点输入。四种等待严格映射。提取使用 textContent/innerHTML/input value/原始 href/src/全属性；缺失属性为 null。点击前注册 popup，跟随等待最多3秒且受总预算约束，无弹窗不是失败；当前页手动关闭不能偷偷换页。

普通引用 {name}/${name} 使用 M1 Unicode 完整标识符；初值可引用声明初值，依赖循环或输出未产生须报错。节点文本解析一次；number/bool/array/object 转 JSON 文本，null 为空，输出类型可变化，不回写文档。

PNG 默认 workspace/runs/<runId>/artifacts。相对路径限本轮产物目录，绝对路径尊重用户配置；大小写不敏感 .png 是文件，否则目录。显式文件已存在报错，唯一生成名不覆盖；自定义目标保留工作区副本。结果为真实落盘后的路径。完整提取数据也存产物文件，进程事件仅引用与短预览。

## 接口与内部契约（实施协调）

HTTP 前缀 /api/v1/workflows/runs，静态路由在旧 /{id} 前注册。POST 接收 {runId,document,layout,profileId}。相同 id/请求幂等返回原运行，不同请求409；响应不明查询同 id，不换 id 重跑。不强制文档落库。GET 列表支持 workflowId、offset、limit，返回 {items,activeRunId,nextOffset}。GET /{runId} 完整记录；POST /{runId}/stop 幂等停止。GET /{runId}/events?afterSeq&limit 返回 {items,hasMore,nextSeq}；GET /{runId}/stream?afterSeq 为可补读 SSE；GET /{runId}/artifacts/{artifactId} 仅读取已登记产物。

Run state: starting | running | finishing | stopping | succeeded | failed | cancelled | interrupted。

RunRead: runId, workflowId, name, profileId, profileName, state, document, layout, profileSnapshot, nodeOrder:string[], currentNodeId:string|null, startedAt, finishedAt:string|null, latestSeq:number, completedNodeIds:string[], error:RunError|null, artifacts:RunArtifact[], warnings:WorkflowIssue[]。RunSummary 为上述摘要（去掉 document/layout/profileSnapshot/artifacts/warnings/nodeOrder）。时间均后端 UTC ISO。RunError: {code,message,nodeId:string|null,path:string[]}。

RunEvent: {runId,seq,timestamp,type,nodeId:string|null,level:'info'|'warning'|'error',message,durationMs:number|null,artifactId:string|null,error:RunError|null}。RunArtifact: {id,nodeId,kind:'json'|'image',name,mimeType,relativePath,outputPath:string|null,preview:string}；relativePath 是本轮 artifacts 内的文件名，读取须防 symlink/path 逃逸。不要把密码/License/原始异常堆栈写入事件。

根任务负责 domain/workflows/run_validation.py：PreparedWorkflow(document:dict,node_ids:list[str],variables:dict,warnings:list[WorkflowIssue])；prepare_run(document,layout)->PreparedWorkflow；resolve_node_config(node,variables)->dict，失败抛 WorkflowError，issues 定位 nodeId/path。effective document 只补缺省参数，原始快照仍单独保留供 UI 对照。

运行 worker 负责人提供 infrastructure/process/workflow_worker.py 的 WorkflowWorkerManager(temp_root:Path,runs_root:Path)。async execute(run_id,prepared,profile,executable,proxy,license_key,on_event)->dict，回调 async on_event(dict)。stop(run_id)、shutdown() 均 await 清理；busy()->bool。prepared 为上面的 PreparedWorkflow。manager 只执行，不处理资源锁或 DB。其返回 {state:'succeeded'|'failed'|'cancelled',error:RunError|null} 在进程树清理后发生。

worker 事件 type 为 ready/node_started/node_succeeded/node_failed/log，nodeId/level/message/durationMs/error 按需，成功产物放 artifact:RunArtifact。最终 finished 由 manager 消化为返回值，不在回调中提前确认终态。大结果不进 JSONL。应用层分配持久化 seq；状态+事件原子提交后通知 SSE。

应用层负责快照/幂等/工作区活跃名额及 Profile usage guard、kernel_target_lock，从 accepted 到 cleanup 保持占用；修改配置可用、删除所用配置/内核409。bootstrap 统一装配运行服务、quiesce blocker、shutdown；启动时遗留活跃记录标 interrupted，不重放。

## 前端与生命周期

独立 useWorkflowRun，组件先于页面。顶部 Profile 选择/运行/停止/进度，底部日志+只读结果+最近运行；持久化事件补读去重。普通重连不重启服务。日志名称来自快照；仅同工作区且当前 document 等于快照时标记/定位，布局改动不影响；修改后提示，撤销一致可恢复。

启动前提交聚焦字段并同步 clone editor.current()；未提交无效变量重命名阻止启动；不调用 save。运行不进入 undo。新建/打开/关闭/退出/换区复用统一离开：dirty+active 提供保存并停止/放弃并停止/取消；保存成功才停止，失败保留草稿与运行；取消不停止；清理后才离开/quiesce。换区失败保留原文档，不恢复已停止运行。仅主窗口关闭时 Studio 运行继续。

## 验收

受控本地网页及独立临时工作区验证全部六节点、参数分支、输出/截图、>64KiB 结果、变量、超时/停止、启动去重、断线续读、进程退出、资源锁、草稿隔离和离开保护。后端 pytest/Ruff/mypy、前端 tests/typecheck/lint、OpenAPI/structure/scripts/build、source/frozen/packaged 入口。平台逐项记录实测，未测 Windows 不声称通过。
