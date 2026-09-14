# 审查证据摘录

- 日期：2026-09-12。状态：confirmed（来源文本核验），不表示历史能力在新系统已实现。
- L 后数字是原文件行号。旧源码从固定 Git 提交读取；主目录文档属于审查时 working-tree 资料，可能由其他任务继续更新。
- 只摘录与审查论点相关段落，完整路径、摘要见 [review-manifest.json](review-manifest.json)；裁定见 [汇总审查](README.md)。

## legacy-product

- 路径：`/Users/zhangtiancheng/Documents/projects/browser-automation/.ai/01-Project-Management/Product-Definition-and-Information-Architecture.md`
- 来源：324748abe7095f085b4ffb9467be9cb5c8851a5c
- SHA-256：`bbaafa8c21a4beb709f1320c82196df6e6a203cb27b71966a787a425f1ddddd0`

```text
L10: 2026-09-09 工作流专项以[最新共识](../06-Workflow-Studio/Consensus.md)为准：大规模复用、暖色双视图、仅 Web 流水线，暂不做版本管理/工作流仓库、状态机、Android 和桌面自动化。下述完整项目能力为长期目标；当前 W0 只落文档，既有六面板及资源归属不变。
L11:
L12: ## 1. Project Definition
L13:
L14: 一个项目代表围绕同一业务和同一组业务数据展开的一系列资源、工作流和运行记录。项目不是文件夹，也不是单个工作流的包装。
L15:
L16: 例如一个账号业务项目可以同时包含注册、申请卡、找回、换绑邮箱、领取卡等工作流；这些工作流共享人员表、邮箱表、账号表等数据表，但拥有各自的输入契约和数据领取条件。
L17:
L18: 项目拥有：
L19:
L20: - 工作流定义；运行记录内部固定执行配置快照，不提供版本管理；
L21: - 数据表及其字段规则、来源设置和系统状态；
L22: - 启动批次、任务、节点执行尝试、事件和产物；
L23: - 项目引用的全局代理、环境模板、设备和组件；
L24: - 项目内保存的持久环境；
L25: - 项目级健康状态、运行统计和归档状态。
L26:
```

## legacy-inputs

- 路径：`/Users/zhangtiancheng/Documents/projects/browser-automation/.ai/01-Project-Management/Workflow-Data-and-Execution-Model.md`
- 来源：324748abe7095f085b4ffb9467be9cb5c8851a5c
- SHA-256：`68be3080f42ea4cc43a819b84fbf7e6908975b01bc31a79d3c071db29f90eefa`

