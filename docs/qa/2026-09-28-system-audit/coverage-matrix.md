# 真实系统 QA 覆盖矩阵

- 日期：2026-09-28。
- 状态：confirmed（本轮已取得的执行结果与证据）；proposed（尚未完成的验收标准）。
- 基线：`33ae3aa49600840b1700c83723408c494dc201a8`。
- 本文是覆盖账本与执行结果索引。PARTIAL 代表已取得真实证据但该行仍有未完成子项，不能等价 PASS；NOT_IMPLEMENTED 是已批准能力的实际缺口。统计以本轮权威报告为准，不累加探索失败或重复复核。

## 真实性规则与数据来源

1. 生产业务代码、真实 SQLite/Alembic、真实进程/文件系统、正式 Electron/preload/HTTP、实际 CloakBrowser 必须组成正式本地链；不以 fake executor、fetch/mock transport 或改 Store 得到预期结果。
2. 数据使用本次实际采集的仓库文件清单（路径、扩展名、字节数、SHA256）、实际运行日志、真实导出的工作簿、公开真实网页及明确指定的 QA 远端资源。业务流使用隔离 QA 工作区，写入它自己的实际记录；不克隆/修改生产业务数据。
3. 本地真实 HTTP/SMTP/SSH 服务可验证实际协议、网络断开和错误恢复，但它们不等于第三方供应商。特别是本地代替 Telegram/OpenAI/Google 的响应服务器必须登记为服务替代，不能满足用户要求的供应商实网验收。
4. 故障注入与 mock 区分：杀死本次拥有的子进程、真实断连接、使临时目录只读、实际中断写入属于真实故障；直接修改函数返回值或绕过业务状态不属于真实系统证据。
5. 对发邮件/Telegram、远程代理切换、付费模型生成等有外部效果场景，只在用户明确指定测试目标/账号/预算后执行；其余独立本地检查继续进行。不得为了凑通过数用模拟账号替代。
6. 每条结果至少记录源码 commit、启动方式（源码/打包）、平台、隔离工作区、真实依赖、步骤、期望、实际、请求/运行/命令 ID 的脱敏标识、证据文件、清理结果。密钥、cookie、密码和完整私密输入不进报告。

## 场景与通过标准

