# 安卓模拟器管理完善规格说明书

- 日期：2026-09-19
- 版本：1.0
- 状态：active implementation baseline（2026-09-22 用户已授权 AM1–AM4 实施；本文件仍不表示真实设备验收已经通过）。
- 仓库：`1127152834/auto-flow`
- 代码基线：`codex/architecture-baseline@5f07e2adadfd273c6483065d43272aeaf7ed74f0`
- 文档分支：`codex/android-management-spec-20260919`
- 配套文件：[实施计划](../plans/2026-09-19-android-emulator-management.md)、[范围决定](../../../.ai/decisions/2026-09-19-android-management-scope.md)
- 原文档编写阶段授权边界：仅编写并提交文档；当前执行阶段已由用户另行授权在隔离 worktree 实施 AM1–AM4。仍不接入退役工作流、不覆盖主工作区改动、不自动合并默认分支。

## 0. 当前执行基线校准（2026-09-22）

本规格最初以 `codex/architecture-baseline@5f07e2adadfd273c6483065d43272aeaf7ed74f0` 编写。实施时以当前仓库 HEAD `a92f0688f206d4339ff4468c1871f3ccdd6816dc` 和隔离分支 `codex/android-management-complete` 为准；主工作区未提交改动不纳入本任务。当前 Alembic 唯一 head 为 `0019_recording_commands`，因此 AM1 增量迁移必须从该 head 继续，原文中 `pm07_environments` 只作为历史基线记录。规格中的功能边界不变：保留现有 Mac/Lima/ReDroid 和安全护栏，不恢复退役工作流执行链；真实设备、网络、账号条件不足时记录 `blocked`。

## 1. 目标与交付方式

把现有安卓模块完善为无需工作流即可独立使用的本机模拟器管理器。用户能够检查环境、选择镜像和模板、创建独立实例、手动操作、管理应用、停止后保留数据、重新打开，并在异常时诊断和恢复。

采用渐进式改造，不替换当前运行时，不另建执行引擎。完整产品分为四个有独立验收门槛的批次：

| 批次 | 交付范围 | 退出条件 |
| --- | --- | --- |
| AM1 基础管理稳定版 | 管理界面收敛、只读环境诊断、统一状态、持久操作、控制会话、数据保留 | 一台真实实例完成正常链和中断恢复链；不依赖 Studio |
| AM2 镜像与模板版 | 兼容镜像登记/拉取、不可变版本、模板、谷歌组件验证记录 | 基础镜像和一个候选自定义镜像分别验证；未通过者不标记可用 |
| AM3 多实例效率版 | 批量操作、容量等待、聚合状态、按需预览、应用管理增强 | 多实例不串控制、不超额分配；批次逐项结果可追踪 |
| AM4 数据与维护版 | 本机停机备份、恢复为新实例、保留数据管理、安全清理、诊断导出 | 恢复演练通过；失败不破坏源数据；清理范围可核实 |

GApps 可行性验证在 AM1 稳定链打通后提前开展，不必等 AM2 全部界面完成；正式镜像管理及验证状态在 AM2 交付。每批验收后停止，继续下一批需要明确实施授权。未通过谷歌兼容性验证不阻塞基础管理交付，但不得宣称谷歌能力已完成。

### 1.1 方案取舍

选择“保留底层安全机制、重整管理契约与界面”。只修改外观不能解决会话和状态问题；整体换用其他平台会扩大迁移、数据和平台风险。当前阶段不引入官方 AVD、Cuttlefish、远程设备服务器或多租户管理。

### 1.2 全局约束

以下约束在实施计划中逐条沿用：

- GC-01：本轮运行平台仅 Apple Silicon macOS + 现有 Lima/ReDroid；其他平台明确提示不支持，不影响主应用启动。
- GC-02：Python 保持 >=3.11,<3.12；Node.js 使用 >=22.12 的 22.x；依赖遵循现有锁文件，不因本模块整体升级。
- GC-03：前端保留 React/TypeScript、TanStack Query、共享 shadcn/Radix/Tailwind；后端保留 FastAPI/Pydantic、SQLAlchemy/Alembic。
- GC-04：保留顶部全局导航与暖灰/黏土棕主题，不新增全局侧栏，不建立第二套基础控件或 contracts 包。
- GC-05：后端使用 apps/backend/src/autoflow；前端使用 apps/desktop/src/renderer/domains/android；OpenAPI 类型仍生成到 renderer/shared/api/generated.ts。
- GC-06：本轮不实现工作流执行、自动分配、人工接管工作流、自动回收或旧 Studio 运行时复活；保留历史数据与兼容拒绝边界。
- GC-07：所有改变设备、数据、镜像或运行环境的操作必须显式授权；检查和列表读取不得隐式创建、启动、修复或删除资源。
- GC-08：保留归属校验、独占控制、generation/sequence 栅栏、幂等请求和结果未知保护；不得以清空状态或自动重放解决冲突。
- GC-09：仅采用增量迁移，不修改既有迁移字节、不重建用户数据库；每批保持一个迁移 head。
- GC-10：ADB 与 sidecar 仅监听回环地址，前端不直接执行进程、访问数据库或拼接任意宿主机路径。
- GC-11：不上传账号、输入文本、设备数据、APK、镜像或原始日志到仓库；诊断导出默认脱敏并排除应用数据与屏幕截图。
- GC-12：每个批次同时交付契约、实现、界面、测试与验证记录；mock 测试通过不等于真实设备通过。

