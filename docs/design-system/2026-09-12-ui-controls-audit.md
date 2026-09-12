# AutoFlow 实际控件盘点

- 日期：2026-09-12；状态：confirmed（源码事实），建议部分为 proposed。
- 范围：renderer 控件、真实入口及样式；未启动或操作正在使用的应用，未进行本轮视觉、辅助技术或跨平台验收。
- 置信度：源码与静态入口判断高；运行时外观、性能和跨库浮层兼容性未验证。
- 完整逐点证据：[使用点明细](2026-09-12-ui-controls-usage.md)、[含 import、属性、文件 SHA-256 的机器清单](2026-09-12-ui-controls-source-inventory.json)。下文路径均相对 `apps/desktop/src/renderer/`；行号必须结合快照标签读取。

## 1. 基线与隔离

首次检查实际终端在主目录，并非独立 worktree。主目录当时 HEAD 为 `c7c3021`，存在并行未提交修改。已有 `~/.codex/worktrees/e7ce/autoflow` 停在 `6a3b401`，与主线相差 481 个文件，不能据此认定当前系统缺少业务页面。本任务另建：

- 工作目录：`/Users/zhangtiancheng/Documents/projects/autoflow-ui-controls-plan`。
- 分支：`codex/ui-controls-plan`，起点 `c7c3021`；只写本任务文档。
- 盘点过程中主目录推进到 `60bc035`，含 `f37a5e1` 语言/时区目录与 `60bc035` 代理检测协议提交；最终核对又推进至 `15cf2e8`，新增模型品牌资源和ProviderLogo更新，不改变控件计数。机器清单 `committed` 表示本任务起点，`main-working` 表示固定时点只读快照（时间见JSON），不混用行号。
- `main-working` 中 automation studio 草稿仍不在 App 入口链；主目录文档及草稿的未提交状态不由本任务处理。
- 最终复核时主目录又出现进行中的 User Agent 目录扩展：`EnvironmentOptionField.tsx` 的 name 加入 userAgent，字段id和当前值显示做了适配；后台目录、presets、generated类型也有并行修改。本次只读识别，不复制、不覆盖。固定快照中的UA仍为datalist；这不代表并行任务结束后的状态。实施T0须检查其最终接线，若UA已复用EnvironmentOptionField，就保留该模式和数据源，仅统一预设选择控件，不能倒退为旧硬编码UA目录。
- 未修改主目录、后端、生成 API 类型、业务数据或系统凭据。实施前必须以届时已提交主线重新核对差异，不能把此文档分支的旧业务代码覆盖回去。

已读约束：`AGENTS.md`、`.ai/README.md`、`.ai/memory/project-context.md`、四份现有 ADR、`docs/PROJECT_STRUCTURE.md`、`docs/architecture/README.md`。模型保留已有供应商侧栏及分步流程；浏览器不新增模块侧栏。代理 capability 和设置归属继续由现有领域逻辑决定。

## 2. 入口与范围

