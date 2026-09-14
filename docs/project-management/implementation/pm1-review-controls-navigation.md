# PM1 共享控件、既有消费者与应用导航独立审查

- 日期：2026-09-13。
- 状态：confirmed / reviewed；本记录限定的规格审查与工程质量审查均通过，3 项发现已修复并复核，无未关闭的实质问题。
- 置信度：高，针对下述静态审查及已执行测试覆盖的行为。
- 审查工作区：`autoflow-project-management-pm1`。
- 比较基线：`dbb01f5759f2effd34b70918579cfb9f8bcca67e`。审查对象是该基线之上的未提交工作树；记录时 HEAD 仍为此提交。本文中的源码行号对应记录时工作树。
- 控件来源：`1fb58e188c3b1063c86e19d4c6d80bba0ecbe92e` 及其父链。
- 审查角色：独立审查智能体 `review_project_product`；实现与修复由主协调执行。审查阶段只读代码、运行验证，本轮仅新增本记录，不修改业务代码或提交。

## 1. 依据、顺序与范围

审查以 [PM1 执行卡](../../superpowers/plans/2026-09-13-project-management-pm1.md)包 1、包 4，以及固定规则第 10 项为直接依据。已读取仓库 `AGENTS.md`、`.ai/README.md`、`.ai/memory/project-context.md`、PM1 授权及 Studio/设置相关决策、[目录结构](../../PROJECT_STRUCTURE.md)与[系统架构](../../architecture/README.md)。

方法采用 Superpowers `requesting-code-review/SKILL.md` 及其 `code-reviewer.md`，文件位于 `/Users/zhangtiancheng/.claude/plugins/cache/superpowers-marketplace/superpowers/5.0.7/skills/requesting-code-review/`；结合已读取的 Ponytail 技能约束审查范围，不借接入任务扩建通用组件库。

先核对规格、真实调用方和反例，向实现者报告可复现问题；随后检查同一包的工程质量。规格发现未关闭时不出具通过结论。最终在修复复核后，分别确认规格符合与工程质量通过。该结论不是整个 PM1 的交付或合并批准。

| 范围 | 实际审查内容 |
| --- | --- |
| 共享控件选择性接入 | tokens、controls、全局样式入口及宽度修复；Table、Pagination、SearchInput、Select、ScrollArea、Spinner、Skeleton；Button、IconButton、Input、Textarea、Modal、Dialog、AlertDialog、OverlayHost 及必要依赖。 |
| 既有消费者兼容 | 13 个原有 Select 消费文件的值转换、空值选项、禁用语义、RHF ref/onBlur、错误提示关联；相关消费者测试。 |
| App 与导航 | `App.tsx`、`ApplicationHeader.tsx`、`navigation.ts` 及其测试；全局入口、项目 hash 解析、无效地址返回、离开保护、Back/Forward、工作区与实例切换的应用接入边界。 |
| 既有能力保留 | 比较 Studio M1、Studio IPC、`useDesktopSession`、`ApiProvider`，确认选择性接入没有覆盖其会话实现。 |

**不在范围内：** `apps/desktop/src/renderer/domains/projects/` 的领域实现、后端项目接口/事务/迁移、项目领域完整验收、生成 API 类型本身、整个 PM1 的全套门禁与真实 Electron 验收。执行 `App.projects.test.tsx` 仅用于验证 App 的导航与会话集成边界，不代表已经审查 projects 领域实现。

## 2. 规格审查发现及修复复核

### CNR-01 · P1：已有导航历史后直接改 hash 会卡住导航

