# AutoFlow 修复与验收台账

日期：2026-09-28。状态：in_progress。来源：本次用户实施授权、历史审计 f853d7ee 与当前源码核验。基线见 baseline.json；历史报告不改写。未提交的文档、AOCI 与历史证据全部保留，不 push、不发布。

基线修复切片截至 `faf8fc21`；生产 End 实现与两轮修复为 `b16e1715`、`1fdda1c8`、`d1c18362`，定向独立复审已通过。下表“当前证据与根因”保留本轮修复前核验；最终行为看状态及对应分报告，不表示缺陷仍存在。PM9 End 五类源码 worker 真实登录保存/复用场景通过；循环/嵌套停止传播、持久 saved_unlinked 修复入口及未知请求原键恢复已补齐，共享进程清理缺陷已在 `d6f9cb0f` 修复并独立复审；最终后端全量已完成；e49144f2 的前端、打包及原生 End 通过，最终两项前端修复 c2367a17 已复审，最终门禁与真实原生验证已通过；人工跨应用重启续接的语义差异仍待裁定。置信度：有源码、红绿检查或真实结果的已完成条目为高；尚未定位的组合失败为未知。

本轮范围为安全隔离、已批准 PM9 R2/R3、已证实正确性和诊断问题、可信质量门禁。外部账户/付费/消息/共享 VM 变更不在执行范围。平台未实测不得标记通过。各行必须在执行后补证据与提交；pending 不表示已经修复。

