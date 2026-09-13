# Automation Studio M5 验收记录

- 日期：2026-09-13；状态：实现完成，macOS arm64 实测通过；未实测平台单独记录。
- 依据：[正式规格](../superpowers/specs/2026-09-13-automation-studio-m5-design.md)、[实施计划](../superpowers/plans/2026-09-13-automation-studio-m5-implementation.md)。
- 环境：macOS arm64、CloakBrowser Chromium 145.0.7632.109.2，独立临时工作区、127.0.0.1/localhost 多 origin 页面。没有第三方账号或生产流程。
- 置信度：已列出的自动化及实机结果为高；Windows、macOS Intel 为未知，不计作通过。

## 已交付

正式 Studio 支持从头调试、顶层直接起跑、运行至嵌套节点；调试固定可见临时浏览器。断点随布局手动保存，活跃断点绑定启动快照。继续、单步、暂停、停止使用原工作流运行资源及 worker，不另建调试执行器。

节点前暂停不消耗节点预算；单步包含条件、循环头、配对终点及 break/continue。正常暂停可原子修改流程变量，循环局部只读。当前检查点、历史检查点、增量变化、循环位置、最近来源及耗时可查看。失败暂停保留浏览器检查，禁止继续/修改/重试；结束后保留 failed 终态及原错误。

命令持久化稳定 ID、请求哈希、状态和 worker 确认；前后端均校验暂停身份/修订号。HTTP 丢失不自动换 ID 重发单步。诊断文件和结果沿原索引登记，purpose 分开计数；变量大值按需读取，列表追加只记追加项。

全库日志支持级别、关键词、节点与 executionId 筛选。JSONL、结果 ZIP/清单、变量诊断 JSON 固定截止序号导出。正式 Electron 通过受控 IPC、原生保存对话框和主进程流式文件写入完成导出。失败不会用半个文件替换原文件。

## 实测矩阵

| 场景 | 实际结果与验证方式 |
| --- | --- |
| 调试与真实变量修改 | 嵌套跨域 iframe 中输入、点击、提取；每轮在输入前断点暂停，修改运行变量，结果严格核对为 `modified` 和 `second`。原快照不变，结果两项，诊断不混入计数。源码与冻结 worker。 |
| 双层循环单步 | 外层2轮、内层每次2轮；条件判断4次、内层循环头6次、条件终点4次，仅真分支产生2次真实点击。每次单步后累计调度数只增加1，显示两层真实轮次。 |
| 暂停预算 | 真实启动暂停12秒持续心跳后继续；独立调度用例将下一节点预算设为0.01秒、先暂停0.04秒仍成功。动作执行使用原超时，心跳不延长动作预算。 |
| 命令幂等和过期 | 重复相同 step 返回原确认，不增加调度；同 ID 换动作409；旧暂停/修订请求拒绝。前端等待确认时连点只发一次，迟到分页不覆盖新检查点；收起面板保留未提交修改。 |
| 变量保护 | 批量补丁含局部名时整批拒绝；有效补丁影响随后真实网页。磁盘写入失败不应用任何变量。有限数字校验拒绝 JSON 中溢出数值，防止序列化时静默变 null。局部进入/退出和追加增量有单测及真实循环证据。 |
| 顶层起跑 | 跳过缺URL的前置节点，仅验证执行后缀；明确补充 provided 变量、在暂停浏览器手动导航，再执行 input/extract，实际值为 manual-page。块内起点和损坏配对精确拒绝。 |
| 运行至此 | 从入口真实执行到循环内 input，轮次为1；目标不经过时正常完成并记录未到达（领域调度测试），不强行选择分支。 |
| 失败现场 | 真实定位超时后 failed_paused；页面列表仍可读，后继不执行、继续被拒绝。结束后检查受管进程已清理，最终 failed、原失败 nodeId 不变。正常暂停停止则 cancelled，并保存结束检查点。 |
| 大量诊断 | 1000轮列表追加，最终通过真实 input/extract 核对长度1000、末项1000；1000个追加记录均为单项增量，诊断50项分页。70,000字符变量通过文件读取完整，未塞入结果事件预览。 |
| 日志与导出 | 全库节点筛选及跨页读取、结果 ZIP 签名、诊断 JSON 完整解析、70KiB ZIP内容/manifest单测；正式 UI 搜索持久化调试日志并通过原生文件导出。 |
| 断线与崩溃 | 重启后检查点ID不变。暂停期间真实 SIGKILL sidecar，监护清理受管浏览器；重启后 interrupted、调度数仍0；新调试能获取资源。SSE断流/补读沿用M2回归；不把断流当作失败。 |
| 暂停时离开 | 正式窗口新建：取消保留暂停；外部真实 revision 更新造成保存冲突，保存失败仍保留草稿和浏览器；放弃并停止后才清空画布进入新流程。开发、构建及正式包均执行。 |
| 历史迁移 | 0008增量增加诊断索引/命令表；旧结果默认result，按原artifactId事件恢复截止序号。降级/再升级后标识、路径与按截止序号筛选保持一致。不伪造旧变量记录。 |
| M1回归 | 正式 Electron 13组：真实保存重开、六节点编辑/撤销/剪贴板、冲突、离线恢复、窗口复用、关主窗、退出、切区保存/放弃/取消及回滚。 |
| M2回归 | 真实浏览器8组：六节点、输入/提取/等待各分支、标签页、截图路径/冲突、失败停止/资源锁、SSE续读和重启、临时会话隔离。 |
| M3回归 | 真实浏览器8组：拾取点击无业务副作用、取消恢复、特殊/重复标识、开放Shadow、同域/跨域/嵌套框架、导航与页关闭失效；新浏览器使用拾取目标执行六节点。 |
| M4回归 | 真实worker7组：嵌套条件/循环、continue/break、列表快照、网页条件错误、1000轮纯变量、55次产物分页、动态计数及清理。 |