| 类别 | 实际入口/证据 | 判定与本次决策 |
|---|---|---|
| 应用壳 | `main.tsx` → `app/App.tsx`；`app/ApplicationHeader.tsx:12–13` | 真实入口；导航按钮、重连反馈纳入统一；不增加业务导航项 |
| 浏览器配置 | `domains/profiles/pages/BrowserManagementPage.tsx` | 真实入口；搜索、筛选、卡片操作、四分区表单及确认弹窗全部纳入 |
| 内核 | `profiles/components/ProfileFormDialog.tsx` → `domains/kernels/components/KernelManagerDialog.tsx:202` | 嵌套弹窗，不是独立路由；License、版本筛选、下载反馈、删除确认全部纳入 |
| 代理与代理池 | `proxies/pages/ProxyManagementPage.tsx` → `ProxyFleet`、`LocalProxyGroups`、`ProxyDetailDrawer`、`ProxyConnection` | 真实入口；包含连接设置、详情抽屉、地点/轮换条件区和本地组编辑，不以 capability 暂时禁用为由漏检 |
| 模型 | `models/pages/ModelManagementPage.tsx` → 供应商侧栏、目录、三步向导、模型编辑/测试/删除 | 真实入口；保留领域布局和既有就地反馈，不借统一控件改变模型交互规格 |
| 设置 | `settings/pages/SettingsPage.tsx`、`settings/components/DiagnosticDialog.tsx` | 真实入口；Tabs、缩放/动效选项、路径/诊断滚动、复选确认及操作反馈 |
| 总览 | `dashboard/pages/DashboardPage.tsx`、`domains/dashboard/components/DashboardCards.tsx:26` | 真实入口；资源入口卡、加载/错误/空数据反馈；无表单，不制造新控件 |
| 独立预览 | `proxy-preview.tsx` 与 `apps/desktop/src/renderer/proxy-preview.html` | 非主应用入口；可补齐同一组件 API 以确保构建，但不能当作真实页面验收 |
| 未接入草稿 | 主目录 `domains/automation/studio/pages/StudioPage.tsx` | 静态入口不可达，单列原始清单，不排本轮领域迁移、不改草稿 |
| 共享未接入 | `shared/components/ResourceState.tsx`、`shared/components/ui/select-radix.tsx`、`shared/components/ui/tooltip.tsx` | 文件存在不等于页面在用；复用前补全或明确范围 |
| 包骨架 | `packages/ui/.gitkeep`；根 package.json workspace 仅 `apps/desktop` | 本轮不搬包；将可复用控件继续落在 desktop shared |

入口分析使用 TS AST 的相对静态 import/export 传递可达性。它是文件级保守分析，不证明每个导出都渲染；不能仅凭 JSX 标签未命中而判定 Radix Primitive 文件未使用。列表中 map 的一个 JSX 位置会产生多个控件，计数不是屏幕实例数。

## 3. 数量口径

| 项目（源码位置） | committed c7c3021 | main-working 15cf2e8 |
|---|---:|---:|
| renderer 非测试 ts/tsx/css 文件 | 89 | 91 |
| main.tsx 静态可达文件 | 83 | 84 |
| 领域 `<Select>` 调用 | 19 | 21 |
| 页面直接 `<select>` | 1 | 1 |
| 需要迁移的 select 调用总位置 | 20 | 22 |
| 领域 `<datalist>` | 3 | 1 |
| 领域直接 `<input>` | 3 | 3 |
| 应用/领域直接 `<button>` | 11 | 11 |
| 领域 `<details>` | 3 | 3 |
| 真实表格 | 3 | 3 |

共享实现中另有 `<select>` 1 处、`<input>` 1 处、`<button>` 1 处，不能重复计入调用总数。最新 `EnvironmentOptionField` 的一个 Select 声明被语言、时区两个字段复用。新增的第 21 处共享 Select 调用是代理“检测协议”，已计入最终范围。

## 4. 控件家族、现有能力与决定

