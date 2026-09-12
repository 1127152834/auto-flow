import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useId, useMemo, useRef, useState, type FormEvent } from 'react'
import { FormProvider, useForm, type FieldErrors } from 'react-hook-form'
import type { InstalledKernel, KernelRef, ProfileRead } from '../../../shared/api/types'
import { ApiClientError } from '../../../shared/api/client'
import { notify } from '../../../shared/components/Toaster'
import { Button } from '../../../shared/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '../../../shared/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../../shared/components/ui/tabs'
import { useDefaultKernel, useInstalledKernels } from '../../kernels/hooks'
import {
  createProfileFormSchema,
  emptyProfileForm,
  kernelKey,
  parseKernelKey,
  toForm,
  toWrite,
  type ProfileFormValues,
} from '../form-schema'
import { useCreateProfile, useProfileEnvironmentOptions, useProxyOptions, useUpdateProfile } from '../hooks'
import { AdvancedFields } from './AdvancedFields'
import { BasicFields } from './BasicFields'
import { EnvironmentFields } from './EnvironmentFields'
import { KernelProxyFields } from './KernelProxyFields'
import { UnsavedChangesDialog } from './UnsavedChangesDialog'

type Tab = 'basic' | 'environment' | 'resources' | 'advanced'
const noKernels: readonly InstalledKernel[] = []
const noProxyOptions = { proxies: [], pools: [] }

export type ProfileFormDialogProps = {
  open: boolean
  onOpenChange(open: boolean): void
  initialProfile: ProfileRead | null
  onManageKernel(selectedKernel: KernelRef | null, trigger: HTMLButtonElement): void
  onSaved?(profile: ProfileRead): void
  disabled?: boolean
  onReconnect?(): void
}

const fieldTabs: Record<keyof ProfileFormValues, Tab> = {
  name: 'basic', description: 'basic', startUrl: 'basic',
  locale: 'environment', timezone: 'environment', humanPreset: 'environment', userAgent: 'environment',
  viewportMode: 'environment', viewportWidth: 'environment', viewportHeight: 'environment', colorScheme: 'environment',
  browserKernel: 'resources', releaseChannel: 'resources', proxyMode: 'resources', proxyId: 'resources',
  proxyPoolId: 'resources', headless: 'resources', geoip: 'resources', humanize: 'resources',
  extensionPathsText: 'advanced', expertArgsText: 'advanced',
}
const fieldOrder = Object.keys(fieldTabs) as Array<keyof ProfileFormValues>
const wireFields: Record<string, keyof ProfileFormValues> = {
  browserVersion: 'browserKernel', browserEdition: 'browserKernel', releaseChannel: 'browserKernel', viewportJson: 'viewportMode',
  extensionPathsJson: 'extensionPathsText', expertArgsJson: 'expertArgsText',
}
const focusSelectors: Partial<Record<keyof ProfileFormValues, string>> = {
  viewportMode: '[data-profile-viewport-focus]',
}

const errorMessage = (error: unknown) => error instanceof Error ? error.message : '保存失败，请重试'

