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
