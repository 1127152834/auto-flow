# R1 页面层级与目录 Implementation Plan

> **2026-09-13 当前修订：** 视觉基准及页面组合任务已由[Gallery直接还原计划](2026-09-13-project-management-gallery-realignment.md)替代。用户只允许原全局左菜单改现有顶部导航，其余按原图。B0不再是基准；R1视觉重新验收、R2已有业务实现但视觉未通过、R3未完成。本文后续B0/紧凑头/用户逐阶段确认等描述仅保留历史语境；有效的事务、身份、恢复和业务测试任务继续执行，以新计划为当前入口。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`-`) syntax for tracking.

**Goal:** 在现有顶部导航下交付最近项目卡片、全部项目目录、统一项目页头和紧凑数据工具栏，保留真实查询与返回状态。

**Architecture:** 现有项目API不变；组件先于页面。新增Popover只补真实缺口，Drawer复用现有Modal的placement，不新造浮层系统。

**Tech Stack:** React、TypeScript、Tailwind、现有shadcn/Radix、TanStack Query、Vitest、Electron。

---

前置：[总计划](2026-09-13-project-management-alignment-implementation.md)B0的R1画板已确认。所有命令在implementation工作区根目录执行，Vitest按相对desktop路径过滤。测试预期是行为断言通过，不预报测试数量。

## R1-01：项目和对象页头

**Files:** Modify `apps/desktop/src/renderer/domains/projects/components/ProjectHeader.tsx`、`apps/desktop/src/renderer/domains/projects/components/ProjectTabs.tsx`；Modify `apps/desktop/src/renderer/domains/projects/pages/ProjectOverviewPage.tsx`、`apps/desktop/src/renderer/domains/project-data/pages/DataTableDirectoryPage.tsx`、`apps/desktop/src/renderer/domains/project-data/pages/DataTableDetailPage.tsx`；Create `apps/desktop/src/renderer/domains/projects/components/ProjectHeader.test.tsx`。

- 先扩展页头props并写渲染测试，compact时仍有返回项目目录、项目名和编辑的可访问名称；归档禁编辑；六页签不改标签/顺序。

```tsx
// ProjectHeader.tsx：在现有props上增加，默认保留一级页行为。
type HeaderDensity = 'default' | 'compact'
// Props增加 density?: HeaderDensity；h1保持唯一页面标题，compact上下文改为p。
// 核心class：density === 'compact' ? 'text-base font-semibold' : 'text-2xl font-semibold'
// ProjectTabs持续使用nav/aria-current，不把原按钮导航变成无行为的TabPanel。
```

- 运行 `npm test -- src/renderer/domains/projects/components/ProjectHeader.test.tsx src/renderer/app/App.projects.test.tsx`，新compact断言先失败。
- 现有页头增加可选density，表/记录二级页使用compact上下文+对象h1；保留顶部全局导航，项目页签采用已有横向导航。仅样式布局变更不改项目状态模型。
- 重跑上面测试及 `npm run typecheck`；真实窗口检查长名称、200%缩放、页签滚动、h1层级与焦点，记录R1截图。提交 `refactor: align project header hierarchy with prototypes`。

## R1-02：最近卡片与全部目录

**Files:** Modify `apps/desktop/src/renderer/domains/projects/components/ProjectDirectory.tsx`、`apps/desktop/src/renderer/domains/projects/components/ProjectDirectory.test.tsx`、`apps/desktop/src/renderer/domains/projects/pages/ProjectsWorkspace.tsx`、`apps/desktop/src/renderer/domains/projects/pages/ProjectsWorkspace.test.tsx`、`apps/desktop/src/renderer/domains/projects/hooks.ts`；Create `apps/desktop/src/renderer/domains/projects/components/ProjectCard.tsx`。

目录模式为 `recent | all`，首次为recent，稳定工作区sessionStorage保存模式及all的原条件/滚动。最近调用现有目录接口固定active、`-lastOpenedAt`、page1/pageSize6，剔除未访问项；不能从用户当前搜索的某一页推算最近列表。全部目录继续服务端搜索、状态、排序和分页，不客户端加载所有项目；在最近视图输入搜索词时切到all并应用搜索/page1，不能只搜索六张最近卡片。