| 问题 | 当前证据与根因 | 受影响调用方 | 目标行为与最小改动 | 验证 | 状态 |
|---|---|---|---|---|---|
| SEC-01 共享读边界 | 当前文件仍静态回退 SimpleHTTPRequestHandler；HEAD 同样需约束 | 静态 GET/HEAD、download、preview、thumb、list、单文件共享 | 统一根目录路径解析及实际打开；不泄露相邻文件 | 隔离真实 HTTP、编码/穿越/链接/正常下载 | 本机30项通过，见 share.md |
| SEC-02 上传竞态 | 后缀候选直接 wb，exists 不识别悬空链接 | upload；同根 mkdir/delete 需审查 | 相对于受控目录排他创建；失败清理；平台适配 | 同名/链接/并发/请求中断真实文件检查 | 本机通过；Windows待实测，见 share.md |
| SEC-03 凭据隔离 | _key 仍只 hash(name)，元数据则按工作区隔离 | 创建/读/字段变更/重命名/删/切换 | 稳定工作区命名空间；旧条目不自动认领、不删除 | 两真实 SQLite + 专属系统凭据；旧键恢复边界 | 本机26后端+109前端+9原生检查通过，见 credentials.md |
| SEC-04 Electron | 修复前缺共同可信页面约束；已追踪IPC调用链 | 主窗口/Studio/IPC | 拒绝非受信页面与子 frame，保留开发/本地页面 | 本地防御拒绝测试；不继续被拦截的利用链 | 110项通过；built/dev/packaged合法入口各5检查通过，见 electron.md、native-ui.md；不是动态利用成功证明 |
| A-01 PM9 R2/R3 | 已批准规格；R2生产桥已在7876acc6接通，R3仍缺失 | dispatcher/project worker/runtime/data/environment/manual/UI | 复用现有能力服务；固定身份RPC、持久恢复；不改内存表语义 | 真 worker/浏览器/SQLite 全链、fencing/幂等/重启 | R2数据通道42项及真实浏览器写回/状态链通过；End五类真实源码worker链及两轮审查整改已通过，见 pm9-end/README.md；冻结worker与e49144f2完整包重启复用通过；最终前端5686通过、最新包End重启复用及原生配置通过，人工恢复待语义裁定，见 pm9-data.md、pm9-r3-implementation.md |
| DB-01 唯一约束 | ORM(task_id,lease_id) 与迁移(task_id,record_ref) | 数据能力 cursor | 按业务唯一性核对模型；不改历史迁移 | 新/旧库升级、metadata check、冲突数据 | 已修复；metadata组合35项通过，见 nodes.md、metadata.md |
| N-01 CSV | 历史真实仅表头返回一行 | csv 读取节点 | 有表头时跳过第一行，即使无数据 | 真实空/表头/普通 CSV | 已修复；限定验收见 nodes.md |
| N-02 Python argv | 当前审计指出 str.split | 文件脚本节点/子进程 | 保留字符串契约，明确跨平台引号；无 shell=True | 真脚本/中文空格/引号/错误输入 | 已修复；限定验收见 nodes.md |
| FUNC-01 共享预览 | 当前 import 指向不存在模块 | preview 与共享页面 | 返回明确不支持并同步页面；现有媒体/文本下载保留 | 真 HTTP 不再500、不假成功 | 明确415与UI提示；本机通过 |
| N-03 SHA | 历史未知算法静默 sha256 | 散列节点 | 白名单拒绝未知值 | 真实文件文本与独立 hashlib | 已修复；限定验收见 nodes.md |
| F-01 代理必填字段 | 历史元数据213，批准216 | 导出器/后端准入/前端配置 | 从当前正确配置同步必填约束与检查集合 | 缺字段拒绝、完整配置准入、生成一致 | 6脚本+20前端+23后端通过，见 required-fields.md |
| N-04 导入错误 | 持久错误 details 存在，UI 只显示通用码 | Excel import/status/presentation-error | 白名单展示行列字段和类型要求 | 真 XLSX 错映射→定位→修正→保存/重启 | 展示修复29项通过；原生错误行列字段、修正导入5条、刷新及重启通过，见 diagnostics.md、native-ui.md |
| A-04/A-10 Android | available=true 与 docker0 缺失并存；stderr 丢弃 | runtime/environment/management/UI | 依赖诊断+稳定错误分类；准确工作流文案 | 当前 VM 只读诊断；自有资源；不修共享 VM | 14后端+12前端通过，真实诊断确认网络缺失；见 diagnostics.md |
| F-02/A-06 文案 | PROJECT_STRUCTURE 入口已由其他任务修正；其他旧描述待处理 | 教学/Android/架构与.ai入口 | 更新当前能力，保留历史记录 | 当前目录与页面人工核对 | 教学及入口已更新；定向1239项通过，原生UI待验 |
| QA-01 旧门禁 | 历史64后端/54前端/4脚本失败分报告 | smoke/迁移schema/registry/生命周期/生成检查 | 逐项契约证据后更新；检查不写既有证据 | 定向红绿→最终全量；原始失败分类 | 最终后端4326通过/0失败/50跳过；80项迁移子集通过。前端e49144f2为433文件5683通过；c2367a17最终433文件5686通过，lint/type/build/package通过；根脚本102通过。默认50跳过中49已门控实跑，1付费模型未执行，见final-validation-results.md |
| QA-02 静态检查 | Ruff137；普通mypy过，strict1041债务 | CI/后端src/tests | 修实际lint；strict独立基线、禁止新增，不泛化Any | lint/typecheck/债务门禁真实运行 | Ruff全后端、mypy506文件通过；strict1041历史债务、增量门禁0新增；End/进程修复后最终Ruff、mypy509文件、strict0新增和OpenAPI通过，见quality-gates.md |
| DEP-01 依赖 | Monaco嵌入旧DOMPurify、Paramiko/setuptools公告命中 | 编辑器/SSH/构建及识别 | 复核官方公告、依赖路径、兼容后有界更新 | 锁/安装/产物/相关功能，不跑强制全升级 | Monaco0.57实际嵌入3.4.15且原生编辑通过；SSH禁RSA SHA-1，13真实协议/worker检查通过；setuptools及主机信任缺口未关闭，见 dependencies.md |
| UI-01 保存身份 | 打开文档后Toolbar闭包绑定旧docId，保存错误仅记控制台 | Studio打开/保存/运行前保存 | 绑定当前Store文档身份，409保留草稿并显示错误 | 旧行为2项失败；48定向通过；原生revision1→2及重启 | 已修复，40da11b8，见 studio-save.md |
| MAN-01 人工错误重放 | 持久failed命令重放曾作为202成功回执 | resume/finish幂等查询 | 返回持久原错误及HTTP状态，不重复副作用 | 真实SQLite/HTTP旧行为失败；19定向通过 | 已修复，58fa444c，见 manual-command-errors.md；不代表人工继续已形成运行闭环 |
| QA-03 组合终态异常 | 默认全量三个应failed的Run返回WORKFLOW_RESULT_UNKNOWN/interrupted；定向重复未复现 | credential/timing/webhook项目worker与清理 | 保留错误事实并定位真实底层异常，不能改预期或加超时 | 原始全量日志、21项定向及5次诊断重复、全量诊断中 | 已确认owned进程缺陷在Task4修复并独立复审，59项定向及真实SIGKILL检查通过；最终默认4326通过，原三个组合失败未重现，但其历史根因仍未知，不能倒推已证明同因，见 worker-cleanup-diagnosis.md |
| UI-03 Studio配置分歧 | 原生nested data.config保存后外层新值被旧内层遮蔽；SQLite revision3有双值 | Studio配置面板、加载/保存/导入、实际Runtime | 共享配置适配兼容flat/nested，展示/保存/实际执行一致，不改公共字段与运行优先级 | 原生失败截图/SQLite已归档；修复后同工作区原生重验 | 已修复23247c28/e49144f2，原生保存revision4、重开、整应用重启及实际End环境名一致通过，见native-session-LCCIyR/README.md；原失败保留native-session-VwvJnD/README.md；最终两项附加修复c2367a17原生真实RecordRef及子流程保存/整应用重启通过，见native-session-HuHw5N/README.md |
| UI-02 连接恢复横幅 | 原生正式运行持久成功，交互中断横幅仍显示；刷新消失 | ProjectInteractionHost轮询 | 仅清已恢复的通信错误，保留真实脚本/操作错误 | 新增错误→恢复及真实错误保留回归；专属sidecar真实SIGSTOP/CONT | 已修复30ae0138及dae16113/d2bcae4f/8828eb2a三轮审查整改；16定向通过，独立复审通过。真实中断/恢复PNG、AX及SQLite单次执行见interaction-notice-round1/README.md；claim窄窗口仅边界回归，最终前端全量5686及同版构建/打包通过 |

验证按切片进行，最终稳定状态运行全量 pytest、门控 CloakBrowser、Vitest、根脚本、lint、typecheck、OpenAPI、迁移与源码/打包启动。真实场景单独计数；失败、环境阻塞和未执行保留。

最终独立审查又发现静态 End recordTargets 隐藏与子流程下拉读取外层旧配置，两项均由 c2367a17 有界修复、133定向通过并限定复审关闭。单元夹具存在旧RecordRef形状的Minor，保留并明确不能用其证明合法目标执行。另有UI-04：环境时间显示与任务时间相差8小时，真实截图已保留，时区契约根因尚未确认，未修复。

当前交付结论：有界修复及现有本机门禁形成可审查提交，但完整生产验收未通过。人工持久恢复、SSH主机信任、setuptools兼容升级、UI-04时区差异及未执行平台/外部/容量矩阵仍保留，见delivery.md和remaining-validation.md。原始失败证据未替换；所有计数按独立范围报告。