```text
L38: 工作流声明多个具名输入。输入分为：
L39:
L40: ### Data input
L41:
L42: - 每个任务领取一个对象；
L43: - 对象只允许一层键值属性，不允许对象嵌套对象；
L44: - 工作流声明必需字段、可选字段、字段类型和输入是否必需；
L45: - 提供的数据可以包含额外字段，但不得缺少必需字段；
L46: - 字段层级必须匹配，例如要求 `account.username` 时，`username` 必须属于 `account` 输入对象，而不是独立输入。
L47:
L48: ### Fixed input
L49:
L50: - 在启动批次时设置；
L51: - 同一批次的所有任务共享；
L52: - 不参与逐条数据领取。
L53:
L54: 系统不存在默认“主数据”。每个工作流根据自己的输入契约验证所有输入。
L55:
L56: ### Instance variables（2026-09-09）
L57:
L58: 项目业务数据持久共享；固定输入来自现有自动化参数及启动覆盖，运行只读；工作流全局变量按执行实例从初值深复制，下一实例重新初始化；节点输出和循环 item/index 按局部作用域管理。变量赋值不自动写项目数据或下一次初值，并发实例不得共享可变副本。编辑期变量功能在 W1.3，真实执行在 W2.1，项目数据领取从 W3.1 起。
…
L65: - 同一物理来源未来可以供不同项目引用，模型、字段与状态目录仍按项目独立维护；物理来源定位、去重及真实读取在M3–M5接入。
L66: - 模型可以先保存空字段结构，再显式保存字段配置。字段类型为字符串、数字、布尔值、日期；不允许对象、数组或嵌套结构。字段UUID在重命名时保持不变，字段名是区分大小写的字面键，不解释为路径。
L67: - M2来源仅保存SQLite/Excel/Google Sheets类型及身份方式的配置意图。选中唯一字段不代表已经验证唯一性；选择`_autoflow_id`不代表已检测或初始化，来源始终明确显示“未接入”。
L68: - 字段、状态和来源配置共同使用模型revision；子资源修改在同一事务检查项目活动状态并推进模型/项目版本与修改时间。归档项目整体只读。
L69:
L70: 2026-08-31用户修订来源规则，详见[M4数据契约](./Milestones/M4-Excel-Import-Contract.md)：
L71:
L72: - 外部SQLite：直接只读，每次刷新反映已提交的增删改；不复制整表。
L73: - Excel：一次导入工作区托管SQLite。导入后与原文件脱离，刷新只读本地；重新导入显式全量替换，新代次状态未设置。
L74: - Google Sheets（M5.1）：Google连接绑定项目，该项目的多个模型共用连接；不同项目独立。本地SQLite是运行主库，云端新增数据定时拉取；人工业务变化即时推送，工作流业务变化五分钟批量强制推送。失败保留本地结果与队列，不冒充云端已成功。
L75: - “实时领取”指领取时检查当前有效数据及系统状态，不代表实时请求每一种原始来源。任务领取后输入固定，不由后续同步或重新导入悄悄改写。
…
L156: 数据采用实时领取和懒领取：批次启动时不创建全部任务，也不认领全部数据。每个空闲并发槽循环执行：
L157:
L158: ```text
L159: 检查批次是否仍允许领取
L160: → 为每个必要数据输入寻找一条满足条件的实时记录
L161: → 原子创建对应数据租约
L162: → 为可选输入领取记录或写入空值
L163: → 创建任务并固定任务输入
L164: → 执行工作流
L165: → 结算状态并释放租约
L166: → 继续领取下一组数据
L167: ```
L168:
L169: 同一个任务需要多个数据输入时，租约获取必须支持全有或全无：任一必要输入领取失败，立即释放本轮已取得的其他租约，不创建半成品任务。
L170:
L171: ### Exhaustion and validation
L172:
L173: - 必要输入没有可领取记录：停止创建新任务；活动任务继续完成。
L174: - 可选输入没有可领取记录：该输入使用空值，任务继续。
L175: - 启动前发现当前必要输入为空：提示用户，再由用户决定是否启动一个会立即结束的批次。
…
L204: - 已失败任务是不可变运行记录，不提供重新运行入口；
L205: - 用户可以在数据面板把相关记录改回某个可领取状态，后续新批次再创建新任务。
```

## legacy-concurrency

- 路径：`/Users/zhangtiancheng/Documents/projects/browser-automation/.ai/01-Project-Management/M9-Run-Presets/Concurrency-Contract.md`
- 来源：324748abe7095f085b4ffb9467be9cb5c8851a5c
- SHA-256：`fae2772486752d6ef3f22af4a4725e2cb012ad5587d686269b65c608498b72f7`

```text
L54: 2. B 仍被占用时，其他任务及其他工作流不得领取 B。
L55: 3. A 的任务确认结束后，空闲容量领取下一条符合条件且未被占用的资料，例如 D。
L56: 4. 另一工作流也匹配这批资料时，仍通过同一个占用判断，而不是各自在内存中过滤后直接开工。
L57:
L58: 以上仅为规则示例，不生成假任务或生产测试按钮。
L59:
L60: **防同时重复与防再次处理分开：**完成后是否还能处理，由业务状态、筛选及未来重试规则决定。释放占用不偷偷修改业务状态，也不承诺“这条资料永远只处理一次”。
L61:
L62: ## 5. 执行层约束（后续专项，尚未实现）
L63:
L64: ### 5.1 排他范围与身份
L65:
L66: - 同一 Workspace 调度范围内统一领取；同工作流并发、不同工作流及不同项目检查同一资料的占用。
L67: - 身份基于经确认的共享物理来源和稳定记录身份，不以工作流、项目、表使用项、页面行号或当前排序作为隔离键。
L68: - 同一真实来源被不同项目引用时，共享排他身份，项目自己的业务状态仍独立。
```