- 在ProjectsWorkspace测试中设置“最近A、未访问B、已归档C”和all第二页搜索条件；点击卡片打开再返回，必须恢复模式；进入全部再返回，搜索/页码/滚动不丢。新模式未实现时断言失败。

```ts
// hooks.ts：目标查询键/条件，使用已存在createProjectsApi.list。
const recentConditions = {
  query: '', lifecycle: 'active', sort: '-lastOpenedAt', page: 1, pageSize: 6,
} as const
// useProjectDirectory(api, workspaceKey, instanceId, recentConditions)
// 仅展示返回items中lastOpenedAt != null的项目；数量不足6时不拿未访问项目补齐。
```

- 运行 `npm test -- src/renderer/domains/projects/pages/ProjectsWorkspace.test.tsx src/renderer/domains/projects/components/ProjectDirectory.test.tsx`。
- ProjectCard使用article、独立标题button和兄弟“更多”按钮，避免交互元素嵌套；标题点击/Enter打开，更多里的编辑不触发open。更多只放已实现动作；卡片没有假统计，未访问全部项显示从未打开。最近无记录显示“尚无最近访问”，提供全部/新建入口，不称项目库为空。
- 保存模式与现有all条件分开字段；返回项目目录不重置它们。实际换工作区读对应存储，同工作区重连只刷新查询。创建/编辑后同时使recent/all查询失效，旧实例响应不能弹错成功。
- 同命令重跑并跑 `npm run typecheck`，用真实A/B项目验证最近顺序与重启持久事实；提交 `feat: restore recent project cards and full directory browsing`。

## R1-03：补Popover，复用现有浮层宿主

**Files:** Modify `apps/desktop/package.json`、`package-lock.json`；Create `apps/desktop/src/renderer/shared/components/ui/popover.tsx`、`apps/desktop/src/renderer/shared/components/ui/popover.test.tsx`。Read现有 `apps/desktop/src/renderer/shared/components/ui/overlay-host.tsx`、`apps/desktop/src/renderer/shared/components/ui/select.tsx`、`apps/desktop/src/renderer/shared/components/ui/dialog.tsx`；不创建Drawer文件，现有 `apps/desktop/src/renderer/shared/components/Modal.tsx` 已支持 `placement="drawer"`。

