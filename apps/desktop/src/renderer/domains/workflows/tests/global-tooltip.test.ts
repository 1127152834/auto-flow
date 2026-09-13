import { afterEach, expect, it, vi } from 'vitest'
import { installGlobalTooltip } from '../lib/globalTooltip'
let dispose: (() => void) | undefined
afterEach(() => { dispose?.(); dispose = undefined; document.body.replaceChildren(); vi.useRealTimers() })
it('migrates dynamic titles without losing icon labels, renders text safely and restores native titles on cleanup', async () => {
  vi.useFakeTimers()
  const button = document.createElement('button')
  button.title = '<img src=x onerror=bad()>'
  document.body.append(button)
  dispose = installGlobalTooltip()
  expect(button.hasAttribute('title')).toBe(false)
  expect(button.getAttribute('aria-label')).toBe('<img src=x onerror=bad()>')
  button.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }))
  await vi.advanceTimersByTimeAsync(160)
  const tooltip = document.querySelector('[role="tooltip"]')!
  expect(tooltip.textContent).toBe('<img src=x onerror=bad()>')
  expect(tooltip.querySelector('img')).toBeNull()
  expect(tooltip.getAttribute('aria-hidden')).toBe('false')
  dispose()
  dispose = undefined
  expect(button.title).toBe('<img src=x onerror=bad()>')
  expect(button.hasAttribute('data-tip')).toBe(false)
  expect(document.querySelector('[role="tooltip"]')).toBeNull()
})
it('observes new controls and updated titles, cancels pending display on scroll and can remount', async () => {
  vi.useFakeTimers()
  dispose = installGlobalTooltip()
  const button = document.createElement('button')
  button.title = 'first'
  button.setAttribute('aria-label', 'explicit label')
  document.body.append(button)
  await Promise.resolve()
  button.title = 'updated'
  await Promise.resolve()
  expect(button.getAttribute('data-tip')).toBe('updated')
  expect(button.getAttribute('aria-label')).toBe('explicit label')
  button.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }))
  window.dispatchEvent(new Event('scroll'))
  await vi.advanceTimersByTimeAsync(160)
  expect(document.querySelector('[role="tooltip"]')).toBeNull()
  dispose()
  dispose = installGlobalTooltip()
  button.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }))
  await vi.advanceTimersByTimeAsync(160)
  expect(document.querySelectorAll('[role="tooltip"]')).toHaveLength(1)
  expect(document.querySelector('[role="tooltip"]')!.textContent).toBe('updated')
})
