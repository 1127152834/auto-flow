import { createRef } from 'react'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Checkbox } from './checkbox'
import { RadioGroup, RadioGroupItem } from './radio-group'
import { Switch } from './switch'

beforeEach(() => vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} }))
afterEach(() => { cleanup(); vi.unstubAllGlobals() })
describe('choice toggles', () => {
  it('renders both checked and mixed indicators, including uncontrolled mixed state', async () => {
    const user = userEvent.setup()
    render(<><Checkbox aria-label="全选" defaultChecked="indeterminate" /><Checkbox aria-label="已选" checked /></>)
    const mixed = screen.getByRole('checkbox', { name: '全选' })
    expect(mixed.getAttribute('aria-checked')).toBe('mixed')
    expect(mixed.querySelector('[data-af-choice-glyph="mixed"]')).not.toBeNull()
    expect(screen.getByRole('checkbox', { name: '已选' }).querySelector('[data-af-choice-glyph="checked"]')).not.toBeNull()
    mixed.focus()
    await user.keyboard(' ')
    expect(mixed.getAttribute('aria-checked')).toBe('true')
    await user.keyboard(' ')
    expect(mixed.getAttribute('aria-checked')).toBe('false')
  })
  it('preserves controlled callbacks, ref and native form values without submitting', async () => {
    const user = userEvent.setup()
    const change = vi.fn(), submit = vi.fn(e => e.preventDefault()), ref = createRef<HTMLButtonElement>()
    const { container } = render(<form onSubmit={submit}><Checkbox ref={ref} aria-label="日志" checked name="logs" value="included" onCheckedChange={change} /><Switch name="enabled" defaultChecked aria-label="启用" /></form>)
    expect(ref.current).toBe(screen.getByRole('checkbox'))
    expect(new FormData(container.querySelector('form')!).get('logs')).toBe('included')
    expect(new FormData(container.querySelector('form')!).get('enabled')).toBe('on')
    await user.click(screen.getByRole('checkbox'))
    expect(change).toHaveBeenCalledWith(false)
    expect(screen.getByRole('checkbox').getAttribute('aria-checked')).toBe('true')
    expect(submit).not.toHaveBeenCalled()
  })
  it('uses Arrow keys to select radios and skips disabled items', async () => {
    const user = userEvent.setup()
    render(<RadioGroup aria-label="位置"><RadioGroupItem value="a" aria-label="上海" /><RadioGroupItem value="b" aria-label="北京" disabled /><RadioGroupItem value="c" aria-label="杭州" /></RadioGroup>)
    expect(screen.getByRole('radiogroup', { name: '位置' })).toBeTruthy()
    const first = screen.getByRole('radio', { name: '上海' }), last = screen.getByRole('radio', { name: '杭州' })
    await user.click(first)
    await user.keyboard('{ArrowDown>}')
    await waitFor(() => expect(last.getAttribute('aria-checked')).toBe('true'))
    await user.keyboard('{/ArrowDown}')
    expect(document.activeElement).toBe(last)
    expect(last.getAttribute('aria-checked')).toBe('true')
    expect(last.querySelector('[data-af-choice-dot]')).not.toBeNull()
    await user.keyboard('{ArrowUp>}')
    await waitFor(() => expect(first.getAttribute('aria-checked')).toBe('true'))
    await user.keyboard('{/ArrowUp}')
    expect(first.getAttribute('aria-checked')).toBe('true')
  })
  it('Switch toggles with Space and disabled controls never call changes', async () => {
    const user = userEvent.setup(), change = vi.fn()
    render(<><Switch aria-label="模拟行为" /><Switch aria-label="禁用开关" disabled onCheckedChange={change} /><Checkbox aria-label="禁用复选" disabled onCheckedChange={change} /></>)
    const toggle = screen.getByRole('switch', { name: '模拟行为' })
    toggle.focus()
    await user.keyboard(' ')
    expect(toggle.getAttribute('aria-checked')).toBe('true')
    await user.click(screen.getByRole('switch', { name: '禁用开关' }))
    await user.click(screen.getByRole('checkbox', { name: '禁用复选' }))
    expect(change).not.toHaveBeenCalled()
  })
})
