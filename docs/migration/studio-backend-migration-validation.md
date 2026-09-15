# Studio 后端迁入验收矩阵

状态：B0 实施完成；正式用户数据库副本项外部等待。B1 正式五节点主链已通过，正常关窗、停止与异常离开矩阵仍在收尾；依赖已满足的 B2/B4 源码模块族按批准策略并行迁入。日期：2026-09-15。

## 1. 使用方式

- 227 个节点的 681 条逐项验收记录位于 [capabilities.json](studio-frontend-completion/capabilities.json) 的 `backendMigration.acceptanceCases`。每个节点固定包含 source-parity、contract、real-execution 三条，状态和证据只在该处更新。
- 本文只登记共享基础设施、跨节点业务链路和里程碑门槛，避免把同一规则复制 227 遍。
- 每条通过记录必须包含实际命令、退出码、结构化结果和证据路径。Mock 结果只能用于前端合同回归，不能核销 `real-execution`。
- 测试数据全部位于程序创建的临时工作区；正式用户数据库只允许读取副本。

## 2. 测试层级

| 层级 | 目的 | 允许替身 | 不允许替代 |
|---|---|---|---|
| 源码差分 | 比较冻结 WebRPA 与迁入实现的输入、输出、错误和副作用 | 本地 fixture、窄 fake port | 根据前端名称猜测行为 |
| domain/application | 验证图、变量、状态机、幂等和用例 | Clock、ID、窄端口 fake | Mock 执行器冒充节点实现 |
| repository/worker | 验证 SQLite、文件、进程通道、取消和恢复 | 临时目录、受控子进程 | 用户数据库、人工改表 |
| HTTP/SSE | 验证真实 loopback、鉴权、事件补读和大值 | 本地受控 HTTP/SMTP/SSH 等服务 | 直接调用 React Store |
| CloakBrowser | 验证真实页面、iframe、下载、截图和清理 | 本地多 origin 网页 | Playwright mock、第三方不稳定网站 |
| Electron E2E | 验证正式主窗口到 Studio 的用户链路 | 临时工作区和本地服务 | 页面内部函数、Store 注入、Mock 动作 |
| 正式包 | 验证 PyInstaller/Electron 包、原生依赖和退出 | 各平台内部签名前目录包 | 交叉平台分支模拟 |

## 3. 基线与数据兼容

| ID | 前置与操作 | 通过标准 | 层级 | 状态/证据 |
|---|---|---|---|---|
| BE-B0-001 | 校验 `reference/WebRPA` HEAD、status 和产品版本 | commit 为 `5ccb900e...`, checkout 无修改，版本 3.2.0 | 静态 | 已核实；[baseline.json](studio-backend-migration/evidence/preparation/baseline.json) |
| BE-B0-002 | 从 `_SUBMODULES`、装饰器和手动注册静态解析 227 类型 | 226 个装饰器注册，`subflow` 手动注册；无缺失、无排除类型混入 | 静态 | 已通过；[source-mapping.json](studio-backend-migration/evidence/b0/source-mapping.json) |
| BE-B0-003 | 找回 `0010_android_fleet` 文件和父 revision | 文件、commit、父 revision、表变更和 ORM 变更都有真实证据 | 迁移审计 | 已通过；逐字恢复并合并为唯一 head，[migration-graph.json](studio-backend-migration/evidence/b0/migration-graph.json) |
| BE-B0-004 | 对正式数据库只读副本记录 schema、版本和数据哈希 | 不读取秘密值；不改原文件；报告可复现 | 集成 | 外部等待：检查器及脱敏 fixture 已通过，尚无正式副本；[database-copy-report.json](studio-backend-migration/evidence/b0/database-copy-report.json) |
| BE-B0-005 | 在副本上从现有 revision 升级到目标合并 head，中途注入失败再恢复 | 无丢表、丢行、半迁移或错误 stamp；重复启动幂等 | 集成 | 外部等待：临时历史库、故障注入及恢复已通过，正式副本尚未提供；[migration-graph.json](studio-backend-migration/evidence/b0/migration-graph.json) |
| BE-B0-006 | 启动空临时工作区、旧 `0005`–`0008` 数据和当前 `0009` 数据 | 三种来源都进入同一可用 head，旧文档/事件/产物哈希不变 | 集成 | 已通过；45 项迁移关联回归，[migration-graph.json](studio-backend-migration/evidence/b0/migration-graph.json) |
| BE-B0-007 | 对 57 个排除类型和其嵌套自定义模块运行预检 | 明确 `UNSUPPORTED_NODE_TYPE`，原文不变且不执行其它节点 | domain/HTTP | domain 已通过 60 项；当前无生产运行路由，B1.6 接入后补 HTTP 证据；[scope-preflight.json](studio-backend-migration/evidence/b0/scope-preflight.json) |
| BE-B0-008 | 校验上游许可证副本、项目范围内源码使用确认和直接迁入文件来源记录 | 哈希与冻结源一致；确认不被扩写为具体商业/公开发布授权；无未登记的直接迁入文件 | 静态/发布 | 已通过；[source-mapping.json](studio-backend-migration/evidence/b0/source-mapping.json)、[source-provenance.json](studio-backend-migration/source-provenance.json) |

