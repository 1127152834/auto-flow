import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { ProviderLogo } from '../components/ProviderLogo'

afterEach(cleanup)

it('does not carry a failed brand image into the next provider selection', () => {
  const { container, rerender } = render(<ProviderLogo presetId="openai" name="OpenAI" />)
  const firstImage = container.querySelector('img')!
  fireEvent.error(firstImage)
  expect(container.querySelector('img')).toBeNull()
  expect(container.querySelector('svg')).toBeInTheDocument()

  rerender(<ProviderLogo presetId="deepseek" name="DeepSeek" />)
  expect(container.querySelector('img')).toBeInTheDocument()
  expect(container.querySelector('img')?.src).not.toBe(firstImage.src)
  expect(container.querySelector('img')).toHaveAttribute('alt', '')
})
