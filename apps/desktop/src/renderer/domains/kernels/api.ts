import type { ApiClient } from '../../shared/api/client'
import type {
  DefaultKernel,
  DefaultKernelWrite,
  InstalledKernelList,
  KernelCatalog,
  KernelDownload,
  KernelOperation,
  KernelRef,
  License,
  LicenseWrite,
} from '../../shared/api/types'

const apiPath = (path: string) => `/api/v1/kernels${path}`
const segment = (value: string) => encodeURIComponent(value)
const providerRequest = { timeoutMs: 60_000 } as const

export function createKernelsApi(client: ApiClient) {
  return {
    catalog: () => client.request<KernelCatalog>(apiPath('/catalog'), providerRequest),
    installed: () => client.request<InstalledKernelList>(apiPath('/installed')),
    license: () => client.request<License>(apiPath('/license'), providerRequest),
    connect: (body: LicenseWrite) => client.request<License>(apiPath('/license'), {
      method: 'POST', body, ...providerRequest,
    }),
    disconnect: () => client.request<void>(apiPath('/license'), { method: 'DELETE' }),
    default: () => client.request<DefaultKernel>(apiPath('/default')),
    setDefault: (body: DefaultKernelWrite) => client.request<DefaultKernel>(apiPath('/default'), {
      method: 'PUT', body,
    }),
    download: (body: KernelDownload) => client.request<KernelOperation>(apiPath('/download'), {
      method: 'POST', body,
    }),
    cancel: (operationId: string) => client.request<KernelOperation>(
      apiPath(`/operations/${segment(operationId)}/cancel`),
      { method: 'POST' },
    ),
    remove: (kernel: KernelRef) => client.request<void>(
      `${apiPath(`/${segment(kernel.version)}`)}?edition=${encodeURIComponent(kernel.edition)}`,
      { method: 'DELETE' },
    ),
    checkUpdate: () => client.request<KernelCatalog>(apiPath('/check-update'), {
      method: 'POST', ...providerRequest,
    }),
  }
}

export type KernelsApi = ReturnType<typeof createKernelsApi>