## legacy-environment

- 路径：`/Users/zhangtiancheng/Documents/projects/browser-automation/.ai/01-Project-Management/Environment-and-Manual-Takeover.md`
- 来源：324748abe7095f085b4ffb9467be9cb5c8851a5c
- SHA-256：`8dd3d40502bf3a8886dd63b5fb8f35d38fc66e188f7724b0b46ce83be4908d31`

```text
L14: | 类型 | 所有者 | 默认生命周期 |
L15: |---|---|---|
L16: | 环境模板 | 全局 | 用户长期维护，只作为创建来源 |
L17: | 临时环境 | 任务 | 任务结束后自动删除 |
L18: | 持久环境 | 项目 | 工作流明确保存后长期保留 |
L19: | 等待人工现场 | 任务 | 保留到用户处理或TTL到期 |
L20:
L21: 自动任务不得直接修改环境模板。持久环境再次用于自动化时应作为创建来源，不让多个并发任务直接共享同一个可变实例。
L22:
L23: ## 2. Slot and Task Ownership
L24:
L25: 批次启动使用已有单一运行方案的并发数与资源解析结果。并发槽是内部执行位置，不恢复旧逐槽配置 UI：
L26:
L27: - 代理可以重复指定；
L28: - 环境模板可以重复使用，但每个任务获得独立环境实例；
L29: - 环境模板允许不设置；未指定时继承项目默认模板，但仍为每个任务创建独立临时环境；
L30: - 一个环境实例同一时间只属于一个任务；
L31: - 普通任务完成、失败或被终止后删除临时环境。
L32:
L33: 节点重试等待期间仍占用并发槽和当前环境，这是同一任务的正常执行。等待人工的资源处理不同，见下文。
L34:
L35: ## 3. Saving an Environment
L36:
L37: 工作流可以在结束节点声明“保存当前环境”。任务结束时：
L38:
L39: 1. 停止自动控制但保持环境状态；
L40: 2. 将临时环境转入项目持久环境；
L41: 3. 记录来源任务、运行配置快照、保存时间和结束结果；
L42: 4. 释放数据租约和并发槽。
L43:
L44: 未明确保存时一律清理，不根据成功或失败做隐式保留。
L45:
L46: ## 4. Entering Manual Wait
L47:
L48: 任意业务节点可以进入等待人工状态。进入时：
L49:
L50: - 保留浏览器或设备及当前页面状态；
L51: - 保留任务输入、数据租约和代理；
L52: - 保留节点执行上下文和最近截图；
L53: - 释放执行槽，使批次可以继续处理其他任务；
L54: - 创建项目内等待人工项并启动用户配置的TTL倒计时。
L55:
L56: 等待人工不是新批次，不复制任务，也不把失败任务变成可重跑任务。
```

## legacy-sheets

- 路径：`/Users/zhangtiancheng/Documents/projects/browser-automation/.ai/01-Project-Management/Milestones/M5.1-Sheets-Local-Write-Contract.md`
- 来源：324748abe7095f085b4ffb9467be9cb5c8851a5c
- SHA-256：`6438444d74437e12bbf991c9fb4d27c1cde2c254d4e6cabe13d133ed3881263d`

