import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { useApi } from '../../app/ApiProvider'
import { watchKernelEvents } from '../../shared/api/events'
import { notify } from '../../shared/components/Toaster'
import type {
  DefaultKernelWrite,
  KernelDownload,
  KernelOperation,
  KernelRef,
  LicenseWrite,
} from '../../shared/api/types'

export const kernelKeys = {
  all: (instanceId: string) => [instanceId, 'kernels'] as const,
  catalog: (instanceId: string) => [instanceId, 'kernels', 'catalog'] as const,
  installed: (instanceId: string) => [instanceId, 'kernels', 'installed'] as const,
  license: (instanceId: string) => [instanceId, 'kernels', 'license'] as const,
  default: (instanceId: string) => [instanceId, 'kernels', 'default'] as const,
  operations: (instanceId: string) => [instanceId, 'kernels', 'operations'] as const,
}

type TerminalState = Extract<KernelOperation['state'], 'cancelled' | 'completed' | 'failed'>
type KernelEventsOptions = {
  onTerminal?(operation: KernelOperation & { state: TerminalState }): void
  onError?(error: unknown): void
}

const isTerminal = (operation: KernelOperation): operation is KernelOperation & { state: TerminalState } => (
  operation.state === 'cancelled' || operation.state === 'completed' || operation.state === 'failed'
)

const operationStateOrder: Record<KernelOperation['state'], number> = {
  queued: 0,
  downloading: 1,
  verifying: 2,
  extracting: 3,
  cancelling: 4,
  cancelled: 5,
  completed: 5,
  failed: 5,
}

export function mergeKernelOperation(current: KernelOperation | undefined, incoming: KernelOperation): KernelOperation {
  if (!current) return incoming
  if (isTerminal(current) || operationStateOrder[current.state] > operationStateOrder[incoming.state]) return current
  return incoming
}

export function upsertKernelOperation(current: KernelOperation[] = [], incoming: KernelOperation): KernelOperation[] {
  const index = current.findIndex((operation) => operation.id === incoming.id)
  if (index < 0) return [...current, incoming]
  const next = [...current]
  next[index] = mergeKernelOperation(current[index], incoming)
  return next
}

function notifyTerminal(operation: KernelOperation & { state: TerminalState }) {
  if (operation.state === 'completed') notify({ title: '内核安装完成', tone: 'success' })
  else if (operation.state === 'cancelled') notify({ title: '内核安装已取消', tone: 'info' })
  else notify({ title: operation.error ?? '内核安装失败', tone: 'error' })
}

export function useKernelEvents(options: KernelEventsOptions = {}) {
  const { client, instanceId } = useApi()
  const queryClient = useQueryClient()
  const callbacks = useRef(options)
  callbacks.current = options

  useEffect(() => {
    const controller = new AbortController()
    const states = new Map<string, KernelOperation['state']>()

    void watchKernelEvents(client, {
      signal: controller.signal,
      onError: (error) => callbacks.current.onError?.(error),
      onSnapshot: ({ operations }) => {
        if (controller.signal.aborted) return
        const cached = queryClient.getQueryData<KernelOperation[]>(kernelKeys.operations(instanceId)) ?? []
        const cachedStates = new Map(cached.map((operation) => [operation.id, operation.state]))
        const cachedById = new Map(cached.map((operation) => [operation.id, operation]))
        const merged = operations.map((operation) => mergeKernelOperation(cachedById.get(operation.id), operation))
        queryClient.setQueryData(kernelKeys.operations(instanceId), merged)
        for (const operation of merged) {
          const previous = states.get(operation.id) ?? cachedStates.get(operation.id)
          states.set(operation.id, operation.state)
          if (previous !== undefined && previous !== operation.state && isTerminal(operation)) {
            if (callbacks.current.onTerminal) callbacks.current.onTerminal(operation)
            else notifyTerminal(operation)
          }
        }
      },
    })

    return () => controller.abort()
  }, [client, instanceId, queryClient])
}

export function useKernelCatalog() {
  const { kernels, instanceId } = useApi()
  return useQuery({ queryKey: kernelKeys.catalog(instanceId), queryFn: kernels.catalog })
}

export function useInstalledKernels() {
  const { kernels, instanceId } = useApi()
  return useQuery({ queryKey: kernelKeys.installed(instanceId), queryFn: kernels.installed })
}

export function useKernelLicense() {
  const { kernels, instanceId } = useApi()
  return useQuery({ queryKey: kernelKeys.license(instanceId), queryFn: kernels.license })
}

export function useDefaultKernel() {
  const { kernels, instanceId } = useApi()
  return useQuery({ queryKey: kernelKeys.default(instanceId), queryFn: kernels.default })
}

export function useConnectKernelLicense() {
  const { kernels, instanceId } = useApi()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: LicenseWrite) => kernels.connect(body),
    retry: false,
    onSuccess: (license) => queryClient.setQueryData(kernelKeys.license(instanceId), license),
  })
}

export function useDisconnectKernelLicense() {
  const { kernels, instanceId } = useApi()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: kernels.disconnect,
    retry: false,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: kernelKeys.license(instanceId) }),
  })
}

export function useSetDefaultKernel() {
  const { kernels, instanceId } = useApi()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: DefaultKernelWrite) => kernels.setDefault(body),
    retry: false,
    onSuccess: (value) => queryClient.setQueryData(kernelKeys.default(instanceId), value),
  })
}

export function useDownloadKernel() {
  const { kernels, instanceId } = useApi()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: KernelDownload) => kernels.download(body),
    retry: false,
    onSuccess: (operation) => queryClient.setQueryData<KernelOperation[]>(
      kernelKeys.operations(instanceId),
      (current = []) => upsertKernelOperation(current, operation),
    ),
  })
}

export function useCancelKernelDownload() {
  const { kernels } = useApi()
  return useMutation({ mutationFn: kernels.cancel, retry: false })
}

export function useRemoveKernel() {
  const { kernels, instanceId } = useApi()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (kernel: KernelRef) => kernels.remove(kernel),
    retry: false,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: kernelKeys.catalog(instanceId) }),
        queryClient.invalidateQueries({ queryKey: kernelKeys.installed(instanceId) }),
        queryClient.invalidateQueries({ queryKey: kernelKeys.default(instanceId) }),
      ])
    },
  })
}

export function useCheckKernelUpdate() {
  const { kernels, instanceId } = useApi()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: kernels.checkUpdate,
    retry: false,
    onSuccess: (catalog) => queryClient.setQueryData(kernelKeys.catalog(instanceId), catalog),
  })
}