| ID | 模块 / 真实场景 | 数据与实际依赖 | 必须验证的结果 | 当前执行限制 / 适用入口 | 本轮状态 | 本轮实际覆盖 / 剩余项 | 证据 |
|---|---|---|---|---|---|---|---|
| SYS-01 | 冷启动、健康握手、重复打开、正常退出 | 独立 userData + workspace；真实 Electron/sidecar | 单实例、随机 loopback、版本一致、退出后无遗留 owned 进程 | `smoke-sidecar.mjs`、`smoke-desktop.mjs`；启动方式分别记证据 | PARTIAL | 真实应用/sidecar启动、认证、退出清理已测；独立单实例争用未测。 | [UI](ui/result.json)、[运行链](runtime/runtime-realqa.md) |
| SYS-02 | sidecar/worker 崩溃后恢复 | 本次启动的真实子进程 | 状态不能假成功；结果未知可查询；重启不重复副作用；旧代次无权提交 | 只结束本次拥有的进程；不能误杀用户实例 | PARTIAL | 真实 sidecar SIGKILL→重启→新任务成功，旧任务中断且资源清理；worker独立崩溃及全部unknown分支未测。 | [运行链](runtime/runtime-realqa.md) |
| SYS-03 | A→B→A 工作区切换，进行中任务阻断 | 两个真实临时工作区及各自记录 | 无串读串写，旧端口失效；切换失败回到原工作区；脏草稿保留/确认 | 原生目录选择需桌面操作；设置 UI | NOT_RUN | 本轮只验证同工作区重启；A→B→A原生切换/进行中阻断未完成真实验收。 | [UI边界](ui/result.json) |
| SYS-04 | 诊断导出与偏好持久化 | 实际版本/进程状态、缩放/减动效 | 导出内容与预览一致，不泄露密钥；重启恢复偏好 | 真实保存面板；不能仅注入 IPC 返回路径 | PARTIAL | 原生200%缩放及重启读取已测；诊断原生保存/减少动效完整链未测。 | [UI](ui/result.json) |
| DB-01 | 新库创建与所有已存在迁移头升级 | 从仓库历史版本迁移生成的隔离 DB | 单一合法 head；历史记录不丢失；重复升级无副作用 | fresh、pm09/pm10/am01 历史分支及 merge head 都需覆盖 | PARTIAL / FAIL | 空库/重复升级、部分历史迁移库完整性通过；ORM metadata 与真实迁移不一致。 | [后端报告](backend-regression.md)、[迁移](backend/migration.json)、[历史库](backend/legacy-migration-postcheck.json) |
| DB-02 | 提交失败/磁盘空间不足/写权限丢失 | 独立目录与真实 SQLite | 没有部分写入；原操作可查询；报告稳定错误 | 磁盘满只在有界测试卷执行，不填满用户系统盘 | NOT_RUN | 真实磁盘满/写权限失败/提交中断演练未执行；回归测试不能替代本项。 | [后端边界](backend-regression.md) |
| BROW-01 | 内核目录、安装、取消、校验、卸载引用 | 实际 CloakBrowser 内核/缓存 | 完整安装可启动，取消无半成品冒充；引用中的内核不能误删 | `smoke-browser-management*`；下载依赖网络 | PARTIAL | 本机已安装公开内核复制到隔离目录并实际启动；下载、安装取消、真实卸载引用未测。 | [运行链](runtime/runtime-realqa.md) |
| BROW-02 | Profile CRUD、复制、新指纹与保留种子 | 本次创建的实际 Profile | 字段保存一致；复制与重新生成行为正确；默认资源引用删除被阻断 | `smoke-profile-test-browser.mjs` + 正式 UI | PARTIAL | 真实创建Profile并启动浏览器；复制、种子再生成、删除引用UI链未测。 | [运行链](runtime/runtime-realqa.md)、[浏览器UI](ui/global-profiles.json) |
| BROW-03 | 页面打开/输入/点击/iframe/tab/下载/截图 | 真实浏览器，公开网页与本次实际文件清单网页 | DOM 结果和网络行为可核对；产物落盘；取消关闭 owned 浏览器 | 需有效内核/必要 license；仅公共只读网页不写第三方 | PARTIAL | 真实生产浏览器补组1任务/26节点访问/19类型全部成功，覆盖页面等待、真实DOM、标签页/刷新/历史/滚动和screenshot节点产物；输入、点击、iframe、上传下载等仍需补。 | [运行链](runtime/runtime-realqa.md)、[逐节点](nodes/coverage.md) |
| BROW-04 | Cookie/localStorage/login 环境保存与恢复 | 本地真实服务建立的 QA 会话 | 关闭后重开恢复登录状态；独立 Profile 不串 cookie | 不用用户实际登录站点；`test_environment_real_browser_chain.py` | NOT_RUN | 本轮浏览器为新建无账号会话；cookie/localStorage持久保存复用链未执行。 | [运行链边界](runtime/runtime-realqa.md) |
| PROXY-01 | 连接配置、同步目录、HTTP/SOCKS5 健康 | 指定 QA ProxyPanel 账户与真实代理 | IP/协议/健康来自真实出口；错误凭据稳定报错；密钥不落日志 | 当前无指定测试账户则 BLOCKED | BLOCKED | 未指定本轮QA ProxyPanel账号/真实代理；UI空态与契约回归不代替代理实网。 | [代理UI](ui/global-proxies.json) |
| PROXY-02 | 工作流内换 IP/地点、并发控制与取消 | 同一 QA 代理、真实浏览器会话 | 原浏览器状态保留；出口真实变化；unknown 不盲重发；占用互斥 | 会改变远端状态；需用户指定 QA 代理和授权 | BLOCKED | 未指定允许切换的QA代理；未执行远端换IP/地点。 | [逐节点未测项](nodes/coverage.md) |
| MODEL-01 | 供应商接入/模型目录/无效 key | 指定测试供应商及系统 Keychain/Credential Manager | 无效 key 不覆盖有效凭据；目录真实；删除与清理一致 | `verify-openrouter-live.py`；不扫描现有用户秘密 | BLOCKED | 未指定真实测试供应商凭据；不读取用户现有Keychain秘密充当授权。 | [模型UI](ui/global-models.json)、[节点边界](node-realqa.md) |
| MODEL-02 | AI 文本/结构化/视觉/工具调用 | 指定模型，用实际文件清单/截图作为输入 | 收到实际供应商响应；耗时/费用/模型名有凭据外证据；取消/限流 | `test_studio_project_model_live.py` 默认跳过；需明确预算与模型 | BLOCKED | 无本轮指定模型/调用预算；没有用本地固定响应冒充AI结果。 | [节点边界](node-realqa.md) |
| DATA-01 | 项目/表/字段/状态/记录 CRUD | 实际仓库文件清单（含中文/空格/Unicode 路径） | typed recordKey、版本、查询和详情一致；状态历史可追溯 | 正式 UI + 真实 API/SQLite；已有 smoke-project-data | PARTIAL | 真实源文件元数据建立项目/表/字段/记录、UI读写/详情、重启保留通过；全状态与删除分支未全测。 | [UI](ui/result.json)、[运行链](runtime/runtime-realqa.md) |
| DATA-02 | 两个窗口编辑冲突、丢失响应原键恢复 | 同一 QA 记录和真实并发请求 | 不覆盖他人修改；原命令返回同一事实；刷新可恢复 | 注入真实连接丢失，不改业务返回 | PARTIAL | 真实原Idempotency-Key重放无重复；旧contentRevision返回409；两窗口与HTTP响应丢失未实测。 | [运行链](runtime/runtime-realqa.md) |
| DATA-03 | 字段变更/删除预检、批状态、关联保护 | 已引用记录、有效/失效字段、多条状态 | 影响数量准确，原子提交；部分结果可定位；活动 lease 阻断破坏写 | `qa-project-alignment-r3.mjs` 中仅取真实边界 | PARTIAL | 字段创建、状态/字段UI读取及lease最终释放有证据；全变更/删除预检/部分失败回收未全测。 | [UI](ui/result.json)、[资源清理](runtime/run-hn1fvbhq/post-run-integrity.json) |
| DATA-04 | Excel 新建/替换/导出与中文/日期/公式 | 从真实文件清单实际生成 XLSX、实际导出文件 | 往返数据/类型一致；公式不被意外执行；取消不发布；替换换代 | 原生文件面板另测；旧 excel smoke 注入面板不能算全链 | PARTIAL | 真实打包App原生保存/打开、5行Excel导出导入逐值核对与SQLite完整性通过；错误类型映射被正确拒绝且未发布，但UI丢失行列定位信息（N-04）；替换/取消/日期公式未全测。 | [原生导出](ui/native-export.json)、[原生导入](ui/native-import.json)、[节点文件链](node-realqa.md) |
| DATA-05 | 大表筛选/排序/翻页/导出 | 1k/10k/100k 条实际采集文件/运行事实，附来源 | P50/P95、内存、UI 响应/取消；结果无遗漏/重复 | 性能预算先记录实测，不虚构通用阈值 | PARTIAL | 1k/8504真实文件记录、86批写入、158查询、43页完整比对通过；10万行/UI/RSS/并发未测。 | [性能](performance.md) |
| AUTO-01 | 自动化四页签保存、资源继承与覆盖 | 正式 Studio 保存的工作流、真实项目资源 | 配置保存、结构校验、运行准入分别可见；资源冲突可定位 | `qa-automation-management-pm3.mjs` | PARTIAL | 真实工作流/自动化API配置、资源验证、批次启动通过；四页签全部UI草稿交互未测。 | [运行链](runtime/runtime-realqa.md) |
| AUTO-02 | 参数批次/多表领取/同记录并发竞争 | 真实数据与生产 worker | 同时只被合法 Task 领取；Input snapshot 不变；停止不再领取 | PM4 fake 脚本不能作为结果；必须另跑生产链 | PARTIAL | 生产worker真实领取2条记录并全部释放，输入快照持久；多表竞争/全部lease写入边界未测。 | [运行链](runtime/runtime-realqa.md) |
| AUTO-03 | 项目完整闭环：取数→浏览器→业务写回 | 真实文件 URL/标题/哈希→网页→项目记录/状态 | 观察到同一 recordRef 的 DB 持久变更，lease 与幂等正确 | 当前 capability 桥缺口 A-01；未实现应 FAIL/NOT_IMPLEMENTED | NOT_IMPLEMENTED | 输入快照尚未接到执行变量/受限项目能力，显式业务写回缺失；运行内存表不是项目表。 | [架构A-01](architecture-coverage.md)、[运行链R1](runtime/runtime-realqa.md) |
| AUTO-04 | End 保留环境、后续记录复用 | 本地 QA 登录会话与真实项目记录 | 先确认浏览器关闭，再保存/关联环境，再 Run 终态 | 当前 PM9 R3 接入未完成；管理端 end API 不能替代节点闭环 | NOT_IMPLEMENTED | 环境管理API存在；生产图End→关闭确认→保留/关联的批准桥未接通。 | [架构A-01](architecture-coverage.md) |
| AUTO-05 | 人工接管、超时、重启后从检查点继续 | 含已完成副作用的真实流程 | 恢复不重做已执行步骤；旧命令/代次被拒；unknown 不消失 | 普通输入弹窗不能替代持久 checkpoint | NOT_IMPLEMENTED | 普通输入交互不等于项目持久人工检查点；批准的业务恢复桥未接通。 | [架构A-01](architecture-coverage.md) |
| AUTO-06 | 普通停止→宽限→强停 | 本次 owned worker 的真实阻塞/停止 | UI 状态与持久事实一致、迟到事件无效、无 orphan | `qa-project-management-pm3.mjs` 真浏览器路径 | PARTIAL | 普通停止、后继不执行和资源清理已真实通过；30秒宽限后强停未测。 | [运行链](runtime/runtime-realqa.md) |
| AUTO-07 | 失败后续/重跑、归档/恢复/安全删除 | 已真实运行并产生证据的项目 | 历史不篡改；失败后续来源准确；活动资源阻断删除 | PM8 fake 场景仅补充逻辑回归 | NOT_RUN | 未用本次真实运行产物演练失败后续/归档/恢复/安全删除全链。 | [运行链未验范围](runtime/runtime-realqa.md) |
| STU-01 | 正式保存/重开/版本冲突/离开保护 | 从 UI 建立真实工作流文档 | 同一服务读取一致；不会静默丢草稿；同命令可恢复 | `smoke-studio-project-documents.mjs`；不运行旧 smoke:studio 当生产证明 | PARTIAL | 正式Studio原生拖入JS节点/编辑/保存/Run→真实worker→持久结果独立比对通过；保存冲突/脏草稿恢复未完成。 | [原生JS完整链](ui/native-js-result.json)、[运行链](runtime/runtime-realqa.md) |
| STU-02 | 条件、循环、分组、嵌套与错误分支 | 实际采集文件按扩展名/大小分组和统计 | 路径/循环次数/结果与独立算法核对；无限循环可取消 | `b3-control-flow`、`b4-*`，需逐脚本核对边界 | PARTIAL / FAIL | 真实foreach/condition/loop/continue/break及三类子流程通过；CSV表头、Python空格参数、非法SHA各有真实缺陷。 | [节点报告](node-realqa.md)、[结果](nodes/results.json) |
| STU-03 | 调试：断点/单步/变量/断线重连 | 同一真实工作流与运行 | 只暂停目标运行；重复命令幂等；断线后结果补读 | 正式 Studio/worker；不能直接 Store 改状态 | NOT_RUN | 本轮未完整执行正式UI断点/单步/变量编辑/断线恢复。 | [节点覆盖](nodes/coverage.md) |
| STU-04 | 全部前端入口/216 唯一批准类型逐一建图与准入 | 当前目录自动枚举，不采用旧入口数量 | 每入口记录 nodeType→executor→平台→实际证据；无虚假可用 | 入口数与唯一类型数不同口径；需要覆盖账本逐项核销 | PARTIAL / FAIL | 217生产类型逐项登记；节点脚本129执行类型，加原生JS与独立19类型浏览器补组后取并集149执行类型/2结构类型；3节点已知失败，66批准类型仍未执行，118节点脚本场景基数不变；必填字段账本缺3代理类型。 | [节点覆盖](nodes/coverage.md)、[原生JS](ui/native-js-result.json)、[真实浏览器补组](runtime/browser-nodes-realqa.md)、[后端报告](backend-regression.md) |
| STU-05 | 录制、选取器、回放与失效元素 | 实际浏览器 DOM、页面变化 | 选取与实际对象一致；录制停止释放监听；失效明确失败 | `b2-picker`、`b7-recording`；真实浏览器 | NOT_RUN | 未完成正式选取/录制/回放链；浏览器实际运行不能替代录制器验收。 | [节点覆盖](nodes/coverage.md) |
| STU-06 | HTTP/API/webhook/file/element/schedule 触发 | 本次本地真实请求、文件变化和 DOM 变化 | 触发去重/等待/取消/重启事实准确；并发互不串消息 | `b6-*`/`p2-schedules`；应用关闭期间行为需单列 | PARTIAL | 真实公网API/API轮询、文件创建、短定时/wait及正式sidecar Webhook→worker→持久结果通过；持久cron、element变化、重启补偿等未全测。 | [节点报告](node-realqa.md) |
| EXT-01 | SMTP/IMAP、Telegram、SSH、网络共享 | 用户指定 QA 收件箱/聊天/主机/共享目录 | 实际远端收件/文件/回执可独立确认，取消/超时可追溯 | 现有 Telegram/mail 脚本重定向到本地服务，不能冒称供应商实网 | PARTIAL / FAIL | 共享文件/目录真实HTTP下载、哈希和stop_share回收通过；安全探针另复现越界读/写及预览500；SMTP/Telegram/SSH真实远端未测。 | [安全报告](security-audit.md)、[节点边界](node-realqa.md) |
| EXT-02 | OCR/图像/音频/视频/视觉动作 | 实际截图、真实录音/本地文档 | 真实模型权重加载、可核验输出、失败无 orphan | 摄像头/麦克风/下载权重/TCC 权限；没有条件则 BLOCKED | PARTIAL | 历史实际应用截图EasyOCR真实权重识别通过；无脸负样本通过；真人/音频/视频/摄像头未测。 | [节点报告](node-realqa.md) |
| EXT-03 | 打印/桌面鼠标键盘/剪贴板/屏幕 | QA 文档、隔离窗口和指定打印设备 | 原生权限/错误提示/取消/资源释放 | 不能把平台 API mock 当实机；避免影响用户其它窗口 | NOT_RUN | 未操作用户全局剪贴板/键鼠/打印机；原生输入、声音等没有假造PASS。 | [节点未测清单](nodes/coverage.md) |
| AND-01 | 平台诊断、镜像/模板与设备准备 | 真实 Lima/ReDroid/Binder/ADB/scrcpy | 真实能力与 UI 一致，缺依赖说明准确 | 本机命令存在不代表 VM 已就绪；仅 Mac arm64 实现 | PARTIAL / FAIL | 生产诊断available=true但启动两次失败；诊断未发现VM缺少docker0，基础依赖可用不等于设备可启动。 | [环境探测](android-environment.json)、[真实设备报告](android/android-realqa.md) |
| AND-02 | 设备创建/启动/停止/重启/独立数据 | 两台专属 QA 设备和实际设备内文件 | 生命周期幂等、两实例数据隔离、删除仅清理自有数据 | 不能直接跑旧 smoke 的 retired workflow 后半段 | PARTIALLY_FAILED_ENVIRONMENT | 两次真实create/幂等/recover/delete及自有卷清理通过，原有6容器与卷不变；start均因VM缺docker0失败。 | [Android实测](android/android-realqa.md)、[诊断重现](android/run-8d7ylddm/results.json) |
| AND-03 | 原生手动控制/截图/旋转/断线 | QA 设备实际 Android 设置应用 | 坐标和帧版本正确；控制权互斥；关闭窗口与结束会话区别准确 | 不登录用户账户，不安装来源不明 APK | BLOCKED_START_FAILED | 设备未进入running，PNG截图、原生手动控制、旋转、正常stop未执行；不以创建或清理成功代替。 | [Android实际边界](android/android-realqa.md) |
| AND-04 | 工作流分配/接管可用性 | 当前正式 API/详情页面 | 当前应明确不可用；UI 不得声称已经可以运行 | 现有明确 409；界面误导为 A-04 | FAIL | 真实UI仍宣传按工作流分配，生产allocate/start固定409不可用。 | [Android页面](ui/global-android.json)、[架构A-04](architecture-coverage.md) |
| SEC-01 | token、Origin、host-only IPC、路径穿越 | 专属临时目录和测试 token | 未授权请求拒绝；文件能力不得越出本次授权/选择范围或绕过 host-only 取密边界 | 安全审计子报告；合法文件/命令节点按其授权能力验收 | PARTIAL / FAIL | 真实共享符号链接越界读写、双工作区同名凭据串扰已复现；主窗口导航动态影响待验。 | [安全报告](security-audit.md) |
| SEC-02 | 危险文件/超大输入/重复命令/敏感日志 | QA 自有 XLSX/zip/路径/无效 DTO | 输入预算与错误稳定；无逃逸/数据丢失/秘密明文 | 安全子报告；文件真实解析 | PARTIAL / FAIL | 实际../产物路径拒绝和共享路径探针已做；静态GET/重名上传漏保护；全文件格式/DoS未测。 | [安全报告](security-audit.md)、[节点报告](node-realqa.md) |
| OBS-01 | 1,000 logs/min、长时循环、事件补读 | 真实生产 worker 产生实际事件 | 日志顺序/分页正确；重连不漏；RSS/磁盘增长可界定 | 建议不少于 30 分钟观测；不能只返回固定 mock 日志 | NOT_RUN | 未执行1000logs/min及30分钟以上RSS/磁盘增长测量；短时日志导出通过不替代负载。 | [节点日志范围](node-realqa.md) |
| UX-01 | 键盘全流程、焦点、200% 缩放 | 正式所有模块主要页面和 modal | 焦点可达/可见；错误被宣读；提交/取消不遮挡；滚动可用 | 实际 CUA /原生窗口；组件单测补充 | PARTIAL | 真实模块导航、表/项目页签、200%缩放、原生文件面板与Studio编辑/运行通过；键盘/焦点/屏幕阅读器全流程未测。 | [UI](ui/result.json)、[原生JS](ui/native-js-result.json)、[原生文件](ui/native-import.json) |
| REL-01 | macOS arm64 源码与打包同版 | 同一 commit 构建产物和临时 userData | 安装启动、迁移、业务闭环、崩溃恢复、退出全部复验 | 本机可做；现有产物若旧版本不能代表 HEAD | PARTIAL | 同版本frozen后端、包内sidecar、packaged Electron健康/回收、原生Excel和正式JS单节点通过；其它冻结节点/安装升级未全测。 | [打包实测](frontend-regression.md)、[打包原生Excel](ui/native-import.json)、[打包JS](ui/native-js-result.json) |
| REL-02 | macOS Intel / Windows x64 | 对应真实 OS/架构 | 同 REL-01，另测系统凭据/路径/进程树/原生面板 | 本机不具备；CI artifact 不代替手装/硬件/账号 | BLOCKED | 当前宿主仅macOS arm64；本轮未取得Windows x64/macOS Intel实机同版证据。 | [平台边界](architecture-coverage.md) |
| REL-03 | 签名/公证/升级/卸载/回滚 | 发布候选安装包、旧版 QA 工作区 | OS 信任链通过、升级保留数据、失败可恢复、卸载行为明确 | 需正式签名与目标 OS；无证据不能宣称可发行 | NOT_RUN | 未执行正式签名、公证、安装升级、卸载、回滚验收。 | [发行边界](architecture-coverage.md) |

