import '@testing-library/jest-dom/vitest'
import { zodResolver } from '@hookform/resolvers/zod'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FormProvider, useForm } from 'react-hook-form'
import { afterEach, expect, it, vi } from 'vitest'
import type { InstalledKernel } from '../../../shared/api/types'
import { createProfileFormSchema, emptyProfileForm, type ProfileFormValues } from '../form-schema'
import { AdvancedFields } from './AdvancedFields'

afterEach(cleanup)

const installed: InstalledKernel = { edition: 'public', version: '146', executablePath: '/kernel', size: 1 }

function Harness({ onSubmit }: { onSubmit: (values: ProfileFormValues) => void }) {
  const schema = createProfileFormSchema({ installedKernels: [installed], proxyOptions: { proxies: [], pools: [] } })
  const form = useForm<ProfileFormValues>({ resolver: zodResolver(schema), defaultValues: { ...emptyProfileForm, name: '工作', browserKernel: 'public|146' } })
  return <FormProvider {...form}><form onSubmit={form.handleSubmit(onSubmit)}><AdvancedFields /><button type="submit">保存</button></form></FormProvider>
}

it('submits trimmed per-line paths and arguments through the shared form', async () => {
  const user = userEvent.setup()
  const onSubmit = vi.fn()
  render(<Harness onSubmit={onSubmit} />)
  await user.type(screen.getByLabelText('扩展目录（每行一个）'), '/one\n/two')
  await user.type(screen.getByLabelText('高级参数（每行一个）'), '--disable-notifications\n--window-position=40,40')
  await user.click(screen.getByRole('button', { name: '保存' }))
  expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ extensionPathsText: '/one\n/two', expertArgsText: '--disable-notifications\n--window-position=40,40' }), expect.anything())
})

it('shows the real reserved-argument guidance and validation error', async () => {
  const user = userEvent.setup()
  render(<Harness onSubmit={vi.fn()} />)
  await user.click(screen.getByText('查看填写说明'))
  expect(screen.getByText(/--user-data-dir、--fingerprint/)).toBeInTheDocument()
  await user.type(screen.getByLabelText('高级参数（每行一个）'), '--proxy-server http://localhost')
  await user.click(screen.getByRole('button', { name: '保存' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('AutoFlow 已管理 --proxy-server')
})
