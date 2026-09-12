# AutoFlow Unified UI Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 统一全部已实现 AutoFlow 页面及弹窗的基础控件视觉、API、键盘与滚动体验，同时保留业务契约和行为。

**Architecture:** 在 desktop renderer shared 内补齐现有 Radix/shadcn 风格组件，先令牌、再控件和展示页、再领域接入。严格单选和自由输入建议使用隔离的 React Aria ComboBox 行为基础；业务数据和校验继续由领域提供。packages/ui 不扩建，后端和接口不变。

**Tech Stack:** Electron、React 19、TypeScript、Tailwind 4、现有 Radix、React Hook Form/Zod、Vitest/Testing Library；拟新增 Radix RadioGroup/ScrollArea、react-aria-components；浏览器级验收拟增加 Playwright 与 axe-core 开发依赖。

---

- 日期：2026-09-12；状态：**approved，用户2026-09-12确认；当前执行T0–T2，T3之后未实施**。
- 设计依据：[设计规格及A01–A15验收矩阵](../specs/2026-09-12-unified-ui-controls-design.md)。源码依据：[盘点](../../design-system/2026-09-12-ui-controls-audit.md)、[逐点清单](../../design-system/2026-09-12-ui-controls-usage.md)。
- 当前文档分支 `codex/ui-controls-plan` 从 c7c3021 建立；实施必须先核对/接入最新已提交主线（盘点截止15cf2e8）。严禁把旧 checkout 中语言/时区硬编码、旧代理协议默认值覆盖主线。
- 所有文件名以下均为仓库根相对精确路径；命令在**任务独立 worktree 根**执行。不是在 `/Users/zhangtiancheng/Documents/projects/autoflow` 主目录执行。
- 原设计阶段不实现复选任务；现已确认，按阶段执行。不自动派子智能体；若用户选择并行执行，先完成共享API/令牌与G0，再分派互不重叠领域，公共文件只由一个负责人修改。
- 实施使用 `executing-plans` 或用户选择后的 `subagent-driven-development`；涉及控件行为用 `test-driven-development`，失败定位用 `systematic-debugging`，提交前用 `verification-before-completion`，最终评审用 `requesting-code-review`；均在阶段开始时读对应本机技能并明确告知。

## 执行约束与阶段门

| 阶段 | 任务 / 依赖 | 交付与退出标准 |
|---|---|---|
| P0 基线 | T0；用户确认 | 隔离、保护路径、实际依赖与原有测试基线 |
| P1 令牌/验证基础 | T1→T2 | 令牌、展示页骨架、浮层兼容G0；不得开始领域替换 |
| P2 共享控件 | T3→T4→T5；T6/T7依赖T3/4 | API与状态完整、组件展示与测试通过；G1 |
| P3 真实领域 | T8浏览器+内核 → T9代理+池 → T10模型 → T11设置/总览/应用壳 | 每一切片自动+真实页面通过；G2；不把展示页截图当页面完成 |
| P4 清理与验收 | T12→T13，依赖全部迁移 | 单一Select入口、残留扫描、生产构建、双平台实测；G3 |

关键风险不留到最后：G0 覆盖 Radix Dialog 中 React Aria ComboBox 的 Portal、焦点锁、RHF ref、Escape 与滚动；失败即停止依赖它的迁移，输出复现和替代建议。G1 是共享组件可接入门，不是跨平台完成。G3 未跑的 Windows/macOS 或读屏流程必须标“未执行”，不能勾选全系统完成。

## T0：冻结实施基线和保护范围

**文件**
- 新建 `docs/design-system/verification/baseline.md`。
- 只读：`AGENTS.md`、`.ai/README.md`、`.ai/memory/project-context.md`、`.ai/decisions/`、`docs/PROJECT_STRUCTURE.md`、本规格与盘点JSON。
- 不修改：`apps/backend/`、`apps/desktop/src/main/`、`apps/desktop/src/preload/`、`apps/desktop/src/shared/`、`renderer/shared/api/`、各领域api/hooks/model/form-schema/presets及数据目录；真实路径扫描见T12。语言/时区 JSON 目录即使已提交也不属于本任务。

- [x] 记录 pwd、分支、HEAD、git status、worktree list，确认工作树由本任务拥有。
- [x] 只读比较主目录HEAD与状态；在任务分支接入最新**已提交**代码，逐项核对盘点增量；不复制主目录未提交文件。记录 EnvironmentOptionField 与代理检测协议是否存在及其提交；主目录最终复核已有未提交UA目录扩展，必须等其已提交稳定版本或避开该文件的领域迁移，不能移走/覆盖并行修改。T1–T7共享工作可独立推进。
- [x] 在任务目录安装锁定依赖，记录原有类型、lint、测试、构建结果；任何旧失败分开记录，不通过删除测试解决。

```bash
git status --short
git branch --show-current
git worktree list
git log -1 --format='%H %s'
npm ci
npm run test:structure
npm test
npm run typecheck
npm run lint
npm run build
```

预期：无本任务未解释变动；验证命令返回0，或记录可复现的原有失败并在影响范围内先解决。不得以工作区旧测试数量当当前正确数量。