```text
L44: - Sheets镜像格式3支持记录内容版本、逻辑删除、公式字段保护和云端行位置提示；旧格式保持可读，完成同步升级后开放写入。
L45: - 人工新增、修改、删除统一先提交本地镜像与持久化变化日志，再立即推送Google；15秒内完成返回已同步，超时或失败保留本地结果和可重试队列。
L46: - Google写入使用`spreadsheets.batchUpdate`；新增、修改、删除分别使用追加、单元格更新和行删除请求。修改只触碰实际变化的映射字段，不覆盖未映射列、公式或格式。
L47: - 远端响应不确定时先按唯一字段核验；新增核对完整目标内容，避免重复追加。拉取发布受本地待推送变化保护。
L48: - 归档、Google配置或断开与当前项目的Sheets操作使用项目级生命周期门闩；不同项目凭据与数据隔离，共享同一Spreadsheet时串行执行远端定位和写入。
L49: - 记录列表、独立新增/详情/编辑页面、删除确认、同步记录、失败重试和来源同步摘要已接入；页面不展示记录键、变化标识或凭据。
L50: - 用户可显式放弃未推送变化；本地业务内容继续保留，后续云端拉取仍叠加该本地覆盖，新的本地修改会取代旧覆盖。
L51: - C阶段历史上采用保守拉取保护：存在未完成人工变化时不发布新镜像。该限制在D阶段被版本校验的本地优先合并替代。
L52:
L53: ## M5.1-D 已实现
L54:
L55: - 内部 `apply_record_change` 共用人工与工作流校验、内容版本和恢复机制；正式HTTP仍只接受人工来源，不提供模拟工作流入口。
L56: - 工作流首次待推送锚定五分钟截止时间，后续写入不延后；人工立即推送并带上同一记录尚未发送的工作流字段。已进入即时队列的内容不降级为延迟队列。
L57: - 同一记录未发送变化合并目标值和实际变化字段；删除取代旧变化。已发送或不确定的版本先核验；旧请求只确认其实际发送版本。
L58: - 每轮固定队列快照；立即同步包含未到期变化。运行中再次请求立即同步会合并为一轮后续强制同步，不丢失当前快照之后的变化。
L59: - `v2_0012`登记远端批次、成员目标版本及恢复进度。单包最多200个子请求、约1.5MB；按修改、倒序删除、新增执行，跨包重新定位。公式复制跨包完成后才确认整条记录。
L60: - 不确定响应先读取核验，权限失败停止后续写包并等待恢复，临时失败采用有限重试与持久化退避。推送失败仍可拉取并合并有读取权限的云端新增。
L61: - 新云端唯一值加入本地；已有记录保留本地业务值、内容版本和系统状态，只更新远端定位、公式和来源元信息。云端缺行保留本地并提示；本地删除标记防止旧行复活。
L62: - 发布新镜像前重新校验项目、账号、绑定、结构及本地修订，期间本地变化重新合并；身份含糊或结构变化保留上次完整镜像。
L63: - 多个项目写入同一远端字段时，最后成功推送生效；各项目本地值和系统状态独立，后续拉取不自动把另一项目的远端修改覆盖进来。
L64: - 来源页显示同步阶段、人工与工作流待推送、失败、待核验、云端缺行及时间；同步历史注明操作来源。没有工作流执行引擎或虚构任务。
```

## legacy-identity

- 路径：`/Users/zhangtiancheng/Documents/projects/browser-automation/.ai/01-Project-Management/Milestones/Record-Identity-Contract.md`
- 来源：324748abe7095f085b4ffb9467be9cb5c8851a5c
- SHA-256：`6474dddb347b65f073811bb64f097bc92bc8520832f3af7813d5c7710fccc512`

```text
L30: A已验收；B已接入公共选择器与Sheets系统列初始化/恢复，新增`v2_0013`，实际验收结果见各阶段交付报告。C已实现SQLite一次导入兜底，当前交付与验收范围见[阶段C报告](Record-Identity-C-Delivery.md)；各阶段未关闭的历史验证项继续单列。
L31:
L32: ### B 保护与实现边界
L33:
L34: - 先持久化操作归属与目标UUID，再写入，超时先核验；不重复生成、不覆盖既有标识。
L35: - 同名但归属不明系统列、重复/篡改标识或无法可靠关联的缺失标识必须停止相关发布/写入，保留上次完整数据。
L36: - 多项目复用已验证系统列，各项目状态独立；解绑不删除共享云端列。
L37: - 系统标识独立于业务字段，不显示在业务表格、映射、编辑及同步摘要中；旧绑定不自动升级。
L38: - 初始化使用现有Spreadsheet串行协调、项目归档、版本及未完成队列保护；当前业务表首次初始化通过应用影响确认后执行。
L39:
```

