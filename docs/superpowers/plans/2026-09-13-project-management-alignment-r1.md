# R1 页面层级与目录 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有顶部导航下交付最近项目卡片、全部项目目录、统一项目页头和紧凑数据工具栏，保留真实查询与返回状态。

**Architecture:** 现有项目API不变；组件先于页面。新增Popover只补真实缺口，Drawer复用现有Modal的placement，不新造浮层系统。

**Tech Stack:** React、TypeScript、Tailwind、现有shadcn/Radix、TanStack Query、Vitest、Electron。

---

前置：[总计划](2026-09-13-project-management-alignment-implementation.md)B0的R1画板已确认。所有命令在implementation工作区根目录执行，Vitest按相对desktop路径过滤。测试预期是行为断言通过，不预报测试数量。

## R1-01：项目和对象页头

**Files:** Modify `apps/desktop/src/renderer/domains/projects/components/ProjectHeader.tsx`、`apps/desktop/src/renderer/domains/projects/components/ProjectTabs.tsx`；Modify `apps/desktop/src/renderer/domains/projects/pages/ProjectOverviewPage.tsx`、`apps/desktop/src/renderer/domains/project-data/pages/DataTableDirectoryPage.tsx`、`apps/desktop/src/renderer/domains/project-data/pages/DataTableDetailPage.tsx`；Create `apps/desktop/src/renderer/domains/projects/components/ProjectHeader.test.tsx`。

- [ ] 先扩展页头props并写渲染测试，compact时仍有返回项目目录、项目名和编辑的可访问名称；归档禁编辑；六页签不改标签/顺序。

```tsx
// ProjectHeader.tsx：在现有props上增加，默认保留一级页行为。
type HeaderDensity = 'default' | 'compact'
// Props增加 density?: HeaderDensity；h1保持唯一页面标题，compact上下文改为p。
// 核心class：density === 'compact' ? 'text-base font-semibold' : 'text-2xl font-semibold'
// ProjectTabs持续使用nav/aria-current，不把原按钮导航变成无行为的TabPanel。
```

- [ ] 运行 `npm test -- src/renderer/domains/projects/components/ProjectHeader.test.tsx src/renderer/app/App.projects.test.tsx`，新compact断言先失败。
- [ ] 现有页头增加可选density，表/记录二级页使用compact上下文+对象h1；保留顶部全局导航，项目页签采用已有横向导航。仅样式布局变更不改项目状态模型。
- [ ] 重跑上面测试及 `npm run typecheck`；真实窗口检查长名称、200%缩放、页签滚动、h1层级与焦点，记录R1截图。提交 `refactor: align project header hierarchy with prototypes`。

## R1-02：最近卡片与全部目录

**Files:** Modify `apps/desktop/src/renderer/domains/projects/components/ProjectDirectory.tsx`、`apps/desktop/src/renderer/domains/projects/components/ProjectDirectory.test.tsx`、`apps/desktop/src/renderer/domains/projects/pages/ProjectsWorkspace.tsx`、`apps/desktop/src/renderer/domains/projects/pages/ProjectsWorkspace.test.tsx`、`apps/desktop/src/renderer/domains/projects/hooks.ts`；Create `apps/desktop/src/renderer/domains/projects/components/ProjectCard.tsx`。

目录模式为 `recent | all`，首次为recent，稳定工作区sessionStorage保存模式及all的原条件/滚动。最近调用现有目录接口固定active、`-lastOpenedAt`、page1/pageSize6，剔除未访问项；不能从用户当前搜索的某一页推算最近列表。全部目录继续服务端搜索、状态、排序和分页，不客户端加载所有项目；在最近视图输入搜索词时切到all并应用搜索/page1，不能只搜索六张最近卡片。

- [ ] 在ProjectsWorkspace测试中设置“最近A、未访问B、已归档C”和all第二页搜索条件；点击卡片打开再返回，必须恢复模式；进入全部再返回，搜索/页码/滚动不丢。新模式未实现时断言失败。

```ts
// hooks.ts：目标查询键/条件，使用已存在createProjectsApi.list。
const recentConditions = {
  query: '', lifecycle: 'active', sort: '-lastOpenedAt', page: 1, pageSize: 6,
} as const
// useProjectDirectory(api, workspaceKey, instanceId, recentConditions)
// 仅展示返回items中lastOpenedAt != null的项目；数量不足6时不拿未访问项目补齐。
```

- [ ] 运行 `npm test -- src/renderer/domains/projects/pages/ProjectsWorkspace.test.tsx src/renderer/domains/projects/components/ProjectDirectory.test.tsx`。
- [ ] ProjectCard使用article、独立标题button和兄弟“更多”按钮，避免交互元素嵌套；标题点击/Enter打开，更多里的编辑不触发open。更多只放已实现动作；卡片没有假统计，未访问全部项显示从未打开。最近无记录显示“尚无最近访问”，提供全部/新建入口，不称项目库为空。
- [ ] 保存模式与现有all条件分开字段；返回项目目录不重置它们。实际换工作区读对应存储，同工作区重连只刷新查询。创建/编辑后同时使recent/all查询失效，旧实例响应不能弹错成功。
- [ ] 同命令重跑并跑 `npm run typecheck`，用真实A/B项目验证最近顺序与重启持久事实；提交 `feat: restore recent project cards and full directory browsing`。

