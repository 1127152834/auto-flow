# 质量门禁修复记录

日期：2026-09-28。状态：in_progress。来源：历史审计 frontend-regression.md 与本轮源码/执行日志；已验证条目置信度高。

F-03：两个 inventory 脚本测试此前调用生成器覆盖历史验收清单、组件扫描与服务矩阵，且无法处理已经批准的原生节点。改为显式 `--output-dir <候选目录>`，测试使用本次 mkdtemp 创建的专属目录，结束删除自身目录。源码与已核销证据仍从仓库只读获取。无输出参数明确拒绝，避免检查或误调用静默改写历史证据。

节点清单分别验证 213 个冻结来源节点与 4 个原生节点（代理 3、项目数据 1）。原生节点保持原有 status、verifiedCases、remaining 和 deliveryBlock，禁止用旧节点共享验收记录将新节点升级为通过。现有冻结节点的独有字段与依赖断言保留。测试逐字节验证历史 capabilities/test-cases/component-tools/service-inventory/contract-matrix 不变，并独立检查候选生成确定性。

`inventory-readonly.log`：14 项通过，无 skip。未覆盖的门禁仍待处理，不代表完整根脚本或全前端回归已恢复。原生节点后续发生正式扩展时必须一起更新显式范围校验，不能从扫描结果自动放宽批准范围。

## F-04 / F-05：前端过期合同与退役教学（confirmed，定向范围）

历史 54 项失败的相关文件重新核对到当前源实现，未批量修改快照。当前目录固定为 213 个冻结节点和代理 3、项目数据 1 共 217 个节点；解析器新增计数逐项归因于 `30dc9686` 的 OCR 输出字段修正与 `7876acc6` 的项目数据节点，并增加两节点字段/默认值独立断言。

31 个退役面板字段保留历史文档往返断言，同时显式验证它们不再出现在当前面板，且其替代控件（受管 modelId 或浏览器 captureMode）存在。14 个已排除通知入口由旧“可编辑”断言改为明确不可添加断言。图片/视频提示词使用实际 textarea，仍执行单字段变更、撤销、重做和文档重开检查。组件清单从现有 AST 脚本生成到独立临时目录，不再将他人未提交的历史 component-tools 当作当前契约。

教学页删除退役 Mock 阶段提示；通知教程收紧为实际支持的 Telegram/Webhook 字段，移除已排除能力。项目入口文档标明历史状态已被当前生产入口替代。新增断言禁止恢复旧提示，不修改历史审计正文。

- `frontend-original-failures-fixed.log`：8 文件、1239 项通过，无 skip（组件与单元边界，不是原生 UI 验收）。
- `documentation-scope.log`：根教学审计 1 项通过。
- `frontend-gates-typecheck.log`：tsc 通过；`frontend-gates-eslint-fixed.log`：改动文件 ESLint 通过。
- 初次 AST 测试路径被 Vite URL 转换导致的加载失败、初次错误工作目录的 lint 命令均保留原始日志；修正测试路径/命令后通过，未改业务成功条件。
- 默认 Studio smoke 已按当前真实 HTTP/窗口生命周期修改，尚未运行打包应用，不记为通过；最终全量前端、根脚本和打包真实验收仍待执行。

## B-01 / B-02：后端过期断言与生命周期（confirmed，定向范围）

按实际 Alembic 图将集成 head 更新为 `0024_studio_credential_namespace`，保留所有历史起点、升级前后行比较、外键检查与历史迁移 SHA 断言；未修改迁移版本文件。BrowserStatus 补齐当前 schema 五个字段的精确默认值；WebDAV 请求 schema 是唯一允许 password 字段的公开 schema，并另外核对配置读取不返回秘密。生产注册表补代理三节点和项目数据节点；来源审计仍逐项核验 213 个冻结节点，4 个原生节点独立检查来源/范围，不伪造上游迁入记录。

Excel 公式缓存夹具兼容 `<v/>` 与 `<v></v>`，新增替换次数必须恰为 1 的断言；原公式和值检查保留。关停测试调用真实应用 lifespan 或按顺序调用并等待实际异步 handler；PM5 浏览器脚本关闭已进入的 TestClient，关闭失败保持非零退出并记录 `shutdownConfirmed=false`。显式 `--keep-browser` 现在等待回车后清理退出，不再让未关闭 portal 永久挂住 Python。

- `backend-migration-current.log`：98 通过；`backend-contract-lifecycle.log`：55 通过；`backend-schema-scope.log`：11 通过。以上组合互相独立。
- `backend-real-lifecycle.log`：2 项真实 CloakBrowser 登录保存恢复/服务重建通过；清理结果写入增强后 `backend-real-cleanup-final.log` 同一登录用例再次通过 1 项（重复验证，不额外累计场景）。
- 历史 0.5 秒 worker 退出偶发失败暂未修改等待上限，等待当前完整回归确认，不能降低时序检查。

## B-03：Ruff 与严格类型债务（confirmed，工程门禁）