## 补充依赖公告扫描

后端已安装环境与 frozen 生产 lock 分别完成真实公开数据库查询：当前环境 187 个 distribution（本项目 editable 包跳过，186 个实际查询），生产跨平台闭包 196 个固定包版本（34 直接、162 传递）。两个扫描均命中相同的 2 个去重公告，涉及生产直接依赖 Paramiko 与 setuptools；原始工具重复公告未重复计数。版本命中与实际应用可利用性分开记录，未修改 lock 或环境。见 [后端依赖扫描](dependency-backend.md)。这不代替 SEC-01/SEC-02 的应用安全边界测试，也不覆盖原生二进制/镜像/最终安装包的完整 SBOM。

## 现有 QA 入口的替代边界

| 入口/家族 | 已核对的边界 | 本轮用途 |
|---|---|---|
| `npm test`、后端 `pytest`、`test:scripts` | 单元/组件/契约/真实 DB/平台逻辑混合；很多外部依赖被替代，真浏览器可 skip | 全量回归补充；不能单独满足真实系统验收 |
| `smoke-project-management.mjs` / `smoke-project-management-desktop.mjs` | 主入口禁止 AUTOFLOW_QA_* 等注入；使用生产装配 | 可用作生产管理链，仍需明确是否实际执行完整业务图 |
| `qa-project-management-pm3.mjs` | 真实浏览器/运行管理；专属 QA 工作区 | 可用；资源准备与本机内核先核对 |
| `qa-project-management-pm4.mjs` | 明确 fake executor | 不作为本轮真实执行证据 |
| `qa-project-management-pm5.mjs` | 默认 pm5_sidecar；删除真实批次 scheduler startup，Run 保持 queued；手动浏览器是真的 | 只证明管理/手动环境链；整脚本结果不能说生产执行交接通过 |
| `qa-project-management-pm6.mjs` | Fake Sheets/token transport、替代系统凭据 | 仅逻辑回归；Google 实网必须用专用 live 路径 |
| `qa-project-management-pm7.mjs`、`pm8.mjs` | QA sidecar + PM4 fake runner | 不作为真实生产执行闭环证据 |
| `qa-pm5-browser-chain.py` | 真实浏览器，内核 catalog stub | 浏览器环境行为证据；不是全资源 UI→执行链 |
| `qa-pm6-google-live.mjs` | Google Sheets 真 REST、系统凭据、真实 UI；文件选择入口有 QA config，单条写入走 API | 真 Google 集成证据；原生选择与全 UI 编辑另测；要求 config/spreadsheet/sheet/gid/label |
| `smoke-pm2-excel.mjs`、`smoke-pm2-detail-flows.mjs` | 默认注入 open/save 面板结果，之后实际 IPC/文件/HTTP/SQLite | 文件链部分证据；使用 native mode/原生操作者补全面板 |
| `smoke-pm2-native-picker.mjs` | 真实原生面板；注释明确不覆盖完整 save 发布 | 原生选择/取消证据，不能单独说完整 Excel E2E |
| `smoke-studio-window.mjs` | 仍断言无真实 workflows API 和 Mock 标识 | 过期入口，先修/归档 |
| `smoke-studio-backend-b1/b2/b3/b4/b7` | 有实际 Electron/sidecar/worker/browser/本地文件链；逐脚本仍须核对受控网站与资源准备 | 可选为正式 UI/本地集成证据，不冒充外网验收 |
| `smoke-model-management.mjs`、`smoke-studio-project-ai-task.mjs` | 本地 HTTP 模型替代服务器；后者 `18–26` 行直接返回“项目默认/覆盖模型响应” | 模型选择、UI 和请求协议回归；不是真实模型能力验收 |
| `smoke-studio-backend-b5-ai-tasks.mjs`、`b5-assistant.mjs`、`b5-scraper-firecrawl.mjs` | `startModel` / `startAssistantModel` 创建本地固定响应模型；分别见 `252`、`213`、`118` 行；scraper 页面也为本地 fixture | 真实 worker/UI 不等于真实 AI；必须用实际模型调用补齐；Firecrawl 命名也不证明商业云服务调用 |
| `smoke-studio-backend-b5-recognition.mjs` | 真实识别/浏览器，输入是脚本产生或准备的图像和本地验证码页面 | 保留识别回归价值；用户本轮要求真实数据，需补实际截图/文档输入 |
| `smoke-studio-backend-b6-telegram.mjs:36` | `sitecustomize` 把 `api.telegram.org:443` 重定向到本地 TLS 服务器 | 协议回归；**不是真 Telegram** |
| `smoke-studio-backend-b6-mail.mjs:35` | `sitecustomize` 把 `smtp.qq.com:465` 重定向到本地 SMTP | 协议回归；**不是真 QQ 邮箱发送** |
| `smoke-android-management.py`、`smoke-android-handoff.py` | 实际设备脚本，但包含已退役 android_manual/运行接口，前者还可选择停止指定旧参考容器 | 不能无审查整套运行；仅本次自有设备，不使用 pause-reference-container |
| `verify-openrouter-live.py` | 实网模型与系统凭据；需指定有效测试 key | 具备凭据/预算才执行，不把缺 key 转为 fake PASS |