## R1-03：补Popover，复用现有浮层宿主

**Files:** Modify `apps/desktop/package.json`、`package-lock.json`；Create `apps/desktop/src/renderer/shared/components/ui/popover.tsx`、`apps/desktop/src/renderer/shared/components/ui/popover.test.tsx`。Read现有 `apps/desktop/src/renderer/shared/components/ui/overlay-host.tsx`、`apps/desktop/src/renderer/shared/components/ui/select-radix.tsx`、`apps/desktop/src/renderer/shared/components/ui/dialog.tsx`；不创建Drawer文件，现有 `apps/desktop/src/renderer/shared/components/ui/Modal.tsx` 已支持 `placement="drawer"`。

已核对本分支没有Popover，但有菜单、Select和Modal。筛选里有表单，不能用菜单item冒充表单行为。仅新增 `@radix-ui/react-popover`，锁定安装解析版本，不引入整套新UI。Radix支持受控打开、焦点管理和非模态面板，见[官方Popover文档](https://www.radix-ui.com/primitives/docs/components/popover)。

- [ ] 写测试：外层Modal→Popover内输入/Select；第一个Escape只关最上层，第二次才关父层；点击外部关闭Popover并恢复触发焦点，Tab可访问输入。
- [ ] 执行 `npm test -- src/renderer/shared/components/ui/popover.test.tsx`，因缺模块失败后运行 `npm install --workspace @autoflow/desktop @radix-ui/react-popover`。
- [ ] 新控件最小包装如下，受控关闭交给消费者；后续如有嵌套弹层问题必须修宿主交互并测试，不用页面CSS硬盖：

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

- [ ] 重跑Popover、dialog、select已有测试和 `npm run typecheck`。Electron检查展开前后 `document.documentElement.scrollWidth <= innerWidth + 1`，父容器宽度不变，200%仍可关闭和提交。提交 `feat: add shared accessible popover for data tools`。

## R1-04：数据卡片与按需查询工具

**Files:** Modify `apps/desktop/src/renderer/domains/project-data/components/DataTableDirectory.tsx`、`apps/desktop/src/renderer/domains/project-data/components/DataTableDirectory.test.tsx`、`apps/desktop/src/renderer/domains/project-data/components/RecordFilterEditor.tsx`、`apps/desktop/src/renderer/domains/project-data/pages/DataTableDetailPage.tsx`、`apps/desktop/src/renderer/domains/project-data/pages/DataTableDetailPage.test.tsx`；Create `apps/desktop/src/renderer/domains/project-data/components/RecordQueryToolbar.tsx`、`apps/desktop/src/renderer/domains/project-data/components/RecordQueryToolbar.test.tsx`。

- [ ] 测试默认不见完整筛选表单；打开改变字段后取消不触发onApply；应用调用一次并回第一页；选列/排序各自取消不修改已应用值；原高级表达式仍可编辑。
- [ ] 执行 `npm test -- src/renderer/domains/project-data/components/RecordQueryToolbar.test.tsx src/renderer/domains/project-data/pages/DataTableDetailPage.test.tsx`，新行为先失败。
- [ ] 使用Popover+现有RecordFilterEditor，封装查询草稿边界。目标事件合同：

```ts
// props中的filter/orderBy类型沿用record-query.ts既有类型；不新造后端语法。
type QueryPanel = 'filter' | 'sort' | 'columns' | null
// open: draft = structuredClone(applied)
// cancel/Escape/outside: panel = null，丢弃查询草稿，不调用onApply
// apply: 校验既有query模型→onApply(draft)→page=1→panel=null
// generation变化: 清理失效fieldId并提示；原记录命令不重发。
```

- [ ] 卡片保留本地/Excel标识、真实recordCount和来源摘要，不能对未知数量用 `?? 0`。来源问题/更多按钮不触发打开卡片。Records主工具保留新增、批状态、导出；没有新模拟功能。
- [ ] 重跑上述测试、目录测试和 `npm run typecheck`；真实筛选→排序→分页→刷新错误保留旧内容，再检查宽度和键盘；提交 `refactor: align data directory cards and compact query tools`。

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

- [ ] fake timers测试4次普通成功仅最多3条可见且溢出合并；同operationId更新原条目并重置到期计时；取消/卸载清计时器；2600ms后进入150ms退出，不产生迟到删除新消息。
- [ ] 执行 `npm test -- src/renderer/shared/components/Toaster.test.tsx`，新增断言先失败。
- [ ] 保留notify返回数值ID兼容，增加可选operationId；有operationId时按其合并，否则按生成ID独立。溢出的普通成功汇总为“另有N项操作已完成”，具体成功仍可在业务对象查询；错误留页面alert，不只依赖Toast。`Map<number, {dismiss, remove}>`管理计时器，更新时清旧timer。所有当前消费者无需强制拥有operationId。
- [ ] 运行R1涉及前端测试、typecheck/lint/build，并真实验收：最近/全部、数据目录、三个查询面板、刷新失败、200%和无横向撑宽。R1报告记录原型ID和截图，未来功能未执行。提交 `fix: bound operation notifications and verify aligned directories`。

R1完成后提交用户验收；不能用R1目录截图宣称独立记录页或字段聚合已完成。