## current-navigation

- 路径：`/Users/zhangtiancheng/Documents/projects/autoflow/apps/desktop/src/renderer/app/ApplicationHeader.tsx`
- 来源：2026-09-12 审查时的工作区文件
- SHA-256：`9db6b42d5f4a2bfa4bc60bd0a93e3fc97b5558d61b56aa4cd7e9bed872ac3c0e`

```text
L3: export type AppRoute = 'dashboard' | 'profiles' | 'proxies' | 'models' | 'settings'
L4: const tabs: { key: AppRoute; label: string }[] = [{ key: 'dashboard', label: '总览' }, { key: 'profiles', label: '浏览器配置' }, { key: 'proxies', label: '代理管理' }, { key: 'models', label: '模型管理' }]
```

## current-settings-language

- 路径：`/Users/zhangtiancheng/Documents/projects/autoflow/apps/desktop/src/renderer/domains/settings/pages/SettingsPage.tsx`
- 来源：2026-09-12 审查时的工作区文件
- SHA-256：`5e34b4f47680ad71c99a493cc0c53e3e9eb78a60f54cf01286a13143b977524b`

```text
L45:   return <main className="min-h-dvh bg-canvas px-4 py-7 text-ink sm:px-6 lg:px-8"><div className="mx-auto w-full max-w-[1050px]"><header><h1 className="m-0 text-3xl font-semibold">设置</h1><p className="mb-0 mt-1 text-muted">管理本机应用与工作区</p></header>{loadError ? <div role="alert" className="mt-4 rounded-control border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">状态更新失败：{loadError}</div> : null}{operationError ? <div role="alert" className="mt-4 flex items-center justify-between gap-3 rounded-control border border-red-200 bg-red-50 p-3 text-sm text-red-800"><span>{operationError}</span><Button className="h-8" onClick={() => setOperationError('')}>关闭</Button></div> : null}{data.workspace.recovery ? <div role="status" className="mt-4 rounded-control border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">{data.workspace.recovery}</div> : null}
L46:     <Tabs value={tab} onValueChange={setTab} className="mt-5"><TabsList className="w-full justify-start gap-5"><TabsTrigger value="general">常规</TabsTrigger><TabsTrigger value="workspace">工作区</TabsTrigger><TabsTrigger value="about">关于</TabsTrigger></TabsList>
…
L50:       <TabsContent value="workspace"><div className="grid gap-5"><SettingsCard icon={FolderOpen} title="当前工作区" description={data.workspace.blocked ? `任务进行中，暂时无法切换：${data.workspace.blockers.join('；')}` : '切换工作区不会搬迁当前数据。'} action={<span className="flex flex-wrap gap-2"><Button onClick={() => void open('workspace')}>打开目录</Button><Button variant="primary" disabled={busy || data.workspace.blocked} onClick={() => void choose('choose')}>切换工作区</Button>{data.workspace.previousPath ? <Button disabled={busy || data.workspace.blocked} onClick={() => void choose('previous')}>切回上一个</Button> : null}</span>}><code className="block overflow-auto rounded-control bg-surface-subtle p-3 text-sm">{data.workspace.path}</code></SettingsCard><SettingsCard icon={Database} title="工作区位置" description="当前工作区内的主要文件与目录。"><div className="divide-y divide-line">{([['database','数据库'],['profiles','浏览器配置'],['kernels','浏览器内核'],['logs','运行日志']] as Array<[SettingsDirectory,string]>).map(([key,label]) => <div key={key} className="grid items-center gap-3 py-3 sm:grid-cols-[9rem_1fr_auto]"><strong>{label}</strong><code className="min-w-0 overflow-hidden text-ellipsis text-xs text-muted">{data.workspace.paths[key]}</code><Button onClick={() => void open(key)}>打开目录</Button></div>)}</div></SettingsCard></div></TabsContent>
L51:       <TabsContent value="about"><div className="grid gap-5"><SettingsCard icon={Info} title="AutoFlow" description="本地浏览器自动化工作台。"><DetailGrid items={[{ label: '应用版本', value: data.runtime.appVersion }, { label: '当前平台', value: `${data.runtime.platform} · ${data.runtime.arch}` }]} /><button type="button" aria-expanded={runtime} onClick={() => setRuntime(!runtime)} className="mt-4 flex items-center gap-1 border-0 bg-transparent p-0 text-sm text-clay">运行环境<CaretDown className={runtime ? 'rotate-180' : ''} /></button>{runtime ? <div className="mt-4"><DetailGrid items={[{label:'桌面运行时',value:`Electron ${data.runtime.electronVersion} · Chrome ${data.runtime.chromeVersion} · Node ${data.runtime.nodeVersion}`},{label:'本地服务',value:data.runtime.backendVersion ? `${data.runtime.backendVersion} · Python ${data.runtime.pythonVersion ?? '不可用'}` : '不可用'},{label:'数据存储',value:`SQLite ${data.runtime.sqliteVersion ?? '不可用'}`}]}/></div> : null}</SettingsCard><SettingsCard icon={FileText} title="排查问题" description="导出基础诊断信息，便于定位本地问题。" action={<Button variant="primary" onClick={() => setDiagnostics(true)}>导出诊断信息</Button>} /><SettingsCard icon={SignOut} title="退出应用" description={data.runtime.platform === 'macos' ? '关闭窗口后应用仍会运行；退出应用会停止本地服务。' : '关闭最后一个窗口会退出 AutoFlow；退出前将停止本地服务。'} action={<Button disabled={busy} onClick={() => void quit()}>退出应用</Button>} /></div></TabsContent>
```

