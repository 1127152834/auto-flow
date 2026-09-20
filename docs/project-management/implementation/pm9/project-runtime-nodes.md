# 项目图与数据能力

日期：2026-09-20；状态：confirmed（R2 当前边界）；来源：真实 HTTP / SQLite / worker / CloakBrowser 测试、冻结内容和父进程权限检查。

项目批次已复用 Studio 图调度器。预检目前开放原有四个浏览器动作、condition、loop、foreach、foreach_dict、break_loop、continue_loop、set_variable 和 project_data；其余节点仍明确拒绝，不能把 Studio 已装配的所有节点都宣称为项目可执行。原 chain/v1 内容继续运行；新准备内容为 graph/v2，保存完整图、数据配置和参数。

Studio 的「项目能力 → 项目数据」节点提供真实项目/表/字段目录、操作与结果变量。节点只能从项目批次获得项目数据权限；直接 Studio 运行会拒绝没有绑定的能力。目录当前每次最多展示 100 个项目/表；超出此范围的搜索和分页尚未补齐。

- `inputs`：返回当前 Task 的冻结输入快照。
- `readRecord`、`queryRecords`：使用字段集合与 readPurpose 的显式授权。
- `createRecord`、`updateRecord`、`deleteRecord`、`setRecordStatus`：使用现有 CAS、租约、执行代次和幂等账本。
- `addField`、`ensureField`、`modifyField`、`previewFieldChange`：使用现有字段权限与影响核验。

每个数据节点 `data` 包含 `operation`、`arguments`、`variableName`；需要表级权限时配置 `tableGrant`（tableId / datasetGeneration / operations / fieldIds / readPurposes）。operations 只能包含该节点的一项操作。Batch 在同一事务验证并冻结授权；worker 不能自报 projectId、operationId 或 executionGeneration。运行时参数从已确认节点访问的 Run/Task 事实确定，commandId 由 runId / generation / visit 确定。

参数是 JSON 对象，使用变量时 `{record['ref']}` 保持对象类型，`{record['contentRevision']}` 保持数字类型，文本 `001` 保持文本。项目参数的 UUID 引用可直接用于数据和控制节点。现有 Studio 普通字符串替换默认行为不变。

验证：真实浏览器测试在两个 Task 中读取另一张来源表的 `001`，经过条件节点写入结果表；输出为 `before-真实参数-001`，只有两条记录。安全边界测试拒绝未提交访问、错节点、错代次、错命令和跨项目请求；同一命令重复返回原结果且仅写入一次。前端配置、注册和导入导出 459 项通过；后端目标回归及原变量差分 130 项通过。

R3 End / 人工暂停恢复与最终安装包全链验收仍在实施，本文不把它们视为已完成。


## 2026-09-20 R3/R4 更新（confirmed，来源：真实 HTTP/子进程/CloakBrowser 测试）

新增 `project_end` 和 `project_manual`，仍与冻结的 227 个 Studio 来源节点分开。End 要求唯一汇合终点，不能在循环体内提前关闭浏览器；人工节点拒绝并行分支。环境名称 1–36 字且项目内唯一，批次应使用不同的记录身份命名。只有已领取或本次创建的记录可被 End 关联。

人工等待持久化检查点版本与访问身份；继续保留同一进程和浏览器，不重放前序动作。终结先由 worker 关闭，再保存/关联并确认结果。等待不消耗自动执行预算，仍受冻结的人工期限限制。进程中断后待处理项取消、旧代次失效，运行经清理确认进入 interrupted；不支持跨进程恢复页面/图栈，不接受任意目标节点或未声明的输入。

正式 Studio 的平铺图文档在项目读取边界转换成已有执行封装，不改写原文档与布局，也不改变已冻结历史。项目/数据表选择器现支持翻页；旧“只能选择前 100 项”的边界已 superseded。读取节点勾选字段会同步查询参数。