- [x] 记录保护路径的基线SHA，保存baseline文档；提交仅包含该文档，提交说明 `docs(ui): record isolated controls implementation baseline`。

## T1：设计令牌与跨控件样式

**文件**
- 新建 `apps/desktop/src/renderer/styles/tokens.css`、`apps/desktop/src/renderer/styles/controls.css`。
- 修改 `apps/desktop/src/renderer/styles/index.css`。
- 新建 `scripts/ui-tokens.test.mjs`。

- [x] 先写并运行颜色对比/必需token测试，证明新文件不存在或边界对比不足时失败。测试对比公式如下，读取tokens中的真实色值，不另写一份会漂移的通过样本。

```js
function luminance(hex) {
  const channels = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4)
  return channels.reduce((sum, v, i) => sum + v * [.2126, .7152, .0722][i], 0)
}
function contrast(a, b) {
  const [lo, hi] = [luminance(a), luminance(b)].sort((x, y) => x - y)
  return (hi + .05) / (lo + .05)
}
```

Run `node --test scripts/ui-tokens.test.mjs`，红灯必须是缺token/对比失败，不是测试路径写错。

- [x] 将设计§3完整token表写入tokens，index引入顺序保持 Tailwind → tokens → controls；保留data-motion语义。只添加现有需求的变量，不创暗色主题。核心新增值：

```css
@theme {
  --color-control-border: #8b8377;
  --color-danger: #b13c32;
  --color-danger-soft: #fbece9;
  --color-warning: #805618;
  --color-warning-soft: #faf0dc;
  --radius-modal: 16px;
}
:root {
  --control-sm: 2rem;
  --control-md: 2.5rem;
  --focus-width: 2px;
  --focus-offset: 2px;
  --scrollbar-rail: 12px;
  --scrollbar-thumb: 6px;
  --motion-control: 100ms;
  --motion-overlay: 150ms;
  --motion-progress: 300ms;
}
```

- [x] 在controls添加 input/textarea自填充、selection、search系统清除按钮归一、数字spinner归一、原生scrollbar parts、textarea resize corner和forced-colors规则；不全局 `appearance:none` 到所有DOM，选择控件的外观由各封装负责。
- [x] 运行 token测试、`npm run typecheck`、`npm run build`；检查未改现有业务schema。提交 `feat(ui): centralize warm clay control tokens`。

人工交付：第一张token色板在T2展示；明确现有line仅做分隔，所有字段边界使用control-border。对应A02。

## T2：正式展示页骨架与浮层兼容验证 G0

**文件**
- 修改 `apps/desktop/package.json`、根 `package-lock.json`、`apps/desktop/src/renderer/main.tsx`。
- 新建 `apps/desktop/src/renderer/shared/ui-lab/UiLabPage.tsx`、`ChoiceOverlayCase.tsx`、`FormFocusCase.tsx`、`fixtures.ts`、`UiLabPage.test.tsx`。
- 新建 `apps/desktop/src/renderer/shared/components/ui/overlay-host.tsx`、`overlay-integration.test.tsx`。
- 修改 `apps/desktop/src/renderer/shared/components/ui/dialog.tsx`、`alert-dialog.tsx`（host/depth及活跃popup Escape顺序保护，保留busy与已有焦点逻辑）。
- 新建 `docs/design-system/verification/choice-overlay-gate.md`。
- 执行补充：新增 `ui-lab/LabCombobox.tsx` 验证探针、`renderer/vite-env.d.ts`、`scripts/smoke-ui-controls.mjs`；根package增加smoke命令。为了G0就能重复验证真实Electron，将T13所需Playwright工具依赖提前锁定为开发依赖，不提前执行领域迁移。

- [x] 核对要安装版本的 peer 依赖后，在workspace精确锁定 radio-group、scroll-area、react-aria-components；安装输出与lockfile记录版本。不要运行会覆盖现有组件的shadcn生成命令。
- [x] 在现有Dialog测试风格上增加三层Dialog及组合框案例：打开建议后第一次Escape只收建议；第二次收内核层并返回父触发器；busy时不能关闭。先运行 `npm --workspace @autoflow/desktop test -- src/renderer/shared/components/ui/overlay-integration.test.tsx` 得到失败。
- [x] 实现最小OverlayHost Context，只传递层级与popup容器。Frame host位于scroll body外，position/focus边界按设计§7；选项浮层使用本层host；模态窗口Portal仍由Radix挂body以避开父层transform，后续Radix选择/菜单在T5/T6接host。组合框案例只有本地fixture，不调用业务接口。
- [x] 添加DEVELOPMENT入口，生产默认入口行为不变：

```tsx
const element = document.getElementById('root')
if (!element) throw new Error('renderer root element is missing')
const root = createRoot(element)
if (import.meta.env.DEV && location.hash === '#/__ui') {
  void import('./shared/ui-lab/UiLabPage').then(({ UiLabPage }) => {
    root.render(<StrictMode><UiLabPage /></StrictMode>)
  })
} else {
  root.render(<StrictMode><App /></StrictMode>)
}
```