## profile-boundary

- 路径：`/Users/zhangtiancheng/Documents/projects/autoflow-project-management-design/.ai/decisions/2026-09-12-profile-test-browser.md`
- 来源：2026-09-12 审查时的工作区文件
- SHA-256：`106fec22631dd304a51a561687dd546a568f52786ff057c94f3e8120ac3a6e83`

```text
L10: 浏览器配置保存可复用的启动参数和固定指纹种子。它不是浏览器实例，也不拥有日常浏览记录或登录会话。未来项目管理中的环境面板负责持久化浏览器实例；本次不提前实现该模块。
L11:
L12: 列表显示双列配置卡片，窄屏单列。卡片主操作为“打开测试浏览器”，次操作为编辑、复制、重置指纹和删除。每次打开都创建新的临时浏览器会话；每份配置最多一个，启动中、运行中、关闭中均不允许再开。打开成功后主按钮切换为“关闭浏览器”，手动关窗后自动恢复打开状态。正常关闭所有测试窗口或退出 AutoFlow 时回收进程和临时数据。
L13:
L14: 测试启动读取服务器保存的当前配置快照，使用明确安装的 CloakBrowser 内核、指纹、语言/时区、视口、UA、扩展、参数及代理资源；不能静默忽略代理或自动换内核。为实现可见测试，启动时覆盖 headless=False，但不修改保存的配置。起始页面加载失败须明确提示，不能隐藏错误。
L15:
L16: 指纹重置改变配置的 seed，并在卡片中立即显示新的值及前后变化。已打开的窗口保持其启动快照；新 seed 对下次测试生效。原接口已经持久化 seed，本次核验完整链路并改进缓存与反馈，不把既有能力误记为未实现。
L17:
L18: ## 实施顺序与验证
```

## studio-roadmap

