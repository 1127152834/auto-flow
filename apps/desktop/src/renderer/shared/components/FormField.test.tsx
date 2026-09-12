import { afterEach, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import userEvent from '@testing-library/user-event'
import { Controller, useForm } from 'react-hook-form'
import { FormField } from './FormField'
import { Input } from './ui/input'

afterEach(cleanup)

it('associates label and error with its control', () => {
  render(<FormField label="浏览器内核" error="请选择浏览器内核" htmlFor="kernel">{a11y => <Input {...a11y} />}</FormField>)
  expect(screen.getByLabelText('浏览器内核')).toHaveAttribute('id', 'kernel')
  expect(screen.getByRole('alert')).toHaveAttribute('id', 'kernel-error')
  expect(screen.getByLabelText('浏览器内核')).toHaveAttribute('aria-describedby', 'kernel-error')
  expect(screen.getByLabelText('浏览器内核')).toHaveAttribute('aria-invalid', 'true')
})

it('binds a Controller input explicitly and restores hint after validation clears', async () => {
  function Case() {
    const { control, handleSubmit, setFocus } = useForm({ defaultValues: { name: '' } })
    return <form onSubmit={handleSubmit(() => {})}>
      <Controller name="name" control={control} rules={{ required: '请填写名称' }} render={({ field, fieldState }) =>
        <FormField htmlFor="case-name" label="配置名称" hint="用于识别" error={fieldState.error?.message}>{a11y => <Input {...field} {...a11y} />}</FormField>} />
      <button type="submit">验证</button><button type="button" onClick={() => setFocus('name')}>聚焦</button>
    </form>
  }
  const user = userEvent.setup(); render(<Case />)
  const input = screen.getByRole('textbox', { name: '配置名称' })
  expect(input).toHaveAccessibleDescription('用于识别')
  await user.click(screen.getByRole('button', { name: '验证' }))
  expect(input).toHaveFocus(); expect(input).toHaveAccessibleDescription('请填写名称')
  await user.type(input, '日常浏览')
  expect(input).toHaveAccessibleDescription('用于识别')
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '聚焦' }))
  expect(input).toHaveFocus()
})
