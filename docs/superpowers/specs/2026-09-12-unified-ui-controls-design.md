# AutoFlow 统一基础控件设计规格

- 日期：2026-09-12；状态：**approved，用户2026-09-12确认；实现与平台验收分别记录**。
- 来源：[实际源码盘点](../../design-system/2026-09-12-ui-controls-audit.md)、用户本轮明确要求、既有暖灰/黏土棕视觉和领域 ADR。
- 使用技能：Superpowers `using-superpowers`、`brainstorming`、`using-git-worktrees`；实现任务由 `writing-plans` 细化；以 `ponytail` 的复用原则限制范围。
- 当前：T0–T12 已实施，T13 本机自动检查与跨平台人工检查分别记录；最终状态见 `../../design-system/verification/ui-controls-results.md`。

## 1. 目标、边界与推荐方案

让五个已实现入口及其全部弹窗共享 AutoFlow 的控件视觉和 API：控件本体、下拉选项面板、焦点、错误、禁用、浮层和滚动条都受同一规范控制。保留语义化 DOM 和成熟键盘交互；不改后端、API、数据、业务能力和页面信息架构。

| 方案 | 优点 | 代价 / 决定 |
|---|---|---|
| A：原生控件统一 CSS | 初期工作少，文字编辑可保留原生语义 | 无法统一系统 select/datalist 面板，不满足需求；不采用 |
| **B：现有 Radix/shadcn 风格封装补齐，少量引入成熟组合框基础** | 大部分已有行为与测试可复用；独立 token、组件 API；按真实调用迁移 | 需要验证两种行为库的浮层/焦点协作；**推荐** |
| C：整个系统改为单一新组件库，并把 packages/ui 建为完整 workspace | 库来源单一 | 扩大到所有已成熟 Dialog/Menu/Tabs、构建和包边界，当前没有第二个 UI 消费端；不采用 |