## 如何完成“所有测试”的可审查交付

本轮应把所有**已有可运行回归**与所有**本机具备真实依赖的生产链**执行完，逐项保留失败；不能用“全量单元测试通过”覆盖平台/账号/硬件缺口。矩阵按以下状态结算：

- PASS：本轮同版本真实运行达到该行标准，附证据。
- FAIL：实际运行或明确生产契约表现违反标准，附复现。
- NOT_IMPLEMENTED：当前业务桥/执行能力确实缺失；不能记 skip 后忽略。
- BLOCKED：缺明确测试账号/目标、设备、平台或签名条件，附具体前提。BLOCKED_START_FAILED 表示本轮真实启动失败导致后继无法执行。
- PARTIALLY_FAILED_ENVIRONMENT：部分真实步骤通过、关键步骤因已诊断环境故障失败；不能记整体 PASS，也不凭环境故障推定业务代码有同一根因。
- NOT_RUN：已设计但本轮尚未执行，说明原因与下一动作。

关闭整个验收需要：所有 P0/P1 缺陷有修复与同场景复测；所有矩阵行有结果；所有 216 唯一节点类型及前端入口映射有清楚平台/实际证据或不可用声明；三平台安装验收与真实外部服务矩阵完成。实际环境未满足这些条件前，不能宣布“系统所有测试均已通过”。

