import { expect, it, vi } from 'vitest'
import type { ApiClient } from '../../shared/api/client'
import type { DefaultKernelWrite, KernelDownload, KernelRef, LicenseWrite } from '../../shared/api/types'
import { createKernelsApi } from './api'

it('exposes the fixed kernel requests without retrying writes itself', () => {
  const request = vi.fn()
  const api = createKernelsApi({ request, health: vi.fn() } as unknown as ApiClient)
  const license = { licenseKey: 'secret' } as LicenseWrite
  const defaultKernel = {} as DefaultKernelWrite
  const download = {} as KernelDownload
  const kernel = { edition: 'licensed', version: '146.0.1.1' } as KernelRef

  api.catalog()
  api.installed()
  api.license()
  api.connect(license)
  api.disconnect()
  api.default()
  api.setDefault(defaultKernel)
  api.download(download)
  api.cancel('operation/id')
  api.remove(kernel)
  api.checkUpdate()

  expect(Object.keys(api)).toEqual([
    'catalog', 'installed', 'license', 'connect', 'disconnect', 'default', 'setDefault',
    'download', 'cancel', 'remove', 'checkUpdate',
  ])
  expect(request.mock.calls).toEqual([
    ['/api/v1/kernels/catalog', { timeoutMs: 60_000 }],
    ['/api/v1/kernels/installed'],
    ['/api/v1/kernels/license', { timeoutMs: 60_000 }],
    ['/api/v1/kernels/license', { method: 'POST', body: license, timeoutMs: 60_000 }],
    ['/api/v1/kernels/license', { method: 'DELETE' }],
    ['/api/v1/kernels/default'],
    ['/api/v1/kernels/default', { method: 'PUT', body: defaultKernel }],
    ['/api/v1/kernels/download', { method: 'POST', body: download }],
    ['/api/v1/kernels/operations/operation%2Fid/cancel', { method: 'POST' }],
    ['/api/v1/kernels/146.0.1.1?edition=licensed', { method: 'DELETE' }],
    ['/api/v1/kernels/check-update', { method: 'POST', timeoutMs: 60_000 }],
  ])
})