| 家族 | 源码依据与调用位置（未注明者使用 committed 行号） | 已有能力 / 缺口 | 决策与真实需求 |
|---|---|---|---|
| Button / IconButton | `shared/components/ui/button.tsx`；`app/ApplicationHeader.tsx:12–13`、`domains/dashboard/components/DashboardCards.tsx:26`；`domains/models/components/ModelDirectory.tsx:19`、`shared/components/Modal.tsx` 关闭按钮 | cva 四个 variant、disabled/focus；无统一尺寸、icon、loading API；11 处直接 button，有 h7/h8/h9 覆盖 | 复用 Button；补 size/loading/IconButton；导航/资源卡保留语义薄封装，不把卡片强行变普通实心按钮 |
| Input / Textarea | `shared/components/ui/input.tsx`、`shared/components/ui/textarea.tsx`；`domains/profiles/components/BasicFields.tsx:15/18/22`、`domains/profiles/components/AdvancedFields.tsx:22/25`、`domains/models/components/ModelForm.tsx:25/34` | 基本边框/禁用/焦点；invalid 与 read-only、自填充等视觉不完整 | 补齐状态/ref/尺寸；继续语义 input/textarea，不重写文字编辑 |
| Search | `domains/profiles/pages/BrowserManagementPage.tsx:84`；`domains/proxies/components/ProxyFleet.tsx:61`；`domains/models/components/ModelDirectory.tsx:17`；供应商目录/侧栏/模型发现；`domains/proxies/components/LocalProxyGroups.tsx:122` | 部分用 type=search，部分自行放搜索图标；清除/可访问名称分散 | 统一 SearchInput（Input 组合），清除操作和图标留位；保持每个页面原筛选逻辑 |
| Number | `domains/profiles/components/EnvironmentFields.tsx:78/82`（main 为85/89）、`domains/models/components/ModelForm.tsx:29`、`domains/proxies/components/ProxyDetailDrawer.tsx:212`（main219） | 当前数字字段主要是 text + inputMode=numeric；领域持有字符串与校验 | 不造 NumberStepper；统一 Input numeric 视觉与输入策略，保留草稿字符串和领域范围校验；不引入系统 spinner |
| Password | `domains/kernels/components/LicensePanel.tsx:47`、`domains/models/components/ProviderConnectionStep.tsx:22`、`domains/proxies/components/ProxyConnection.tsx:139` | password 输入；代理 Key 已有显示切换；模型空值表示不更换 | PasswordInput 复用 Input；显隐作为显式可选能力，只在现有允许显示处接入；不改变凭据取回/保存方式 |
| Checkbox | `shared/components/ui/checkbox.tsx`；`domains/models/components/ProviderModelsStep.tsx:16`、`domains/settings/components/DiagnosticDialog.tsx:45`；`domains/proxies/components/LocalProxyGroups.tsx:124` 原生 checkbox | Radix Root 无 Indicator；组成员绕过共享封装 | 补勾号/混合态/焦点/禁用；替换组成员原生 checkbox；选中范围保持现有规则 |
| RadioGroup | `domains/proxies/components/ProxyDetailDrawer.tsx:198`（main205）原生 radio 地点列表 | 没有共享 RadioGroup；可用性由地点库存及 capability 决定 | 新增 Radix RadioGroup，仅用于现有地点选择，保留禁用原因 |
| Switch | `shared/components/ui/switch.tsx`；环境自定义尺寸、KernelProxyFields:BooleanSwitch、代理启用/轮换、供应商启用 | Radix Thumb 已有，自有焦点/disabled/read-only 规范不足 | 补齐共享状态，不改变业务开关语义 |
| Select | `shared/components/ui/select.tsx` 原生 select；未接入 `shared/components/ui/select-radix.tsx` | 后者缺 Viewport、ItemText、Indicator 等完整结构；目前全部真实下拉仍走系统面板 | 完成 Radix Select，先独立验证后逐点迁移，最终删除旧原生封装；不是替换一个 import 就结束 |
| 可搜索单选 / 自由输入建议 | `EnvironmentOptionField:42`（main）、`domains/profiles/components/EnvironmentFields.tsx:106` datalist（main）；`domains/models/components/ModelIdInput.tsx:11–13` 手写 listbox | 语言/时区已从后端取目录并允许手动；UA 系统 datalist；模型建议缺完整组合框键盘机制 | 新增受控 Combobox/Autocomplete，推荐 React Aria ComboBox 行为封装；保留自定义输入；数据仍由领域提供 |
| 多选 | `domains/models/components/ProviderModelsStep.tsx:15–16` 模型发现列表；`domains/proxies/components/LocalProxyGroups.tsx:122–124` 成员列表；`domains/models/components/ModelForm.tsx:31–32` 标签 | 前两者是可筛选 checklist；标签是自由文本、逗号/回车/失焦提交与去重 | 复用 Checkbox + SearchInput + ScrollArea；标签抽到模型领域 TagInput；本轮不造无调用方的通用下拉 MultiSelect |
| 菜单 / Popover / Tooltip | `domains/models/components/ModelDirectory.tsx:19`、`ProviderDetail` 的 DropdownMenu；`shared/components/ui/tooltip.tsx` 未使用 | 菜单已有 Radix 键盘基础；浮层样式/层级分散；无独立 Popover 用户需求 | 补菜单与 Tooltip；Popover 只作为选择建议内部实现，不暴露新业务面板；Tooltip 服务纯图标操作/截断文本，不替代 label |
| Dialog / AlertDialog / Drawer | `shared/components/ui/dialog.tsx`、`alert-dialog.tsx`、`shared/components/Modal.tsx`；profiles、kernels、proxies、models 全部弹窗 | 已有 busy 防关闭、Modal 焦点返回及领域 dirty guard；两个原语浮层均 z50；代理抽屉直接写 Dialog 布局 | 保留行为与测试；统一 frame/关闭按钮/层级与滚动；Drawer 用 Radix Dialog 的边缘 frame，无触摸拖拽新库 |
| Tabs / 折叠 | `shared/components/ui/tabs.tsx`；ProfileFormDialog、ProxyDetailDrawer、SettingsPage；AdvancedFields:13、ModelForm:34、ModelTestPanel:10；SettingsPage:47 自写展开 | Tabs 已有 Radix 状态；原生 summary 箭头样式未统一 | 补 Tabs 键盘可见焦点；轻量 Disclosure 统一现有折叠，只定制 details/summary 标记与样式，保留原生无障碍行为 |
| 表格 / 分页 | `domains/proxies/components/ProxyFleet.tsx:84/123`、`domains/proxies/components/LocalProxyGroups.tsx:38`、`domains/models/components/ModelDirectory.tsx:18` | 三张语义 table，样式分散；代理真实 offset/limit 上下一页，无共享分页 | 薄 Table 样式与 Pagination（仅上一页/下一页/范围）；不引入 TanStack Table、不制造排序和页码选择需求 |
| 反馈 / 加载 / 空态 | `shared/components/Toaster.tsx` 三个页面挂载；`shared/components/State.tsx`；未接入 ResourceState；领域角色 status/alert、ProxyPageSkeleton；`domains/kernels/components/KernelOperationStatus.tsx:37` | Toast 2600+150ms，tone 尚无相应样式；State 的 `.state` 未见定义；反馈重复；下载已区分未知进度 | 复用 Toaster API；统一 Alert/EmptyState/Skeleton/Spinner/Progress 展示，不迁移查询状态机；模型就地测试反馈保留，不新增 Toast 流程 |
| ScrollArea / 滚动条 | `styles/index.css` 无滚动条规则；列表/表格/弹窗已有 overflow，详见下节 | 系统默认外观；无共享 ScrollArea | 全局 Chromium 滚动条 token 化；局部选项/长列表使用 Radix ScrollArea；不劫持 wheel、不模拟滚动位置 |

