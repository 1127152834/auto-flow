import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, expect, it, vi } from 'vitest'
import { SheetsColumnCreation } from './SheetsColumnCreation'
import type { SheetsSourceContext } from './DataTableSourcePanel'
import type { SheetsBinding } from '../sheets-api'

afterEach(cleanup)
const report = { impactRevision: 9, expectedRevisions: { tableRevision: 5 }, blockers: [] }
const binding = { connectionId:'c', spreadsheetId:'s', sheetId:0, bindingEpoch:1, mapping:[], identityStrategy:{kind:'column',columnId:'A'}, syncPaused:false } as SheetsBinding
function setup(items: object[] = []) {
  const api = { columnOperations:vi.fn().mockResolvedValue({ items, pageSize:100,total:items.length }), previewColumn:vi.fn().mockResolvedValue(report),
    createColumn:vi.fn().mockResolvedValue({status:'reconciling'}),previewOriginalColumn:vi.fn().mockResolvedValue(report),
    verifyColumn:vi.fn().mockResolvedValue({status:'succeeded'}),retryColumn:vi.fn(),cancelColumn:vi.fn() }
  const onChanged = vi.fn()
  const context = { api, tableId:'t', datasetGeneration:'g',tableRevision:5, scopeKey:'ws:p', fields:[{ref:{fieldId:'f'},name:'备注',writable:true,formula:false}], onChanged } as unknown as SheetsSourceContext
  render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><SheetsColumnCreation context={context} binding={binding} disabled={false}/></QueryClientProvider>)
  return {api,onChanged}
}
it('requires a selected field and source-write confirmation, keeping unknown results in recovery', async () => {
  const { api, onChanged } = setup()
  const button = screen.getByRole('button',{name:'确认新建来源列'})
  expect(button).toBeDisabled()
  await userEvent.selectOptions(screen.getByLabelText('新建来源列的本地字段'),'f')
  expect(button).toBeDisabled()
  await userEvent.click(screen.getByRole('checkbox'))
  await waitFor(() => expect(button).toBeEnabled())
  await userEvent.click(button)
  await waitFor(() => expect(api.createColumn).toHaveBeenCalledWith('t',expect.objectContaining({fieldId:'f',columnName:'备注',impactRevision:9,expectedBindingEpoch:1,datasetGeneration:'g'}),expect.any(String),expect.any(Function)))
  expect(await screen.findByText('来源列尚未确认，请核验原操作。')).toBeVisible()
  expect(onChanged).not.toHaveBeenCalled()
})
it('recovers the same unknown column and offers no unsafe cancellation or second create', async () => {
  const {api,onChanged} = setup([{kind:'column',syncOperationId:'original',status:'unknown',statusRevision:3}])
  await userEvent.click(await screen.findByRole('button',{name:'核验原来源列'}))
  await waitFor(() => expect(api.verifyColumn).toHaveBeenCalledWith('t','original',{impactRevision:9,expectedTableRevision:5}))
  expect(api.createColumn).not.toHaveBeenCalled()
  expect(api.retryColumn).not.toHaveBeenCalled()
  expect(screen.queryByRole('button',{name:'取消原未发送增列'})).not.toBeInTheDocument()
  expect(onChanged).toHaveBeenCalledOnce()
})
