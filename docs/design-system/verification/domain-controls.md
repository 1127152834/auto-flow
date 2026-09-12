# 领域控件接入 T8–T12

日期：2026-09-12。状态：implemented；人工平台验收见 `ui-controls-platform-matrix.md`。工作区为 `autoflow-ui-controls-plan` / `codex/ui-controls-plan`，未写主目录。

所有下列路径以 `apps/desktop/src/renderer/` 为根。完整调用位置、import 别名、实际入口及未接入文件见本目录 `ui-controls-audit.json`；历史盘点保留原样，不能拿历史“原生 Select”数量当当前状态。

| 范围 | 正式落点与变化 | 保持的领域行为 / 验证 |
|---|---|---|
| 浏览器配置 | `domains/profiles/components/{EnvironmentFields,EnvironmentOptionField,KernelProxyFields,AdvancedFields,ProfileFormDialog}.tsx`；目录组合框、显式 FormField/RHF 绑定、Disclosure、共享分页/搜索/空态 | locale/timezone/UA JSON、手动模式、Stable/Preview、代理模式 reset、不存在资源回显并禁止选中、跨页签错误聚焦、未保存确认；原有领域测试和真实 Electron |
| 内核弹窗 | `domains/kernels/components/{LicensePanel,KernelOperationStatus,KernelManagerDialog}.tsx`；PasswordInput、Progress、统一状态色 | 唯一 CloakBrowser；仍从配置表单进入，HTTP/SSE、License、下载协议均不改；真实嵌套打开/返回焦点，远端下载不伪造成功 |
| 代理/代理组 | `domains/proxies/components/{ProxyFleet,LocalProxyGroups,ProxyDetailDrawer,ProxyConnection,presentation}.tsx`；Table/Pagination、Combobox、Checkbox/ScrollArea、Drawer、PasswordInput、Badge | SOCKS5 优先与协议 payload、成员数组顺序/移动/搜索保持、capability/retryAfter 锁、凭据显隐；领域测试 + 页面 fixture；真实空连接表单验证 |
| 模型 | `domains/models/components/{ModelIdInput,TagInput,ModelForm,ModelDirectory,ProviderCatalogStep,ProviderConnectionStep,ProviderModelsStep,ProviderSidebar}.tsx` | Autocomplete 明确区分键入 ID 与选择候选；选择候选才回填 context/displayName。保留标签草稿、中文逗号、去重、IME 分支、只读模型 ID、完整发现集合全选、现有向导和关闭语义 |
| 设置/总览/壳 | `domains/settings/pages/SettingsPage.tsx`、`DiagnosticDialog.tsx`、`domains/dashboard/`、`app/{App,ApplicationHeader}.tsx` | 缩放 string→90/100/110/125 数字，motion system/reduce/full 不变；Disclosure、诊断 Checkbox、共同 Skeleton/Alert/EmptyState、导航 Button 与 aria-current；连接/重连代码不改 |
| 共享层收口 | `shared/components/ui/select.tsx` 为唯一 Select；删除 `select-radix.tsx` 和未使用 `ResourceState.tsx`；`FormField` 只接受显式 render-prop | 不模拟 ChangeEvent，不 clone 子组件；`clearable={false}` 用于领域固定枚举，防止新清除按钮引入非法空值；可空的共享示例仍验证 null 与空字符串分别编码 |

## 自审发现与修复

- Autocomplete 原先根据“输入文本恰好等于候选 ID”提前标为已选，点击同一候选没有 selection-change，导致元数据不回填。现在保存单独的显式选择状态；真实模型页面 fixture 和 ModelEditor 用例验证回填。
- 选择器替换后不能保留 `e.target.value`，设置显式映射字符串为原数字枚举；代理轮换回调参数避免遮蔽领域 `value` 对象。
- Proxy API Key 保留原有显隐能力，License 和模型 Key 按原能力默认不展示显隐按钮；不扩大凭据权限。
- 固定枚举不提供额外清除动作；不可用的内核/代理选项保留显示但禁止选择。
- 样式中的固定 z-index 退出，浮层使用层级变量；既有测试从旧 class 改为验证层级变量，真实焦点/缩放仍由 Electron 检查。
- 旧测试直接对原生 select 发 change/selectOptions 已改为打开真实 listbox 选项；模型建议需先打开/搜索。没有删掉业务 payload、顺序、关闭/恢复、读写冲突断言。

## 审计方法与边界

`npm run audit:ui` 使用 TypeScript AST 扫描全部 renderer TS/TSX/CSS，并沿 `main.tsx` 的 import/reexport/dynamic-import 图记录真实入口。JSX Fragment/map、import alias、字符串标签 alias 均有扫描测试。精确 allowlist 限文件、元素、用途；两个表单隐藏 input 额外要求 `type="hidden"`，不能放过同文件的可见输入。

原生 input/textarea/button 只在共享语义基础内保留，Disclosure 独占 details/summary。Radix/React Aria 生成的隐藏表单节点不当作原生视觉面板；自动/真实列表验证面板是应用绘制的 listbox。

样式线索是人工复核输入，不是视觉通过证明：

- `styles/tokens.css` 是唯一主题值定义；ProviderLogo 的白底保留官方品牌图承载背景。
- `outline-none` 仅在共享浮层/菜单/列表焦点管理区域，真实触发器仍有 focus ring，选项使用库的 highlighted/focused 状态。TabsContent 不画额外外框。
- `overflow-auto` 保留在表格、诊断预览、Dialog 内容、组列表和候选列表；所有滚动容器使用 `styles/controls.css` 的 Chromium 滚动条样式；需独立轨道的代理组使用 ScrollArea。
- Toast 用 layer-toast；Dialog/Menu/Select/Combobox 共用 OverlayHost。无领域固定数值 z-index。

未接入文件单列：`proxy-preview.tsx` 是独立原型入口；`app/query-provider.tsx` 是未使用旧入口；`domains/proxies/index.ts` 是未被主入口引用的导出；`vite-env.d.ts` 仅类型声明。`LocationPicker`、`RotationForm`、`AllowlistForm` 是保留在代理组件文件中的能力实现，当前真实代理页仍由 capability 限制远程写功能；本轮没有把它们接成新的业务能力。RadioGroup/地点选择有组件测试，不能据此宣称远端地点切换已联调。

正式组件展示仍为开发模式 `#/__ui`，覆盖 T0–T7 的状态和交互；生产构建扫描必须确认实验室/专用长样本未进入包。最终验收依赖真实应用和独立页面 fixture，两者分别记录，不以展示页替代页面回归。
