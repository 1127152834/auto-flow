# R2 独立记录详情与编辑 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将记录详情、新增、编辑恢复为真实独立页面，保留完整typed身份、列表返回状态、草稿、版本冲突和原命令恢复。

**Architecture:** 路由仍由现有hash owner负责；将Modal里的表单逻辑提取后复用现有编辑协调Hook。平台外链通过受控IPC，页面不使用Node或任意shell。

**Tech Stack:** React、TypeScript、现有表单/Modal/Select、Electron IPC、Vitest、现有FastAPI记录接口。

---

前置：B0的R2正常/错误画板已确认，R1页头/工具栏可复用。RecordRef不换身份模型；不模拟PM4占用。不新增记录HTTP体系。

## R2-01：规范键编码与路由

**Files:** Create `apps/desktop/src/renderer/domains/project-data/record-route.ts`、`apps/desktop/src/renderer/domains/project-data/record-route.test.ts`；Modify `apps/desktop/src/renderer/domains/projects/types.ts`、`apps/desktop/src/renderer/app/navigation.ts`、`apps/desktop/src/renderer/app/navigation.test.tsx`、`apps/desktop/src/renderer/domains/project-data/records-api.ts`、`apps/desktop/src/renderer/domains/project-data/records-api.test.ts`。

- [ ] 用下列反例先测试新增纯函数，整合到已有导航测试时使用有效UUID项目/表/代次：

```ts
import { describe, expect, it } from 'vitest'
import { encodeRecordKey, decodeRecordKey } from './record-route'
describe('record route identity', () => {
  it.each(['001', '1', '中文/📄?x=1', '文'.repeat(8000)])('round trips text %s', value => {
    expect(decodeRecordKey('text', encodeRecordKey({ type: 'text', value }))).toEqual({ type: 'text', value })
  })
  it('retains key type independently', () => {
    const value = encodeRecordKey({ type: 'text', value: '1' })
    expect(decodeRecordKey('text', value)).not.toEqual(decodeRecordKey('integer', value))
  })
  it('rejects invalid Unicode and noncanonical encodings', () => {
    expect(() => encodeRecordKey({ type: 'text', value: '\ud800' })).toThrow()
    expect(() => decodeRecordKey('text', 'MQ==')).toThrow()
    expect(() => decodeRecordKey('integer', 'MDAx')).toThrow()
  })
})
```

- [ ] 执行 `npm test -- src/renderer/domains/project-data/record-route.test.ts src/renderer/app/navigation.test.tsx`，先因缺模块或路由失败。
- [ ] 从records-api提取现有UTF-8 base64url编码函数，不改变filter/orderBy编码。新增decode须严格校验无padding、base64url字母、fatal UTF-8、encode回转一致；文本非空≤8000码点且拒孤立代理，整数JSON-safe且规范十进制，uuid小写标准形式。后端仍最终校验。
- [ ] 在ProjectRoute添加记录分支并实现parse/hash双向；具体类型和路由如下：

```ts
import type { RecordKey } from '../project-data/records-api'
export type RecordLocation =
  | { mode: 'create' }
  | { mode: 'detail' | 'edit'; datasetGeneration: string; recordKey: RecordKey }
// 既有ProjectRoute增加record?: RecordLocation；仅tab=data且tableId/dataTab=records可用。
// records/new = 6段；records/{generation}/{type}/{encoded} = 8段；编辑末尾/edit = 9段。
// 解析失败返回现有error分支，不回退到另一条记录，也不截断长键。
```

- [ ] 重跑路由、records-api和typecheck；追加UUID、负数/0、+1/-0/超安全整数、8001码点、坏generation、跨项目返回、保留字歧义的明确断言。提交 `feat: add stable typed routes for project records`。

## R2-02：表单内容从Modal中提取

**Files:** Create `apps/desktop/src/renderer/domains/project-data/components/RecordEditorForm.tsx`、`apps/desktop/src/renderer/domains/project-data/components/RecordEditorForm.test.tsx`；Modify `apps/desktop/src/renderer/domains/project-data/components/RecordEditorDialog.tsx`、`apps/desktop/src/renderer/domains/project-data/components/RecordEditorDialog.test.tsx`、`apps/desktop/src/renderer/domains/project-data/components/ScalarValueEditor.tsx`、`apps/desktop/src/renderer/domains/project-data/components/ScalarValueEditor.test.tsx`（以上均在同一components目录）；Read `apps/desktop/src/renderer/domains/project-data/record-draft.ts`、`apps/desktop/src/renderer/domains/project-data/scalar-draft.ts`。

