# 项目管理内部身份展示

日期：2026-09-15。状态：confirmed（展示规则与已验证行为）；本专项最终验收通过，范围与未执行项以专项 verification.json 为准。

来源：用户本次 UUID 展示修复要求、实际源码、先失败后修复的组件测试、真实隔离 Electron 验证。独立工作区 `autoflow-project-management-pm3`，主项目只读。

- 内部 UUID 保留数据库、HTTP/路由、React/query key、并发与幂等恢复作用。禁止全局 UUID 文本清洗。
- project-data/presentation.ts 区分 system/field：系统记录使用业务文本标题或未命名记录加时间，业务身份保留原值，包括用户 UUID。
- 失效资源、字段、输入和节点选项必须提供语义标签；共享 Select 不负责猜测业务名称，不改变选项值。
- projects/presentation-error.ts 按原错误 code 生成中文；未知错误通用失败；结果不明保持核对原操作指引。原异常、事务、恢复身份和工作区隔离不变。
- 批次显示自动化名称及开始时间；任务使用已有 ordinal 的1-based投影；节点从本次运行 prepared content 冻结 data.name/data.label/中文目录解析，不读取当前工作流。
- 管理展示提交865868f、0f251b5、33396f8、636931e、841a1f7。ProjectsWorkspace只在明确交接后局部提交两个错误展示入口，路由WIP未被混入。
- 原PM3任务拥有运行后端、project-runs、generated、AutomationDetailPage和路由装配；本专项独立验收，不代为提交其WIP。最终源码基线必须同时记录HEAD和已保留工作树，不能把HEAD当作所有运行成果已提交。
- 专项QA使用/tmp隔离构建，避免写原任务out；真实UI建立项目/自动化/系统表/记录，真实CloakBrowser与后端执行。业务字段身份经Excel检查/映射/导入建立；失效资源用正式HTTP资料准备，不改数据库。
- 检查器只扫描已知内部身份的感知文本/属性，排除data-*、DOMvalue、href/hash和网络；业务UUID共前缀只在完整业务值对应位置豁免，不能掩盖独立技术短ID。
- 全量检查曾发现Unicode模拟逐字输入超时，改用同边界真实粘贴，保留全部值/提交断言与原timeout；并捕获并行截图aria-label变更。最终静态补查发现AutomationDetailPage/BatchLauncher原始错误和validation文案出口，列为必须关闭的实际问题，未按“测试多数通过”交付。

证据、审查闭合与手测：docs/project-management/implementation/pm3/uuid-display/README.md。只交付本专项，不宣称PM3全部完成。Windows、其他架构、打包与用户手测未执行。

最终核验：a5e7d48 加登记工作树的固定副本完成前端3224项、后端1407项及单独真实浏览器8项，类型/lint/OpenAPI/构建/脚本/结构通过；真实Electron三个流程26图逐图复核。强停仅对测试Electron唯一worker进行明确SIGSTOP注入，真实停止/宽限/强停后验证PID及启动时间对应进程退出。资源错误/刷新错误为明确HTTP注入；自然节点失败独立验证。未知错误与validation出口已经闭合。

原负责人随后提交d5f27ba/bacbccf。2026-09-15逐文件哈希比较确认桌面源码、后端源码、后端测试与固定验收副本完全一致；身份独立测试及Unicode测试由原负责人包含在bacbccf。本专项仅提交剩余QA与证据，不覆盖原任务执行卡及资料。200%缩放本次专项未运行，用户手测保持未执行。