## 4. B1 首个真实闭环

| ID | 前置与操作 | 通过标准 | 层级 | 状态/证据 |
|---|---|---|---|---|
| BE-B1-001 | Studio 新建 open_page→input_text→click_element→get_element_info→screenshot，保存、关闭重开 | 文档、布局、revision 和配置真实持久化；未产生运行 | Electron E2E | 保存、销毁测试窗口后重开及 SQLite 恢复已通过；这只核销文档往返，不作为正常关窗保护证据，[开发构建](studio-backend-migration/evidence/b1/formal-electron-iIAZre/result.json)、[目录包](studio-backend-migration/evidence/b1/formal-electron-9HK0sY/result.json) |
| BE-B1-002 | 选择主应用 Profile，运行未保存草稿 | 只创建运行快照，不创建/更新工作流文档；CloakBrowser 完成真实页面动作 | Electron/CloakBrowser | 正式 Electron 已用保存后的文档完成 Profile 选择及真实运行；未保存草稿组合仍待验收，[目录包主链](studio-backend-migration/evidence/b1/formal-electron-9HK0sY/result.json)、[未保存快照合同](studio-backend-migration/evidence/b1/http-sse-runtime.json) |
| BE-B1-003 | 比对输入值、点击计数、提取值和 PNG | 页面值一致、计数恰为 1、提取字节和截图可核对 | CloakBrowser | 已通过：macOS arm64 独立 provider 与正式 Electron 目录包真实 UI 均核对页面副作用、提取值和 PNG；[provider](studio-backend-migration/evidence/b1/five-browser-nodes.json)、[正式目录包](studio-backend-migration/evidence/b1/formal-electron-9HK0sY/result.json) |
| BE-B1-004 | 同 runId 同请求重发、丢弃首次 HTTP 响应后查询 | 只启动一个 worker/浏览器，页面动作不重复 | HTTP/worker | 已通过：repository、协调器与前端响应丢失恢复使用同一身份；相同请求只启动一个 worker，[http-sse-runtime.json](studio-backend-migration/evidence/b1/http-sse-runtime.json) |
| BE-B1-005 | 同 runId 不同快照重发 | 返回 409 和稳定错误包，原运行不变 | HTTP | 已通过：生产 HTTP 返回 `RUN_ID_CONFLICT`，原运行保持 running，[http-sse-runtime.json](studio-backend-migration/evidence/b1/http-sse-runtime.json) |
| BE-B1-006 | 执行中断 SSE，再按最后序号重连 | 已持久化事件补齐、无重复，断线不改变运行状态 | HTTP/SSE | 合同已通过：严格序号、UTF-8 帧、断开后的 `afterSeq` 补读与前端游标恢复；正式 sidecar 网络断流待 B1.7 组合复核，[http-sse-runtime.json](studio-backend-migration/evidence/b1/http-sse-runtime.json) |
| BE-B1-007 | 导航、输入、截图期间分别停止 | 当前操作及时取消，后续节点无副作用；清理完成后才确认 cancelled | worker/CloakBrowser | 尚未验收 |
| BE-B1-008 | 杀 worker、杀浏览器、异常退出 sidecar | 运行标记 interrupted/failed，网页动作不重放，进程和锁最终可回收 | 进程集成 | worker/进程树清理与启动恢复 interrupted 已分别通过；sidecar 组合待 B1.6-B1.7，[browser-worker.json](studio-backend-migration/evidence/b1/browser-worker.json)、[run-events-artifacts.json](studio-backend-migration/evidence/b1/run-events-artifacts.json) |
| BE-B1-009 | Profile/内核/License/代理缺失或正在删除 | 启动前返回定位明确的错误；没有半启动运行或泄露秘密 | application/HTTP | 尚未验收 |
| BE-B1-010 | 保存中继续编辑、revision 冲突、磁盘失败 | 当前草稿不被旧响应覆盖，失败不误报保存成功 | repository/Electron | repository 原子性、revision 错误包、稳定写身份及前端迟到响应保护已通过；正式 Electron 磁盘失败交互待 B1.7，[document-persistence.json](studio-backend-migration/evidence/b1/document-persistence.json)、[http-sse-runtime.json](studio-backend-migration/evidence/b1/http-sse-runtime.json) |
| BE-B1-011 | 运行中关 Studio、退出、换区，分别选择保存/放弃/取消 | 按草稿→停止清理→离开顺序；取消保留现场；保存失败不先停止 | Electron E2E | 尚未验收 |
| BE-B1-012 | 冻结 sidecar 和 Electron 目录包运行同一链路 | 包中不读取 reference 或开发服务器；退出无受管残留 | 正式包 | 已通过：目录包运行五节点真实链，包内扫描未发现冻结源码、Mock 服务或 Vite 地址，终态无受管浏览器残留；正常关窗/退出保护仍归 BE-B1-011，[目录包证据](studio-backend-migration/evidence/b1/formal-electron-9HK0sY/result.json) |