## 2. 基线事实与待验证风险

本节仅表示对固定提交的静态阅读。代码路径均相对仓库根目录；此前真实设备验证不自动继承为本轮证据。

| 基线事实 | 证据路径/符号 | 本轮处理 |
| --- | --- | --- |
| 首页按可分配/工作流占用/启动与停止分组 | `apps/desktop/src/renderer/domains/android/components/ResourceBoard.tsx`，`group` | AM1 改为实例卡片/列表，不以工作流组织首页 |
| 页面轮询分配和所有设备的工作流历史 | `apps/desktop/src/renderer/domains/android/pages/AndroidPage.tsx`，`useQueries` | AM1 停止非当前范围查询 |
| 输入序号属于控制台组件，会话属于父页面 | `apps/desktop/src/renderer/domains/android/components/DeviceConsole.tsx`，`sequence`；`AndroidPage.tsx`，`open` | 增加返回重进回归；不能把推导风险写成已实机复现 |
| 当前只发现固定 Android 13 ARM64 镜像 | `apps/backend/src/autoflow/providers/android/management.py`，`IMAGE`/`images` | AM2 独立镜像目录，固定具体 imageId |
| 创建默认三台，可选临时实例；预览系统文字固定 | `CreateInstances.tsx`；`adapters/http/android_fleet_schemas.py`，`BatchCreate` | 新 UI 默认一台持久实例；系统信息从镜像记录读取 |
| 生命周期有持久状态、操作回执和失败隔离 | `application/android/management.py` | 延续并建立可查询的独立操作历史 |
| 已校验容器/卷归属，删除可保留卷 | `providers/android/management.py`，`verify`/`manage` | 不降级；增加保留数据入口和恢复证据 |
| 控制会话按 generation/sequence 拒绝过期输入 | `application/android/console.py`，`_check`/`command` | 作为不可破坏的回归约束 |
| 当前工作流边界明确拒绝执行/接管 | `bootstrap/android.py`，`CurrentAndroidRunBoundary` | 不改为假成功；本轮 UI 不调用 |
| 当前迁移图测试期望 head=pm07_environments | `apps/backend/tests/integration/test_migration_heads.py` | 新迁移基于该 head；基线改变时重新审计父节点 |

范围依据还包括 `AGENTS.md`、`.ai/README.md`、`.ai/memory/project-context.md`、`.ai/decisions/2026-09-17-valid-branch-integration.md`、`docs/PROJECT_STRUCTURE.md` 和 `docs/architecture/README.md`。旧四屏原型约束仅在与本次管理优先方向不冲突时保留；不改写历史批准记录。

## 3. 领域概念与数据所有权

### 3.1 四类核心资源

| 资源 | 必要事实 | 约束 |
| --- | --- | --- |
| 运行环境 Runtime | 平台、工具、虚拟机、Binder、容器服务、资源预算、检查时间 | 所有实例共用；检查与修改分离 |
| 系统镜像 Image | imageId、来源、源摘要、架构、Android 版本、组件声明、验证记录 | imageId 是本地不可变镜像身份；源 manifest digest 单独保存，二者不得混淆 |
| 设备模板 Template | id、revision、name、imageId、CPU/内存/分辨率/DPI/语言/时区 | 存为 profile 资源，保留当前 /profiles API 命名；UI 称“设备模板” |
| 设备实例 Device | deviceId、创建时配置快照、容器/卷归属、观察状态、占用、最近操作 | 模板后续变化不能改写实例；运行系统和数据属于该实例 |

实例 revision 在配置、占用及管理写入时递增；被动状态观察不递增，以免批次预检不断失效。

AM1/AM2 的已有实例配置除名称外只读。修改 CPU、内存、分辨率、语言、时区或镜像时，明确引导“按新配置创建实例”，不暗中重建容器或迁移原数据。在线调参和原地跨系统升级不在本规格内。

### 3.2 新增管理对象

- `Operation`：持久化管理操作，有稳定 ID、目标、请求摘要、步骤、结果与恢复建议。
- `ControlSession`：当前控制会话。输入权仍由既有设备 claim/锁与 generation 机制裁决，不创建平行的第二套控制仲裁器。
- `ImageVerification`：某镜像、某运行环境、某测试范围、某时刻的结果；不等同认证证书。
- `Backup`：同机停机数据备份；记录具体镜像和配置，恢复产生新实例而不覆盖源实例。

`owner` 是已有设备占用事实的展示投影，不是另一个可独立修改的 owner 数据源。新手动会话写入明确的 `ownerKind=manualSession` 及会话 ID；旧 `ownerRunId` 继续作为兼容投影。无法解释的历史占用标为 `unknown` 并隔离核实，不能凭“查不到工作流”清空占用。

## 4. 功能需求

### AM-R01 范围与导航（AM1）

模块标题统一“安卓设备”；副标题“管理本机安卓实例、应用与数据”。主操作为“创建实例”及运行实例的“打开设备”。隐藏工作流分配、等待任务、接管工作流、自动回收相关入口，并停止其查询。历史临时实例不删除、不转换数据；显示“历史临时实例，本版本不会自动清理”。新创建只允许 persistent，后端对新的 temporary 请求返回 `ANDROID_TEMPORARY_DISABLED`，同编号的历史已接收请求仍返回原记录。