## 脚本索引（文件枚举，不是执行结果）

本次枚举 74 个 QA / smoke / OpenRouter live 入口；下表列出每个入口。标有“需复核”的文件只完成名称/源码信号盘点，尚不能主张整条真实性已审核。

| 脚本 | 准入分类 |
|---|---|
| `qa-automation-management-pm3.mjs` | 正式业务/桌面场景候选；注入与依赖需逐项复核 |
| `qa-pm5-browser-chain.py` | 真浏览器；kernel lookup stub |
| `qa-pm6-google-live.mjs` | 真 Google；指定账号/远端 QA 表前提 |
| `qa-project-alignment-r1.mjs` | 正式业务/桌面场景候选；注入与依赖需逐项复核 |
| `qa-project-alignment-r2.mjs` | 正式业务/桌面场景候选；注入与依赖需逐项复核 |
| `qa-project-alignment-r3.mjs` | 正式业务/桌面场景候选；注入与依赖需逐项复核 |
| `qa-project-management-pm3.mjs` | 正式业务/桌面场景候选；注入与依赖需逐项复核 |
| `qa-project-management-pm4.mjs` | fake executor，仅管理回归 |
| `qa-project-management-pm5.mjs` | 真实手动浏览器；停用生产调度 |
| `qa-project-management-pm6.mjs` | Fake Sheets/token/凭据存储 |
| `qa-project-management-pm7.mjs` | fake executor，仅管理回归 |
| `qa-project-management-pm8.mjs` | fake executor，仅管理回归 |
| `qa-project-uuid-flow.mjs` | 正式业务/桌面场景候选；注入与依赖需逐项复核 |
| `qa-project-uuid-leaks.mjs` | 正式业务/桌面场景候选；注入与依赖需逐项复核 |
| `qa-radius-system.mjs` | 视觉/控件巡检；不证明生产业务闭环 |
| `qa-record-external-link.mjs` | 正式业务/桌面场景候选；注入与依赖需逐项复核 |
| `qa-record-grid-entry.mjs` | 正式业务/桌面场景候选；注入与依赖需逐项复核 |
| `qa-record-grid-files.mjs` | 正式业务/桌面场景候选；注入与依赖需逐项复核 |
| `qa-table-system.mjs` | 视觉/控件巡检；不证明生产业务闭环 |
| `smoke-android-handoff.py` | 真实设备但含退役运行合同，禁止整套盲跑 |
| `smoke-android-management.py` | 真实设备但含退役运行合同，禁止整套盲跑 |
| `smoke-browser-management-desktop.mjs` | 正式业务/桌面场景候选；注入与依赖需逐项复核 |
| `smoke-browser-management.mjs` | 正式业务/桌面场景候选；注入与依赖需逐项复核 |
| `smoke-desktop.mjs` | 正式业务/桌面场景候选；注入与依赖需逐项复核 |
| `smoke-gallery-r3-batch-partial.mjs` | 正式业务/桌面场景候选；注入与依赖需逐项复核 |
| `smoke-model-management.mjs` | 本地模型替代；不满足真实 AI |
| `smoke-pm2-detail-flows.mjs` | 默认注入原生面板结果；native mode 单列 |
| `smoke-pm2-excel.mjs` | 默认注入原生面板结果；native mode 单列 |
| `smoke-pm2-native-picker.mjs` | 原生文件面板；需要桌面操作者 |
| `smoke-profile-test-browser.mjs` | 正式业务/桌面场景候选；注入与依赖需逐项复核 |
| `smoke-project-data.mjs` | 正式业务/桌面场景候选；注入与依赖需逐项复核 |
| `smoke-project-management-desktop.mjs` | 生产装配、禁止 QA 注入；需本轮运行 |
| `smoke-project-management.mjs` | 生产装配、禁止 QA 注入；需本轮运行 |
| `smoke-sidecar.mjs` | 正式业务/桌面场景候选；注入与依赖需逐项复核 |
| `smoke-studio-backend-b1.mjs` | 生产 Studio 场景候选；本地 fixture/平台/依赖需逐项复核 |
| `smoke-studio-backend-b2-advanced-browser.mjs` | 生产 Studio 场景候选；本地 fixture/平台/依赖需逐项复核 |
| `smoke-studio-backend-b2-network-monitor.mjs` | 生产 Studio 场景候选；本地 fixture/平台/依赖需逐项复核 |
| `smoke-studio-backend-b2-page-load.mjs` | 生产 Studio 场景候选；本地 fixture/平台/依赖需逐项复核 |
| `smoke-studio-backend-b2-picker.mjs` | 生产 Studio 场景候选；本地 fixture/平台/依赖需逐项复核 |
| `smoke-studio-backend-b2-remaining-browser.mjs` | 生产 Studio 场景候选；本地 fixture/平台/依赖需逐项复核 |
| `smoke-studio-backend-b2-web-basic.mjs` | 生产 Studio 场景候选；本地 fixture/平台/依赖需逐项复核 |
| `smoke-studio-backend-b3-control-flow.mjs` | 生产 Studio 场景候选；本地 fixture/平台/依赖需逐项复核 |
| `smoke-studio-backend-b4-advanced-data.mjs` | 生产 Studio 场景候选；本地 fixture/平台/依赖需逐项复核 |
| `smoke-studio-backend-b4-data-structure.mjs` | 生产 Studio 场景候选；本地 fixture/平台/依赖需逐项复核 |
| `smoke-studio-backend-b4-math-statistics.mjs` | 生产 Studio 场景候选；本地 fixture/平台/依赖需逐项复核 |
| `smoke-studio-backend-b4-table.mjs` | 生产 Studio 场景候选；本地 fixture/平台/依赖需逐项复核 |
| `smoke-studio-backend-b4-utility-tools.mjs` | 生产 Studio 场景候选；本地 fixture/平台/依赖需逐项复核 |
| `smoke-studio-backend-b5-ai-tasks.mjs` | 本地模型替代；不满足真实 AI |
| `smoke-studio-backend-b5-assistant.mjs` | 本地模型替代；不满足真实 AI |
| `smoke-studio-backend-b5-recognition.mjs` | 识别真实 runtime + 准备图像；需真实输入补测 |
| `smoke-studio-backend-b5-scraper-firecrawl.mjs` | 本地模型替代；不满足真实 AI |
| `smoke-studio-backend-b6-allure.mjs` | 生产 Studio 场景候选；本地 fixture/平台/依赖需逐项复核 |
| `smoke-studio-backend-b6-api-trigger.mjs` | 生产 Studio 场景候选；本地 fixture/平台/依赖需逐项复核 |
| `smoke-studio-backend-b6-command-log.mjs` | 生产 Studio 场景候选；本地 fixture/平台/依赖需逐项复核 |
| `smoke-studio-backend-b6-desktop-platform.mjs` | 生产 Studio 场景候选；本地 fixture/平台/依赖需逐项复核 |
| `smoke-studio-backend-b6-element-change.mjs` | 生产 Studio 场景候选；本地 fixture/平台/依赖需逐项复核 |
| `smoke-studio-backend-b6-file-watcher.mjs` | 生产 Studio 场景候选；本地 fixture/平台/依赖需逐项复核 |
| `smoke-studio-backend-b6-http-logs.mjs` | 生产 Studio 场景候选；本地 fixture/平台/依赖需逐项复核 |
| `smoke-studio-backend-b6-mail.mjs` | 本地协议服务器替代外部供应商 |
| `smoke-studio-backend-b6-network-sharing.mjs` | 生产 Studio 场景候选；本地 fixture/平台/依赖需逐项复核 |
| `smoke-studio-backend-b6-probability.mjs` | 生产 Studio 场景候选；本地 fixture/平台/依赖需逐项复核 |
| `smoke-studio-backend-b6-scheduled-task.mjs` | 生产 Studio 场景候选；本地 fixture/平台/依赖需逐项复核 |
| `smoke-studio-backend-b6-scripts.mjs` | 生产 Studio 场景候选；本地 fixture/平台/依赖需逐项复核 |
| `smoke-studio-backend-b6-ssh.mjs` | 生产 Studio 场景候选；本地 fixture/平台/依赖需逐项复核 |
| `smoke-studio-backend-b6-telegram.mjs` | 本地协议服务器替代外部供应商 |
| `smoke-studio-backend-b6-text-to-speech.mjs` | 生产 Studio 场景候选；本地 fixture/平台/依赖需逐项复核 |
| `smoke-studio-backend-b6-webhook-trigger.mjs` | 生产 Studio 场景候选；本地 fixture/平台/依赖需逐项复核 |
| `smoke-studio-backend-b7-recording.mjs` | 生产 Studio 场景候选；本地 fixture/平台/依赖需逐项复核 |
| `smoke-studio-backend-p1-platform.mjs` | 生产 Studio 场景候选；本地 fixture/平台/依赖需逐项复核 |
| `smoke-studio-backend-p2-schedules.mjs` | 生产 Studio 场景候选；本地 fixture/平台/依赖需逐项复核 |
| `smoke-studio-project-ai-task.mjs` | 本地模型替代；不满足真实 AI |
| `smoke-studio-project-documents.mjs` | 正式业务/桌面场景候选；注入与依赖需逐项复核 |
| `smoke-studio-window.mjs` | 过期 Mock 阶段入口，A-02 |
| `verify-openrouter-live.py` | 真 OpenRouter；指定账号/预算前提 |