保留main.tsx已有import（StrictMode、createRoot、App及样式）；此片段替换原来的root挂载段，保留缺root时报错与StrictMode。UiLabPage输出 `data-ui-lab="autoflow-ui-controls-lab"` 作为生产泄漏扫描标识。

- [x] 测RHF setFocus/reset/dirty与ref、键盘进入选项和关闭后焦点、popup不被overflow裁剪。jsdom不能证明视觉裁剪，必须在任务实例Electron实际打开案例验证。
- [x] 记录G0成功/失败截图与步骤。G0通过才允许后续进入T5与领域迁移；失败时只保留复现，不扩大替换范围。运行shared tests、typecheck/build，提交 `feat(ui): add isolated control lab and overlay host`。对应A01/A06/A09。

## T3：Button、输入、Field绑定

**文件**
- 修改 `apps/desktop/src/renderer/shared/components/ui/button.tsx`、`input.tsx`、`textarea.tsx`。
- 新建同目录 `icon-button.tsx`、`search-input.tsx`、`password-input.tsx`、`spinner.tsx`、`spinner.test.tsx`、`button.test.tsx`、`input.test.tsx`、`search-input.test.tsx`、`password-input.test.tsx`。
- 修改 `apps/desktop/src/renderer/shared/components/FormField.tsx`、`FormField.test.tsx`。
- 新建 `apps/desktop/src/renderer/shared/components/FieldGroup.tsx`、`FieldGroup.test.tsx`。
- 新建 `apps/desktop/src/renderer/shared/ui-lab/TextControlCases.tsx`，修改UiLabPage接入。

- [ ] 写关键行为测试并运行红灯：loading按钮不重复触发、不隐去名称；Search清除回传一次且焦点留input；Password显隐不提交表单且保留值；readOnly可focus/select；FormField与Controller组合把描述传到input。示例测试完整最小用例：

```tsx
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom/vitest'
import { Button } from './button'
afterEach(cleanup)
it('loading blocks duplicate actions and retains an accessible name', async () => {
  const user = userEvent.setup()
  const save = vi.fn()
  render(<Button loading onClick={save}>保存配置</Button>)
  const button = screen.getByRole('button', { name: '保存配置' })
  expect(button).toHaveAttribute('aria-busy', 'true')
  await user.click(button)
  expect(save).not.toHaveBeenCalled()
})
```

- [ ] 按设计§5加入size/ref/loading API；Button默认type=button，IconButton要求aria-label。先实现供Button使用的Spinner（Phosphor CircleNotch、装饰aria-hidden、reduce时静态），不依赖T7。输入继续传标准事件和ref；Search/Password用输入组合，不重写文字编辑。所有现有提交Button在各切片显式保留type=submit。
- [ ] FormField支持children渲染函数，传实际控制元素a11y属性；迁移期间旧ReactNode路径保留兼容，最终T12移除clone。FieldGroup用fieldset/legend，不把组id分发给每个选项。
- [ ] 补text/search/password/numeric/textarea的全部适用状态、长文本与真实RHF例子到展示页，测试ref/setFocus与错误消失恢复hint。
- [ ] Run `npm --workspace @autoflow/desktop test -- src/renderer/shared/components`、`npm run typecheck`、`npm run lint`。人工检查键盘、中文IME、placeholder/readOnly区分与40/32密度。提交 `feat(ui): standardize text controls and field bindings`。对应A03。

## T4：Checkbox、RadioGroup、Switch、Disclosure

**文件**
- 修改 `apps/desktop/src/renderer/shared/components/ui/checkbox.tsx`、`switch.tsx`。
- 新建同目录 `radio-group.tsx`、`disclosure.tsx`、`choice-toggle.test.tsx`、`disclosure.test.tsx`。
- 新建 `apps/desktop/src/renderer/shared/ui-lab/ToggleCases.tsx`，接入UiLabPage。

- [ ] 写radio箭头跳过disabled、Space切换checkbox、indeterminate符号、Switch禁用、Disclosure Enter/Space展开收起测试。使用角色断言，不只快照class。
- [ ] Run `npm --workspace @autoflow/desktop test -- src/renderer/shared/components/ui/choice-toggle.test.tsx src/renderer/shared/components/ui/disclosure.test.tsx`，确认缺实现时红灯。
- [ ] 复用Radix Root/Indicator/Thumb；RadioGroup完整Item/Indicator。Disclosure直接封装语义details/summary，隐藏系统marker加Phosphor chevron，不实现第二套键盘逻辑。受控需要时通过open/onToggle适配settings现有state。

```tsx
// Checkbox 的关键结构；实际props/ref透传沿用相应Radix Root类型。
<CheckboxPrimitive.Root {...props} ref={ref}>
  <CheckboxPrimitive.Indicator>
    {props.checked === 'indeterminate' ? <Minus aria-hidden size={14} /> : <Check aria-hidden size={14} />}
  </CheckboxPrimitive.Indicator>
</CheckboxPrimitive.Root>
```