M1的退出/换区矩阵验证共享离开协议；本轮另实测 debug 暂停的新建、取消和真实保存冲突。没有将所有关闭方式与所有暂停状态的笛卡尔组合表述为逐项实机测试。worker异常/取消/资源清理失败另由进程和应用测试覆盖。普通连接恢复沿原机制，不重启浏览器。

## 证据

- [源码调试8组](automation-studio-m5-qa/source-debug.json)、[冻结调试8组](automation-studio-m5-qa/frozen-debug.json)。
- [开发URL](automation-studio-m5-qa/dev-studio.json)、[构建HTML](automation-studio-m5-qa/built-studio.json)、[正式macOS包](automation-studio-m5-qa/packaged-studio.json)，各4组。
- 正式界面：[画布](automation-studio-m5-qa/packaged-editor.png)、[暂停与变量](automation-studio-m5-qa/packaged-paused.png)、[执行结果](automation-studio-m5-qa/packaged-executed.png)、[诊断搜索](automation-studio-m5-qa/packaged-diagnostics.png)。
- 回归：[M1](automation-studio-m5-qa/m1-regression/built-html.json)、[M2](automation-studio-m5-qa/m2-regression/source.json)、[M3](automation-studio-m5-qa/m3-browser.json)、[M4](automation-studio-m5-qa/m4-regression/source-control.json)。
- 工程命令与结果：[checks.json](automation-studio-m5-qa/checks.json)。

## 修复记录

1. 暂停心跳与动作预算分别维护，避免心跳让挂起网页动作无限续期。
2. 变量补丁先生成并成功写入候选检查点，再原子修改运行变量，避免写盘失败时部分生效。
3. 停止时只接收最终诊断，丢弃尚未确认的节点完成消息；期限内未退出仍进入受管进程树清理，不提前释放名额。
4. 变量/日志翻页使用请求代次；旧暂停和旧筛选的迟到响应丢弃。旧命令HTTP响应不能清除后续命令的等待状态。
5. 日志保留有界实时窗口但单独维护连续序号；节点累计次数由持久化摘要提供，不因截断前端日志少计。
6. 正式导出从renderer整包Blob调整为原生主进程流式写入，临时文件完整后才替换目标。
7. 新增迁移为旧产物回填原事件序号，防止历史结果在较早导出截止位置被提前包含。
8. 2000个合法长标识断点状态可能超过原64KiB协议行上限；传输上限改为有界4MiB以容纳标识JSON转义。2000个长Unicode标识的真实子进程协议测试通过；变量和结果仍走文件引用。

后端全量570项回归及最后38项进程专项全部通过；前端427项、66个测试文件通过。Ruff、mypy（162源码文件）、TypeScript、ESLint、OpenAPI、3项目录检查、12项脚本检查、renderer/main/preload、冻结与本地Electron包构建通过。最后一次协议上限调整后重跑进程专项及冻结/正式应用用例，没有把专项数量重复加成全量测试数量。

## 平台与剩余范围

macOS arm64 开发URL、构建HTML、PyInstaller sidecar 和本地未签名 AutoFlow.app 实际运行。Windows x64、macOS Intel 尚未实机验收；未执行发行签名/公证。

M5不代表WebRPA核心全部对齐。子流程、异常分支/自动重试、录制、双视图、分组注释和剩余网页动作仍由后续里程碑实施。差异依据见 [能力来源表](../automation-studio/WEBRPA_CAPABILITY_MATRIX.md)。