保留现有 Android 路由与主应用离开守卫，不能改变项目、浏览器、代理或 Studio 的全局行为。升级后的安卓页面不调用工作流 API；兼容工作流接口仍返回明确不可用错误。

### AM-R02 运行环境诊断（AM1）

检查项固定为 platform、adb、lima、ssh、scrcpy、vm、docker、binder、images、capacity、disk。每项返回 `pass|fail|unknown|unsupported`、稳定错误码、简明说明、检查时间和建议动作。未采集的数据为 null/unknown，不用 0 冒充。

AM1 提供重新检测、查看经审核的安装/启动步骤、复制固定诊断命令。自动安装工具、自动重启共享 VM 不在 AM1–AM4 范围。不能把当前准备脚本直接绑定到“检查”：该脚本含设备创建路径。

镜像缺失可以阻止新建，但不能把仍能使用的已有设备控制能力一并判定不可用。保留旧 environment.available 兼容字段，新增按动作区分的 capability 及原因。

### AM-R03 统一状态与可用操作（AM1）

运行状态 `runtimeState`：`stopped|starting|ready|retained|missing|unknown`。
控制投影 `owner.kind`：`none|manualSession|legacyWorkflow|unknown`。
管理状态由最近非终结 Operation 决定，不挤进 runtimeState。

展示优先级为“待核实/危险错误 > 活跃管理操作 > 控制状态 > 运行状态”。已失效的观察不得显示绿色“已就绪”。允许动作由后端 `allowedActions` 和 `blockedReasons` 返回，前端仅格式化；后端执行时再次验证。

| 条件 | 主操作 | 禁止或附加条件 |
| --- | --- | --- |
| stopped 且无占用 | 启动设备 | 镜像、卷和环境必须可核实 |
| ready 且无占用 | 打开设备 | 查看详情/缩略图不申请控制 |
| ready 且本应用手动控制 | 返回控制台/独立窗口 | 停止前显式结束控制 |
| 活跃 Operation | 查看进度 | 不接受同设备冲突写操作 |
| retained | 恢复实例 | 原镜像和原数据卷必须存在 |
| missing | 查看诊断 | 不以空白数据冒充恢复 |
| unknown 或 recovery_required | 检查状态 | 未核实前不开放普通管理/输入操作 |

### AM-R04 持久操作与结果未知（AM1）

生命周期动作沿用 `start|stop|restart|delete|recover`，创建沿用持久 batch。新增 Operation 为统一查询读模型，不改变旧 HTTP 返回资源的语义。

每个写请求以工作区身份、动作、目标和 requestId 构成幂等边界；规范化请求摘要不同而 ID 相同必须 409。先原子保存意图，再执行外部操作，最终观察成功后才能写 succeeded。HTTP 202 仅表示已接收。超时、失去响应、sidecar 中断后，标记结果未知并核实，不自动重放。

操作状态：`queued|running|waiting_capacity|succeeded|failed|cancelled|needs_verification`。重试是新的 attempt，关联原操作，不能覆盖原失败证据。未知结果不能使用新 ID 强行重试。AM1 生命周期全局并发维持 1；同设备所有破坏性操作始终互斥。

完整操作日志默认保留 90 天；非终结记录永不自动清除。历史记录归档后仍保留 requestId+请求摘要+最终结果的紧凑回执，不能因为达到现有回执数量上限让设备永久不可操作。删除设备时保留操作墓碑，不允许复用旧 deviceId。

### AM-R05 手动会话与窗口语义（AM1）

会话控制器按 `(workspaceIdentity, backendInstanceId, deviceId, sessionId, generation)` 隔离；维护输入序号和队列，组件仅订阅。不会把旧队列发送到新设备、新工作区或新后端。

打开嵌入式控制台必须显式申请控制。离开嵌入式控制台时停止接收新输入、释放按键/触控、核实结束会话，但不停止 Android。结束失败时展示仍占用/待核实，允许留在页面或显式离开后从列表处理，不能显示已释放。

用户显式打开的原生窗口可在列表页继续运行；列表标记归属并提供结束入口。原生窗口存活由服务端按进程身份核实，不能因前端未轮询就关闭正常窗口；原生进程关闭后由服务端释放控制，Android 继续运行。每台设备最多一个可写控制端，原生/嵌入式切换先释放旧端、递增代次、再启用新端。

HTTP GET 读取会话不再承担续租。嵌入式会话采用单独心跳：每 5 秒一次，30 秒失联触发回收尝试；此为控制会话规则而非停止设备规则。回收未确认继续隔离。应用关闭、工作区切换与 sidecar 退出复用现有关闭协调，不靠 React unmount 的异步回调保证清理。

输入序号只在确认新会话时初始化；旧代次、重复序号必须拒绝。视频断开只允许重连画面/重新核实控制，不重放触控。支持点击、拖动、长按、返回、主页、最近任务、旋转、音量和显式文本发送；中文输入需实测，不能以键盘事件存在作为已支持依据。

### AM-R06 数据保留、移除与恢复（AM1）

停止保留容器和卷。`deleteData=false` 移除容器但保留卷，界面名称为“移除实例，保留数据”；`deleteData=true` 为“永久删除实例及数据”，确认框显示实例名称和范围。