- [ ] 为三态、组错误、长label、禁用原因添加展示场景；保证视觉18px且label命中区32px，forced-colors可见。
- [ ] 同命令绿灯后运行shared tests/typecheck，提交 `feat(ui): unify choice toggles and disclosures`。对应A05。

## T5：Select、Combobox、Autocomplete与滚动容器

**依赖：T2 G0、T3、T4。**

**文件**
- 修改 `apps/desktop/src/renderer/shared/components/ui/select-radix.tsx`（迁移暂存入口）。
- 新建同目录 `choice-types.ts`、`combobox.tsx`、`scroll-area.tsx`、`select.test.tsx`、`combobox.test.tsx`、`scroll-area.test.tsx`。
- 修改 `apps/desktop/src/renderer/shared/ui-lab/ChoiceOverlayCase.tsx`、`FormFocusCase.tsx`。
- 新建 `apps/desktop/src/renderer/shared/ui-lab/ChoiceCases.tsx`、`ScrollCases.tsx`。

- [ ] 先加空串/null、同label不同value、当前失效值、disabled、错误重试、500项搜索、IME自由输入与RHF setFocus测试。空值必须使用碰撞安全映射：

```ts
const encodeValue = (value: string | null): string => value === null ? '' : `v:${value}`
const decodeValue = (value: string): string | null => value === '' ? null : value.slice(2)
// 单测必须覆盖 null、''、'v:x'、'__custom__'、中文与带冒号资源键。
```

- [ ] 执行 `npm --workspace @autoflow/desktop test -- src/renderer/shared/components/ui/select.test.tsx src/renderer/shared/components/ui/combobox.test.tsx src/renderer/shared/components/ui/scroll-area.test.tsx` 得到红灯。
- [ ] 完成Radix Select完整结构；将设计ChoiceProps落为应用侧类型，不暴露第三方collection类型到domains。ComboBox严格模式仅选项提交回传值，Autocomplete允许自由字符串且选项回调独立；两个导出共享底层，不复制一套焦点算法。
- [ ] 加ScrollArea viewport/双轴scrollbar/thumb/corner，采用12/6px常显溢出策略；所有popup接OverlayHost；aria-labelledby/describedby/ref落在input/trigger。
- [ ] 添加真实RHF submit→错误页签→setFocus的集成案例；测试reset回显、清空、blur、dirty等，不把第三方onBlur事件格式直接塞进领域state。
- [ ] 运行共享测试/typecheck/lint；Electron展示页检查长文、500项、嵌套浮层、滚轮/拖动、Escape。记录过滤/打开耗时，达不到设计目标先profile；不预装虚拟化库。提交 `feat(ui): add accessible custom choices and scroll areas`。对应A04/A07。

## T6：统一浮层外框、菜单、Tooltip、Tabs

**文件**
- 修改 `apps/desktop/src/renderer/shared/components/ui/dialog.tsx`、`alert-dialog.tsx`、`dropdown-menu.tsx`、`tooltip.tsx`、`tabs.tsx`、`dialog.test.tsx`、`dropdown-menu.test.tsx`。
- 修改 `apps/desktop/src/renderer/shared/components/Modal.tsx`、`Modal.test.tsx`。
- 新建 `apps/desktop/src/renderer/shared/components/Drawer.tsx`、`Drawer.test.tsx`。
- 新建 `apps/desktop/src/renderer/shared/components/ui/tooltip.test.tsx`、`tabs.test.tsx`。
- 新建 `apps/desktop/src/renderer/shared/ui-lab/OverlayCases.tsx`。

- [ ] 扩展已有测试：菜单转弹窗后焦点正确；Tooltip不替代按钮label；Tabs焦点/选中独立；危险确认取消初焦；忙时Escape/遮罩/关闭按钮都不能关闭；触发器消失后的focus fallback。
- [ ] 执行 `npm --workspace @autoflow/desktop test -- src/renderer/shared/components` 验证新增断言先失败。
- [ ] 统一DialogContent frame边界、OverlayHost和size；Modal固定header/footer、body单一滚动；Drawer仅改变同一frame为右侧布局。不要在各domain继续增加z-index或再写焦点return。
- [ ] Tooltip延迟400ms、退出100ms；键盘focus即能显示，Escape关闭；Dropdown项统一危险/禁用/highlight，使用`asChild`给IconButton避免button嵌套。Tabs/Disclosure动作保持原语控制。
- [ ] 绿灯后在展示页验证三级浮层、滚动体菜单、窄窗口与reduced motion；提交 `feat(ui): standardize overlays menus and tabs`。对应A06。

## T7：表格、分页与反馈组合

**文件**
- 修改 `apps/desktop/src/renderer/shared/components/ui/badge.tsx`，统一tone和密度；不把只读Badge赋予按钮角色。
- 新建 `apps/desktop/src/renderer/shared/components/ui/table.tsx`、`pagination.tsx`、`alert.tsx`、`empty-state.tsx`、`skeleton.tsx`、`progress.tsx`。
- 新建同目录 `pagination.test.tsx`、`feedback.test.tsx`。
- 修改 `apps/desktop/src/renderer/shared/components/Toaster.tsx`、`Toaster.test.tsx`、`State.tsx`；`ResourceState.tsx` 仅在迁移实有复用后保留，否则T12删除未用包装。
- 新建 `apps/desktop/src/renderer/shared/ui-lab/DataFeedbackCases.tsx`。

