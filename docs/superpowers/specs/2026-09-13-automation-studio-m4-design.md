# M4：条件、循环与变量处理

日期：2026-09-13；状态：confirmed；来源：用户批准的完整 M4 实施计划。

## 产品与执行契约

正式 Studio 自动成对插入 condition/condition_end、loop/loop_end；条件 true/false 汇合，循环 body/done 不绘制回边，支持32层结构化嵌套。break_loop/continue_loop 影响最近循环。六类浏览器节点和拾取定位保持兼容。新增 set_variable 的 assign/add/subtract/append 操作；循环支持 count/foreach/while。

条件为 all/any 规则表单，顺序短路，不执行表达式。值来源是 literal(value) 或 variable(name,path)，path 为对象键/非负列表索引数组。比较严格区分数字、布尔、字符串；empty 仅 null/空字符串/空列表/空对象。网页 exists/not_exists/visible/not_visible 复用 selector/framePath；零匹配正常、定位错误失败。条件单次总预算 timeoutSeconds 默认60。

次数/列表进入循环时复制一次；while每轮重算条件。index一基、item为列表当前项，只读且仅循环体可见；不得与流程变量、输出或祖先循环局部名冲突。maxIterations默认1000，范围1..100000；全运行最多100000次调度。while达到上限后条件仍真则失败。每步/每轮让出事件循环并响应停止，循环体独立使用节点超时。

流程变量更新对后续路径可见，不回写草稿。分支汇合取正常到达路径的变量交集；循环后不保证循环体新变量存在。重命名更新文本、结构化引用和局部绑定，按作用域处理。设置允许创建变量；增减要求已有数字，追加要求已有列表且只追加一个值。

## 编排和兼容

配对字段为起点config.endNodeId和终点config.ownerNodeId。普通输入in/输出out，控制端口显式命名。禁止任意回环、交叉配对、跨块跳入跳出。未连线或缺参数可保存；结构损坏拒绝；运行只接受完整有效控制图。复制/删除起点扩展到整块，结束节点不可独立删除，整体撤销。

schemaVersion增加2；旧1文档在编辑器内等价升级且不置脏，手动保存再写2；旧运行快照不改写。domain负责编译/类型/变量规则，application负责顺序调度，provider负责浏览器动作。一次运行一个worker，结构化计划不展开循环。不引入并行DAG框架。

## 日志、产物与保护

每次调度有executionId和loopPath（loopNodeId/iteration），开始/成功/失败关联一致。运行终态由调度结束及清理确认，不能以文档节点数推断。沿用事件seq/SSE；历史无executionId按旧单次事件显示。摘要增加executionCount/currentExecutionId/currentLoopPath，画布显示当前执行和累计次数。

增加产物索引表及增量迁移，迁入旧登记但不移动文件；原读取URL保持；新增分页产物列表及nodeId/executionId过滤。每轮结果保留，详情首屏加artifactCount/nextArtifactCursor。默认截图名唯一；显式同名文件仍拒绝覆盖。

延续草稿快照、Profile冻结、单运行/拾取互斥、保存后清理再离开、服务崩溃不重放。子流程、异常分支/重试、Debug、录制、双视图和分组注释属于后续范围。

## 验收

受控本地多origin页面验证变量/网页条件、嵌套循环、break/continue、结果累积、跨域iframe/Shadow、保存重开独立运行。包含1000轮纯变量、停止、上限、重复产物分页、大结果、旧数据迁移和M1–M3回归。pytest/Ruff/mypy、前端测试/TS/ESLint、OpenAPI/目录/脚本、renderer/main/preload、冻结后端与正式包检查。macOS与Windows实机结果分别记录，未测试不标通过。

## 落地字段与历史读取细则

- 固定来源：`{kind:"literal", value:JSON, valueType?:"string"|"number"|"boolean"|"array"|"object"|"null"}`；变量来源：`{kind:"variable", name:string, path:(string|number)[]}`，路径最多32层。`valueType`仅记录表单所选字面量类型，使尚未填完整的数字/JSON文本可以保存并显示问题；执行前严格核验，不将文本当表达式。
- 条件：`match:"all"|"any"`，`rules`为1..100条。值规则 kind=value、left/right、operator；一元运算不读取right。网页规则 kind=page、selector/framePath、operator。
- loop.count/foreach 用 source；while 用 match/rules；maxIterations 为1..100000整数。循环头事件的 loopPath 记录本次判断的候选轮次；branch=done 表示判断结束，不声称该轮循环体已执行。
- 产物分页：`GET /workflows/runs/{id}/artifacts?after=0&limit=50&nodeId=...&executionId=...`，返回 items/nextCursor；after 是运行内 ordinal，不是数组偏移，筛选不改变顺序。单个产物地址保持原样。运行详情 artifactCount/nextArtifactCursor 描述首屏之外的数据。
- 日志仍每次按200条补读，实时消息短批次合并，视图先显示最近200条，按需显示更早段落；运行状态刷新合并，避免每条循环事件都请求运行详情。结果按50条分页，完整内容只在展开时读取。
- 调度上限在下一次节点开始前拒绝，多余尝试不会计入 executionCount。管道清理期间排空的数据没有经过事件事务，不补写成成功动作。
