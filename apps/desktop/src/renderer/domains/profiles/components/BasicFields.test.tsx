import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FormProvider, useForm, useWatch } from 'react-hook-form'
import { afterEach, expect, it } from 'vitest'
import { emptyProfileForm, type ProfileFormValues } from '../form-schema'
import { BasicFields } from './BasicFields'

afterEach(cleanup)

function Harness() {
  const form = useForm<ProfileFormValues>({ defaultValues: emptyProfileForm })
  const values = useWatch({ control: form.control })
  return <FormProvider {...form}><BasicFields /><output>{JSON.stringify(values)}</output></FormProvider>
}

it('binds every basic field to the shared profile form', async () => {
  const user = userEvent.setup()
  render(<Harness />)
  await user.type(screen.getByLabelText('名称'), '工作环境')
  await user.type(screen.getByLabelText('描述'), '长期登录')
  await user.clear(screen.getByLabelText('起始网址'))
  await user.type(screen.getByLabelText('起始网址'), 'https://example.com')
  expect(screen.getByText(/"name":"工作环境"/)).toHaveTextContent('"description":"长期登录"')
  expect(screen.getByText(/"name":"工作环境"/)).toHaveTextContent('"startUrl":"https://example.com"')
})