保留数据记录继续出现在“保留的数据”筛选中。恢复复用原卷、原镜像与配置；归属不符、卷缺失、镜像缺失均明确失败，不新建空卷补位。已有未知状态先执行 recover 核实；recover 不承诺自动修好，不重启其他设备。

删除前预检与实际执行均校验工作区、deviceId、容器标签、卷标签和挂载关系。取消只影响尚未开始的动作，已发生的删除不可宣称已撤销。

### AM-R07 创建与管理界面（AM1）

首页采用卡片网格/实例列表，默认卡片，保留用户视图偏好。摘要为总数、运行中、已停止、需处理；筛选后同时显示匹配数/总数，避免计数口径混淆。搜索名称；筛选状态、模板、保留数据；名称搜索只在当前工作区。

创建继续使用独立页面，默认数量 1、persistent、创建后启动；批量数量折叠。保留当前宽高/DPI/CPU/内存合法范围和偶数宽高校验。GET /profiles 不再隐式保存默认模板；无模板时提供显式“创建标准模板”动作，通过既有 PUT /profiles/{id}、revision=0 保存已核实镜像的配置。模板初始化完成前不能用空配置提交；切换模板后的默认值与用户覆盖值明确区分。

复制配置只复制镜像与参数，不复制应用数据、账号、Android 身份或会话。详情展示实际配置快照，不随模板编辑改变。空态分别处理首次使用、筛选无结果、加载中、服务断开和错误；服务断开保留旧数据并标记陈旧。

页面使用共享 Button、Dialog、Select、Table 等控件；局部样式只负责布局。1280×800 和 1440×900 窗口、长名称、键盘访问、200% 缩放需验证；状态不能仅靠颜色识别。无设备时不保留固定高度的三列空框。

### AM-R08 系统镜像管理（AM2）

支持两条入口：登记本地已有 Docker 镜像；从明确允许的 registry/仓库引用拉取。首先只支持当前 provider 兼容的 Linux ARM64 ReDroid 镜像，不支持任意 ROM/刷机 ZIP。

展示引用、imageId、sourceDigest、架构、Android 版本、磁盘信息、声明的组件和验证状态。tag 仅作来源说明；实例创建绑定解析后的 imageId。拉取同名新 tag 产生新镜像版本，不覆盖旧实例绑定。内容校验失败、架构不符或无可信版本资料时不得自动标为兼容。

自定义镜像运行前说明当前运行时使用特权容器的信任边界；用户确认来源后才可创建专用验证实例。仅检查元数据不得启动镜像。没有可用 sourceDigest 的本地镜像仍可登记，但必须保存本地 imageId 和来源类型，不能伪造 registry digest。

镜像移除区分取消登记与删除本机镜像内容；被任何未永久删除的实例、保留卷、有效模板或备份引用时阻止删除内容。不得调用全局 image prune 或 volume prune。私有仓库登录管理、本地 tar 镜像导入和图形化编译系统不在本轮范围。

### AM-R09 模板与实例配置快照（AM2）

支持模板新增、编辑、复制、归档；归档后不可用于新建，已有实例仍显示历史快照。保留 /profiles 路径和 revision 乐观并发检查。

默认标准模板参数为 720×1280、DPI 320、CPU 配额 1、内存 1536 MiB、zh-CN、Asia/Shanghai；镜像须为已验证候选，不固定文字冒充探测结果。宽 320–1920、高 320–2560、DPI 120–640、CPU 1–8、内存 768–8192 MiB；CPU/内存还须满足环境预算，数量 1–20。

既有实例迁移为配置快照时保留原 imageId 和数据卷身份。无法查证的系统版本显示“未核实”，不得填默认 13 作为事实。

### AM-R10 谷歌组件验证（AM2，可提前探测）

采用“基础镜像 + 一个候选谷歌组件镜像”的小范围验证，不在产品内加入一键执行外部 GApps 脚本。谷歌组件的专有性质、许可和完整性限制见第 13 节；不提供伪造认证或绕过完整性判断功能。

组件状态与验证结果分开：`googleComponents=absent|declared|detected|unknown`；`validation=not_tested|passed|failed|blocked`。系统中检测到相关包，只能表示 detected。

验证记录必须绑定 imageId、运行环境版本、Android/API/ABI、谷歌包版本、应用包名及版本、验证项、时间、结果、脱敏证据与限制。人工登录使用用户明确提供的测试账号，仅在专用新实例中操作；不把账号或登录后数据制成镜像/公共模板。

验收项为首次启动、商店打开、测试账号登录、选择的免费测试应用下载/启动、停机重启、第二台独立实例数据隔离。账号/网络/目标应用条件未提供时记录 blocked 和具体原因，不能把未测试写成通过。镜像验证通过不代表所有实例或所有依赖完整性检查的应用通过；组件发生更新后保留旧记录并标记需要复验。

### AM-R11 批量操作（AM3）

支持批量创建、启动、停止、移除保留数据、永久删除；单批 1–20 项，不接受空目标或重复 deviceId。批次冻结 deviceId 列表、动作、每项预期 revision、确认范围和 requestId，不按后来变化的筛选重新计算目标。

批次状态 `queued|running|succeeded|partially_failed|failed|cancelled`；每项关联 Operation。部分失败不覆盖成功结果；取消仅停止尚未准入项，已执行项持续报告。重试失败项使用新 attempt 并重新预检；结果未知项只可核实。