- 对应规格：执行卡包 4 第 1、4 项要求覆盖 hashchange 离开确认，并在取消时恢复规范 hash。
- 发现位置：`navigation.ts` 修复前第 75–76 行对直接 hash 赋值继承当前 `history.state` 的假设，以及随后的历史游标恢复。
- 复现：从项目目录经 `navigate()` 打开项目，使内部索引为 1；注册未保存离开保护；再设置 `window.location.hash = '#/settings'`。
- 修复前实测：新 hash 条目没有 `afNavigationIndex`，却被当作索引 0。恢复当前条目时执行越过历史末尾的 `history.go(+1)`，等待无法完成。100 ms 后界面仍在项目概览，URL 已是设置，离开保护调用次数为 0；后续普通 `navigate()` 也被持续的 busy 状态忽略。
- 影响：一次受支持的外部 hash 变化就能使后续导航失效，且不能出现应有的离开确认，因此定为 P1。
- 修复：保留“无历史索引”的 `null` 状态；对新 hash 条目分配当前索引加一，再执行恢复与确认。见 [navigation.ts](../../../apps/desktop/src/renderer/app/navigation.ts#L25)第 25、69–81 行。
- 复核：新增 [navigation.test.tsx](../../../apps/desktop/src/renderer/app/navigation.test.tsx#L53)第 53 行的 `guards a new hash entry with null state after an indexed project visit`，验证保护被调用、URL 恢复及后续普通导航可继续。该测试及最终导航回归通过。
- 状态：已关闭；置信度高。

### CNR-02 · P2：离开确认期间按 Back，取消后 URL 与页面不一致

- 对应规格：执行卡包 4 第 1、4 项要求 Back/Forward 受保护，取消后保留原处并恢复规范 hash。
- 发现位置：`navigation.ts` 修复前第 74 行把 busy 期间的真实历史事件直接忽略。
- 复现：打开项目概览；有未保存内容时，通过全局导航请求进入设置；确认尚未回答时执行 `window.history.back()`，随后选择继续编辑，即离开保护返回 `false`。
- 修复前实测：确认前 URL 和界面均为项目概览；Back 后 URL 已变为 `#/projects`；取消后界面仍是项目概览，URL 继续停在目录地址。
- 影响：取消承诺失效，浏览器历史位置与可见页面分离，后续 Back/Forward 的含义不再可靠。此问题不依赖 CNR-01 的无索引条目，因此单独记录为 P2。
- 修复：busy 期间可以拒绝新的导航意图，但仍须把已发生的历史游标变化恢复到当前条目；导航提交等待恢复完成。见 [navigation.ts](../../../apps/desktop/src/renderer/app/navigation.ts#L36)第 36、46–48、83、89–91 行。
- 复核：新增 [navigation.test.tsx](../../../apps/desktop/src/renderer/app/navigation.test.tsx#L66)第 66 行的 `restores a Back event received while a global navigation confirmation is pending`，验证取消后页面与 URL 都保留项目概览。该测试及原有 Back/Forward 回归通过。
- 状态：已关闭；置信度高。

### CNR-03 · P2：父 fieldset 禁用后，已展开的 Select 仍能写值

- 对应规格：执行卡包 1 要求既有消费者变更仅用于 API 兼容，不丢失禁用行为；包 4 要求应用不可交互期间正确门控。
- 发现位置：`select.tsx` 修复前第 22–23 行只检查自身 `disabled` 属性；已有消费者 [ProfileFormDialog.tsx](../../../apps/desktop/src/renderer/domains/profiles/components/ProfileFormDialog.tsx#L179)与 [RotationScheduleForm.tsx](../../../apps/desktop/src/renderer/domains/proxies/components/RotationScheduleForm.tsx#L20)通过父 `fieldset disabled` 禁用表单。
- 复现：先打开 Select，再把父 fieldset 设为 disabled，随后点击仍在门户中的选项。实际场景包括浏览器配置表单下拉展开时，本地服务转为离线。
- 修复前实测：触发按钮的 `matches(':disabled')` 已为 `true`，listbox 仍打开，点击“全池轮换”仍产生 `onValueChange('full_pool')`。独立 jsdom 脚本执行真实 Select 与 Radix，仅替换视觉图标以适配脚本模块加载。
- 影响：原生 select 随 fieldset 禁用的既有语义在自定义门户接入后丢失，用户仍能修改被禁用的表单字段，定为 P2。
- 修复：统一 `canChange()` 检查显式 disabled/readOnly、触发按钮的实际 `:disabled` 及祖先 `inert`；打开或写入选项时使用该判断，禁止写入时关闭弹层。见 [select.tsx](../../../apps/desktop/src/renderer/shared/components/ui/select.tsx#L14)第 14、23–24 行。该修复不要求添加新的表单状态框架。
- 复核：新增 [select.test.tsx](../../../apps/desktop/src/renderer/shared/components/ui/select.test.tsx#L58)第 58 行的 `honours a fieldset disabled after its portal was already opened`，断言禁用后点击选项不调用变更函数；测试通过。`inert` 分支已静态核对；本审查未单独执行真实 Chromium 的 inert 交互验收。
- 状态：已关闭；置信度高。

## 3. 保留项与兼容核查

### 3.1 控件来源与布局修复

对比 `1fb58e1` 时，Button、Input、Textarea、Dialog、AlertDialog、Modal、Select 和全局样式入口在初次接入时与来源文件一致。Select 随后仅增加 CNR-03 的禁用门控修复。新控件及依赖闭包已在本工作树实际读取，未要求接入无本阶段消费者的组件库功能。

来源与本工作树的两个样式文件 SHA-1 一致：

| 文件 | SHA-1 |
| --- | --- |
| [tokens.css](../../../apps/desktop/src/renderer/styles/tokens.css) | `037d98fc8a184da3646126f2d2b26d8c873e3514` |
| [controls.css](../../../apps/desktop/src/renderer/styles/controls.css) | `34134b933a4b82dbc63c802086c4055fd252902f` |

[index.css](../../../apps/desktop/src/renderer/styles/index.css#L9)第 9–12 行保留 `html/#root` 的宽度及 body 自动宽度，使弹层滚动锁可用 margin 补偿滚动条。这里确认的是修复代码与来源保留；真实窗口几何和 200% 缩放由 PM1 包 5 验收。

### 3.2 13 个既有 Select 消费文件

这里的“13 个”按消费文件计数，不是 Select 实例数。

| 领域 | 已读消费文件 | 核查重点 |
| --- | --- | --- |
| 浏览器配置，4 个 | [EnvironmentFields.tsx](../../../apps/desktop/src/renderer/domains/profiles/components/EnvironmentFields.tsx)、[EnvironmentOptionField.tsx](../../../apps/desktop/src/renderer/domains/profiles/components/EnvironmentOptionField.tsx)、[KernelProxyFields.tsx](../../../apps/desktop/src/renderer/domains/profiles/components/KernelProxyFields.tsx)、[BrowserManagementPage.tsx](../../../apps/desktop/src/renderer/domains/profiles/pages/BrowserManagementPage.tsx) | 跟随浏览器的空字符串值、自定义入口、当前不可用资源、内核选择连带更新、代理模式切换清关联字段；RHF ref/onBlur 与错误 id。 |
| 代理，5 个 | [LocalProxyGroups.tsx](../../../apps/desktop/src/renderer/domains/proxies/components/LocalProxyGroups.tsx)、[LocationPicker.tsx](../../../apps/desktop/src/renderer/domains/proxies/components/LocationPicker.tsx)、[ProxyDetailDrawer.tsx](../../../apps/desktop/src/renderer/domains/proxies/components/ProxyDetailDrawer.tsx)、[ProxyFleet.tsx](../../../apps/desktop/src/renderer/domains/proxies/components/ProxyFleet.tsx)、[RotationScheduleForm.tsx](../../../apps/desktop/src/renderer/domains/proxies/components/RotationScheduleForm.tsx) | 空筛选值、协议选项、筛选重置分页、轮换分钟数的字符串/数字转换、当前远端值及 fieldset 禁用。 |
| 模型，1 个 | [ProviderConnectionStep.tsx](../../../apps/desktop/src/renderer/domains/models/components/ProviderConnectionStep.tsx) | 协议标识与显示名称分离，FormField 标签绑定及 disabled 传递。 |
| 设置，1 个 | [SettingsPage.tsx](../../../apps/desktop/src/renderer/domains/settings/pages/SettingsPage.tsx) | 缩放百分比数值转换、动效枚举及保存期间禁用。 |
| Studio，2 个 | [NodeInspector.tsx](../../../apps/desktop/src/renderer/domains/workflows/components/NodeInspector.tsx)、[VariablePanel.tsx](../../../apps/desktop/src/renderer/domains/workflows/components/VariablePanel.tsx) | 节点字段值、变量类型、布尔初始值和未完成值保留；错误关联及 disabled 传递。 |

已确认迁移统一使用 `onValueChange`，原有不可清空选择显式设置 `clearable={false}`；空字符串作为业务值保留。RHF 的 ref 指向触发按钮，onBlur 保留；[FormField.tsx](../../../apps/desktop/src/renderer/shared/components/FormField.tsx)的标签、`aria-invalid`、`aria-describedby` 可继续传到实际触发控件。

主协调原已在修复的两个 overlay 旧 class 断言，以及 ProfileFormDialog 的错误聚焦问题，没有重复列为本审查新发现。已复核 ProfileFormDialog 对非特殊控件使用 `form.setFocus()`，避免 `[name]` 选择器误选 Select 的隐藏提交字段；相关测试最终通过。

### 3.3 应用导航和既有会话

- [ApplicationHeader.tsx](../../../apps/desktop/src/renderer/app/ApplicationHeader.tsx)在既有顶部导航中加入项目入口，品牌入口也经统一导航回调。
- [navigation.ts](../../../apps/desktop/src/renderer/app/navigation.ts)负责 `#/projects` 与 `#/projects/{projectId}/{tab}` 的解析和序列化，拒绝无效项目标识及不支持的页签。
- [App.tsx](../../../apps/desktop/src/renderer/app/App.tsx#L19)延用 `useDesktopSession` 和现有 `ApiProvider`。Provider 按 workspaceKey 保持或重建；同工作区 instance 改变不靠重新挂载清草稿。真正切换工作区时清旧项目 UI 状态并恢复项目目录；不可交互状态设置 inert 并向项目接入传递 disabled。
- [App.projects.test.tsx](../../../apps/desktop/src/renderer/app/App.projects.test.tsx)覆盖项目上下文与六页签入口、取消全局导航后保留草稿、同工作区实例切换保留草稿、切换期间禁提交、真实换工作区清理及无效地址返回。该测试使用测试客户端，不作为真实后端联调或 projects 领域内部实现的证明。
- 与 `dbb01f5` 比较，`useDesktopSession.ts`、`ApiProvider.tsx`、StudioPage 实现及 `main/ipc/automation-studio.ts` 没有被控件接入改写；工作流领域实现变更限于上述两个 Select 消费文件。StudioPage 测试有 API 适配更新，不代表会话实现被替换。

## 4. 工程质量审查

同包工程质量审查未新增独立实质问题，结论如下：

- 路由解析与历史协调集中在导航模块，App 负责装配；没有增加第二个查询上下文，也没有把工作区判断复制到共享控件中。
- 导航离开保护对拒绝或异常按不离开处理；修复后协调真实历史游标与异步确认，已有反例均有回归测试。
- Select 的禁用修复沿用现有 DOM 与组件状态，保留 Radix 的弹层和键盘行为，没有引入额外表单管理机制。
- Button 改为默认 `type="button"` 后，已检索所有既有真实 `<form>`/`onSubmit` 调用点；提交按钮均显式声明 `type="submit"`，未发现提交语义丢失。
- 共享控件继续在 renderer/shared 内提供展示与交互能力；没有要求本阶段注册独立 `packages/ui` 或迁移更多业务页面。
- 类型检查与定向 ESLint 均通过。未把通过静态工具等同于真实 Electron 视觉验收。

## 5. 已执行验证

以下命令在审查工作区根目录执行。结果来自本独立审查的工具输出；本次将已有结果写入记录，未为纯文档新增重复业务测试。

### 5.1 修复后的消费者与控件回归

```bash
npm --workspace @autoflow/desktop test -- \
  src/renderer/shared/components \
  src/renderer/app/navigation.test.tsx \
  src/renderer/app/App.projects.test.tsx \
  src/renderer/domains/profiles/components \
  src/renderer/domains/workflows/tests \
  src/renderer/domains/settings/tests/SettingsPage.test.tsx \
  src/renderer/domains/proxies/tests/ProxyManagementPage.test.tsx \
  src/renderer/domains/proxies/tests/ProxyRemoteControls.test.tsx

npm --workspace @autoflow/desktop test -- \
  src/renderer/domains/models/tests \
  src/renderer/domains/profiles/pages/BrowserManagementPage.test.tsx
```

| 最终执行 | 测试文件 | 测试数 | 结果 |
| --- | --- | --- | --- |
| 共享控件、导航及第一组既有消费者 | 32 | 160 | 全部通过 |
| 模型与浏览器管理页面补充回归 | 5 | 52 | 全部通过 |
| 两组去重合计 | 37 | 212 | 全部通过 |

修复过程中另执行导航/App 的 10 项测试，以及 Select/Modal/Dialog/导航/App/ProfileFormDialog 的 38 项定向测试，均通过。这些测试包含在上述最终回归中，不额外累计。

首轮回归曾为 156/157 通过，唯一失败是 `App.projects.test.tsx` 对“暂未开放”的精确文字断言与实际“数据暂未开放”不匹配；主协调修正断言后通过。未把这项已知断言偏差列为新的产品缺陷。

### 5.2 类型与 lint

```bash
npm --workspace @autoflow/desktop run typecheck

npx eslint \
  apps/desktop/src/renderer/app/App.tsx \
  apps/desktop/src/renderer/app/ApplicationHeader.tsx \
  apps/desktop/src/renderer/app/navigation.ts \
  apps/desktop/src/renderer/shared/components/ui/select.tsx \
  apps/desktop/src/renderer/shared/components/ui/button.tsx \
  apps/desktop/src/renderer/shared/components/Modal.tsx \
  apps/desktop/src/renderer/shared/components/ui/dialog.tsx \
  apps/desktop/src/renderer/shared/components/ui/alert-dialog.tsx \
  apps/desktop/src/renderer/shared/components/ui/overlay-host.tsx
```

两项检查通过。最终 Select 修复后重跑 `typecheck`，并再次对 `select.tsx` 与 `navigation.ts` 执行定向 ESLint，通过。

### 5.3 独立反例证据

除仓库测试外，审查者通过标准输入执行临时 Node/jsdom 脚本，在内存中转译并加载当前真实 TypeScript 实现，未编辑仓库源码：

1. CNR-01 观察到 `route=项目概览`、`URL=#/settings`、`guardCalls=0`，随后普通导航仍无效。
2. CNR-02 观察到确认期间 Back 后、取消确认后，均为 `route=项目概览`、`URL=#/projects`。
3. CNR-03 观察到 `fieldset disabled=true`、`listbox remains open=true`、`changes after disable=["full_pool"]`。

上述脚本输出作为发现依据；修复后的可重复验证已落入对应仓库测试，不将未保存的临时脚本描述为仓库测试资产。

## 6. 最终结论与验收边界

本记录范围内，规格审查通过、工程质量审查通过，CNR-01/02/03 均已关闭，无未解决的实质发现。共享控件来源、既有消费者兼容、导航保护及应用会话接入均有具体源码和测试依据。

此结论不覆盖 projects 领域实现，不代替后端事务或项目业务验收。真实 Electron 窗口的下拉宽度、200% 缩放、截图和桌面完整操作由 PM1 包 5 主流程另行记录；本审查未执行 Windows、其他 CPU 架构或安装包验证，也未据此批准提交、合并、发布或进入 PM2。

## 7. Select 高度分配增量复审

- 日期：2026-09-13。
- 范围：仅 [select.tsx](../../../apps/desktop/src/renderer/shared/components/ui/select.tsx#L31)第 31、33 行的 Content/Viewport 高度与 flex 类名增量；既有消费者作为回归验证对象，仍未扩展到 projects 领域实现。
- 顺序：先核对缩放与可用区域规格、读取本地 Radix 真实实现，再检查工程质量及运行既有消费者回归。
- 当前状态：增量源码规格审查与工程质量审查通过，未发现额外实质问题；已读取主协调重新构建后的 Electron 通过证据，CNR-04 已关闭。第 1–6 节记录的是本增量之前已关闭的 3 项独立审查发现。

### CNR-04 · P2：200% 缩放时向上展开的选项层超出窗口顶端

该问题由主协调人工检查真实构建版截图发现，再增加边界断言复现，不是本审查者独立发现。主协调提供的修复前测量为：

| 缩放 | popup.top | popup.bottom | popup.height | viewportHeight | 应用宽度 |
| --- | --- | --- | --- | --- | --- |
| 200% | -14 | 240 | 254 | 512 | 展开前后不变 |

这说明原来的“展开前后应用宽度不变”只能证明宽度补偿，没有覆盖选项层本身是否完全可见。顶端为 -14，选项层已经超出窗口；对应执行卡包 5 的 200% 缩放与下拉验收，定为 P2。主协调已在 [smoke-project-management.mjs](../../../scripts/smoke-project-management.mjs#L132)加入 `popup.top >= 0 && popup.bottom <= popup.viewportHeight` 的真实窗口边界断言。

原实现只限制 Viewport 的最大高度，上下滚动按钮仍在其外部占据 Content 高度。修复把 Radix 可用高度同时用于整个 Content 的最大高度，并让 Viewport 在剩余空间中收缩：

- Content：增加 `flex flex-col max-h-[var(--radix-select-content-available-height)]`。
- Viewport：增加 `min-h-0 flex-1`，保留原有 `max-h-[min(20rem,var(--radix-select-content-available-height))]`。

### 7.1 规格复核

已读取本工作区 `node_modules/@radix-ui/react-select/dist/index.js` 和 `node_modules/@radix-ui/react-popper/dist/index.js`，核对实际依赖行为：

1. Select Content 本来就使用 column flex；Popper 定位使用 `box-sizing: border-box`，并把 Popper 的可用高度映射为 `--radix-select-content-available-height`。
2. Popper 的 size 中间件按当前定位与碰撞空间更新可用高度变量。修复沿用该变量，没有在业务组件里另算窗口尺寸或固定选择展开方向。
3. Radix 上下滚动按钮使用 `flexShrink: 0`；Viewport 原本使用 `flex: 1` 和 `overflow: hidden auto`。对整个 Content 设最大高度、允许 Viewport 最小高度为 0，符合这一布局分工，可为滚动按钮留出空间。
4. `position="popper"`、`sideOffset={6}`、`collisionPadding={12}`、门户归属、选项数据、RHF ref/onBlur、禁用门控和 Escape 处理均未改变。原来的宽度补偿样式也未改变。

源码规格复核通过，置信度高。此判断说明修复与 Radix 的高度分配机制一致，不把静态推理视为真实窗口尺寸验证。

### 7.2 工程质量与回归

工程质量复核通过：变更仅为两处 className，复用现有 Radix 和 CSS 布局，没有增加尺寸监听器、手工定位状态、平台分支或消费者专用例外。新增的 flex 类与 Radix 已有内联布局一致，不替换其滚动、选项定位或键盘处理。

本增量完成后，将第 5.1 节两组测试路径合并为一次 Vitest 执行，结果为 **37 个测试文件、212 项测试全部通过**；另执行 `npx eslint apps/desktop/src/renderer/shared/components/ui/select.tsx`，通过。回归包含 Select 键盘选值、弹层先于父对话框响应 Escape、只读与禁用门控、浏览器配置表单及其余既有消费者。

这些测试验证既有交互和消费者兼容，不验证实际 CSS 几何。真实布局的关闭证据单独记录如下。

### 7.3 主协调真实 Electron 证据与增量结论

主协调报告重新构建后的完整 Electron QA 退出码为 0；本审查者实际读取了 [built-html.json](../../migration/project-management-pm1-qa/built-html.json)及 `/tmp/autoflow-pm1-final-electron.log`。证据 JSON 的 `result` 为 `passed`、`entry` 为 `built-html`、`checkedAt` 为 `2026-09-12T20:34:16.296Z`，平台为 `darwin/arm64`。这是主协调执行、审查者核对的证据，不表述为本审查者独立操作的 Electron 会话。

| 200% 缩放修复后测量 | 展开前 | 展开后 |
| --- | --- | --- |
| window.innerWidth | 720 | 720 |
| 应用 root 宽度 | 708 | 708 |

选项层 `top=12`、`bottom=240`、`height=228`、`viewportHeight=512`，满足 `top >= 0` 且 `bottom <= viewportHeight`；应用宽度同时保持稳定。证据 JSON 列出 9 组端到端场景通过，包含完整 Electron 重启后项目持久化与重新打开场景。这里引用这些场景作为本次构建回归的主协调证据，不将其扩展为本审查对 projects 领域源码的审查结论。

增量规格审查与工程质量审查最终均通过，CNR-04 关闭，置信度高。该结论覆盖当前受测 macOS ARM64 构建版的 200% 缩放案例；证据中 Windows 仍为 `not-run`。本次仅更新本审查记录，没有修改源码、验收脚本或其他文件。
