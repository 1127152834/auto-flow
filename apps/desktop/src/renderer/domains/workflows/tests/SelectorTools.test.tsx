import '@testing-library/jest-dom/vitest'
import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { SelectorTools } from '../components/SelectorTools'
import type { InspectionApi, InspectionPick, InspectionSession } from '../inspection-api'
import type { WorkflowNode } from '../types'

const session: InspectionSession = { sessionId: 'session', profileId: 'profile', profileName: 'test', state: 'ready', headless: false, pages: [{ pageId: 'page', url: 'http://localhost', title: 'test', revision: 1 }], targetPageId: 'page', pick: null, error: null }
const node: WorkflowNode = { id: 'node', type: 'click_element', label: '点击', config: { selector: '#before', framePath: [] } }
const picked: InspectionPick = { requestId: 'request', pageId: 'page', pageRevision: 1, state: 'selected', result: { selector: '#chosen', framePath: ['#outer', '#inner'], positional: false, tag: 'button', text: '选择目标' }, error: null }
function fixture() {
  const api: InspectionApi = { current: vi.fn().mockResolvedValue(session), start: vi.fn(), close: vi.fn(), page: vi.fn(), pick: vi.fn().mockResolvedValue(picked), getPick: vi.fn().mockResolvedValue(picked), cancel: vi.fn().mockResolvedValue({ ...picked, state: 'cancelled' }), test: vi.fn().mockResolvedValue({ pageId: 'page', pageRevision: 1, selector: '#before', framePath: [], count: 2, first: { tag: 'button', text: 'first', visible: true }, truncated: false }) }
  const apply = vi.fn(), commit = vi.fn()
  const props = { api, session, node, documentId: 'document', variables: [], disabled: false, apply, commit }
  const view = render(<SelectorTools {...props} />)
  return { api, apply, commit, props, ...view }
}
afterEach(cleanup)

it('previews a real response and applies selector plus frame path as one mutation', async () => {
  const user = userEvent.setup(), f = fixture()
  await user.click(screen.getByRole('button', { name: '拾取元素' }))
  await screen.findByLabelText('拾取结果预览')
  expect(f.apply).not.toHaveBeenCalled()
  await user.click(screen.getByRole('button', { name: '应用到节点' }))
  expect(f.apply).toHaveBeenCalledExactlyOnceWith({ selector: '#chosen', framePath: ['#outer', '#inner'] })
  expect(f.commit).toHaveBeenCalledTimes(2)
})
it.each(['node', 'document', 'selector', 'page'] as const)('invalidates a late result after %s changes', async kind => {
  const user = userEvent.setup(), f = fixture()
  let resolve!: (value: InspectionPick) => void
  vi.mocked(f.api.pick).mockReturnValue(new Promise(r => { resolve = r }))
  await user.click(screen.getByRole('button', { name: '拾取元素' }))
  const props = { ...f.props }
  if (kind === 'node') props.node = { ...node, id: 'another' }
  if (kind === 'document') props.documentId = 'another'
  if (kind === 'selector') props.node = { ...node, config: { selector: '#manual' } }
  if (kind === 'page') props.session = { ...session, pages: [{ ...session.pages[0], revision: 2 }] }
  f.rerender(<SelectorTools {...props} />)
  await act(async () => resolve(picked))
  expect(screen.queryByRole('button', { name: '应用到节点' })).not.toBeInTheDocument()
  expect(f.apply).not.toHaveBeenCalled()
})
it('tests count/visibility without changing config and invalidates it after an edit', async () => {
  const user = userEvent.setup(), f = fixture()
  await user.click(screen.getByRole('button', { name: '测试定位' }))
  await screen.findByText('匹配 2 个元素 · 首个可见')
  expect(f.apply).not.toHaveBeenCalled()
  f.rerender(<SelectorTools {...f.props} node={{ ...node, config: { selector: '#different' } }} />)
  await waitFor(() => expect(screen.queryByText('匹配 2 个元素 · 首个可见')).not.toBeInTheDocument())
})
