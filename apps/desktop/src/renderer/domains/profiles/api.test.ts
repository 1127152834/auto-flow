import { expect, it, vi } from 'vitest'
import type { ApiClient } from '../../shared/api/client'
import type { ProfileDuplicate, ProfileWrite } from '../../shared/api/types'
import { createProfilesApi, createProxyOptionsApi } from './api'

it('exposes the fixed profile and proxy-option requests', () => {
  const request = vi.fn()
  const client = { request, health: vi.fn() } as unknown as ApiClient
  const profiles = createProfilesApi(client)
  const proxyOptions = createProxyOptionsApi(client)
  const write = {} as ProfileWrite
  const duplicate = { name: '副本' } as ProfileDuplicate

  profiles.list()
  profiles.environmentOptions()
  profiles.create(write)
  profiles.update('profile/id', write)
  profiles.remove('profile/id')
  profiles.duplicate('profile/id', duplicate)
  profiles.openTestBrowser('profile/id')
  profiles.testBrowsers()
  profiles.closeTestBrowser('profile/id')
  profiles.regenerate('profile/id')
  proxyOptions.list()

  expect(Object.keys(profiles)).toEqual(['list', 'environmentOptions', 'create', 'update', 'remove', 'duplicate', 'openTestBrowser', 'testBrowsers', 'closeTestBrowser', 'regenerate'])
  expect(request.mock.calls).toEqual([
    ['/api/v1/profiles'],
    ['/api/v1/profiles/environment-options'],
    ['/api/v1/profiles', { method: 'POST', body: write }],
    ['/api/v1/profiles/profile%2Fid', { method: 'PUT', body: write }],
    ['/api/v1/profiles/profile%2Fid', { method: 'DELETE' }],
    ['/api/v1/profiles/profile%2Fid/duplicate', { method: 'POST', body: duplicate }],
    ['/api/v1/profiles/profile%2Fid/test-browser', { method: 'POST', timeoutMs: 120_000 }],
    ['/api/v1/profiles/test-browsers'],
    ['/api/v1/profiles/profile%2Fid/test-browser', { method: 'DELETE', timeoutMs: 120_000 }],
    ['/api/v1/profiles/profile%2Fid/regenerate-fingerprint', { method: 'POST' }],
    ['/api/v1/proxy-options'],
  ])
})