AM3 初始生命周期并发仍为 1，批量首先提供排队与可观察性，不承诺同时启动所有设备。单设备互斥和环境容量预留具备独立证据后，另行批准提升并发。

### AM-R12 资源预算与聚合观察（AM3）

CPU 是配额，不承诺独占核心；每台配置不超过环境核心上限。内存准入按运行容器限额、已准入待启动实例预留、新请求和 512 MiB 环境保留量计算；未知外部占用必须显示未知并阻止超额准入，不能当 0。

磁盘同时显示宿主工作区与 Linux VM 可用量，不能混为一个数。创建、拉取和备份分别预检所需空间；无法估计时要求人工确认或返回明确阻塞，不虚构可运行台数。

列表读取不再逐台同步做昂贵环境探测。后台观察器生成快照；活跃设备及活跃操作目标每 3 秒观察，停止设备每 15 秒，故障退避至最多 30 秒。快照带 observedAt；活跃设备超过 10 秒、停止设备超过 45 秒未核实则陈旧。HTTP 读取不执行隐式修复。

前台列表每 3 秒取聚合快照；页面隐藏时暂停展示轮询，不能顺带停止必要会话心跳。历史仅详情按需分页。预览只对可见且 ready 的卡片启用，每卡不快于 5 秒，最多 2 个并发，取消后禁止旧响应覆盖新实例。

### AM-R13 应用管理（AM1基础、AM3增强）

AM1 保留已有 APK 安装与应用启动，补安装后结果核实、中文输入及错误反馈；AM3 增加应用列表搜索、版本/包名/系统应用区分、停止应用、卸载用户应用、清除应用数据。后两者必须确认，系统/保护包不得作为普通可卸载项。

写操作需要当前人工控制权；查看应用信息不应隐式申请控制。APK 上限保持 256 MiB；校验实际读取字节、ZIP/Manifest 可识别性及包元数据。上传过程中增量计算内容摘要，与 requestId/目标/动作绑定，已接收的同编号请求不能替换文件内容。文件进入受控临时区，限制并发和大小，执行后清理；文件名不是宿主路径。split APK、APKS/XAPK 安装不在本版，提示不支持。

不得仅因 HTTP 传输结束而显示安装成功；观察包版本/安装结果。结果未知不自动重新安装或重复启动。应用输入内容、账号、APK 字节不进入操作审计。

### AM-R14 本机停机备份（AM4）

首版仅同机管理的备份，不提供跨设备完整克隆承诺。备份前要求明确停止实例并核实无控制会话、无运行容器和无冲突操作；不能对运行中的 /data 直接打包称为一致性备份。

备份记录包含 backupId、源 deviceId、imageId、配置快照、格式版本 1、文件摘要、字节数、时间和结果。数据写入权限受限的临时目录，完成并校验后原子发布；失败/取消不出现可恢复的成功项。

备份目录由工作区路径服务分配；不从 HTTP 接受任意路径。备份可能包含登录和应用私密数据，创建时提示；不自动上传，不加入 Git。宿主文件权限 0600/目录 0700 作为本机保护，不宣称备份已加密。

### AM-R15 恢复为新实例（AM4）

仅恢复当前应用创建、摘要有效、格式受支持且 exact imageId 可用的备份；恢复始终创建新 deviceId、容器和卷，重新生成 AutoFlow 资源归属，清空历史操作/进程/控制租约。原设备、原备份不修改。

数据读写必须保留恢复所需 UID/GID、mode 和经验证支持的扩展属性。解包前验证路径与类型，拒绝越界路径、设备文件、跨根链接和通过链接穿越写入；若无法安全保存目标系统需要的元数据，返回明确不支持，不静默丢失。

新实例可启动且应用测试数据可读后才判定演练通过。应用私有密钥、DRM、系统身份和账号登录是否可继续有效不作保证；界面称“恢复应用数据”，不称“完整克隆手机”。本轮不支持第三方备份导入、跨镜像版本恢复或外部导出打包。

### AM-R16 数据清理与诊断（AM4）

数据入口显示保留卷、备份和本模块生成的临时文件。清理先预览对象 ID、用途、引用、大小和不可逆影响，再显式确认；执行时再次核实 revision 和归属。无标签或其他工作区资源只报告，不删除。禁止全局 prune、递归删除任意外部路径。

诊断包默认只含应用版本、脱敏环境检查、设备/操作状态、错误码和时间；原始 logcat、截图和应用数据默认排除。高级日志需单次单独同意、限制时间窗口和体积；凭据、输入文本、系统用户名/路径等脱敏后才导出。导出仅保存到受限 Electron 文件能力批准的位置，不自动发送。

### AM-R17 迁移与兼容（各批）

AM1 新增独立操作表，保留 android_devices 和 android_resources 既有记录。AM2/AM4 新资源优先扩展现有资源仓储并加 typed 验证，只有索引/约束确需新增时增加迁移。

历史 active 操作导入为 needs_verification，已删除记录保持墓碑，未知镜像和占用不猜测。AM1 的新迁移建议 revision `am01_management_operations`，基线父节点为 `pm07_environments`。若实施时上游前进，先核对实际 head 后更新新迁移父节点及本文，不修改已发布迁移。

