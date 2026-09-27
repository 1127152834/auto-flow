# AutoFlow 修复与验收台账

日期：2026-09-28。状态：in_progress。来源：本次用户实施授权、历史审计 f853d7ee 与当前源码核验。基线见 baseline.json；历史报告不改写。未提交的文档、AOCI 与历史证据全部保留，不 push、不发布。

本轮范围为安全隔离、已批准 PM9 R2/R3、已证实正确性和诊断问题、可信质量门禁。外部账户/付费/消息/共享 VM 变更不在执行范围。平台未实测不得标记通过。各行必须在执行后补证据与提交；pending 不表示已经修复。

| 问题 | 当前证据与根因 | 受影响调用方 | 目标行为与最小改动 | 验证 | 状态 |
|---|---|---|---|---|---|
| SEC-01 共享读边界 | 当前文件仍静态回退 SimpleHTTPRequestHandler；HEAD 同样需约束 | 静态 GET/HEAD、download、preview、thumb、list、单文件共享 | 统一根目录路径解析及实际打开；不泄露相邻文件 | 隔离真实 HTTP、编码/穿越/链接/正常下载 | 本机30项通过，见 share.md |
| SEC-02 上传竞态 | 后缀候选直接 wb，exists 不识别悬空链接 | upload；同根 mkdir/delete 需审查 | 相对于受控目录排他创建；失败清理；平台适配 | 同名/链接/并发/请求中断真实文件检查 | 本机通过；Windows待实测，见 share.md |
| SEC-03 凭据隔离 | _key 仍只 hash(name)，元数据则按工作区隔离 | 创建/读/字段变更/重命名/删/切换 | 稳定工作区命名空间；旧条目不自动认领、不删除 | 两真实 SQLite + 专属系统凭据；旧键恢复边界 | confirmed，待修复 |
| SEC-04 Electron | 审计源码缺共同可信页面约束；待逐调用方复核 | 主窗口/Studio/IPC | 拒绝非受信页面与子 frame，保留开发/本地页面 | 本地防御拒绝测试；不继续被拦截的利用链 | 核对中 |
| A-01 PM9 R2/R3 | 已批准规格；历史生产桥缺失，当前未有业务提交 | dispatcher/project worker/runtime/data/environment/manual/UI | 复用现有能力服务；固定身份RPC、持久恢复；不改内存表语义 | 真 worker/浏览器/SQLite 全链、fencing/幂等/重启 | 核对中 |
| DB-01 唯一约束 | ORM(task_id,lease_id) 与迁移(task_id,record_ref) | 数据能力 cursor | 按业务唯一性核对模型；不改历史迁移 | 新/旧库升级、metadata check、冲突数据 | 核对中 |
| N-01 CSV | 历史真实仅表头返回一行 | csv 读取节点 | 有表头时跳过第一行，即使无数据 | 真实空/表头/普通 CSV | 核对中 |
| N-02 Python argv | 当前审计指出 str.split | 文件脚本节点/子进程 | 保留字符串契约，明确跨平台引号；无 shell=True | 真脚本/中文空格/引号/错误输入 | 核对中 |
| FUNC-01 共享预览 | 当前 import 指向不存在模块 | preview 与共享页面 | 返回明确不支持并同步页面；现有媒体/文本下载保留 | 真 HTTP 不再500、不假成功 | 明确415与UI提示；本机通过 |
| N-03 SHA | 历史未知算法静默 sha256 | 散列节点 | 白名单拒绝未知值 | 真实文件文本与独立 hashlib | 核对中 |
| F-01 代理必填字段 | 历史元数据213，批准216 | 导出器/后端准入/前端配置 | 从当前正确配置同步必填约束与检查集合 | 缺字段拒绝、完整配置准入、生成一致 | 核对中 |
| N-04 导入错误 | 持久错误 details 存在，UI 只显示通用码 | Excel import/status/presentation-error | 白名单展示行列字段和类型要求 | 真 XLSX 错映射→定位→修正→保存/重启 | 核对中 |
| A-04/A-10 Android | available=true 与 docker0 缺失并存；stderr 丢弃 | runtime/environment/management/UI | 依赖诊断+稳定错误分类；准确工作流文案 | 当前 VM 只读诊断；自有资源；不修共享 VM | 核对中 |
| F-02/A-06 文案 | PROJECT_STRUCTURE 入口已由其他任务修正；其他旧描述待处理 | 教学/Android/架构与.ai入口 | 更新当前能力，保留历史记录 | 当前目录与页面人工核对 | 部分历史结论已修订 |
| QA-01 旧门禁 | 历史64后端/54前端/4脚本失败分报告 | smoke/迁移schema/registry/生命周期/生成检查 | 逐项契约证据后更新；检查不写既有证据 | 定向红绿→最终全量；原始失败分类 | 核对中 |
| QA-02 静态检查 | Ruff137；普通mypy过，strict1041债务 | CI/后端src/tests | 修实际lint；strict独立基线、禁止新增，不泛化Any | lint/typecheck/债务门禁真实运行 | 核对中 |
| DEP-01 依赖 | Monaco嵌入旧DOMPurify、Paramiko/setuptools公告命中 | 编辑器/SSH/构建及识别 | 复核官方公告、依赖路径、兼容后有界更新 | 锁/安装/产物/相关功能，不跑强制全升级 | 核对中 |

验证按切片进行，最终稳定状态运行全量 pytest、门控 CloakBrowser、Vitest、根脚本、lint、typecheck、OpenAPI、迁移与源码/打包启动。真实场景单独计数；失败、环境阻塞和未执行保留。