没有实际生产调用的日期选择器、颜色选择器、滑块、文件上传、多选下拉、树表、拖拽排序、复杂数据网格，不列本轮开发任务。Electron 目录选择器是平台集成，不属于 renderer 控件重做范围；不改 IPC、窗口标题栏或系统选择文件界面。

## 5. 全部 select 决策账本（main-working）

| 文件:行 / 字段 | 迁移目标 |
|---|---|
| `domains/models/components/ModelDirectory.tsx:17` 模型状态 | Select，替换直接原生 select |
| `domains/models/components/ProviderConnectionStep.tsx:19` 协议种类 | Select |
| `domains/profiles/components/EnvironmentFields.tsx:91` 视口；99 色彩；102 人类预设 | Select；空串是有效业务选项，不能丢失 |
| `profiles/EnvironmentOptionField.tsx:42` 语言/时区复用 | Combobox 选择预设 + 原有手动模式；保留当前值、未指定值、加载失败后手动输入 |
| `domains/profiles/components/KernelProxyFields.tsx:50/63/69` 内核/发布通道/代理模式 | Select；保留内核不可用值、公开版强制 stable、代理模式清空关联选择 |
| `domains/profiles/components/KernelProxyFields.tsx:76/82` 固定代理/代理池 | Combobox 严格单选；缓存缺失项只展示为不可用，不擅自清空 |
| `domains/profiles/pages/BrowserManagementPage.tsx:86` 代理模式筛选 | Select |
| `domains/proxies/components/LocalProxyGroups.tsx:122` 成员健康筛选 | Select |
| `domains/proxies/components/ProxyDetailDrawer.tsx:82/137` 检测协议/凭据协议 | Select；保留 SOCKS5 默认与用户明确协议，不恢复旧逻辑 |
| `domains/proxies/components/ProxyDetailDrawer.tsx:203/215` 地点运营商/轮换模式 | Select；保留 capability gating |
| `domains/proxies/components/ProxyFleet.tsx:63/69/73` 健康/运营商/城市 | 健康 Select；运营商与城市 Combobox，以当前已提供选项过滤，不扩 API 数据范围 |
| `domains/settings/pages/SettingsPage.tsx:49` 缩放/减少动效 | Select；保留设置存储枚举与即时应用 |