CI 工作目录下 Ruff 本轮原始 138 条（含本次新增测试导入顺序），修复以原配置导入整理及删除原本无效的 noqa 为主。IMAP 轮询/标记已读/退出失败现在记录安全的异常类型，不记录可能含凭据的异常正文；网页变更时间取现有 context clock，IMAP 时间明确 UTC；相邻鼠标点遍历使用 pairwise。行为回归 `ruff-behavior-regression.log` 20 通过。最终 `ruff-gates-fixed.log` 全后端 Ruff 通过。

初次仅 select 部分规则使 Ruff 将其他有效 noqa 误判无效；已从 HEAD 精确恢复既有注释，再按完整配置的 fixable 白名单执行。未改既有 lint 策略、未增加跳过、未以新增 suppressions 获得通过。初始错误日志保留，最终 diff 只保留必要整理和有证据的修复。

普通 mypy `mypy-gates-final.log`：506 源文件通过。strict 原始本轮1048，新增7项已补具体返回/句柄/消息类型，剩1041；其中既有构造器诊断仅从完全无注解变成参数缺注解，仍算债务。`strict-type-baseline.json` 固定现有943个诊断身份、1041个实例；CI `check_strict_types.py` 对完整 strict 输出按文件+符号+错误码+消息+数量比较，新增错误失败，已解决条目要求同步删基线。检查只读、不自动批准新债务，单元验证行号变动、不同函数、重复次数、消息变化及未知输出拒绝。

`strict-gate-current.log`：1041基线、1041当前、0新增，增量门禁通过；**不是 strict 全量通过**。当前基线固定 Darwin 静态分析目标，跨平台普通 mypy 保留；未将配置加入 CI 冒充远程 CI 或 Windows 实测。

## 当前全量检查仍在进行

前端首次默认回归：431文件，5646通过/2失败；两项必填元数据 fixture 数量漏计本次项目数据节点。修正为217并新增项目数据必填字段/写操作绑定规则断言，`frontend-required-protocol-fixed.log` 定向4通过。根脚本 `root-scripts-current.log`：101通过、0失败、0skip。后端完整回归运行中，最终计数另记；以上结果不是最终稳定发行验收。

2026-09-28 默认 Studio smoke 追加核验（confirmed）：生产路由 `/api/workflows` 已取代退役 Mock 阶段；默认入口验证真实空 SQLite 文档目录及正式画布。主窗口关闭后保留隐藏的交互宿主，Studio继续运行，正常退出再确认 sidecar 停止。built HTML、开发 Vite URL、macOS arm64 目录包各5项通过，见 `studio-smoke-{built,dev,packaged}/`。默认验收输出改为唯一新目录，避免覆盖历史资产；未改写旧Mock验收报告。

Monaco0.57的exports映射让 `require.resolve('monaco-editor/package.json')` 指向不存在文件：这是升级后新增的门禁脚本路径错误。`scripts-final.log`保留101通过/1失败；改为公开模块子路径定位实际嵌入DOMPurify，原版本断言保持，`scripts-final-fixed.log`完整102项通过。此前101项的通过时点在此依赖升级之前，不能据此声称升级后门禁已绿。

2026-09-28 后续全量结果：`frontend-final.log`为431文件5650项通过。`backend-final.log/xml`为4278通过、3失败、44跳过；失败集中于三个负向生产worker场景，预期failed而实际为WORKFLOW_RESULT_UNKNOWN/interrupted。原断言和时限保留，不能改成接受interrupted来消除失败。

这三个文件的21项定向复跑通过，并在带诊断的5次重复中仍各21通过。它只能证明未稳定复现，不能证明缺陷消失。`cleanup_diagnostic_plugin.py`只调用真实原方法，捕获异常打印栈后原样抛出，不提供成功响应或改变清理结果。全量诊断期间PM9 End实施开始修改源码，部分后启动worker可能读取新源码，因此这轮诊断只能用于定位，最终默认回归必须在稳定源码上另执行。

2026-09-28 End两轮修复及共享进程修复后的最终静态门禁（HEAD d6f9cb0f）：`final-ruff.log`全后端通过；`final-mypy.log`509个源文件通过；`final-strict.log`仍1041历史债务、0新增；`final-openapi.log`生成一致性通过。`final-root-scripts.log`完整102通过。`final-backend-build.log`冻结后端构建exit0、168.53秒，构建开始/结束源码摘要一致。对应command.json保留命令、cwd、HEAD及退出码。后端完整运行回归尚未完成，以上不代表运行验收。

最终默认回归第一轮（`final-backend-default.log/xml/command.json`，HEAD d6f9cb0f，源码摘要前后一致）：4325通过、1失败、50跳过，1106.46秒pytest时间。唯一失败是`test_production_registry_contains_every_migrated_executor`的精确集合遗漏本轮正式新增`project_end`；不是产品执行失败，不允许因此删除完整集合断言。Task5按批准End契约补齐，复验结果另记。历史三项负向worker终态异常在本轮均通过；因当时缺候选PID诊断，不倒推其根因。迁移相关80项是本轮默认回归子集，清单见`final-backend-default-summary.json`，不额外累计。50项跳过分为本机浏览器门控与付费模型实网门控，补跑单独记账。