- [ ] 增加表单测试：编辑无关字段时未改异常单元格不被写出；身份字段/公式只读；错误聚焦实际控件；同工作区submissionEpoch变但session不变保留脏值；切换session重建基线；双击只提交一次。
- [ ] 运行 `npm test -- src/renderer/domains/project-data/components/RecordEditorForm.test.tsx src/renderer/domains/project-data/components/RecordEditorDialog.test.tsx`，新增能力先失败。
- [ ] 将已有草稿、冻结FormContext、fieldErrors、requestEpoch、锁和submit/recover代码原样归入可独立渲染的表单；用下列Props划分，避免重新实现recordValues：

```ts
// RecordEditorForm导出Props沿用RecordEditorDialogProps中的业务字段，
// 移除open/onOpenChange，增加id:string和footer?:ReactNode。
// 表单始终已挂载，sessionKey唯一决定重置；页面不以instanceId作为React key。
// RecordEditorDialog保留Modal+离开确认，并把业务props转交RecordEditorForm。
// onSubmit仍接收DataCellWrite[]；recordValues(fields,drafts,initialRecord,identityFieldId)唯一生成差量。
```

- [ ] ScalarValueEditor新增可选 `presenceDisplay: 'always' | 'contextual'`，默认always保持其他消费者；记录页使用contextual。普通值直接输入，展开“值选项”才能切missing/null；已为missing/null/异常时保留明确标签。false/0/空字符串不因truthy判断丢失。
- [ ] 重跑record-draft、scalar-draft、三组件测试及typecheck；确认提取前已有保护反例仍过。提交 `refactor: reuse record form logic across page and dialog shells`。

## R2-03：记录详情与编辑页面装配

**Files:** Create `apps/desktop/src/renderer/domains/project-data/pages/RecordDetailPage.tsx`、`apps/desktop/src/renderer/domains/project-data/pages/RecordEditPage.tsx`、`apps/desktop/src/renderer/domains/project-data/pages/RecordPages.test.tsx`；Create `apps/desktop/src/renderer/domains/project-data/components/RecordFieldsView.tsx`；Modify `apps/desktop/src/renderer/domains/project-data/pages/DataTableDetailPage.tsx`、`apps/desktop/src/renderer/domains/project-data/pages/DataTableDetailPage.test.tsx`、`apps/desktop/src/renderer/domains/projects/pages/ProjectsWorkspace.tsx`。

页内容的布局合同（RecordFieldsView只展示字段值，写动作由协调器传入）：

```tsx
// RecordDetailPage中的内容区：不是Dialog；右侧是内容，不是导航。
<section aria-label="记录详情" className="grid min-w-0 gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
  <div className="min-w-0">{fieldsView}</div>
  <section aria-label="业务状态" className="min-w-0">{statusForm}</section>
</section>
// RecordEditPage主内容预留底栏空间，footer组件使用现有sticky层级。
<main className="min-w-0 pb-24">{editorForm}</main>
```

`fieldsView/statusForm/editorForm`是对应页面props中的ReactNode，由DataTableDetailPage用RecordFieldsView、状态编辑内容和RecordEditorForm构造；页面壳不拥有第二套数据查询或命令。直接URL测试必须断言记录内容位于main且无新增/编辑dialog。

- [ ] 测试直接打开详情URL不依赖列表预加载；data/ref不匹配拒绝呈现；404提供返回列表；旧代次不能自动转到新记录。查看→编辑→保存通过真实API客户端，详情主内容不是role=dialog。
- [ ] 执行 `npm test -- src/renderer/domains/project-data/pages/RecordPages.test.tsx src/renderer/domains/project-data/pages/DataTableDetailPage.test.tsx`，新页面先失败。
- [ ] 保持DataTableDetailPage为同表作用域协调器，按route.record组合列表或记录子页，避免路由切换反复卸载编辑Hook；ProjectsWorkspace继续唯一项目与导航上下文。记录读取用createRecordsApi.get，queryKey包括workspace、instance、project、table、generation、keyType、keyValue，传AbortSignal。
- [ ] 详情左字段右业务状态/更新时间；状态选择+显式保存复用RecordStatusDialog的业务调用，可提取内容而不复制版本逻辑；删除复用DataDeletionDialog和影响预检。窄宽两栏上下排列，长值wrap/展开。
- [ ] 新增/编辑页组合RecordEditorForm及固定页脚，底栏预留空间不盖字段。点击列表新增/编辑改为onNavigate，不再打开旧Modal。取消走现有guard；提交成功的返回route由确认响应的RecordRef生成，不能用用户草稿键猜身份。
- [ ] 重跑页面/编辑Hook/原表测试，人工从真实界面新增、编辑、单条设置/清空状态、删除，校验业务状态不随内容保存自动改变。提交 `feat: align record detail and editing as dedicated pages`。

