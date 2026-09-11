import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { ApiProvider } from '../../app/ApiProvider'
import type { ProfileWrite } from '../../shared/api/types'
import { profileKeys, useCreateProfile } from './hooks'

afterEach(() => vi.unstubAllGlobals())

it('places the sidecar instance before the resource in query keys', () => {
  expect(profileKeys.all('instance-1')).toEqual(['instance-1', 'profiles'])
  expect(profileKeys.proxyOptions('instance-1')).toEqual(['instance-1', 'proxy-options'])
})

it('does not retry a failed profile write', async () => {
  const fetchMock = vi.fn(async () => new Response(JSON.stringify({
    error: { code: 'INTERNAL_ERROR', message: 'failed', details: {}, requestId: 'request-1' },
  }), { status: 500 }))
  vi.stubGlobal('fetch', fetchMock)
  const wrapper = ({ children }: { children: ReactNode }) => (
    <ApiProvider baseUrl="http://127.0.0.1:1" token="secret" instanceId="instance-1">
      {children}
    </ApiProvider>
  )
  const { result } = renderHook(() => useCreateProfile(), { wrapper })

  await act(async () => {
    await result.current.mutateAsync({} as ProfileWrite).catch(() => undefined)
  })

  expect(fetchMock).toHaveBeenCalledTimes(1)
})