- [ ] 写分页首/尾/空数据边界与aria-label测试、未知进度无valuenow、spinner装饰不重复播报、Toast tone与定时退场测试。
- [ ] Run `npm --workspace @autoflow/desktop test -- src/renderer/shared/components/ui/pagination.test.tsx src/renderer/shared/components/ui/feedback.test.tsx src/renderer/shared/components/Toaster.test.tsx` 得到红灯。
- [ ] Table仅暴露语义table/thead/tbody/tr/th/td样式封装；不加排序、列管理、远程状态。Pagination接收offset/limit/total/count/onOffsetChange，计算保持现有ProxyFleet行为：

```ts
const start = total === 0 ? 0 : offset + 1
const end = Math.min(offset + count, total)
const previous = Math.max(0, offset - limit)
const next = offset + limit
const canPrevious = offset > 0
const canNext = offset + count < total
```

- [ ] Alert/EmptyState只表达渲染状态；ResourceState不得把“有缓存+刷新错误”隐藏掉。Progress `value:number|null`，null无伪百分比；复用T3已实现且减少动效时变静态的Spinner。Toaster保持notify函数与挂载流程，仅统一呈现与关闭控件；State使用可见样式替代无定义类。
- [ ] 运行shared tests/typecheck/build；展示页覆盖正常/空搜索/初始空/加载/缓存失败/未知进度/retry/toast。提交 `feat(ui): standardize data and feedback patterns`。完成G1。

## T8：浏览器配置与内核切片

**文件（生产修改仅以下组件）**
- `apps/desktop/src/renderer/domains/profiles/pages/BrowserManagementPage.tsx`。
- `apps/desktop/src/renderer/domains/profiles/components/BasicFields.tsx`、`EnvironmentFields.tsx`、`EnvironmentOptionField.tsx`（来自最新主线）、`KernelProxyFields.tsx`、`AdvancedFields.tsx`、`ProfileFormDialog.tsx`、`ProfileActionDialog.tsx`、`UnsavedChangesDialog.tsx`、`ProfileList.tsx`。
- `apps/desktop/src/renderer/domains/kernels/components/LicensePanel.tsx`、`KernelManagerDialog.tsx`、`KernelReleaseList.tsx`、`KernelOperationStatus.tsx`、`DeleteKernelDialog.tsx`。
- 修改上述已有同名`.test.tsx`；新增 `domains/profiles/components/EnvironmentOptionField.test.tsx`、`domains/kernels/components/DeleteKernelDialog.test.tsx`（前缀同renderer）。

- [ ] 更新测试使用用户点击/键盘选择自有面板，不能继续用`user.selectOptions`掩盖原生select残留。先加失效内核、public→stable、切换代理模式清空id、locale/timezone手动与失败fallback、UA自由输入、嵌套确认的断言并运行红灯。
- [ ] 逐个表单Field接入render-prop与ref；按审计22处账本迁移本模块select。保留领域value变换，例如：

```tsx
onValueChange={(value) => {
  const next = value ?? ''
  field.onChange(next)
  if (parseKernelKey(next)?.edition === 'public') {
    setValue('releaseChannel', 'stable', { shouldDirty: true, shouldValidate: true })
  }
}}
```

- [ ] EnvironmentOptionField保留最新options props与manual状态/焦点行为，预设用Combobox；不触碰profiles/api.ts、hooks.ts、presets.ts或后端JSON。UA若仍为datalist则改Autocomplete；若T0确认已走EnvironmentOptionField，则复用该字段的Combobox+手动模式并保留后端目录，不拆回旧实现。Numeric仍交schema校验；AdvancedFields改Disclosure。
- [ ] 列表搜索/按钮/空态，内核License、版本按钮、Progress、取消/失败、删除确认使用统一控件；原有事件流与请求重试不变。Manager仍只由“管理内核”进入。
- [ ] Run `npm --workspace @autoflow/desktop test -- src/renderer/domains/profiles src/renderer/domains/kernels`、typecheck/lint。真实任务实例验证A10全流程与A06三级浮层、A07滚动。真实License/远程下载若无测试条件，记录未执行，不调用用户账户做虚构验收。
- [ ] 提交 `refactor(ui): migrate browser and kernel controls`，附真实截图和未执行项到verification文档；只通过本切片才继续。

## T9：代理、代理池与抽屉切片

**文件**
- 修改 `apps/desktop/src/renderer/domains/proxies/components/ProxyConnection.tsx`、`ProxyFleet.tsx`、`ProxyDetailDrawer.tsx`、`LocalProxyGroups.tsx`、`presentation.tsx`。
- 修改 `apps/desktop/src/renderer/domains/proxies/pages/ProxyManagementPage.tsx`（只展示组合）。
- 修改 `apps/desktop/src/renderer/domains/proxies/tests/ProxyManagementPage.test.tsx`。
- 新建 `apps/desktop/src/renderer/domains/proxies/tests/ProxyControls.test.tsx`。