B 的具体选择：保留所有已安装 Radix 原语，补 `@radix-ui/react-radio-group` 与 `@radix-ui/react-scroll-area`；组合框选用 `react-aria-components` 的 ComboBox 能力，分别封装严格单选 `Combobox` 和允许自由字符串的 `Autocomplete`。其官方文档明确区分选项值与输入值，并支持 `allowsCustomValue`；不自行实现 listbox 的方向键与焦点协议。[React Aria ComboBox](https://react-aria.adobe.com/ComboBox)

这是**已批准技术选择**；2026-09-12 已在任务 Electron 的 G0 案例验证 ComboBox Portal、RHF ref、Escape 和滚动，结果与平台边界见 `docs/design-system/verification/choice-overlay-gate.md`。这不代表领域接入或双平台验收完成。如果不能通过，不迁移领域代码；提交失败证据和替代方案（Base UI 组合框/自动补全的定向替换）供确认，不静默重写所有 Radix。安装时核对 peer dependencies 并锁定实际验证版本，不用 CLI 覆盖现有 shadcn 文件。

## 2. 架构落点

```text
renderer/styles/
  tokens.css                  颜色、尺寸、字体、层级、动效变量
  controls.css                跨语义输入的浏览器外观归一、滚动条、强制色适配
  index.css                   引入上述文件；保留主题/全局基础与现有 data-motion 协议
renderer/shared/components/ui/
  button.tsx / icon-button.tsx / input.tsx / textarea.tsx
  search-input.tsx / password-input.tsx
  checkbox.tsx / radio-group.tsx / switch.tsx
  select.tsx                  最终唯一 Select 公开入口，Radix 行为
  combobox.tsx                严格选择与自由输入两个导出，React Aria 在此隔离
  choice-types.ts             选择控件的应用侧类型，不导出第三方业务类型
  dropdown-menu.tsx / tooltip.tsx / dialog.tsx / alert-dialog.tsx / tabs.tsx
  scroll-area.tsx / disclosure.tsx / table.tsx / pagination.tsx
  alert.tsx / empty-state.tsx / skeleton.tsx / spinner.tsx / progress.tsx
renderer/shared/components/
  FormField.tsx               label、hint、error → 实际控制节点的明确绑定
  FieldGroup.tsx              fieldset/legend + 组级提示/错误
  Modal.tsx / Drawer.tsx      使用同一个 Dialog frame；不创建第二套焦点引擎
  Toaster.tsx / State.tsx     复用新的视觉组件，保留现有业务调用
renderer/shared/ui-lab/       仅开发模式加载的正式展示与验收场景
renderer/domains/*/           options 映射、请求、校验、能力、选择业务语义仍在领域
```

不创建全局 UI barrel，不把所有依赖一次性打进首屏；延续直接文件 import。`shared/lib/utils.ts` 继续承担 cn，不能引用不存在的 cn.ts。不搬 packages/ui。TagInput 仅被模型字段调用，放在 `domains/models/components/TagInput.tsx`；多选 checklist 的数据/选择范围仍由两个领域组件控制。

生产原生 select 退出前允许临时 `select-radix.tsx` 作为新实现入口，避免旧事件式 API 一次性破坏所有页面。最后一批迁移完成后把实现归一到 `select.tsx` 并删除临时文件，不保留永久双轨。

## 3. 视觉令牌

### 3.1 色彩与语义

以下为拟定固定值；既有基础色保留，新值必须经过展示页和真机确认。

| token | 值 | 使用 |
|---|---|---|
| canvas / surface / surface-subtle / surface-hover | #f1eee7 / #fbfaf7 / #f6f3ee / #f5f1e9 | 画布、控件/浮层、次级区域、悬停 |
| ink / muted | #34322e / #625e57 | 正文 / 辅助信息、placeholder；不靠降低透明度制造正文层次 |
| clay / clay-strong / clay-soft | #8d4e2f / #88492c / #f2e3d7 | 主按钮、按压、选中底色 |
| line / line-strong | #d8d3c9 / #c7c0b5 | 卡片和表格分隔，不能独自作为输入可辨识边界 |
| **control-border** | **#8b8377** | 输入边界、未选 checkbox/radio 边界、scroll thumb |
| focus | #8d4e2f | 2px 实线 focus-visible 环，offset 2px；输入组只包围实际目标 |
| danger / danger-soft | #b13c32 / #fbece9 | 删除、字段错误、失败；不使用品牌棕充当错误色 |
| success / success-soft | #4f694a / #e6ece2 | 成功状态、勾选之外的业务健康反馈 |
| warning / warning-soft | #805618 / #faf0dc | 过期、受限提示，不自行推导业务警告 |
| disabled-surface / disabled-ink | #ebe7df / #7b746a | 禁用仍可读，去掉 hover；必要说明保持 muted 正常对比 |
| overlay | rgba(52,50,46,.32) | 模态遮罩，不叠加高饱和深色 |

按 sRGB 相对亮度公式计算：ink/surface **12.26:1**、muted/surface **6.18:1**、clay/surface **6.17:1**、白字/clay **6.44:1**、control-border/surface **3.59:1**、control-border/canvas **3.23:1**、danger/surface **5.65:1**。现有 line/surface 只有 **1.43:1**。这些是静态色值计算，不是整屏 WCAG 认证；实现需对所有实际叠色和焦点背景复测。

正常小字目标至少 4.5:1；用于辨识控件及状态的非文字信息目标至少 3:1；disabled 也保留可理解的文案。[WCAG 非文字对比说明](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html)

### 3.2 字体、密度与结构

- 沿用现有系统字体栈；不假定 Inter 已打包。正文 14/20px、说明 12/18、控件 label 14/20 medium、区块标题 16/24 semibold、页面标题 24/32 semibold。代码/路径/标识使用 monospace。200% 缩放不以 CSS 缩小字号抵消。
- spacing：4、8、12、16、20、24、32；字段 label 到控件 8、hint/error 到控件 4；同组字段间16、分区间24、页面主区间24/32。
- `size=sm` 32px：表格内操作、紧凑筛选；`md` 40px：默认表单/工具栏。字段内容两行以上自然增长，不固定 text line height 截字。没有调用需求不加 xs/lg。
- IconButton 命中面积32/40px；图标16/18px，关闭图标18px；checkbox/radio 可见18px、关联 label 命中区域至少32px高；Switch40×22，Thumb18，位移18。
- 圆角：控件8、卡片12、弹窗16、badge和thumb999；边框1px。字段错误仍1px边框+文案，避免改变布局。
- 阴影：popup `0 6px 20px rgba(52,50,46,.12)`；modal `0 20px 64px rgba(52,50,46,.18)`；普通输入无阴影，仅焦点环。使用 Phosphor 现有图标体系；默认 regular，禁止再加 Lucide 只为复制上游示例。
- 页面内行宽可收缩；输入 `min-width:0`；下拉宽至少触发器宽、最多`min(36rem, viewport - 32px)`；UA/长名称选项可两行且完整值可复制/查看，不让长串撑开弹窗。

## 4. 状态矩阵

| 控件 | default / hover / active | selected / checked | focus | disabled / loading | error / read-only |
|---|---|---|---|---|---|
| Button/IconButton | 依 variant；hover 微变背景；active 使用 strong，无缩放跳动 | 切换按钮才用 aria-pressed；普通按钮无 selected | 统一2px环 | disabled禁触发；loading保留label/宽度，Spinner，aria-busy，阻止重复提交 | danger是动作语义；不发明只读按钮 |
| Input/Textarea/Search/Password | surface+control-border；hover边框clay，输入焦点不变高度 | 原生文字选择使用 clay-soft+ink | focus-visible/输入focus清晰；父组不出现第二重环 | disabled 不可编辑；查询 loading 图标不覆盖输入文字 | aria-invalid+danger边框+错误文字；readOnly可聚焦/选中/复制，subtle底，不伪装禁用 |
| Select/Combobox | 自有触发器与选项面板；hover和键盘highlight同底色 | 勾号+clay-soft；active option与已选项可以不同 | 输入/触发器环；选项焦点指示由库状态驱动 | loading保留已选值/缓存项，加载文案；disabled不可打开 | error连接到trigger/input；readOnly展示已选值，允许复制，不打开/修改 |
| Checkbox/Radio/Switch | control-border；hover加subtle底；没有OS外观 | checkbox明确勾号，indeterminate横线；radio中心点；switch位置+底色 | 控件环，不让整组每项同时环 | 禁用保持状态、文案与原因；异步保存可busy并锁当前动作 | 组级错误FieldGroup；无真实只读用途不扩展业务；需要只读时不可变但可访问 |
| Menu/Tabs/Disclosure | item悬停/选中态统一；Disclosure自有chevron | Tabs下划线+文字；菜单不用checkbox冒充普通操作 | roving tabindex由Radix；summary默认键盘行为 | disabled item不可选；加载不导致焦点突然消失 | 不发明这些控件的字段error态 |
| Table/Badge/Feedback | 中性分隔，行hover仅实际可交互时 | 状态文字+图标，颜色不独自传意 | 行内实际操作聚焦，不给只读整行按钮角色 | Skeleton结构与内容同尺寸；旧数据刷新保留 | 错误保留原因+重试；暂无数据/筛选无结果分开 |

Hover 不是唯一反馈。所有交互可只用键盘完成；pointer-disabled 不能代替语义 disabled。invalid + focus 同时存在时保留 danger 边框与 clay 外环；禁用优先于 hover/active。

## 5. 统一 API 与表单契约

```ts
// 以下是应用侧拟定 API，不是已安装库的类型声明。
type ControlSize = 'sm' | 'md'
type ChoiceOption = {
  value: string
  label: string
  description?: string
  keywords?: readonly string[]
  disabled?: boolean
}
type ChoiceProps = {
  id?: string
  name?: string
  value: string | null
  onValueChange(value: string | null): void
  onBlur?: () => void
  options: readonly ChoiceOption[]
  placeholder?: string
  size?: ControlSize
  disabled?: boolean
  readOnly?: boolean
  loading?: boolean
  errorMessage?: string
  onRetry?: () => void
  'aria-label'?: string
  'aria-labelledby'?: string
  'aria-describedby'?: string
  'aria-invalid'?: boolean
}
// Select: ChoiceProps + ref 到 HTMLButtonElement。
// Combobox: ChoiceProps + ref 到 HTMLInputElement；输入query是临时搜索状态。
// Autocomplete: value:string; onValueChange(value:string):void;
//   options:readonly ChoiceOption[]; onOptionSelect?(option:ChoiceOption):void;
//   其余可访问/状态属性同ChoiceProps，ref到HTMLInputElement。
```

- Select/Combobox 统一使用值回调，**不伪造 ChangeEvent**；原有 `event.target.value` 在领域调用点改为参数 `value`。空串是合法业务选项（跟随浏览器/所有状态）；`null` 才是未选择。Radix Item 不接空串，内部把所有值编码为 `v:${value}`，解码仅去掉第一段 `v:`；与 value 本来带 `v:` 也不冲突。库的空值映射为 null；不能把 `__custom__` 等内部命令写进业务字段。
- 严格 Combobox 中搜索文本和选中值独立；输入过滤不向 API 写临时 query；Escape/失焦回到已选标签。已失效资源由领域提供标记项和错误，组件不能自动改选第一项。
- Autocomplete 的字符串编辑每次正常 onChange 都回传；建议提交才触发 onOptionSelect。UA 留空、自定义模型 ID 都允许；IME composition 时 Enter 不选项、不提交表单。用库的成熟交互，并测试事件顺序。
- `Button` 保持 primary/secondary/ghost/danger，增加 size/loading/loadingText；默认 type=button，所有真实提交点显式 type=submit。既有 `<button>` 内卡片/导航通过同一视觉 primitives 或专用 composition 接入，不把 aria-current 误换成 aria-pressed。
- Input/Textarea API 基于 `ComponentPropsWithRef<'input'|'textarea'>` 保留 register 的 name/onChange/onBlur/ref；只省略冲突的原生 size 属性再提供 ControlSize。不添加 UI 层数字 parseInt；当前数字草稿和 schema 保持原样。
- Checkbox 保持 Radix `boolean|'indeterminate'`；Switch boolean；RadioGroup value/onValueChange。RHF checkbox布尔字段通过 `checked === true` 映射，不能把 indeterminate 写进 boolean 模型。
- FormField 最终采用 render-prop 把 `{id, 'aria-invalid', 'aria-describedby'}` 交给**实际 input/trigger**。不 clone 任意 Controller/Fragment。暂留旧 children 支持只为迁移，每个调用转完后移除隐式 clone。FieldGroup 使用 fieldset/legend，radio/checklist 的描述连到组，选项各有 label。

```tsx
// 领域接入目标示例；这些是设计合同，不是本轮落地代码。
<Controller name="releaseChannel" control={control} render={({ field, fieldState }) => (
  <FormField htmlFor="profile-release-channel" label="发布通道" error={fieldState.error?.message}>
    {(a11y) => <Select {...a11y} name={field.name} ref={field.ref}
      value={field.value} onValueChange={(value) => field.onChange(value ?? '')}
      onBlur={field.onBlur} options={channelOptions} />}
  </FormField>
)} />
```

`channelOptions` 来自既有领域 stable/preview 常量。RHF shouldFocusError/setFocus 必须能聚焦实际交互节点；页签内第一个错误先切换到对应页签再聚焦/滚入视口；不更改 schema、校验触发时机和 API payload。错误播报不重复、error 消失时恢复 hint 与 describedby。

T3 已实现的组合输入约定：SearchInput 使用受控 value:string、标准 onChange 和可选 onClear；清除后聚焦真实 input，不构造事件对象。PasswordInput 的 allowReveal 默认为 false，仅在领域原有能力允许时开启。Button 的 loadingText 使用布局占位保留宽度、原 label 保持为可访问名称；IconButton 必须提供 aria-label。标准输入 ref 可供 RHF register/Controller/setFocus 使用。

## 6. 下拉与大量选项

- 少量枚举 Select；资源/目录选择 Combobox；自由文本+建议 Autocomplete；多选保留可搜索 checklist。选项 label 与业务 value 分离，搜索匹配 label/value/keywords，保持原顺序，不引入远程搜索 API。
- Radix Select 使用完整 Trigger/Value/Portal/Content/Viewport/Item/ItemText/ItemIndicator/滚动按钮结构，而非只包 Root 和 Item。[Radix Select 官方结构](https://www.radix-ui.com/primitives/docs/components/select)
- 打开时定位已选项；ArrowUp/Down、Home/End、Enter、Escape 遵循相应原语；Select 的 typeahead 不截获中文输入；ComboBox 输入保留编辑键。Tab 不困在选项列表，按库标准完成/离开。
- 浮层 max-height 为可用高度减16px、上限320px；低高度屏幕不得遮住触发器；空集合显示“暂无选项”，无匹配显示“没有匹配项”，加载失败显示原因+重试。缓存选项仍能使用的情况下不得因远程目录失败清空列表。
- 语言/时区维持主线 `EnvironmentOptionField` 的“选择预设/自定义输入”模式，只把预设面板升级为可搜索；目录请求、options结构、当前值、未指定值、手动后setFocus与失败降级均不变。UA 在盘点快照中独立，默认用Autocomplete替代系统datalist；但最终复核发现主目录正在扩展同一EnvironmentOptionField到UA。若其最终实现已走目录预设+手动模式，则沿用该模式，用同一Combobox升级预设面板，不拆回旧UA字段。不能恢复旧hardcoded语言/时区/UA目录，不改后台目录协议。
- 验收样本0/1/50/500项，1000项为压力样本；200字中文名称、512字符ID、2048字符UA、相同label不同value、disabled、资源已失效、过滤后当前项不在结果。500项基础要求无输入丢字/滚动卡死；记录实测设备和耗时。以过滤响应p95≤100ms、打开≤200ms为测量目标（不是已测结果）。超过目标先减少无关重渲染；只有剖析证明需要才追加成熟虚拟列表实现，不预先造虚拟化框架。
- 发现模型的全选当前作用于完整发现集合，过滤不得静默改变全选范围；代理组过滤不得删除隐藏的已选成员。标签保留逗号/中文逗号/回车/失焦与去重规则。

## 7. 浮层、焦点与滚动

### 7.1 统一层级合同

| token / 层 | 值 | 规则 |
|---|---:|---|
| page / sticky | 0 / 10 | 页面与表头 |
| page popup | 30 | 无模态时Select/Menu/Tooltip |
| modal depth 0 | overlay50 / content51 / popup52 | 普通表单/代理抽屉 |
| modal depth 1 | overlay60 / content61 / popup62 | 浏览器表单内核管理 |
| modal depth 2 | overlay70 / content71 / popup72 | 内核删除确认；高于第二层列表 |
| toast | 100 | 不抢焦点，仍遵守当前模态可访问边界 |

Dialog frame 内提供位于滚动 body 外的 popup host；Radix与React Aria的Portal都优先挂到当前frame host，否则挂应用级host。宿主必须在模态可访问子树内、不受主体 overflow 裁剪。实现仅需要 React context 传 depth/host，不建立全局窗口管理器。不用页面各写 z-[9999]，也不靠同值 z50 与 DOM 顺序侥幸叠放。此合同须在 G0 与真正嵌套弹窗验收，API 实际支持需核对安装版本。

- Escape 一次只关闭最上层 popup，然后是最上层 modal；不把关闭建议传播为关闭表单。
- 现有 busy/dirty 策略优先：保存/删除进行中禁关闭，焦点留在当前层；dirty 时走已有未保存确认。AlertDialog 不以单击遮罩触发确认/丢弃；保持成熟原语的危险确认语义。
- 打开普通表单聚焦第一个可编辑控件；较长只读说明可先聚焦标题；危险确认默认“取消”。关闭回到原触发器，若触发器因删除消失，回到当前资源列表的合理位置/容器；继续复用 Modal 已有 fallback。
- Drawer 只是 Dialog 的右侧布局，宽`min(40rem,100vw-16px)`；不加手势关闭。当前所有原始 Dialog 使用同一 frame 布局约束和控制层，不同时维护 Modal/Drawer 的第二套行为实现。

### 7.2 自有滚动条

- 全应用滚动条：rail12px，thumb可见6px、最小长度24px、radius999、默认control-border/hover clay；track透明或surface-subtle，横纵相同。可拖动区域覆盖rail，而非只有可见细条。
- 根页面、表格横向区、textarea、诊断pre保留原生滚动机制，以统一CSS定义 Chromium scrollbar parts；避免标准 scrollbar-color/width 与 Chromium伪元素相互覆盖。原生 textarea resize corner 统一中性色，保留纵向调整能力；不自写拖拽调整算法。
- 局部选择列表使用 Radix ScrollArea 的 viewport、vertical/horizontal scrollbar、thumb、corner；统一可见策略为 **有溢出时常显**，防止 macOS “自动隐藏”与 Windows “常显”导致模块布局不同。Radix本身保留原生滚动，而不模拟滚轮行为。[Radix Scroll Area](https://www.radix-ui.com/primitives/docs/components/scroll-area)
- `min-height:0`、max-height、必要的 `scrollbar-gutter:stable` 用于主体；不能同时给 Radix overlay rail 再重复预留原生gutter。双滚动只在有明确边界的局部列表出现，表单不能每个区块各造一个滚动窗。
- 不拦截 wheel/trackpad；在嵌套列表边界使用 `overscroll-behavior:contain` 防止滚动泄漏到遮罩底页。可键盘滚动区域提供 label、按需求 tabIndex=0，PageUp/Down/Home/End 可达；聚焦表单字段时不被固定footer遮挡。
- `forced-colors: active` 允许系统高对比色替代品牌色与thumb，保留边框/焦点/勾号；这是辅助功能适配，不是回退系统 select 面板。

### G0 实施补充（2026-09-12，confirmed）

T3续验新增 UI-G0-01 偶发关闭待查项，后续重复通过不代表根因已修复；详见 `docs/design-system/verification/text-controls.md`。T5前必须重新评估G0。

- Dialog/AlertDialog 的模态 Portal 继续由 Radix 挂在 body；每层 Content 内提供 `data-overlay-host`，位于可滚动主体外。React Aria 的选项弹层挂到当前 host，保证属于该层可访问子树。未来 Radix 选择/菜单弹层接入同一 host 属于 T5/T6，不把当前所有 Portal 都描述为已迁移。
- `data-af-popup` 标识本层 React Aria 活跃弹层。Radix document capture 的 Escape 会先于组合框键盘处理器；父 Dialog 在发现活跃弹层时 preventDefault，组合框继续执行自己的 Escape/revert。退出中的弹层不阻塞父层。组合框未展开时保留原 busy 和关闭回调。
- G0 探针精确锁定 `react-aria-components@1.21.1`，局部使用其 `UNSTABLE_portalContainer`；该版本类型已标 deprecated。T5 应核对推荐的 PortalProvider 接口并复跑 G0，业务层不得依赖这个实现细节。
- 该版本 Popover 不提供 `--available-height` CSS 变量。使用 `maxHeight={320}` 与弹层 `overflow-y:auto`，由定位引擎继续按视口收缩；不要根据不存在的变量定义滚动约束。

## 8. 动效与反馈

- 普通 hover/focus 100ms，checkbox/switch选中120ms；弹窗/抽屉150ms opacity+最多8px位移，不滑满整屏。Toast150ms进出，正常成功提示2600ms后退场；下载width300ms linear；Spinner旋转700ms linear。Spinner随Button基础任务交付，反馈任务复用它，避免Button与反馈模块相互等待。
- 沿用设置 `data-motion=full/reduce` 与系统减少动态效果规则；reduce 时不旋转、不脉动、不位移，用静态图标+状态文字表达处理中，进度仍更新。无全局动效新偏好字段。
- Toast 不抢焦点，success/info用polite；主要错误保留就地可恢复反馈，不只用短时通知。统一 Toaster 的图标、tone和关闭按钮；已有页面挂载位置与事件API保持，避免本轮改通知状态机。
- Skeleton aria-hidden，容器单一status播报；刷新保留旧数据时只标记busy，不把可用内容替换成空白。下载未知百分比不伪造进度，aria-valuenow省略；错误/取消/重试文本仍来自现有领域状态。

## 9. 正式组件展示/验收页

新建 `shared/ui-lab/UiLabPage.tsx`，通过 renderer `main.tsx` 的 `import.meta.env.DEV && location.hash === '#/__ui'` 条件懒加载，入口为开发窗口 `#/__ui`。不加入ApplicationHeader，不依赖ApiProvider或真实账户，不改变生产页面默认启动；打包时该模块及fixture必须消失。不为此引入 Storybook。

展示页分组：Tokens；Actions；Text fields；Choice controls；Menus/tabs/disclosure；Overlays；Tables/feedback；Scroll/zoom。每个案例标注组件API、实际使用页面、状态与验收ID；可切换32/40密度、长文本/0/500项、invalid/disabled/readOnly/loading、reduced motion。提供键盘操作说明、RHF submit/setFocus/reset真实表单案例，以及三层弹窗+内部组合框+长表单场景。

展示页 fixture 只属于验收样本；真实页面仍连原后端，禁止用演示数据掩盖业务回归。验收截图按平台/缩放/场景命名，在 `docs/design-system/verification/` 记录结果、应用提交、Electron版本、OS版本、操作步骤和缺陷；未跑记录“未执行”。

## 10. 可审查验收清单与阻断项

| ID | 自动验收 | 真实应用人工验收 / 阻断条件 |
|---|---|---|
| A01 基线 | Git保护路径无变动；main快照差异重新核对 | 不覆盖语言/时区目录或代理最新协议逻辑 |
| A02 令牌 | 颜色对比计算；非法raw色/尺寸扫描 | 暖灰/黏土棕不变，真实字段/弹窗密度一致 |
| A03 按钮/输入 | 类型、ref、submit、loading重复点击、invalid/readOnly测试 | 中文输入法、粘贴/选择/复制、密码显隐、自填充样式无系统突变 |
| A04 选择 | Select/Combobox empty/null/disabled/键盘/IME/RHF测试 | 不出现原生select/datalist面板，500项/长文可用 |
| A05 勾选与开关 | 勾号/混合态、radio方向键、Switch键盘和禁用 | 地点库存与capability不可被视觉修改绕过；隐藏成员选中不丢失 |
| A06 浮层 | 三层Dialog+popup Escape、busy/dirty/focus-return、Portal测试 | 配置→管理内核→删除确认全程可操作，无背景可点/错误遮挡 |
| A07 滚动 | 结构、scrollbar类覆盖、焦点滚动测试 | 鼠标滚轮/触控板/拖拽thumb/横向滚动/键盘；mac自动与常显、Windows均一致 |
| A08 反馈 | role/status、timer、reducedmotion、未知进度测试 | 错误可恢复；模型继续就地反馈；Toast不遮主操作 |
| A09 展示页 | DEV可达、production产物无UiLab marker/fixture | 所有场景有编号、对应真实页面链接/说明 |
| A10 浏览器/内核 | 保留现有profile/kernel套件；新控件语义断言 | 创建/编辑/复制/指纹/删除，四Tabs、UA、语言/时区手动、资源失效、License/下载/取消 |
| A11 代理/池 | 保留proxy套件，检测协议/筛选/分页/成员值回归 | 连接设置、协议选择、地点radio、轮换disabled、组编辑/删除、横向表格 |
| A12 模型 | 保留models套件，ID自由输入/附加数据/标签/全选语义 | 三步向导、模型增改删/测试、菜单、侧栏、只读ID与密钥不更换 |
| A13 设置/总览 | 保留settings/dashboard/App套件 | 缩放/动效/诊断/路径/重连、总览全部反馈状态 |
| A14 平台 | 构建、类型、lint、源码残留扫描；记录运行OS | macOS和Windows分别100/125/150/200%；1280×800与1440×900，补1024×768；无不可达操作 |
| A15 无障碍 | DOM roles、labels、describedby、基础axe扫描 | macOS VoiceOver、Windows NVDA关键流程；高对比和键盘全程；未跑不得宣称通过 |

合入门槛：A01–A13自动检查通过且当前平台真实页面通过；另一平台未执行时只能标“平台验收未完成”，不能声称系统控件专项完成。A14/A15逐平台补齐后才关闭专项。纯静态色值、jsdom和组件展示截图均不能替代真实应用验收。

## 11. 已确认的设计决策

用户已确认本规格整体方向：在 desktop shared 内补齐现有 Radix，组合框采用隔离封装的成熟行为基础；暖灰/黏土棕+32/40密度+更清晰控件边界；自有滚动条；不改变业务流程。G0 验证失败或后续实际数据要求新的交互能力时，单独提交变更依据。T0–T2 仅记录已验证事实，未执行的 G1/G2/G3 不标记完成。


### T4 实现补充（2026-09-12）

实现落点保持 desktop shared。Checkbox/RadioGroupItem 自身32×32px命中区包含18px图形；Switch自身44×32px包含44×24px轨道和20px滑块。调用方label可继续扩展命中区，不需要用伪元素越界制造点击区域。Checkbox图形按 Radix Indicator 的 data-state 切换，以兼容 checked 和 defaultChecked 的半选状态；不增加本地冗余 checked state。

Disclosure 使用 `summary: ReactNode` 和原生 details props（包括 ref/open/onToggle）；summary必须是描述性内容，不在其中放第二个交互按钮。需要受控时由调用方在 onToggle 读取 currentTarget.open。隐藏系统 marker 并绘制 Phosphor chevron，不自造 aria-expanded、键盘处理或不可靠的高度动画。

RadioGroup 的 Root 提供组名/值与方向，错误绑定到组；需要 RHF setFocus 时将 ref 连接首个可用 Item。零间隔合成 keydown/keyup 可命中 Radix 异步焦点竞态，已登记 UI-T4-01；正常顺序的自动验证不能替代实体键盘/读屏验收。详见 `docs/design-system/verification/toggle-controls.md`。

## 2026-09-12 实施补充（confirmed）

共享 ChoiceProps 补 `clearable?: boolean`；保持已有可空用例默认可清除，领域固定枚举明确传 false，避免出现接口不接受的空值。PasswordInput 仅代理原有显隐入口传 allowReveal。Autocomplete 的输入草稿与显式候选选择分开，保证元数据仅随候选提交。API/后端/数据不变。