export function ProfileFormDialog({ open, onOpenChange, initialProfile, onManageKernel, onSaved, disabled = false, onReconnect }: ProfileFormDialogProps) {
  const installed = useInstalledKernels()
  const defaultKernel = useDefaultKernel()
  const proxyOptions = useProxyOptions()
  const environmentOptions = useProfileEnvironmentOptions(open && !disabled)
  const installedKernels = installed.data?.items ?? noKernels
  const proxies = proxyOptions.data ?? noProxyOptions
  const schema = useMemo(() => createProfileFormSchema({ installedKernels, proxyOptions: proxies }), [installedKernels, proxies])
  const form = useForm<ProfileFormValues>({
    resolver: zodResolver(schema),
    defaultValues: initialProfile ? toForm(initialProfile) : emptyProfileForm,
  })
  const create = useCreateProfile()
  const update = useUpdateProfile()
  const [tab, setTab] = useState<Tab>('basic')
  const [pendingFocus, setPendingFocus] = useState<keyof ProfileFormValues | null>(null)
  const [discardOpen, setDiscardOpen] = useState(false)
  const [operationError, setOperationError] = useState('')
  const wasOpen = useRef(false)
  const defaultApplied = useRef(false)
  const lock = useRef(false)
  const formId = useId()
  const busy = create.isPending || update.isPending
  const dirty = form.formState.isDirty

  useEffect(() => {
    if (open && !wasOpen.current) {
      form.reset(initialProfile ? toForm(initialProfile) : emptyProfileForm)
      setTab('basic')
      setDiscardOpen(false)
      setOperationError('')
      defaultApplied.current = Boolean(initialProfile)
    }
    wasOpen.current = open
  }, [form, initialProfile, open])

  useEffect(() => {
    if (!open || initialProfile || defaultApplied.current || !defaultKernel.isSuccess || !installed.isSuccess) return
    defaultApplied.current = true
    const selected = defaultKernel.data.kernel
    if (selected && installedKernels.some((item) => kernelKey(item) === kernelKey(selected)) && !form.getValues('browserKernel')) {
      form.setValue('browserKernel', kernelKey(selected), { shouldDirty: false, shouldValidate: true })
    }
  }, [defaultKernel.data, defaultKernel.isSuccess, form, initialProfile, installed.isSuccess, installedKernels, open])

  useEffect(() => {
    if (!pendingFocus) return
    const frame = window.requestAnimationFrame(() => {
      const selector = focusSelectors[pendingFocus] ?? `[name="${pendingFocus}"]`
      document.querySelector<HTMLElement>(`.autoflow-dialog-content ${selector}`)?.focus()
      setPendingFocus(null)
    })
    return () => window.cancelAnimationFrame(frame)
  }, [form, pendingFocus, tab])

  const focusError = (name: keyof ProfileFormValues) => {
    setTab(fieldTabs[name])
    setPendingFocus(name)
  }
  const focusFirstError = (errors: FieldErrors<ProfileFormValues>) => {
    const name = fieldOrder.find((field) => errors[field])
    if (name) focusError(name)
  }
  const requestClose = () => {
    if (lock.current || busy) return
    if (dirty) setDiscardOpen(true)
    else onOpenChange(false)
  }
  const applyServerErrors = (error: ApiClientError) => {
    const entries = Object.entries(error.fields ?? {})
    for (const [field, message] of entries) {
      const name = (wireFields[field] ?? field) as keyof ProfileFormValues
      if (name in fieldTabs) form.setError(name, { type: 'server', message })
    }
    const first = fieldOrder.find((name) => form.getFieldState(name).error)
    if (first) focusError(first)
  }
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (disabled || lock.current) return
    lock.current = true
    setOperationError('')
    void form.handleSubmit(async (values) => {
      try {
        const saved = initialProfile
          ? await update.mutateAsync({ profileId: initialProfile.id, body: toWrite(values) })
          : await create.mutateAsync(toWrite(values))
        notify({ title: initialProfile ? '配置已保存' : '配置已创建', tone: 'success' })
        form.reset(values)
        onSaved?.(saved)
        onOpenChange(false)
      } catch (error) {
        if (error instanceof ApiClientError && error.fields && Object.keys(error.fields).length) applyServerErrors(error)
        else setOperationError(errorMessage(error))
      } finally {
        lock.current = false
      }
    }, (errors) => {
      lock.current = false
      focusFirstError(errors)
    })(event)
  }

  return <>
    <Dialog open={open} onOpenChange={(next) => { if (!next) requestClose() }} busy={busy}>
      <DialogContent className="grid max-h-[90vh] w-[min(94vw,58rem)] grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden p-0">
        <header className="px-6 pt-6">
          <DialogTitle>{initialProfile ? '编辑浏览器配置' : '新建浏览器配置'}</DialogTitle>
          <DialogDescription className="mt-1">固定指纹种子由系统维护；选择资源后才能保存。</DialogDescription>
        </header>
        {disabled ? <div role="alert" className="mx-6 flex flex-col gap-3 rounded-control border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 sm:flex-row sm:items-center sm:justify-between"><span>本地服务离线，草稿已保留。重新连接后请手动保存。</span>{onReconnect ? <Button type="button" onClick={onReconnect}>重新连接</Button> : null}</div> : null}
        <FormProvider {...form}>
          <form id={formId} className="min-h-0 overflow-y-auto px-6" onSubmit={submit}>
            <fieldset disabled={disabled} className="m-0 min-w-0 border-0 p-0">
              {operationError ? <p role="alert" className="mb-0 rounded-control border border-red-200 bg-red-50 p-3 text-sm text-red-800">{operationError}</p> : null}
              <Tabs value={tab} onValueChange={(value) => setTab(value as Tab)}>
                <TabsList className="sticky top-0 z-10 grid w-full grid-cols-4 bg-surface pt-2">
                  <TabsTrigger value="basic">基础信息</TabsTrigger>
                  <TabsTrigger value="environment">浏览器环境</TabsTrigger>
                  <TabsTrigger value="resources">内核与代理</TabsTrigger>
                  <TabsTrigger value="advanced">高级选项</TabsTrigger>
                </TabsList>
                <TabsContent value="basic" className="pb-6"><BasicFields /></TabsContent>
                <TabsContent value="environment" className="pb-6"><EnvironmentFields
                  options={environmentOptions.data}
                  optionsLoading={environmentOptions.isFetching}
                  optionsError={environmentOptions.error ? errorMessage(environmentOptions.error) : null}
                  onRetryOptions={() => { void environmentOptions.refetch() }}
                /></TabsContent>
                <TabsContent value="resources" className="pb-6"><KernelProxyFields
                  installedKernels={installedKernels}
                  proxyOptions={proxies}
                  kernelsLoading={installed.isPending}
                  kernelsError={installed.error ? errorMessage(installed.error) : null}
                  proxyOptionsLoading={proxyOptions.isPending}
                  proxyOptionsError={proxyOptions.error ? errorMessage(proxyOptions.error) : null}
                  onManageKernel={(event) => onManageKernel(parseKernelKey(form.getValues('browserKernel')), event.currentTarget)}
                /></TabsContent>
                <TabsContent value="advanced" className="pb-6"><AdvancedFields /></TabsContent>
              </Tabs>
            </fieldset>
          </form>
        </FormProvider>
        <footer className="flex justify-end gap-2 border-t border-line bg-surface px-6 py-4">
          <Button type="button" disabled={busy} onClick={requestClose}>取消</Button>
          <Button type="submit" form={formId} variant="primary" disabled={disabled || busy}>
            {busy ? '正在保存…' : initialProfile ? '保存' : '创建配置'}
          </Button>
        </footer>
      </DialogContent>
    </Dialog>
    <UnsavedChangesDialog open={discardOpen} onOpenChange={setDiscardOpen} onDiscard={() => {
      setDiscardOpen(false)
      form.reset(initialProfile ? toForm(initialProfile) : emptyProfileForm)
      onOpenChange(false)
    }} />
  </>
}
