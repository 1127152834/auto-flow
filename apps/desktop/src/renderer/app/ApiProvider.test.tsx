import '@testing-library/jest-dom/vitest'
import { useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { useEffect, useState } from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import type { StreamingApiClient } from '../shared/api/client'
import { ApiProvider, useApi } from './ApiProvider'

afterEach(cleanup)
function Probe({ observe }: { observe(client: QueryClient): void }) {
  const api = useApi(), client = useQueryClient(), [draft, setDraft] = useState('')
  const query = useQuery({ queryKey: ['record', api.instanceId], queryFn: () => api.client.request<string>('/record'), retry: false })
  useEffect(() => observe(client), [client, observe])
  return <><output>{query.data ?? 'loading'}</output><input aria-label="draft" value={draft} onChange={event => setDraft(event.target.value)} /><button onClick={() => client.setQueryData(['record', api.instanceId], 'saved')}>save</button></>
}
const transport = (request: () => Promise<string>) => ({ request, health: vi.fn(), stream: vi.fn() }) as StreamingApiClient
it('keeps live query observers and drafts attached to the same cache after a service reconnect', async () => {
  const seen: QueryClient[] = [], observe = (client: QueryClient) => { seen.push(client) }
  const old = transport(async () => 'old'), next = transport(async () => 'new')
  const view = render(<ApiProvider baseUrl="http://old" token="old" instanceId="old" client={old}><Probe observe={observe}/></ApiProvider>)
  await screen.findByText('old'); fireEvent.change(screen.getByLabelText('draft'), { target: { value: 'unsaved' } })
  view.rerender(<ApiProvider baseUrl="http://new" token="new" instanceId="new" client={next}><Probe observe={observe}/></ApiProvider>)
  await screen.findByText('new'); fireEvent.click(screen.getByText('save'))
  expect(await screen.findByText('saved')).toBeVisible()
  expect(screen.getByLabelText('draft')).toHaveValue('unsaved')
  expect(new Set(seen).size).toBe(1)
})
it('isolates a late old instance response and creates a fresh cache for a different workspace', async () => {
  let finish!: (value: string) => void
  const old = transport(() => new Promise(resolve => { finish = resolve })), next = transport(async () => 'new')
  const observe = vi.fn()
  const view = render(<ApiProvider key="workspace-a" baseUrl="http://old" token="old" instanceId="old" client={old}><Probe observe={observe}/></ApiProvider>)
  fireEvent.change(screen.getByLabelText('draft'), { target: { value: 'unsaved' } })
  view.rerender(<ApiProvider key="workspace-a" baseUrl="http://new" token="new" instanceId="new" client={next}><Probe observe={observe}/></ApiProvider>)
  await screen.findByText('new'); await act(async () => finish('late old'))
  expect(screen.queryByText('late old')).not.toBeInTheDocument()
  const first = observe.mock.calls[0][0]
  view.rerender(<ApiProvider key="workspace-b" baseUrl="http://new" token="new" instanceId="new" client={next}><Probe observe={observe}/></ApiProvider>)
  await screen.findByText('new'); expect(screen.getByLabelText('draft')).toHaveValue('')
  expect(observe.mock.calls.at(-1)![0]).not.toBe(first)
})