- [ ] 加协议保持、radio disabled/箭头、过滤不丢成员、分页上下界、password显示、busy锁与异常恢复用例；运行新用例得到红灯。
- [ ] 原生radio替换RadioGroup；原生checkbox替换Checkbox；fieldset/legend关联组。检测与凭据协议保留新主线默认/回调，不能将SOCKS5优先改回HTTP。
- [ ] 成员编辑用SearchInput + Checkbox + ScrollArea；代理表格Table+Pagination；运营商/城市Combobox；健康/轮换协议Select；抽屉接Drawer。capability、库存、outcome_unknown与retryAfter行为保持领域原值。

```tsx
// 成员选择仍由领域管理，不让搜索结果替代已选集合。
<Checkbox checked={memberIds.includes(proxy.id)}
  onCheckedChange={(checked) => toggle(proxy.id, checked === true)}
  aria-label={`选择代理 ${proxy.name}`} />
```

保留现有memberIds数组及toggle函数、上下移动顺序和边界禁用，不把有序成员改成另一份Set状态；搜索只影响候选展示。

- [ ] Run `npm --workspace @autoflow/desktop test -- src/renderer/domains/proxies`、typecheck/lint。人工A11必须覆盖列表→详情→协议→地点、长列表、组编辑、分页、只读/禁用原因与复制控件；无真实可用capability时测试fixture只算自动证据。
- [ ] 提交 `refactor(ui): migrate proxy and pool controls`，记录当前平台截图。

## T10：模型切片

**文件**
- 修改 `apps/desktop/src/renderer/domains/models/pages/ModelManagementPage.tsx`（加载/失败/无供应商反馈，数据请求不改）。
- 修改 `apps/desktop/src/renderer/domains/models/components/ProviderSidebar.tsx`、`ProviderCatalogStep.tsx`、`ProviderConnectionStep.tsx`、`ProviderModelsStep.tsx`、`ProviderWizard.tsx`、`ProviderDetail.tsx`、`ProviderDeleteDialog.tsx`、`FeedbackCard.tsx`。
- 修改同目录 `ModelDirectory.tsx`、`ModelEditor.tsx`、`ModelForm.tsx`、`ModelIdInput.tsx`、`ModelTestPanel.tsx`、`ModelDeleteDialog.tsx`。
- 新建同目录 `TagInput.tsx`。
- 修改 `apps/desktop/src/renderer/domains/models/tests/ModelManagementPage.test.tsx`、`ProviderWizard.test.tsx`、`ModelEditor.test.tsx`；新增 `TagInput.test.tsx`、`ModelIdInput.test.tsx`。

- [ ] 写手动modelKey、建议附加数据回调、IME Enter、只读ID、标签去重/中文逗号/失焦提交、完整发现集合全选、菜单转弹窗焦点测试；红灯必须能显示旧手写建议的行为缺口。
- [ ] ModelDirectory直接原生select改Select；目录Table、SearchInput、IconButton/Menu；ModelIdInput改Autocomplete但仍回传领域option补充元数据。TagInput只抽现有字符串行为，不变成建议多选控件。
- [ ] 三步向导checklist滚动/搜索、连接password、文本域、Disclosure、provider选择按钮的selected/aria语义接入共同视觉。供应商编辑仍在ProviderWizard的editing分支，没有独立ProviderEditDialog文件。保留最新ProviderLogo与品牌资源；保留供应商侧栏、split编辑、原有表单关闭行为；不得给模型新增未保存确认或Toast流程。

```tsx
// 键盘标签提交继续避开输入法确认事件。
onKeyDown={(event) => {
  if (event.nativeEvent.isComposing) return
  if (event.key === 'Enter' || event.key === ',' || event.key === '，') {
    event.preventDefault()
    commitTag()
  }
}}
```

`commitTag`在TagInput内定义为trim→非空且不重复时回传新数组→清空draft；不丢已有labels。

- [ ] Run `npm --workspace @autoflow/desktop test -- src/renderer/domains/models`、typecheck/lint；人工A12完成向导→模型目录→增改删/测试→菜单与只读复制。保留已存Key空输入表示不更换。
- [ ] 提交 `refactor(ui): migrate model management controls`。

## T11：设置、总览和应用壳收口

**文件**
- 修改 `apps/desktop/src/renderer/domains/settings/pages/SettingsPage.tsx`、`components/DiagnosticDialog.tsx`、`components/SettingsCard.tsx`。
- 修改 `apps/desktop/src/renderer/domains/dashboard/pages/DashboardPage.tsx`、`components/DashboardCards.tsx`。
- 修改 `apps/desktop/src/renderer/app/ApplicationHeader.tsx`、`app/App.tsx`（只控制元素/呈现，连接逻辑不改）。
- 修改 `domains/settings/tests/SettingsPage.test.tsx`、`domains/dashboard/tests/DashboardPage.test.tsx`、`app/App.test.tsx`（前缀均为renderer）。
- 新建 `apps/desktop/src/renderer/app/ApplicationHeader.test.tsx`。

