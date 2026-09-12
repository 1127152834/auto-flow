import { expect, it } from 'vitest'
import { render } from '@testing-library/react'
import { Spinner } from './spinner'
it('is decorative so its owning control supplies the accessible status', () => {
  const { container } = render(<Spinner />)
  expect(container.querySelector('svg')?.getAttribute('aria-hidden')).toBe('true')
  expect(container.querySelector('[role="status"]')).toBeNull()
})
