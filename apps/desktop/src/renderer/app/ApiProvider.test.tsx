import { useQueryClient, type QueryClient } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { useEffect } from 'react'
import { expect, it } from 'vitest'
import { ApiProvider, useApi } from './ApiProvider'

function Probe({ onQueryClient }: { onQueryClient(client: QueryClient): void }) {
  const api = useApi()
  const queryClient = useQueryClient()
  useEffect(() => { onQueryClient(queryClient) }, [onQueryClient, queryClient])
  return <span>{api.instanceId}</span>
}

it('creates an isolated query session when the sidecar instance changes', () => {
  const clients: QueryClient[] = []
  const onQueryClient = (client: QueryClient) => {
    if (!clients.includes(client)) clients.push(client)
  }
  const view = render(
    <ApiProvider baseUrl="http://127.0.0.1:1" token="old" instanceId="old-instance">
      <Probe onQueryClient={onQueryClient} />
    </ApiProvider>,
  )
  expect(screen.getByText('old-instance')).toBeTruthy()

  view.rerender(
    <ApiProvider baseUrl="http://127.0.0.1:2" token="new" instanceId="new-instance">
      <Probe onQueryClient={onQueryClient} />
    </ApiProvider>,
  )

  expect(screen.getByText('new-instance')).toBeTruthy()
  expect(clients).toHaveLength(2)
  expect(clients[0]).not.toBe(clients[1])
})
