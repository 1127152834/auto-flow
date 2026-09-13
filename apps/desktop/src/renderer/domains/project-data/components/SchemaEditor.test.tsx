import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { SchemaEditor } from './SchemaEditor'

afterEach(cleanup)
beforeEach(() => {
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
  HTMLElement.prototype.hasPointerCapture = vi.fn(() => false)
  HTMLElement.prototype.setPointerCapture = vi.fn()
  HTMLElement.prototype.releasePointerCapture = vi.fn()
  HTMLElement.prototype.scrollIntoView = vi.fn()
})
const field = { ref: { projectId: 'p', tableId: 't', datasetGeneration: 'g', fieldId: 'f' }, key: 'title', name: '标题', type: 'string' as const, required: false, validation: {}, writable: true, formula: false, fieldRevision: 1 }
const props = { sessionKey: 's', generation: 'g', tableName: '资料库', sourceLabel: '空白表', directory: { tableRevision: 2, items: [field] }, onPreview: vi.fn(), onSubmit: vi.fn(), onReset: vi.fn() }
const impact = { impactRevision: 9, calculatedAt: '2026-09-14T00:00:00Z', expiresAt: '2026-09-14T00:10:00Z', affectedRecords: 0, backfillBytes: 0, blockers: [], warnings: [], referenceAvailability: { automations: 'notImplemented', sync: 'notImplemented' } }

it('keeps the gallery table and applies drawer changes locally before one outer save', async () => {
  const user = userEvent.setup(), onPreview = vi.fn().mockResolvedValue(impact), onSubmit = vi.fn().mockResolvedValue({})
  render(<SchemaEditor {...props} onPreview={onPreview} onSubmit={onSubmit} />)
  expect(screen.getByRole('table', { name: '字段与校验' })).toBeVisible()
  expect(screen.getByRole('button', { name: /^保存字段$/ })).toBeDisabled()
  await user.click(screen.getByRole('button', { name: '编辑字段 标题' }))
  await user.clear(screen.getByLabelText('显示名称'))
  await user.type(screen.getByLabelText('显示名称'), '文章标题')
  await user.click(screen.getByRole('button', { name: '应用到草稿' }))
  expect(onPreview).not.toHaveBeenCalled()
  expect(onSubmit).not.toHaveBeenCalled()
  expect(screen.getByRole('cell', { name: /文章标题/ })).toBeVisible()
  await user.click(screen.getByRole('button', { name: /^保存字段$/ }))
  await waitFor(() => expect(screen.getByRole('button', { name: '确认保存字段' })).toBeVisible())
  await user.click(screen.getByRole('button', { name: '确认保存字段' }))
  await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1))
  expect(onSubmit.mock.calls[0][0]).toMatchObject({ impactRevision: 9, candidate: { fields: [{ fieldId: 'f', definition: { name: /文章标题/ } }] } })
})

it('returning from impact preserves the draft and blockers prevent committing', async () => {
  const user = userEvent.setup(), onSubmit = vi.fn()
  render(<SchemaEditor {...props} onSubmit={onSubmit} restoredCandidate={{ datasetGeneration: 'g', expectedTableRevision: 2, fields: [{ kind: 'existing', fieldId: 'f', expectedFieldRevision: 1, definition: { key: 'title', name: '新标题', type: 'string', required: true, validation: {} } }] }} onPreview={vi.fn().mockResolvedValue({ ...impact, blockers: [{ code: 'FIELD_VALUES_INCOMPATIBLE', fieldId: 'f', clientId: null, message: 'bad values', affectedRecords: 3 }] })} />)
  await user.click(screen.getByRole('button', { name: /^保存字段$/ }))
  expect(await screen.findByText(/3 条记录不满足新的字段规则/)).toBeVisible()
  expect(screen.getByRole('button', { name: '确认保存字段' })).toBeDisabled()
  await user.click(screen.getByRole('button', { name: '返回修改' }))
  expect(screen.getByRole('cell', { name: /新标题/ })).toBeVisible()
  expect(onSubmit).not.toHaveBeenCalled()
})


it('lets an unknown save return to its original-key recovery action without allowing another save', async () => {
  const user = userEvent.setup(), recover = vi.fn().mockResolvedValue({});
  const restoredCandidate = { datasetGeneration:'g', expectedTableRevision:2, fields:[{kind:'existing' as const,fieldId:'f',expectedFieldRevision:1,definition:{key:'title',name:'草稿',type:'string' as const,required:false,validation:{}}}] };
  const view = render(<SchemaEditor {...props} restoredCandidate={restoredCandidate} onPreview={vi.fn().mockResolvedValue(impact)} onRecover={recover}/>);
  await user.click(screen.getByRole('button',{name:/^保存字段$/}));
  await screen.findByRole('button',{name:'确认保存字段'});
  view.rerender(<SchemaEditor {...props} restoredCandidate={restoredCandidate} recoveryPending onRecover={recover}/>);
  expect(screen.getByRole('button',{name:'确认保存字段'})).toBeDisabled();
  await user.click(screen.getByRole('button',{name:'返回核对保存结果'}));
  await user.click(screen.getByRole('button',{name:'核对保存结果'}));
  expect(recover).toHaveBeenCalledTimes(1);
});
