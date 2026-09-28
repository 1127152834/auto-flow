# 2026-09-28 审计修复

状态：in_progress。来源：本轮用户明确授权有界修复、PM9批准能力与真实回归。历史审计f853d7ee不改写；现有未提交文档与AOCI资产不接管。

共享安全切片：统一GET/HEAD/download/preview/thumb/list和上传/目录写操作边界，排他创建与目录句柄防替换，单文件共享不暴露兄弟文件。预览明确415与页面提示。修复前16失败/5通过；修复后24项真实HTTP/磁盘 + 6项host/executor共30通过。平台差异集中于共享文件适配器；Windows安全句柄分支未实机验收。详细证据见docs/qa/2026-09-28-remediation/share.md。

本轮AOCI仍由另一任务建立，checkpoint明确deferred_until_stable，未改写正式索引。总任务仍需凭据/Electron、PM9、正确性、诊断、质量门禁与最终全量/打包真实验收。

- confirmed：SEC-03 以 SQLite 持久 UUID 隔离系统凭据键；旧键保持不动、缺秘密要求全部重录。26 后端、109 前端、9 macOS 原生检查通过，证据见 credentials.md。AOCI 在第三块遭并发索引变化中止，未接管维护。

- confirmed：SEC-04 所有 Electron IPC 统一校验入口文档与主 frame，异步响应/运行上下文推送复核；双窗口阻止导航/重定向/新窗口/webview；打包忽略开发 URL。110 定向检查、ESLint、tsc 通过，详见 electron.md；不是历史利用链复现。

- confirmed：独立审查发现并修复共享关闭 fd 复用、失败清理误删、暂存大小写别名三个问题；真实红绿证据和29项检查见share.md追加节。Windows规范路径及DELETE最终对象防御已加入，实机仍待验。

- confirmed：N-01/N-02/N-03 与 DB-01 有界修复完成。55 项关联回归、14 项数据库组合（有重叠）、3 个生产 worker 场景通过；复审 NUL 拒绝补丁后15项通过。Windows原生参数与打包路径未实测。详见 nodes.md。本次AOCI完整交付5块280条、严格Challenge7/10、治理未对齐；继续源码绑定工程，不接管初始化。

- confirmed：F-01 修复代理三节点必填元数据；213冻结来源+3原生规则分别追溯，--check只读。6脚本、20前端、23后端通过，不计供应商实网。详见 required-fields.md。

- confirmed：N-04 共享错误展示保留已知单元格诊断，29项组件/状态测试通过；真实导入UI待最终包验收。Android 环境探测补真实默认bridge接口检查，非零命令保留有界脱敏原因；14后端+12前端通过。只读真实Lima确认docker0缺失，应用正确标不可用；未改共享VM，正常启动仍阻塞。详见 diagnostics.md。

- confirmed（限定范围）：A-01 R2 项目数据私有 RPC、冻结节点授权与 Studio 配置接通。42 后端回归（含一个真实生产 worker + SQLite 数据链）、12前端组件、6生成脚本通过。写回执移除未授权列，节点已结束／旧代次／其他项目工作区拒绝。完整浏览器、End、持久人工和打包 UI 仍待实现或验证，见 pm9-data.md。本轮 AOCI 280条5块 Challenge9/10，治理未对齐；独立审查后续遭自动安全拦截未重试。

2026-09-28：R2 数据 RPC 已提交 7876acc6；真实 bootstrap/HTTP/SQLite/生产 worker/CloakBrowser 的领取→网页→正式数据写回→状态推进场景 confirmed。新增真实发现：clearBefore=false 快速输入仍覆盖原值，已在共享执行器修复；原失败断言及 B1 差分组合 32 通过（1 真实、31 差分），退出资源检查通过。End/持久人工与打包 UI 未验收，不扩写为 PM9 完成。

2026-09-28：F-03（confirmed）两个清单检查改为显式候选输出目录，14 项回归通过并核对 5 份历史证据字节不变。原生节点仍保留未完成验收状态，213 冻结来源与 4 原生扩展独立校验。详见 quality-gates.md；完整门禁尚未验收。

2026-09-28：F-04/F-05 定向 confirmed：退役 Mock 教学与当前 217 节点/受管模型/排除通知入口合同已对齐；旧字段读取往返、撤销/重做断言保留。8 文件1239项、根教学1项、tsc与改动文件ESLint通过。完整默认回归与原生UI未计通过；见quality-gates.md。AOCI交付5/5，Challenge8/10 partial且治理未对齐，未接管其他任务索引。

2026-09-28：质量门禁切片 confirmed：98迁移、55合同生命周期、11schema/来源通过；真实CloakBrowser登录恢复与服务重建2项通过，清理报告增强后登录场景另复跑1通过。Ruff全后端通过、mypy506文件通过；strict仍1041历史错误，新增7项已消除，固定Darwin目标的只读基线门禁0新增并纳入CI，不称strict全通过。根脚本101通过；前端默认5646通过/2计数断言失败，修正项目数据必填字段后定向4通过。后端全量尚在运行。依赖公告刷新网络失败，未盲目升级。

2026-09-28：DB-01 metadata补充 confirmed：代理注册、Sheets identity_verification、索引/约束名/凭据列类型按现有迁移对齐；精确保护两个仅迁移保留的历史表，不排除未知表。真实SQLite Alembic check无差异/无排序警告；35项组合（含3种实际结构破坏必须失败）通过，strict0新增、Ruff通过。无历史迁移改动、无用户数据库写入；见metadata.md。

2026-09-28：UI-09 confirmed：真实目录包发现打开已有流程后错误 POST 导致409，根因为载入后的身份回调捕获旧文档；修复共享回调并添加当前文档保存错误横幅。48项定向、完整前端5650项、类型/lint/build通过；重新打包后原生保存修订1→2、刷新重开、正常退出重启后读取均通过。原生Excel导出5条、错误映射显示行列字段、修正映射导入5条及重启读回通过。源码浏览器补跑43项、冻结项目数据真实场景1项通过。PM9 End/人工恢复未完成，不能合并计为闭环通过。

2026-09-28：A-01有界补充confirmed：人工resume/finish失败操作的同键重试从错误202改为回放原失败HTTP/code/message/details；先查原结果再验到期。两个真实SQLite/HTTP红灯及修复后相关19项、定向Ruff/mypy通过。未改变恢复/End业务语义，生产CoreRun恢复缺口仍存在；详见manual-command-errors.md。