- [ ] 增加设置两Select值映射、临时请求busy、诊断checkbox、导航aria-current、断线重连按钮及空/失败状态测试并运行红灯。
- [ ] 设置zoom options用string映射后还原原数字枚举90/100/110/125，不新增150/200持久化值；动效system/reduce/full不变。详情与运行环境按钮改Disclosure；诊断code/pre可选中复制和滚动。
- [ ] 资源卡/导航使用统一action视觉和显式button语义；不要改变页面路由或新增侧栏。总览/服务状态组合共享反馈组件，仍显示现有真实数据。
- [ ] Run `npm --workspace @autoflow/desktop test -- src/renderer/domains/settings src/renderer/domains/dashboard src/renderer/app`、typecheck/lint；人工A13真实应用回归。150/200%是验收运行时缩放，不修改设置API枚举。
- [ ] 提交 `refactor(ui): finish settings dashboard and shell controls`，完成G2。

## T12：退出旧实现、残留扫描与生产隔离

**文件**
- 修改 `apps/desktop/src/renderer/shared/components/ui/select.tsx` 为最终Radix入口；删除临时 `select-radix.tsx` 后更新所有已迁移import。
- 修改 `apps/desktop/src/renderer/shared/components/FormField.tsx` 移除隐式clone兼容；未使用的 `ResourceState.tsx` 经import核对后删除或保留实际调用，不留下第二套空态系统。
- 新建 `scripts/audit-ui-controls.mjs`、`scripts/audit-ui-controls.test.mjs`、`scripts/ui-controls-allowlist.json`。
- 修改根 `package.json` 增加 `audit:ui` 命令；必要时修改 `apps/desktop/src/renderer/proxy-preview.tsx` 仅适配新API。
- 更新 `docs/design-system/2026-09-12-ui-controls-usage.md` 的实施后附录、`docs/PROJECT_STRUCTURE.md`、`.ai/memory/project-context.md`（只有已确认且已实现的事实）。

- [ ] 先为扫描器添加测试fixture：import alias、路径导出、动态import、Fragment、map、原始input/select/datalist、违规className、未接入preview/草稿；验证不会把Primitive内部input算作领域绕过。
- [ ] AST遍历入口和生产全部renderer两条链：实际入口用于覆盖率，所有production源用于防潜在回归；未接入草稿单列。允许名单精确到文件+元素+用途，不能全局允许domains或整个shared。
- [ ] 最终规则与人工辅助扫描：

```bash
rg -n '<(select|datalist|input|textarea|button|summary)\b|type=.?(radio|checkbox)' apps/desktop/src/renderer --glob '*.tsx' --glob '!*.test.tsx'
rg -n 'appearance-|accent-|outline-none|z-\[|#[0-9a-fA-F]{3,8}|overflow-[xy]?-?(auto|scroll)' apps/desktop/src/renderer --glob '*.tsx' --glob '*.css' --glob '!*.test.tsx'
```

AST要求：domains/app无裸select/datalist/input/textarea；rawbutton只可在有理由的共享语义封装（导航/资源卡若仍raw必须逐点说明并复用统一action样式），summary限Disclosure；没有裸radio/checkbox。第三方为了原生表单提交生成的隐藏input/select不算系统面板，但必须确认aria-hidden/tab顺序，不能通过隐藏生产下拉规避检查。

样式扫描排除token定义和明确领域品牌标识色；图标/状态色应token化。系统日期/文件等控件如未来出现必须新增用途评审，不一刀切把语义DOM全部禁掉。CSS扫描只是线索，实际computed style/截图才证明没有系统外观。

- [ ] 完成唯一Select入口和FormField调用迁移；运行`node --test scripts/audit-ui-controls.test.mjs`、`npm run audit:ui`、全套前端test/typecheck/lint/build。
- [ ] build后扫描 `apps/desktop/out/renderer`：不得包含 `autoflow-ui-controls-lab`、UiLab fixture专用长样本标识；测试DEV入口可达且prod hash不能启用演示页。不要把“全局不存在select DOM”当通过条件，Radix表单隐藏节点可能合法。
- [ ] `git diff --name-only <T0记录的基线>`检查保护路径为空；提交 `refactor(ui): remove native control bypasses and enforce audit`。对应A01/A09与扫描门。

## T13：真实应用、平台和辅助技术验收 G3

**文件**
- 修改 `apps/desktop/vitest.config.ts` 排除 `tests/ui/**`；修改 `apps/desktop/tsconfig.json` 把新测试配置与 `tests/ui` 纳入类型检查。
- 新建 `apps/desktop/playwright.ui.config.ts`、`apps/desktop/tests/ui/electron-fixture.ts`、`controls.real-pages.spec.ts`、`controls.accessibility.spec.ts`。
- 修改 `apps/desktop/package.json`、根package-lock，新增精确验证版本的 `@playwright/test`、`@axe-core/playwright` 开发依赖与 `test:ui` 命令；不把它们加入renderer运行时。
- 新建 `docs/design-system/verification/ui-controls-results.md`、`docs/design-system/verification/ui-controls-platform-matrix.md`。
- 更新设计/计划状态、`.ai/sessions/`验收记录；设计修改若已确认才补ADR，不覆盖旧历史。

