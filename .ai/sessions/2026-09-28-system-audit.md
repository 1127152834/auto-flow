# 2026-09-28 系统架构审计与真实 QA

- 日期：2026-09-28（Asia/Shanghai）。
- 状态：confirmed（本轮证据）；proposed（修复顺序）。
- 来源：用户明确要求全面架构/应用设计检查及真实场景测试；规范依据 AGENTS.md、.ai/README.md、project-context、架构索引与相关已批准决策。
- 基线：33ae3aa49600840b1700c83723408c494dc201a8，codex/project-management-pm9 的实际工作树。开始时既有文档/历史证据变更全部保留。

## 结论与事实

当前不能按全量生产验收通过处理。真实复现共享静态 GET 越界、重名上传候选链接越界创建、跨工作区同名 Studio 凭据串扰，以及共享预览缺模块、CSV 仅表头被当记录、Python 参数破坏带空格路径、未知 SHA 算法静默降级等。项目生产执行与业务数据 capability / 环境 End / 持久人工恢复仍存在已批准 PM9 R2/R3 的闭环缺口。

Superseded（仅限以下旧结论，不覆盖原始历史记录）：当前 Studio 与项目执行共享 WorkflowRuntime；资源已有静态引用删除保护；packages/ui 空目录符合当前已批准代码组织方式。没有凭旧资料要求重造引擎或搬包。

## 验证

- 全量默认后端：4257 项，4150 pass / 64 fail / 43 skip。多数失败为过时迁移head/快照/夹具，不等于64个业务故障；42项门控真实浏览器补跑40pass/2fail，失败诊断以权威后端报告为准。
- 前端：5628 项，5574 pass / 54 fail；Node22复现同54失败；脚本92pass/4fail；typecheck/lint/OpenAPI/build通过。
- 后端ruff137问题；普通mypy通过502源文件，strict1041错误157文件；真实空库/重复迁移/integrity/FK通过，ORM metadata漂移失败。
- 真实生产sidecar/SQLite/worker/CloakBrowser、公网页面、真实源码数据、停止/崩溃恢复、图控制、CSV/XLSX/ZIP/Allure/OCR/共享/Webhook均留原始证据；正式JS脚本在打包App原生编辑器创建后完成生产worker往返并持久核对。
- 节点脚本118场景115pass/3个真实缺陷；另原生JS与19类真实浏览器补验，综合触达149执行类型/2结构类型，剩66类型未执行。
- 当前源码macOS arm64 frozen backend/.app实际构建启动；原生Excel保存/打开/导入导出5条源码清单逐值相等；Cmd+Q后服务退出。未验签名公证/安装升级或其他平台。
- 8504个真实跟踪文件作为负载，正式API批写/筛选/排序/完整分页验证通过；默认首页P95 32.826ms、大小排序P95 139.781ms，每类10次，不能外推长期或10万行。
- Android两次创建/幂等通过，start因共享VM缺docker0失败；自有设备/卷recover+delete完成，原有6容器和卷不变。诊断available=true与缺少具体错误是应用设计缺口；没有修改共享VM。

## 产物与边界

总入口：[docs/qa/2026-09-28-system-audit/README.md](../../docs/qa/2026-09-28-system-audit/README.md)。包含46项功能覆盖矩阵、217类型节点台账、可重跑脚本、分报告与脱敏日志。所有数字以对应机器结果为准，Mock回归与真实场景分层，不计算虚假的统一通过率。

本轮仅增加审计与测试产物，未修改业务源码、全局配置、既有业务库或外部账号；临时进程和自有Android/Keychain资源已清理，UI/主运行链QA工作区保留用于核验。没有发送外部消息、付费调用或发布。没有替换/覆盖其他任务的未提交文件。

依赖扫描结果独立记录于本轮报告；它是已知公告匹配，不等于已证明攻击可达。Electron导航动态复现受到自动安全审查限制，保留静态发现，不绕过限制。

外部专用账号/预算、Google Sheets/代理/邮件/Telegram/SSH、硬件、Windows/macOS Intel、长期soak和剩余节点分支未全部验证。用户尚未提供这些具体资源范围，未擅用已有账户。

## 下一步（proposed）

1. 修复3项共享/凭据隔离问题，保留真实复现作为回归。
2. 沿既有PM9计划完成单条生产业务闭环，架构改动先按项目规范设计/规格/计划后确认。
3. 对齐ORM/迁移，修复节点缺陷与错误可解释性，更新过期测试/smoke/教学与只读检查流程。
4. 在指定测试资源与平台补完覆盖矩阵，不用模拟外部成功响应代替验收。

## 并发变更与 AOCI

收尾时另一任务修改 .gitignore、AGENTS.md、docs/PROJECT_STRUCTURE.md，新增项目地图与 AOCI 资产。本轮未改写或提交这些文件。PROJECT_STRUCTURE 顶部已标记旧 Mock 结论 superseded；架构报告 A-06 已修正。真实源码清单摘要保留取样时语义，不能要求与后来修改的文件一致。

新增 AOCI 合同已读取；压缩恢复后的显式重载交付当时 40 条索引，认知确认遇到 cognition_snapshot_unavailable（并发资产变化），停止该认知链，不声称完整认知验证完成。当前索引仍在另一任务初始化，本轮没有用 maintain 替代 bootstrap，也没有改写其正式资产。结论均依赖本轮源码与真实执行证据。