## R2-04：受控外链桥

**Files:** Create `apps/desktop/src/shared/external-links.ts`、`apps/desktop/src/main/ipc/external-links.ts`、`apps/desktop/src/main/ipc/external-links.test.ts`；Modify `apps/desktop/src/main/index.ts`、`apps/desktop/src/main/index.test.ts`、`apps/desktop/src/preload/index.ts`、`apps/desktop/src/preload/index.test.ts`、`apps/desktop/src/renderer/shared/api/types.ts`、`apps/desktop/src/renderer/domains/project-data/components/RecordFieldsView.tsx`。

合同只增加 `openExternalLink(url:string): Promise<DesktopResult<{opened:true}>>`；复制用现有系统允许的clipboard API，只在用户点击时执行。main桥捕获异常并返标准DesktopResult，不向renderer返回stack或任意路径。

- [ ] 测试不是当前窗口、子frame、无frame、file/javascript/data协议、相对URL、用户名密码URL全部拒绝，openExternal未被调用；合法https调用一次；OS拒绝时返回明确失败。
- [ ] 执行 `npm test -- src/main/ipc/external-links.test.ts src/preload/index.test.ts`，新增handler先失败。
- [ ] 复用kernel-paths中sender.id/mainFrame比较模式，依赖注入allowedSenderId与openExternal。纯URL校验实现如下；handler前置检查sender再调用它：

```ts
export function validatedExternalUrl(raw: unknown): string {
  if (typeof raw !== 'string' || /[\u0000-\u0020\u007f]/u.test(raw)) throw new Error('链接无效')
  const url = new URL(raw)
  if (!['http:', 'https:'].includes(url.protocol) || !url.hostname || url.username || url.password) throw new Error('仅支持 HTTP 或 HTTPS 链接')
  return url.href
}
```

- [ ] main注册固定IPC，preload只暴露命名函数；`AutoflowBridge`交叉加入可选ExternalLinkBridge，禁止renderer拥有ipcRenderer/shell。RecordFieldsView失败就地提示，打开失败不能Toast成功。
- [ ] 重跑main/preload测试和typecheck；真实点击本地测试站HTTP链接并检查目标，测试合法HTTPS只验证系统打开，不要求访问外网成功。提交 `feat: open record links through controlled desktop IPC`。

## R2-05：返回、草稿与恢复完整回归

**Files:** Modify `apps/desktop/src/renderer/domains/project-data/use-data-table-editing.ts`、`apps/desktop/src/renderer/domains/project-data/use-data-table-editing.test.tsx`、`apps/desktop/src/renderer/app/navigation.test.tsx`、`apps/desktop/src/renderer/domains/project-data/pages/RecordPages.test.tsx`；Create `apps/desktop/src/renderer/domains/project-data/record-return-state.ts`、`apps/desktop/src/renderer/domains/project-data/record-return-state.test.ts`；Modify `scripts/smoke-project-data.mjs`。

- [ ] 补反例：UUID系统键的未确认命令恢复；当前validTarget仅接受text/integer，需按生成RecordKey合法联合验证uuid，不允许任意字符串放行。后端身份校验不改。
- [ ] 运行 `npm test -- src/renderer/domains/project-data/use-data-table-editing.test.tsx src/renderer/domains/project-data/record-return-state.test.ts src/renderer/app/navigation.test.tsx`，新UUID/返回路径先失败。
- [ ] 返回快照结构如下，采用已有表查询状态序列化与校验，不保存任意URL；具体filter/orderBy类型使用record-query现有类型：