- 路径：`/Users/zhangtiancheng/Documents/projects/autoflow/docs/automation-studio/REVERSE_ENGINEERED_DEVELOPMENT_PLAN.md`
- 来源：2026-09-12 审查时的工作区文件
- SHA-256：`d303db6b1c7398ff708a17099607d679b083009b7880de3caf5fb5c7c555ff7b`

```text
L3: - 日期：2026-09-11
L4: - 状态：供评审的开发计划；本轮只规划，不开始业务实现。
L5: - 源码基线：`reference/WebRPA`，commit `5ccb900e8dcf1530aae66f676d87593c416c7ebb`。
L6: - 目标：按照 WebRPA 已存在的功能、契约和依赖关系，推导从零构建 AutoFlow 的顺序。此顺序是工程推导，不是对 WebRPA 历史开发顺序的断言。
L7: - 执行顺序以本文为准；旧 `PLAN.md` 的产品形态和目录边界继续适用，旧 `MILESTONES.md` 的阶段编号不再用于排期。
L8: - 技术约束：Electron + React + FastAPI sidecar；CloakBrowser 唯一运行时；Windows/macOS；自动化不依赖 Manager。
…
L126: ### R2：当前工作流持久化与服务连接
L127:
L128: **模块：** F01–F02、F19 的必要配置。**依赖：** R0；与 R1 开发重叠，验收在 R1 后。
L129:
L130: 开发内容：Electron/sidecar 连接与恢复；当前工作流 CRUD、校验、保存加载；应用数据目录；必要浏览器资源引用。沿用架构中 SQLite 的存储选择，文档 JSON 导出是交换手段，不建设版本仓库。HTTP DTO 通过 OpenAPI 生成前端类型；临时 Mock 与真实客户端共用相同输入输出。
…
L143: ### R3：第一条真实网页自动化
L144:
L145: **模块：** F07–F12、F13 最小结果。**依赖：** R1–R2、可用的 CloakBrowser。
L146:
L147: 开发内容：修正原型，建立按边执行的基础链、每次运行上下文、唯一注册表；接通 CloakBrowser 启动/页面/关闭；以五个原 `module_type` 实现真实操作。运行 API、节点事件、停止、超时和结果同步接通，不分成几轮孤立的后端工程。
L148:
L149: **验收：**
L150:
L151: - [ ] 本地网页中执行 `open_page → click_element → input_text → wait → get_element_info`，页面内容和返回值均与输入样例一致。
L152: - [ ] 打乱文档节点数组而不改变连线，执行顺序不变；未迁移图结构在执行前报清楚，不默默当线性流程运行。
L153: - [ ] 点击类型、等待策略、输入标志、读取属性、输出变量/列、默认超时按源行为对照；遗漏字段不以“后端转发了参数”视为完成。
L154: - [ ] `${name}`/`{name}` 等本批所需变量语义通过参考样例；连续两次运行不串变量、页面或结果。
L155: - [ ] 真实点击失败能定位节点、selector、页面 URL；超时和用户停止能区分。
L156: - [ ] 等待中停止和浏览器异常退出会结束本次运行；清理只处理本次运行拥有的资源，不误关共享会话。
L157: - [ ] 同一工作流重复点击运行按明确策略拒绝重复；不同运行标识下事件不串流。
L158: - [ ] 生产浏览器只能由 CloakBrowser 基础设施创建；没有 Chrome/Edge/Firefox/DrissionPage 回退选择。
L159:
L160: **演示：** Studio 中配置真实流程，运行后显示网页结果，再演示元素不存在和等待中停止。
L161:
L162: **门槛：** 这是首个“真实可运行”的产品节点。测试适配器和动画不能替代验收；移除参考目录后仍能运行。
…
L217: ### R7：独立 Studio 跨平台交付
L218:
L219: **模块：** F01–F16 首期部分。**依赖：** R0–R6；平台冒烟从早期持续进行。
L220:
L221: **验收：**
L222:
L223: - [ ] Windows x64、macOS Intel、macOS Apple Silicon 各自真实验证；缺设备的目标标为待验收，不能由另一平台结果代替。
L224: - [ ] 安装包能启动 Electron、sidecar、CloakBrowser；浏览器缺失时提示并按已确定的供应方式恢复。
L225: - [ ] 正常关闭、强制退出、浏览器崩溃、服务重启后不会遗留本应用拥有的子进程或永久 running 记录；不自动重放中断任务。
L226: - [ ] G01–G16 场景全部有结果；运行记录、截图和输出位于正确应用目录。
L227: - [ ] 排除能力不出现在可运行目录中；加载含未支持节点的文档能解释阻断原因并保留原文档。
L228: - [ ] 干净构建无需 reference 仓库或其依赖；已选节点之外的 OCR/媒体/桌面库不会被默认引入。
L229:
L230: **演示：** 安装后从录制到修改、保存、回放、失败排查、重启恢复的完整使用路径。
…
L242: ### R9：Manager/Studio 组合
L243:
L244: **模块：** AutoFlow 自有 Manager、F18–F20 中实际选定的管理能力。**依赖：** R7；涉及调度再依赖 R8 调度包。
L245:
L246: **验收：** Manager 可打开指定自动化的 Studio，配置资源、启动运行、查看结果；同一 automation 的编辑会话不重复；双窗口显示同一运行事实；关闭/重新打开 Studio 不复制任务或丢编辑内容；自动化核心测试不需要项目管理。停靠和弹出另列子项，只有实现并验证状态保留后才标完成。
L247:
L248: 不以完成 Manager 为借口引入 WebRPA 整套 RBAC、审批、分布式编排或市场。独立 Studio 的首版交付不等待 R8/R9。
```