## 5. B2 浏览器与定位

| ID | 场景 | 通过标准 | 状态 |
|---|---|---|---|
| BE-B2-001 | 35 个网页节点逐项执行全部配置分支 | 每个节点三条逐项用例通过；未迁节点预检失败 | 尚未验收 |
| BE-B2-002 | CSS、XPath、多匹配、零匹配、非法语法 | 行为与冻结执行器一致；错误含 nodeId/path | 尚未验收 |
| BE-B2-003 | 主页、同域/跨域嵌套 iframe、开放 Shadow DOM | 目标身份正确，不回退到其它页面或框架 | 尚未验收 |
| BE-B2-004 | 弹窗、新标签、刷新、前进/后退、页关闭和下载 | 页面选择和关闭策略与原版一致，丢失当前页明确失败 | 尚未验收 |
| BE-B2-005 | Profile 启动参数、指纹、语言、时区、代理、扩展和无头/可见模式 | 使用冻结快照且不修改 Profile；秘密不落日志 | 尚未验收 |
| BE-B2-006 | 拾取→定位测试→应用→保存→独立运行 | 独立运行命中同一目标；取消和迟到结果不改文档 | 尚未验收 |
| BE-B2-007 | 运行、Debug、拾取、录制争用同一工作区 | 取得资源原子互斥，清理前不释放 | 尚未验收 |
| BE-B2-008 | 1 MiB 提取、下载和截图 | 事件只含摘要/引用，文件大小与哈希完整 | 尚未验收 |

## 6. B3 控制流、变量、子流程和模块