- [ ] Playwright Electron启动使用单独临时user-data-dir，测试结束只清理自身目录，不读写用户工作区；沿用现有 `scripts/smoke-desktop.mjs` 的隔离原则。该脚本当前只验证健康与退出，不能当控件E2E。Playwright Electron API仍标为experimental，必须先验证项目Electron版本能启动。[官方Electron API](https://playwright.dev/docs/api/class-electron)
- [ ] `electron-fixture.ts`封装mkdtemp→launch→firstWindow→测试→close→rm，finally确保清理；运行时缩放通过测试侧webContents.setZoomFactor，不改设置枚举与持久化协议。测试进程先验证运行时 `app.getPath('userData')` 确实等于新建目录，否则立即停止；用户数据目录由`--user-data-dir`隔离，现有DesktopSettingsStore默认工作目录即该目录。
- [ ] 使用真实App入口与真实本地sidecar覆盖A10–A13。条件错误/忙/下载场景可在独立fixture中可控重放，但报告分为“真实端到端”“页面fixture”“共享控件fixture”，不得把模拟License登录写成正式版验证。远程账号条件不足的步骤保留未执行。
- [ ] axe自动扫描已打开的真实页面/弹窗；无严重/关键错误且不存在可定位的label/role/焦点问题。人工辅助技术覆盖中文label、radio组、选项、错误和嵌套焦点；axe不能证明键盘体验完整。
- [ ] 每平台执行：100/125/150/200% × 1280×800/1440×900，补1024×768低高度；macOS滚动条自动/常显、Windows常显与系统显示缩放；文字、关闭/保存/底部操作全部可达。VoiceOver/macOS与NVDA/Windows分别记录，不能用macOS推断Windows通过。
- [ ] 执行总检查并保存命令、退出码、提交和设备版本：

```bash
npm run test:structure
npm test
npm run typecheck
npm run lint
npm run build
npm run audit:ui
npm --workspace @autoflow/desktop run test:ui
npm run smoke:desktop
```

预期全部命令返回0；test:ui配置限定`tests/ui`，Vitest排除该路径，避免两种runner互相执行。现有Settings集成测试可能启动真实sidecar，必须确认只用自身临时目录；不为UI任务执行主目录环境的命令。

- [ ] 按“平台｜OS/架构｜提交｜窗口/缩放｜场景ID｜自动/真实/fixture｜结果｜证据｜缺陷”保存矩阵。阻断项：业务payload漂移、系统select/datalist可见、焦点被困/逃逸、busy可重复提交、200%主要操作不可达、滚动条或选中标志不可见。
- [ ] 使用 `verification-before-completion` 重新核对本次新鲜证据，再按 `requesting-code-review` 评审；只在A01–A15范围都完成时把计划标completed。平台/账户条件未满足则标“实现完成，验收未完成”并列精确缺口，不合成通过记录。
- [ ] 提交 `test(ui): verify unified controls across real application flows`。合并到主线作为用户后续确认动作，不在本轮设计阶段执行。

## 测试策略与工作量边界

测试优先保护可被控件替换破坏的行为：事件格式、空值、焦点、IME、提交重复、可用性、保留已选、嵌套层级；不为每一条Tailwind class写镜像快照。视觉令牌变化以计算+实屏判断。32/40等简单样式改动不单独制造十几个重复测试。

新增测试例的命令在各任务给出，领域测试沿用当前helpers/fixture，不能写一个与生产流程断开的假页面自证。测试库缺少PointerEvent/ResizeObserver等浏览器能力时，在测试环境补最小polyfill并说明；最终仍由真实Electron验证，不用polyfill掩盖实现问题。

每任务提交后记录通过项与真实未跑项。迁移发现新生产入口时先追加源码账本/对应验收任务；未接入automation草稿不趁机迁移。只在用户明确选择并行方式后才使用子智能体，适合的分工是G1后浏览器/代理/模型领域各自分支，公共控件、依赖和最终全局扫描由主负责人维护。

## 规格覆盖自审

| 规格要求 | 任务 |
|---|---|
| 真实源码与主目录差异、保护并行任务 | T0、T12 |
| 暖灰/黏土棕、字体/密度/边框/焦点/动效 | T1、T3、T4、T6、T7 |
| 全部实际控件家族、RHF、ARIA、IME、长文与大量选项 | T3–T7 |
| 自有下拉/滚动条、嵌套Popup/Dialog、缩放 | T2、T5、T6、T13 |
| 正式验收展示页且不进入生产 | T2、T3–T7、T12 |
| 浏览器/内核、代理/池、模型、设置/总览/应用壳 | T8、T9、T10、T11 |
| 不扩大成全组件库、无用MultiSelect/NumberStepper | T4、T5、T7、T10范围约束 |
| 原生控件残留扫描、真实页面和双平台验收 | T12、T13 |

设计已确认，本批T0–T2已实施；G0的本机验证与未执行项见验收报告。后续按T3–T13推进，G1后再决定领域并行，不自动扩派子智能体。
