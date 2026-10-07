import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { Input } from '../../../../shared/components/ui/input'
import { ConfigField } from './ConfigField'

afterEach(cleanup)
const field = (error?: string | null, hint?: string) => render(
  <ConfigField label="元素选择器" error={error} hint={hint}>{c => <Input {...c} />}</ConfigField>,
)

describe('ConfigField', () => {
  it('有错误时在控件下方显示 alert，并关联 aria-describedby 与 aria-invalid', () => {
    field('请填写元素选择器')
    const input = screen.getByLabelText('元素选择器')
    const alert = screen.getByRole('alert')
    expect(alert.textContent).toBe('请填写元素选择器')
    expect(input.getAttribute('aria-invalid')).toBe('true')
    expect(input.getAttribute('aria-describedby')).toContain(alert.id)
    expect(input.compareDocumentPosition(alert) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('无错误时不渲染 alert，也不带 aria-invalid，不占位', () => {
    const { container } = field('')
    const input = screen.getByLabelText('元素选择器')
    expect(screen.queryByRole('alert')).toBeNull()
    expect(input.hasAttribute('aria-invalid')).toBe(false)
    expect(input.hasAttribute('aria-describedby')).toBe(false)
    expect(container.querySelectorAll('p')).toHaveLength(0)
  })

  it('提示文本可选，并与错误一起被 aria-describedby 引用', () => {
    field('格式不对', '例如 #submit')
    const ids = (screen.getByLabelText('元素选择器').getAttribute('aria-describedby') ?? '').split(' ')
    expect(ids).toHaveLength(2)
    expect(screen.getByText('例如 #submit').id).toBe(ids[0])
  })
})
