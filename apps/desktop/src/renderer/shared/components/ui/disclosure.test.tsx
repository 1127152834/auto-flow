import { createRef, useState } from 'react'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it } from 'vitest'
import { Disclosure } from './disclosure'

afterEach(cleanup)
it('uses native details/summary with a decorative chevron and forwards ref', async () => {
  const user = userEvent.setup(), ref = createRef<HTMLDetailsElement>()
  render(<Disclosure summary="填写说明" ref={ref}><p>每行一个路径</p></Disclosure>)
  const summary = screen.getByText('填写说明').closest('summary')
  expect(summary).not.toBeNull()
  expect(ref.current?.tagName).toBe('DETAILS')
  expect(summary?.querySelector('svg[aria-hidden="true"]')).not.toBeNull()
  expect(ref.current?.open).toBe(false)
  await user.click(summary!)
  expect(ref.current?.open).toBe(true)
  await user.click(summary!)
  expect(ref.current?.open).toBe(false)
})
it('supports open/onToggle state ownership and external reset', async () => {
  function Example() {
    const [open, setOpen] = useState(true)
    return <><Disclosure summary="高级选项" open={open} onToggle={event => setOpen(event.currentTarget.open)}>高级内容</Disclosure><output>{open ? '展开状态' : '收起状态'}</output><button onClick={() => setOpen(true)}>外部展开</button></>
  }
  const user = userEvent.setup()
  render(<Example />)
  const summary = screen.getByText('高级选项').closest('summary')
  expect(summary).not.toBeNull()
  await user.click(summary!)
  await waitFor(() => expect(screen.getByRole('status').textContent).toBe('收起状态'))
  await user.click(screen.getByRole('button', { name: '外部展开' }))
  expect(summary?.parentElement?.hasAttribute('open')).toBe(true)
})