| ID | 场景 | 通过标准 | 状态 |
|---|---|---|---|
| BE-B3-001 | 起始节点、孤立节点、条件/错误边和汇合 | 与冻结 parser 的选路和副作用一致 | 尚未验收 |
| BE-B3-002 | 循环、foreach、foreach_dict、infinite_loop、break/continue | 轮次、局部变量和退出路径一致；可停止 | 尚未验收 |
| BE-B3-003 | 并行分支 | 验证偏序和结果集合；不为测试稳定改成串行 | 尚未验收 |
| BE-B3-004 | `${name}`、`{name}`、递归列表/字典、表达式和缺失变量 | 与冻结变量测试一致，错误明确 | 尚未验收 |
| BE-B3-005 | 子流程按名称/ID、组几何、无入口回退、循环引用和 32 层限制 | 原算法一致；必要位置和尺寸保存恢复 | 尚未验收 |
| BE-B3-006 | 自定义模块更新、依赖缺失、运行中修改 | 运行使用冻结解析内容；缺失依赖启动前拒绝 | 尚未验收 |
| BE-B3-007 | 同一节点循环/重试多次 | 每次有 executionId，日志与产物不覆盖 | 尚未验收 |
| BE-B3-008 | 1,000 轮纯变量流程中停止 | 事件循环可响应，停止后无后续调度或资源泄漏 | 尚未验收 |

## 7. B4 纯数据与表格

| ID | 场景 | 通过标准 | 状态 |
|---|---|---|---|
| BE-B4-001 | 88 个节点的默认值、类型、空值、错误和独有分支 | 所有逐节点 source-parity/contract/real-execution 通过 | 尚未验收 |
| BE-B4-002 | 字符串、正则、JSON、列表、字典、数学和统计边界 | 与原 type_utils/safe_expr/json_safe 行为一致 | 尚未验收 |
| BE-B4-003 | 表格/CSV 的中文、空单元格、大列表和文件往返 | 值、顺序、编码和哈希一致，不静默截断 | 尚未验收 |
| BE-B4-004 | 无效编码、NaN/Infinity、超大索引和错误类型 | 结构化失败且后续策略按配置执行 | 尚未验收 |
| BE-B4-005 | 运行中取消 CPU 密集或大序列化任务 | 在定义的检查点响应；无半份产物 | 尚未验收 |

## 8. B5 AI、模型和 MCP

| ID | 场景 | 通过标准 | 状态 |
|---|---|---|---|
| BE-B5-001 | 22 个 AI 节点逐项使用主应用模型 ID | 不读取第二套配置；请求与模型选择一致 | 尚未验收 |
| BE-B5-002 | 流式响应、取消、超时、供应商错误、限流和大结果 | 状态、错误和结果引用符合合同；取消不继续写结果 | 尚未验收 |
| BE-B5-003 | MCP 保存、测试、重载、调用、拒绝和断线 | 修订与命令幂等；权限结果不被绕过 | 尚未验收 |
| BE-B5-004 | API key、代理密码和 License | 不进入快照、事件、日志、诊断或导出 | 尚未验收 |
| BE-B5-005 | AI 助手添加/修改节点及权限批准、拒绝、取消 | 排除类型仍拒绝；画布变化与命令确认一致且可撤销 | 尚未验收 |
| BE-B5-006 | LangGraph 候选版本在 Python 3.11、SQLite 检查点和 PyInstaller 中运行 | 版本被锁定；不默认外发追踪；冻结包启动、暂停和恢复通过 | 尚未验收 |
| BE-B5-007 | 小助手多轮模型→工具→权限→结果→后续模型 | 实际路径经过 LangGraph；不存在绕过图的完整助手循环；前端确认前不报告画布已改 | 尚未验收 |
| BE-B5-008 | 权限等待中拒绝、取消、断线、重启和参数变化 | 旧批准不可复用，恢复查询原命令，不重复有副作用工具 | 尚未验收 |
| BE-B5-009 | 助手检查点、事件、日志与导出秘密扫描 | 工作区隔离；API key、代理密码、License 和完整 Profile 均不出现 | 尚未验收 |

## 9. B6 触发器、计划任务和外部能力