旧 API shape 保持；新增字段为可选兼容字段或独立 /management 资源。旧 temporary 请求、ownerRunId 和不可用工作流端点行为按本规格兼容处理。回退采用关闭新入口及向前修复；生产环境不得用破坏性 downgrade 回退数据。

### AM-R18 验收与可观察性（各批）

验证记录分开列出静态检查、单元/契约、临时数据库集成、mock UI、真实 Electron、真实 ReDroid、谷歌网络条件。每项有命令、环境、提交、时间、结果和未覆盖项。

日志记录操作 ID、目标 ID、阶段和安全错误码，不记录原始输入与私密数据。不得为了测试通过删除旧安全回归；旧原型视觉断言与新方向冲突时更新断言并注明原因。

## 5. API 与状态契约

本节全部是目标契约，不声称基线已有这些新增接口。HTTP 字段 camelCase；Python 内部 snake_case。继续使用共享 ApiModel/错误封装，避免单独发明传输协议。

### 5.1 通用结构

`ActionPolicy = {allowedActions: string[], blockedReasons: Record<string,string>}`。

`ManagementDevice = {deviceId, revision, name, runtimeState, owner:{kind,id}, observedAt, stale, specSnapshot, latestOperation, allowedActions, blockedReasons}`。容器 ID、卷路径和 SSH 配置不进入普通 UI DTO。

`OperationRead = {operationId, requestId, targetId, action, state, stageCode, stageLabel, attempt, retryOf, createdAt, startedAt, finishedAt, resultCode, message, allowedActions}`。

`Page<T> = {items:T[], nextCursor:string|null, total:number}`；排序为 createdAt、ID 的稳定组合，limit 默认 50、最大 200。结果未知返回资源的 needs_verification 状态；准入校验错误使用现有错误响应格式。

### 5.2 接口矩阵

所有路径以前缀 `/api/v1/android` 开始。

| 接口 | 批次 | 请求/返回关键内容 |
| --- | --- | --- |
| GET /management/capabilities | AM1 | 管理、控制、镜像、批量、备份能力及禁用原因；workflow=false |
| GET /management/environment | AM1 | 返回只读检查快照及各检查项；不触发安装/创建 |
| POST /management/environment/checks | AM1 | requestId；返回检查操作，明确只读，结果写环境快照 |
| GET /management/devices | AM1 | query/status/profileId/retained/cursor/limit；返回 Page<ManagementDevice> |
| GET /management/operations | AM1 | deviceId/cursor/limit；Page<OperationRead> |
| GET /management/operations/by-request/{requestId} | AM1 | 同工作区按原请求编号核实；静态路由注册在 /{id} 前，未知编号 404 不等于副作用必定未发生 |
| GET /management/operations/{id} | AM1 | 一个操作的状态，找不到返回 404 |
| POST /management/operations/{id}/verify | AM1 | requestId；只核实，不重放旧写操作 |
| POST /devices/{id}/operations | 保留/AM1 | 现有 requestId/action/deleteData；202 仍返回 AndroidDeviceRead，增加 operationId 关联 |
| POST /batches | 保留/AM1 | 现有批量创建；默认 quantity=1，新请求只接受 persistent |
| POST /sessions | 保留/AM1 | 现有会话创建；增加可选 clientSessionId 用于续租方绑定 |
| POST /sessions/{id}/heartbeat | AM1 | clientSessionId/generation；只续当前匹配的嵌入式会话 |
| POST /sessions/{id}/actions | 保留/AM1 | 原 end/native/embedded；takeover/resume 保持不可用边界 |
| GET /management/images | AM2 | Page<ImageRead>，包含引用保护与验证结果 |
| POST /management/images | AM2 | requestId/localReference；只登记元数据，不启动 |
| POST /management/image-pulls | AM2 | requestId/reference；返回 OperationRead；限定允许来源 |
| DELETE /management/images/{id} | AM2 | requestId/expectedRevision/deleteContent；引用冲突返回 409 |
| GET/PUT /profiles/{id} | AM2 | 新增单项 GET，保留已有 PUT/revision；模板读写不修改实例 |
| POST /management/profiles/{id}/archive | AM2 | requestId/expectedRevision；软归档，不删除快照 |
| POST /management/images/{id}/verifications | AM2 | 追加逐项验证观察和脱敏证据索引；服务端归并验证状态，不接收任意 passed 开关、账号或截图字节 |
| POST /management/bulk-operations | AM3 | requestId/action/items[{deviceId,expectedRevision}]/deleteData；返回批次 |
| POST /management/bulk-operations/{id}/actions | AM3 | requestId/action=cancelPending或retryFailed；保留逐项结果 |
| GET /management/bulk-operations/{id} | AM3 | 批次与逐项 Operation 引用 |
| GET /devices/{id}/apps | AM3 | 只读包名/版本/系统标记，不隐式 claim |
| POST /sessions/{id}/apps/actions | AM3 | requestId/generation/packageName/action=launch或stop或uninstall或clearData |
| POST /sessions/{id}/apps/install | 保留/AM3 | multipart file + generation + requestId；既有路径，字节限额不变 |
| GET/POST /management/backups | AM4 | 查询备份；创建用 requestId/deviceId/expectedRevision |
| POST /management/backups/{id}/restore | AM4 | requestId/newName；新实例和恢复 Operation |
| POST /management/cleanup/previews | AM4 | resourceIds/types；返回签名/摘要绑定的候选快照 |
| POST /management/cleanup | AM4 | requestId/previewId/confirmationDigest；再次核实归属 |
| POST /management/diagnostics | AM4 | requestId/deviceIds/includeAdvancedLogs=false；返回安全导出资源 ID |

