# A-01：PM9 R2 数据能力接线

日期：2026-09-28。状态：局部实现与定向验证 confirmed，完整 PM9 验收仍 in_progress。依据：已批准 PM9 R1–R4 规格；当前生产调用链；本目录日志。置信度：高（下述限定范围）。

历史问题仍存在：生产项目 worker 虽已复用共享 WorkflowRuntime，但没有项目数据 RPC；bootstrap 默认未声明正式数据写权限。运行内存表和项目数据表的所有权不同，不能通过修改 table_add_row 来弥补。

本切片新增一个原生 project_data 节点，沿已有 worker JSONL 管道调用 ProjectDataCapabilityService。固定操作包括输入快照、记录读查增改删、状态、字段和原操作查询。SQLite 只由宿主持有。宿主从私有管道绑定 runId/执行代次，再查本工作区 Task、输入快照、冻结节点和已提交且活动的 nodeVisit/attempt。请求不能增加工作区、项目、任务或执行代次字段。

每个节点声明固定表、数据集代次和字段集合，批次接受事务验证项目归属及当前目录后冻结授权；调用时进一步收窄至该节点声明，不能借用同一流程其他节点的表权限。已有数据仓储继续负责事务、租约、版本冲突、读证据及操作幂等。节点从 visit 身份确定 commandId，失败不换键重发。原生 SQL 调用在取消时排空后才释放 worker 清理责任。

审查发现写入仓储返回完整行快照会泄漏未授权列。本切片的私有 worker 边界从首次写入、重放及原操作查询回执移除 values，只返回引用、版本和确认；数据库内部完整审计保持不变。读取字段仍由 read/query 明确授权。回归在同表建立一个未授权列，确认列值真实保留在 SQLite，但不出现在读取与写回执中。

前端复用 Studio 配置面板、表／字段目录和已有变量输入。切换表会重新固定代次并清空字段授权；目录失败可重试；数据集变化不会静默改写保存的绑定。保存后从项目自动化任务运行。Studio 直接执行没有 Task 授权，在取得资源或启动 worker 前明确返回 CAPABILITY_MISSING。对应项目能力检查也标记 required。

参数沿既有变量展开规则：对象／数字插入 JSON 模板时不加引号；字符串值使用 JSON 字符串。读结果在 result，领取快照在 inputs，写回执在 result 并附 replayed；每次成功结果附 commandId。运行内存表未改变，Task 输入快照不会被写回修改。

证据：

- pm9-capabilities-before.log：新增宿主边界测试在旧实现上 2 项失败，明确缺少 worker_call。
- pm9-capabilities-worker-initial.log：真实 worker 暴露参数模板类型不正确，修正测试配置为已有 JSON 模板语义；没有更改共享变量求值契约。
- pm9-capabilities-worker-second.log / third.log：生产节点已成功，SQL 核验代码误用了复合主键及 values 属性；按当前模型修正为三列主键和 values_json。
- pm9-data-acceptance.log：42 项通过，包括 6 项本切片检查、真实子进程执行、现有权限／并发／查询快照和 Studio 协调器回归。
- 真实子进程用生产 dispatcher、生产 worker、真实迁移 SQLite、正式创建的表和记录，完成领取快照、读取、原操作查询与正式写入；输入快照保持不变，记录版本仅增加一次，退出后 worker.busy() 为 false。此场景不含浏览器或外部服务，不能代表用户要求的完整真实业务链。
- pm9-frontend-panels-final.log：12 项通过／3 文件。新面板目录使用单元边界响应，不能计为真实 UI 验收；首轮失败是 Radix 在 JSDOM 的 pointer API 缺失，最终测试使用真实键盘交互及局部 scrollIntoView 环境补齐，没有替换组件或删除断言。
- pm9-required-fields.log：6 项脚本检查通过。213 冻结来源与 4 原生节点独立核对，生成检查仍只读。
- pm9-ruff-final.log、pm9-types-backend.log、pm9-types-desktop.log、pm9-frontend-eslint.log：定向静态检查。strict 历史债务未计为解决。

剩余：真实浏览器写回／状态链、响应丢失与取消组合、循环与子流程数据节点、End、持久人工检查点、重启继续及打包 UI 均须继续。新增节点的全部操作未逐一通过生产 worker；已有服务回归不是每个新入口的实测替代。完整默认回归和构建留在最终稳定版本执行。

独立审查已给出并复现整行回执问题，随后审查工具被自动安全审查阻止；未重试或绕过，不能声称独立复审已全部完成。AOCI 本轮完整读取 280 条／5 块、Challenge 9/10；治理未对齐且另一任务仍初始化，未调用维护或覆盖资产。