```ts
type RecordReturnIdentity = {
  workspaceKey: string; projectId: string; tableId: string; datasetGeneration: string
}
// sessionStorage键只含workspace/project/table；值包含identity及现有查询/列/页码/scrollTop。
// 详情新增originRowKey只用于恢复焦点，不能作为写入target。
// 直接URL无快照→当前表records第一页；旧代次→提示变化、清理无效fieldId，不沿用旧记录target。
```

- [ ] 单次导航保持useDataTableEditing实例；草稿按workspace/project/table/session恢复，读请求额外按instance隔离。后台刷新只更新可用远端事实；409保留draft；未知先查原key；确认完成的迟到响应不更改新页面。未确认持久命令离开视图后仍可回原作用域核验，不用close清掉localStorage。
- [ ] 测试真实前进/后退取消后URL与UI一致；页签/全局导航/Escape/遮罩均保护；真实换工作区禁止提交，同工作区重连不吃草稿。重跑上述测试及data-command/records-api测试。
- [ ] 更新smoke从Modal选择器改为页面语义选择器，保留旧断线/CAS/双工作区断言，不删失败测试来过关。运行 `npm run build` 后 `node scripts/smoke-project-data.mjs`；记录R2截图/机器结果，提交 `fix: preserve record drafts and return context across navigation`。

R2出口：真实列表→详情→编辑→状态→删除→返回流程，以及响应未知/服务重启/工作区隔离通过；外链IPC与长typed键通过。原型占用、环境关联和任务跳转保留未来边界，不以R2验收为PM4背书。

## 连续实施执行卡（2026-09-13）

状态：**进行中**。用户已授权阶段门槛通过后自动继续；本阶段未通过前不进入 R3。

- 前置 R1 已以 `762234d` 保存工程、真实测试、逐图审查和手测资料；用户手测仍未执行。
- R2-01：`954bb79` typed 路由/API 编码，`4bc97df` 修复 U+FEFF 文本身份。规格与工程独立审查通过。
- R2-02：`3e7f6e6` 表单抽取，审查修复 `3bb9615` / `a5deb39` / `c128def`；覆盖异步关闭跨会话、恢复中放弃、固定 Modal 底栏、失败校验后迟到关闭。规格与工程审查均已闭合。
- R2-03：`c590e37` 字段展示及独立页面壳，6 项组件测试与类型检查；规格、工程审查通过，真实路由/页面装配正在进行，不能用组件结果替代真实流程。
- R2-04：`5f2e1d6` 主窗口/主 frame 限定的外链桥，固定协议及错误边界。26 项 handler/main/preload 测试通过，规格与工程审查通过；实际 OS 浏览器打开仍待执行。
- 状态内联子包：`56ed7fe` 复用原 RecordStatusDialog 行为，规格已审；装配必须在确认保存后建立新 session，不能用后台刷新覆盖脏基线。集成测试已验证保存后取消保持新状态以及重复 null 清空。
- R2-05：UUID 未确认编辑恢复反例已先失败，修复使用既有 typed identity 验证；列表返回状态从既有序列化提取，新增工作区/数据代次与焦点身份。正在集成验证。

文件责任：组件智能体仅维护 RecordEditorForm/Dialog、ScalarValueEditor、RecordStatusDialog 和对应测试；协调者独占页面、ProjectsWorkspace 装配、记录 API、编辑 Hook、返回状态、脚本与公共文档。审查智能体只读。

正在执行的验证：页面/API/Hook/返回状态定向测试、类型检查、lint/build；之后真实 Electron/FastAPI/隔离 SQLite 的 UI 新增→详情→编辑→状态→删除→返回、冲突与响应丢失、服务重连、重启和工作区隔离，以及 R2 各画板的截图比对。

尚未执行：本阶段完整 E2E、逐图最终评分、Windows/其他架构/打包、用户手测。上述项目不得标记通过。

### R2-F 冲突页内对照修正（2026-09-13）

- 将记录编辑冲突改为“我的修改 / 最新内容”并排区域；载入不替换输入，明确采用才重建最新修订基线。其他编辑对象保留既有确认弹窗。
- 规格审查发现比较快照跨编辑会话风险，已绑定 session 和带类型记录身份，路由/会话变化撤销异步票据；采用动作遵守保存与恢复锁。
- 定向验证：DataTableDetailPage 35 项测试通过，包含迟到比较不得进入另一记录、明确采用 revision=2 后提交使用该修订。独立规格与工程静态复核均无剩余阻断。
- 真实截图与阶段 E2E 另行核验，本记录不代替视觉通过。