AM2–AM4 未交付的路由不注册或明确 unavailable；capabilities 必须与实际注册能力一致。表中的新增 DTO、操作和测试由实施计划定义，不提前放空 API 假装功能存在。

### 5.3 错误分类

沿用已有 ANDROID_* 错误码；新增至少：`ANDROID_TEMPORARY_DISABLED`、`ANDROID_OBSERVATION_STALE`、`ANDROID_IMAGE_IN_USE`、`ANDROID_IMAGE_UNTRUSTED`、`ANDROID_BACKUP_INCOMPATIBLE`、`ANDROID_CLEANUP_CHANGED`。

422 表示输入不合法；409 表示占用/版本/引用/能力冲突；410 表示旧会话；413 表示超过上传限额；503 表示运行环境不可访问；504 表示等待超时。504 不能作为“实际操作必定未执行”的证据。

## 6. 架构与模块责任

仍遵循 adapters → application → domain，providers/infrastructure 实现端口，bootstrap 装配。无源码位置变化时不移动文件。

| 位置 | 目标职责 |
| --- | --- |
| domain/android/management_models.py、management_rules.py（新） | typed 状态、操作策略、范围校验；纯规则无 IO |
| application/android/management.py（现有） | 生命周期执行和安全边界；接入持久操作仓储，不另起第二执行路径 |
| application/android/console.py、devices.py（现有） | 会话、占用、清理；减少 UI 读取副作用 |
| application/android/diagnostics.py、observations.py（新） | 环境检查与后台观察；不安装工具、不隐式修复 |
| application/android/images.py、templates.py（新） | 镜像引用、验证记录、模板快照 |
| application/android/bulk.py、backups.py（新） | 批次编排、本机停机备份恢复 |
| infrastructure/database/android_operations.py（新） | 原子意图、幂等摘要、状态转移与历史分页 |
| providers/android/image_catalog.py、backup_storage.py（新） | 镜像检查/拉取、卷备份/恢复；所有命令限定参数 |
| adapters/http/android_management.py、android_management_schemas.py（新） | 管理 API 和新增 DTO；保留现有 android.py/android_fleet.py 路由 |
| renderer/domains/android/management-api.ts（新） | 仅使用生成 DTO 的请求封装 |
| renderer/domains/android/hooks/、state/（新） | 查询、操作跟踪、会话控制器和状态映射 |
| renderer/domains/android/components/、pages/（现有） | 领域组件和页面组合，不承担控制租约或底层进程管理 |

新目录只在首个实际消费者任务中创建。AM1 不提前建 AM4 的空服务。分离 domain/android/ports.py 中旧工作流特定类型时保留既有 import 的兼容导出，并由旧边界测试验证，不改动工作流实现。

## 7. 持久化、恢复与并发

新增 android_management_operations 表至少包含 operation_id 主键、workspace_identity、request_id、target_id、action、request_digest、state、attempt、retry_of、payload、created_at、updated_at；唯一约束 `(workspace_identity,request_id)`。设备变更与操作投影须在同一事务保存，避免“操作成功但设备仍旧状态”。

新操作表是操作日志的唯一写入来源；旧 device.operation 仅由同一服务投影。不新增独立的 claim owner 表；设备存量占用仍通过原仓储原子判定及文件锁保护。

启动恢复顺序：初始化数据库 → 核对 runtime/工作区身份 → 恢复操作记录 → 核实受管进程与设备 → 发布可观察快照 → 开放新管理操作。未知进程不按 PID 单独终止，沿用进程出生标识和资源标签核实。

AM1 同设备管理/控制冲突直接拒绝；AM3 批次在未准入状态等待。应用退出不强行停止所有 Android，不删除数据；仅回收 AutoFlow 自己的控制端、隧道和未完成作业，确认失败记录待核实。

## 8. 测试与验收矩阵

所有“通过”均需实施后的证据。下表是验收要求，不是本次测试结果。