另外：固定快照中的 User Agent datalist 纳入替换；若并行UA目录任务完成后仍是datalist则改Autocomplete，若已接入EnvironmentOptionField则随该组件统一可搜索预设与手动输入，不重新改回独立字段；ModelIdInput 改同一成熟输入建议基础但保留选项附带的领域数据回调。模型标签不是模型 ID 建议，不混用。最新ProviderLogo与品牌资源属于已实现品牌视觉，不用公共操作图标替换；品牌色列为扫描例外，不能因此放过字段自定义色。

## 6. 滚动与嵌套账本（main-working）

| 使用点 | 拟用方式 / 不能破坏的行为 |
|---|---|
| `domains/profiles/components/ProfileFormDialog.tsx:177`；`shared/components/Modal.tsx` body | 一层主体滚动，固定标题/页签/底部操作；错误字段自动滚入可见区域 |
| `domains/kernels/components/KernelManagerDialog.tsx:203` | 嵌套于配置表单；内核主体滚动，关闭后返回“管理内核” |
| `domains/proxies/components/ProxyDetailDrawer.tsx:64/73` | 右侧 Dialog frame 主体纵向滚动、窄窗口页签横向滚动；焦点不漏回底页 |
| `domains/proxies/components/ProxyDetailDrawer.tsx:204` 地点；`domains/proxies/components/LocalProxyGroups.tsx:123` 成员；`domains/models/components/ProviderModelsStep.tsx:16` 模型发现 | 局部 ScrollArea；列表标签、键盘滚动、选择后不跳页顶 |
| `domains/proxies/components/LocalProxyGroups.tsx:112` 编辑；`domains/models/components/ModelIdInput.tsx:12` 建议 | 编辑 frame；建议浮层 max-height 随可用高度限制 |
| `domains/proxies/components/ProxyFleet.tsx:84`、`domains/proxies/components/LocalProxyGroups.tsx:38`、`domains/models/components/ModelDirectory.tsx:18` | 保留语义 table 与横向原生滚动，统一自绘滚动条；纵向随页面；200% 时操作列可滚到 |
| `domains/settings/components/DiagnosticDialog.tsx:46` pre；`domains/settings/pages/SettingsPage.tsx:50` code | 诊断内容可复制、双轴滚动；路径单行可完整访问，不截断真实值 |
| dropdown/menu/tooltip portal | 使用同一浮层宿主与 token；页面 overflow-hidden 不裁剪 popup |

## 7. 关键结论与限制

1. 这是共享封装不完整、原生入口绕过以及状态规范不足的组合问题，单改颜色文件无法解决。
2. 现有表单 dirty/提交保护、资源过期校验、代理 capability、模型反馈策略是已实现能力，应保留测试，不借换皮重写业务。
3. `FormField` 把属性 clone 到直接子元素，遇到 Controller、Fragment、复合 div 时不能保证属性落在实际交互节点；需要显式控制元素绑定与 RHF focus 验收。不能未经测试宣称 React 19 ref 已损坏。
4. 现有 line/surface 对比约 1.43:1，line-strong/surface 约 1.73:1；不能把它们宣称为合格控件边界。保留轻分隔线，新增更深的 control-border。
5. 本轮验证为源码/目录/文档验证；没有执行 Windows、macOS 真机控件验收，也没有测量跨库弹窗兼容或性能。验收方案见设计和计划，状态均为待实施。