## studio-plan

- 路径：`/Users/zhangtiancheng/Documents/projects/autoflow/docs/automation-studio/PLAN.md`
- 来源：2026-09-12 审查时的工作区文件
- SHA-256：`72f88719f58f4d1e7c3cff222c33debae40df46c38344b4721a2d032a8f6bdca`

```text
L41: 1. **自动化核心独立。** 自动化可以独立编辑和执行，不 import 项目管理代码。
L42: 2. **管理端是上层组合。** 项目管理通过 application API 调用自动化能力，不进入执行器内部。
L43: 3. **CloakBrowser 是唯一浏览器运行时。** 所有网页节点必须通过 `CloakBrowserRuntime`，不能直接创建 Playwright 或其他浏览器实例。
L44: 4. **画布不是领域模型。** React Flow 只负责交互，后端使用 AutoFlow 自己的工作流文档模型。
L45: 5. **窗口不是业务边界。** Manager 和 Studio 是同一应用中的两个界面宿主，共享后端和契约，不复制业务实现。
L46: 6. **先做少量可验证能力。** 先实现基础 Web 节点的完整闭环，再扩大节点数量。
L47: 7. **平台差异显式化。** 第一阶段只实现跨平台网页能力；暂不支持的平台能力返回结构化不可用状态。
L48: 8. **没有产品级版本管理。** 只保存当前工作流和运行记录；内部格式字段只有在序列化确实需要时才增加。
…
L175: ```
L176:
L177: `WorkflowDocument` 表示当前可编辑内容。系统不建立 revision、snapshot、publish 或 compare 表。
L178:
L179: ### 5.2 执行模型
L180:
L181: ```text
L182: Run
L183: ├── runId
L184: ├── workflowId
L185: ├── status: queued | running | succeeded | failed | cancelled | timed_out
L186: ├── startedAt
L187: ├── finishedAt
L188: ├── error
L189: └── nodeResults[]
L190: ```
L191:
L192: ```text
L193: RunEvent
L194: ├── runId
L195: ├── sequence
L196: ├── nodeId
L197: ├── type: run_started | node_started | node_progress | node_succeeded |
L198: │        node_failed | node_cancelled | run_succeeded | run_failed | run_cancelled
L199: ├── timestamp
```