| 验收 ID | 场景与预期 | 关联需求 |
| --- | --- | --- |
| AM-AC01 | 安卓首页不请求 workflows、allocations、device runs；其他模块导航正常 | R01/R07 |
| AM-AC02 | 检查环境缺失/超时/不支持时无创建、启动、安装、删除命令 | R02 |
| AM-AC03 | stop/delete/recover 显示对应操作，unknown 不显示已停止/已就绪 | R03 |
| AM-AC04 | 同 ID 同请求只有一次副作用；不同请求 409；90 天归档后回执仍拒绝重放 | R04 |
| AM-AC05 | 打开→输入→返回→再打开仍可输入；旧队列不串新会话 | R05 |
| AM-AC06 | 切换原生/页面只有一个写端；原生窗口仍开时不因 UI 离开被回收 | R05 |
| AM-AC07 | 旧 generation、重复 sequence、跨工作区 heartbeat 被拒绝 | R05 |
| AM-AC08 | 停止/重启后测试数据仍在；保留卷可恢复；缺卷不创建空白替代 | R06 |
| AM-AC09 | 删除任一实例不影响另一实例及外部卷；过程中失联进入待核实 | R04/R06 |
| AM-AC10 | 初次打开默认创建一台；模板异步加载、长名称、空态与断线均可用 | R07 |
| AM-AC11 | 相同 tag 更新不改变已有 imageId；被卷/模板/备份引用时拒绝删除镜像 | R08/R09 |
| AM-AC12 | 模板 revision 冲突拒绝；已有实例配置与数据不改变 | R09 |
| AM-AC13 | 谷歌组件检测不自动写验证通过；blocked 结果显示原因 | R10 |
| AM-AC14 | 专用镜像完整完成启动/登录/下载/重启/隔离，或明确记录失败，不冒充认证 | R10 |
| AM-AC15 | 批次部分失败、取消未开始项、重试失败项分别保持正确结果 | R11 |
| AM-AC16 | 资源预留期间新启动不会超额准入；未知占用不算 0 | R12 |
| AM-AC17 | 列表读取无逐台同步 inspect；隐藏卡片无预览请求；陈旧快照可辨识 | R12 |
| AM-AC18 | APK 过大/损坏/安装响应丢失有明确结果；卸载/清数据需要确认和控制权 | R13 |
| AM-AC19 | 运行中禁止备份；磁盘不足/取消不发布成功备份 | R14 |
| AM-AC20 | 备份恢复新 ID，数据可读；损坏包、不同 imageId、越界条目均拒绝 | R15 |
| AM-AC21 | 清理预览后引用/归属变化时 409，不删除外部资源 | R16 |
| AM-AC22 | 诊断默认不含账号、输入、原始 logcat、截图或数据；不自动上传 | R16 |
| AM-AC23 | 新库/旧库增量迁移、外键、单 head、旧迁移摘要和业务模块回归通过 | R17 |
| AM-AC24 | 真机/网络/平台未测项单列；mock 与真实证据分开；每批独立报告 | R18 |

真实设备基础链：创建测试实例 → 安装测试应用并写入数据 → 输入与截图 → 返回/再次进入 → 切原生/切回 → 停止/启动 → 重启 AutoFlow → 核对数据 → 中断一个受控操作并恢复。删除测试只使用本轮创建且标签匹配的测试资源。

性能验收使用实测记录而不是推定通过：AM3 在同一环境记录 1/5/10 台设备下聚合 API 延迟、后台探测次数、预览并发、前台交互延迟和内存变化；硬件不足的规模记录 blocked。确定性门槛为列表 API 不执行 runtime.inspect、预览并发不超过 2、不可见卡片无刷新、显示延迟符合快照陈旧规则。

## 9. 发布和回退

每个批次独立分支/提交，变更包含后端、生成类型、前端及测试；合并前核对基线和迁移 head。先用隔离工作区及新建测试设备验收，不直接拿用户原数据做破坏性演练。

AM1 保留原镜像和卷；AM2 新镜像用新实例验证，不原地升级旧设备；AM4 恢复到新资源。回退时停用新入口并保留新表/记录，采用向前补丁；禁止丢弃数据库、删除未知卷或篡改历史 migration。

## 10. 明确不做事项

工作流/自动回收、Windows/Intel Mac 运行时、远程服务器、多租户权限、设备群控输入、ADB 公网暴露、代理池集成、Play Integrity 绕过、全功能 ROM 编译器、任意镜像/脚本执行、在线热备份、跨版本数据迁移、第三方备份导入、账号批量复制，不属于 AM1–AM4。

录屏中心、完整文件管理器、任意 Shell 终端及运行环境一键安装另行立项。新需求不能以“顺便完善”为由混入当前批次。

## 11. 与实施计划的关系

实施计划 T01–T20 覆盖 AM-R01–AM-R18。T01–T07 交付 AM1；T08–T12 交付 AM2；T13–T16 交付 AM3；T17–T20 交付 AM4。T11 是独立可行性与证据任务，在 T07 后可以提前执行；任何 GApps 网络测试仍需单独运行授权和测试账号条件。

详细设计中新增的 DTO、模块和迁移均为 proposed。实施前先评审本规格和计划；本次“编写文档”的授权不等于允许后续代理自动执行全部批次。

## 12. 文档完成标准

本次文档交付需满足：规格/计划/范围记录互相可定位；需求和验收可映射到任务；新增路径与已有路径明确区分；示例字段一致；没有以空占位代替关键决定；远端新分支可读；对比基线只有文档变更。文档检查不替代业务测试。

## 13. 参考依据

仓库事实以本文件固定提交为准。外部资料核对日期为 2026-09-19；实施时固定实际引用版本并再次核实。

1. [ReDroid 官方说明](https://github.com/remote-android/redroid-doc)：支持 Linux 容器实例、自定义构建及谷歌组件集成方向，并明确警告不能把 ADB 暴露公网。本规格不直接照搬示例的公网端口或执行远程 shell 脚本。
2. [Google Mobile Services](https://www.android.com/gms/)：GMS 不属于 AOSP，供应和分发需要独立许可安排；开源管理软件不代表镜像内组件全部开源。正式分发前需单独审查。
3. [Play Integrity verdicts](https://developer.android.com/google/play/integrity/verdicts)：设备、应用与账号有独立判断；安装谷歌组件不等于通过完整性验证。本规格不承诺认证或全应用兼容。
4. 项目技术/命令依据：`package.json`、`apps/desktop/package.json`、`apps/backend/pyproject.toml`、`README.md`；安全和迁移依据见第 2 节。