| ID | 场景 | 通过标准 | 状态 |
|---|---|---|---|
| BE-B6-001 | 61 个节点逐项执行正常、失败、取消和不可用平台 | 三条逐节点用例通过；不可用返回 CapabilityUnavailable | 尚未验收 |
| BE-B6-002 | webhook/API/email/通知使用本地受控服务 | 请求方法、头、正文、代理、超时和次数可核对 | 尚未验收 |
| BE-B6-003 | SSH 上传/下载/命令和断线 | 本地 SSH fixture 内容与哈希一致；会话关闭 | 尚未验收 |
| BE-B6-004 | 文件/屏幕共享启动、访问、停止和端口冲突 | 地址、访问和停止真实；退出后无监听端口 | 尚未验收 |
| BE-B6-005 | 触发器启动、触发、去重、取消和重启 | 一次事件只启动一次；重启不重放历史动作 | 尚未验收 |
| BE-B6-006 | 计划任务创建、到点、禁用、错过、日志和删除 | 时区、次数和运行记录可核对；停写时不新启动 | 尚未验收 |
| BE-B6-007 | shutdown/lock/printer 等平台节点 | 在可控测试适配器验证命令；实机仅在隔离环境按平台记录 | 尚未验收 |
| BE-B6-008 | JS/Python/输入提示/语音双向请求 | claim/result/cancel 幂等，停止回收在途请求 | 尚未验收 |

## 10. B7 录制

| ID | 场景 | 通过标准 | 状态 |
|---|---|---|---|
| BE-B7-001 | 中文输入、连续编辑、点击/双击、选择、勾选、按键、滚动 | 步骤不重复，实际值保留 | 尚未验收 |
| BE-B7-002 | 输入后立即导航/提交/刷新/停止 | 已确认尾部不丢；未确认尾部明确提示 | 尚未验收 |
| BE-B7-003 | 新标签、iframe、Shadow DOM 和未来文档注入 | 生成步骤可在独立浏览器重放 | 尚未验收 |
| BE-B7-004 | 暂停/恢复/停止、断流、重连、重复命令 | 已提交序号补读不丢不重，不重放手动动作 | 尚未验收 |
| BE-B7-005 | 审查编辑、变量化、生成预览、整批加入、撤销/重做 | 一次操作原子；迟到响应不覆盖新草稿 | 尚未验收 |
| BE-B7-006 | 10,000 步、64 MiB、单值 1 MiB 和磁盘失败 | 达限明确暂停，不截断后继续生成；失败保留已确认步骤 | 尚未验收 |
| BE-B7-007 | 保存重开、关闭录制浏览器、独立运行 | 新浏览器副作用与录制一致，原会话状态未泄漏 | 尚未验收 |

## 11. B8 Debug、日志、诊断和恢复

| ID | 场景 | 通过标准 | 状态 |
|---|---|---|---|
| BE-B8-001 | 条件、循环、并行和子流程中的断点/暂停/单步/继续 | 一次许可只调度一次，未走路径无伪成功 | 尚未验收 |
| BE-B8-002 | commandId、pauseId、controlRevision 重复/过期/丢响应 | 查询原命令恢复，不多走一步，迟到命令拒绝 | 尚未验收 |
| BE-B8-003 | 暂停变量查看/修改和循环局部变量 | 值与上下文真实；只读项不变；修改有诊断事件 | 尚未验收 |
| BE-B8-004 | 日志全文搜索、级别/节点/执行筛选、分页和断流 | 查询覆盖数据库全部记录，游标不丢不重 | 尚未验收 |
| BE-B8-005 | 1,000 轮、10,000 日志、重复产物和大于 64 KiB 值 | UI 有界加载，导出内容、数量和哈希一致 | 尚未验收 |
| BE-B8-006 | 失败现场、结束调试、浏览器异常和清理重试 | 原失败保留；清理完成后终态正确；锁不提前释放 | 尚未验收 |
| BE-B8-007 | 同工作区重连、sidecar 崩溃、重开历史 | 普通重连恢复确认状态；崩溃标中断且不重放 | 尚未验收 |

## 12. B9 正式交付门槛

- 227 个节点的 681 条逐项用例全部通过或以产品范围文件明确排除；当前范围内不能留“尚未验收”。
- 上述共享用例全部有证据目录、结构化结果和失败修复记录。
- 后端 pytest、Ruff、mypy，OpenAPI 生成一致性，前端合同回归、TypeScript、ESLint、renderer/main/preload 构建通过。
- PyInstaller sidecar 和正式 Electron 包不读取 `reference/WebRPA`、Mock server 或开发服务器。
- macOS arm64、macOS Intel、Windows 分别记录；未实测平台不能标通过。
- 正式用户数据库兼容先在副本通过，实际升级另行执行，不包含在自动化测试命令中。