已核对本分支没有Popover，但有菜单、Select和Modal。筛选里有表单，不能用菜单item冒充表单行为。仅新增 `@radix-ui/react-popover`，锁定安装解析版本，不引入整套新UI。Radix支持受控打开、焦点管理和非模态面板，见[官方Popover文档](https://www.radix-ui.com/primitives/docs/components/popover)。

- 写测试：外层Modal→Popover内输入/Select；第一个Escape只关最上层，第二次才关父层；点击外部关闭Popover并恢复触发焦点，Tab可访问输入。
- 执行 `npm test -- src/renderer/shared/components/ui/popover.test.tsx`，因缺模块失败后运行 `npm install --workspace @autoflow/desktop @radix-ui/react-popover`。
- 新控件最小包装如下，受控关闭交给消费者；后续如有嵌套弹层问题必须修宿主交互并测试，不用页面CSS硬盖：

```tsx
import * as Primitive from '@radix-ui/react-popover'
import type { ComponentPropsWithoutRef } from 'react'
import { useOverlayHost } from './overlay-host'
import { cn } from '../../lib/utils'
export const Popover = Primitive.Root
export const PopoverTrigger = Primitive.Trigger
export const PopoverClose = Primitive.Close
export function PopoverContent({ className, style, ...props }: ComponentPropsWithoutRef<typeof Primitive.Content>) {
  const host = useOverlayHost()
  return <Primitive.Portal container={host.container}>
    <Primitive.Content data-af-popup="" sideOffset={6} align="start" collisionPadding={12}
      {...props} style={{ ...style, ...host.style }}
      className={cn('max-h-[var(--radix-popover-content-available-height)] w-[min(32rem,calc(100vw-2rem))] overflow-auto rounded-card border border-line bg-surface p-4 shadow-modal', className)} />
  </Primitive.Portal>
}
```

- 重跑Popover、dialog、select已有测试和 `npm run typecheck`。Electron检查展开前后 `document.documentElement.scrollWidth <= innerWidth + 1`，父容器宽度不变，200%仍可关闭和提交。提交 `feat: add shared accessible popover for data tools`。

## R1-04：数据卡片与按需查询工具

**Files:** Modify `apps/desktop/src/renderer/domains/project-data/components/DataTableDirectory.tsx`、`apps/desktop/src/renderer/domains/project-data/components/DataTableDirectory.test.tsx`、`apps/desktop/src/renderer/domains/project-data/components/RecordFilterEditor.tsx`、`apps/desktop/src/renderer/domains/project-data/pages/DataTableDetailPage.tsx`、`apps/desktop/src/renderer/domains/project-data/pages/DataTableDetailPage.test.tsx`；Create `apps/desktop/src/renderer/domains/project-data/components/RecordQueryToolbar.tsx`、`apps/desktop/src/renderer/domains/project-data/components/RecordQueryToolbar.test.tsx`。

- 测试默认不见完整筛选表单；打开改变字段后取消不触发onApply；应用调用一次并回第一页；选列/排序各自取消不修改已应用值；原高级表达式仍可编辑。
- 执行 `npm test -- src/renderer/domains/project-data/components/RecordQueryToolbar.test.tsx src/renderer/domains/project-data/pages/DataTableDetailPage.test.tsx`，新行为先失败。
- 使用Popover+现有RecordFilterEditor，封装查询草稿边界。目标事件合同：

```ts
// props中的filter/orderBy类型沿用record-query.ts既有类型；不新造后端语法。
type QueryPanel = 'filter' | 'sort' | 'columns' | null
// open: draft = structuredClone(applied)
// cancel/Escape/outside: panel = null，丢弃查询草稿，不调用onApply
// apply: 校验既有query模型→onApply(draft)→page=1→panel=null
// generation变化: 清理失效fieldId并提示；原记录命令不重发。
```

- 卡片保留本地/Excel标识、真实recordCount和来源摘要，不能对未知数量用 `?? 0`。来源问题/更多按钮不触发打开卡片。Records主工具保留新增、批状态、导出；没有新模拟功能。
- 重跑上述测试、目录测试和 `npm run typecheck`；真实筛选→排序→分页→刷新错误保留旧内容，再检查宽度和键盘；提交 `refactor: align data directory cards and compact query tools`。

## R1-05：反馈去重与R1验收

**Files:** Modify `apps/desktop/src/renderer/shared/components/Toaster.tsx`、`apps/desktop/src/renderer/shared/components/Toaster.test.tsx`；Create `docs/project-management/design-alignment/acceptance/r1/README.md`、`docs/project-management/design-alignment/acceptance/r1/verification.json`和截图；Modify本包实际消费者的通知调用。

关键计时反例（放入既有Toaster测试文件，恢复真实timer放afterEach）：

```tsx
it('limits visible notices and expires an updated operation from its latest update', () => {
  vi.useFakeTimers()
  render(<Toaster />)
  act(() => {
    notify({ title: '已保存', operationId: 'operation-a' })
    notify({ title: '已创建B' })
    notify({ title: '已创建C' })
    notify({ title: '已创建D' })
  })
  expect(screen.getAllByRole('status').length).toBeLessThanOrEqual(3)
  act(() => vi.advanceTimersByTime(2000))
  act(() => notify({ title: '同一操作已核验', operationId: 'operation-a' }))
  act(() => vi.advanceTimersByTime(1000))
  expect(screen.getByText('同一操作已核验')).toBeInTheDocument()
  act(() => vi.advanceTimersByTime(1750))
  expect(screen.queryByText('同一操作已核验')).not.toBeInTheDocument()
})
```

- fake timers测试4次普通成功仅最多3条可见且溢出合并；同operationId更新原条目并重置到期计时；取消/卸载清计时器；2600ms后进入150ms退出，不产生迟到删除新消息。
- 执行 `npm test -- src/renderer/shared/components/Toaster.test.tsx`，新增断言先失败。
- 保留notify返回数值ID兼容，增加可选operationId；有operationId时按其合并，否则按生成ID独立。溢出的普通成功汇总为“另有N项操作已完成”，具体成功仍可在业务对象查询；错误留页面alert，不只依赖Toast。`Map<number, {dismiss, remove}>`管理计时器，更新时清旧timer。所有当前消费者无需强制拥有operationId。
- 运行R1涉及前端测试、typecheck/lint/build，并真实验收：最近/全部、数据目录、三个查询面板、刷新失败、200%和无横向撑宽。R1报告记录原型ID和截图，未来功能未执行。提交 `fix: bound operation notifications and verify aligned directories`。

R1完成后提交用户验收；不能用R1目录截图宣称独立记录页或字段聚合已完成。


## 2026-09-13 执行基线与已确认补充

状态：开发完成、待用户 R1 验收。用户已确认 B0，并明确要求实施 R1；阶段起点 `1e79c7b`，分支 `codex/project-management-implementation`。原三个未跟踪 QA 目录保留。本阶段不修改后端、HTTP、IPC、迁移或 DTO；R2/R3 未开始。B0 历史核验报告保持不变，当前状态以实施账本为准。

执行顺序：准备 → R1-03 → R1-01/R1-02 → R1-04 → R1-05 → R1 验收。

| 责任人 | 独占文件范围 |
| --- | --- |
| 主协调 | 共享 Popover/Toaster、依赖锁、App、ProjectsWorkspace、查询 Hook、数据页面协调、QA 工具与阶段资料 |
| 目录组件智能体 | ProjectHeader、ProjectTabs、ProjectCard、ProjectDirectory 与组件测试 |
| 数据查询组件智能体 | RecordQueryToolbar、受控查询编辑内容与对应测试 |
| 独立审查 | 只读规格审查后工程审查，问题由原负责人修正 |

明确实施约束：

- 最近与全部独立查询；稳定工作区保存模式、全部查询、各视图滚动位置，切换工作区不删除浏览偏好。真实切换仍清理活动对象及编辑上下文。
- 快捷搜索采用指定文本字段：默认首个文本字段，恢复仍有效的选择；输入不查询，Enter/搜索才应用。无文本字段明确禁用。搜索 contains 与高级筛选 AND 组合，最终整体校验；超限拒绝，不删条件。记录与导出共用最终查询。
- 筛选、排序、选列互斥浮层。取消、Escape、外部点击及切换面板丢弃草稿；应用失败保留面板。筛选/排序回第一页，选列不重查且保留页码；无变更不触发重复请求。
- 查询面板随结构/代次变化关闭并清理失效引用；业务编辑草稿仍由既有保护管理。
- 记录工具栏统一新建、批状态、导出，移除重复操作但保留 PM2 真实能力。
- 通知最多三条，可选 operationId 去重且保持数字返回值；成功溢出汇总，错误不可汇总成成功。2600ms 停留、150ms 退出，清理全部计时器；项目去重身份包含工作区。

验收工具：新增 `scripts/qa-project-alignment-r1.mjs` 自动 smoke 与 `--manual`；仅操作工具标记的隔离目录，支持 52 项目/120 记录分页资料、真实竞争编辑、一次性读取失败及提交后响应丢失、服务/应用重启、截图和安全清理。不得新增生产调试接口。用户手测详见 `docs/project-management/design-alignment/acceptance/r1/manual-test.md`，逐项 R1-M01–09，执行结果与用户待验收分开。

阶段验证：npm test、openapi:check、typecheck、lint、build、test:scripts、test:structure；既有 smoke-project-data 与 smoke-pm2-detail-flows 保留业务断言；新增 R1 smoke；后端目录排序/组合筛选定向回归；git diff --check。Windows/其他架构/打包未运行如实标记。每包保留失败测试、通过测试、规格及工程审查记录，提交明确文件。

### 完成记录

- [x] 核对基线及文件责任，登记 B0 用户确认。
- [x] R1-03 共享浮层。
- [x] R1-01/02 组件与真实目录装配。
- [x] R1-04 查询工具与数据页面装配。
- [x] R1-05 通知、全模块核验及手测交付。


### 实际交付与证据（2026-09-13）

原任务说明保留供追溯，执行状态以此表与实施账本为准。人工用例不因开发完成而标通过。

| 包 | 提交 / 实际交付 | 验证与调整 |
| --- | --- | --- |
| 准备 | `9c7c354` | B0 用户确认、独立工作区与责任冻结。 |
| R1-03 | `fb7d02d` | Radix Popover；OverlayHost/Select/Dialog 是已有复用，不重新创建。 |
| R1-01/02 | `73a4bc8` | compact 页头、最近/全部、工作区偏好和真实路由恢复；ProjectTabs 原顺序/标签符合设计，只读复用。 |
| R1-05 基础 | `05aa3e9` | 有界通知、操作去重和计时器。 |
| R1-04 / 05 装配 | `4daa752` | 数据卡片、查询草稿、最终表达式与导出一致、作用域通知；200% 搜索换行，保持 PM2。 |
| R1 工具 | `a13e649` | 隔离资料/真实冲突/响应丢失/重启/双工作区，报告含提交和脚本/构建校验值。 |

[机器报告](../../project-management/design-alignment/acceptance/r1/verification.json)、[审查闭合](../../project-management/design-alignment/acceptance/r1/review-resolution.md)、[手动验收方案](../../project-management/design-alignment/acceptance/r1/manual-test.md)。前端 115 文件 865 项、后端定向 21 项及计划中构建/静态检查通过；两个 PM2 smoke 通过，R1 使用提交后的最新真实应用报告。用户 R1-M01–09、Windows、其他架构、打包验收未执行。

只有 R1 开发和本机自动验收完成；R1 用户验收待执行，R2/R3 未开始。R2 完整记录页面、R3 聚合字段保存不在本次结果内。

## 用户视觉复审后的整改（2026-09-13）

此前开发/自动测试完成记录为历史事实，整体视觉对齐结论由09b56f6审查撤回。当前执行 [整改规格和计划](2026-09-13-project-management-visual-remediation.md)，真实E2E和逐图比对双门槛；R1用户验收pending，R2/R3未开始。

## 2026-09-13 连续实施 R1 完成记录

状态：R1工程交付通过，用户手动验收未执行。按最新用户连续授权，工程、E2E、视觉门槛闭合后进入R2，不再等待阶段确认。此前等待用户文字为原执行机制，历史证据不覆盖。

- 实现提交253cd0b、c0ccb8b、25e7d33、5910508、d76cca9、7b582b2：卡片、紧凑层级、身份固定112px、浮层标题/固定底栏、集合标记、紧凑且保留多行语义的比较值、右上语义通知。
- 独立规格/工程双审发现并关闭：已应用标记、卡片对齐、长名全文、零列宽度、集合顺序、筛选底栏、截图遮挡及重启后视口恢复。70分筛选失败记录保留，修复后100%88分、200%87分。
- [工程报告](../../project-management/design-alignment/acceptance/r1-visual/continuous-machine-report.json)、[逐用例](../../project-management/design-alignment/acceptance/r1-visual/continuous-test-cases.md)、[逐图对照](../../project-management/design-alignment/acceptance/r1-visual/continuous-comparison.html)、[条款核验](../../project-management/design-alignment/acceptance/r1-visual/requirements.json)、[手动测试](../../project-management/design-alignment/acceptance/r1-visual/manual-test.md)。
- 前端115文件875测试通过；定向后端21测试；构建、类型、lint、OpenAPI、脚本22、结构3通过。R1真实链run-5V7HL2通过，PM2两组回归通过。原生文件面板和真实窗口200%由电脑工具验证限定范围。
- 主项目与旧仓未由本任务写入。Windows、其他架构、打包、用户手动用例未执行；源图库与失败证据保留。候选截图不是用户批准金图。
