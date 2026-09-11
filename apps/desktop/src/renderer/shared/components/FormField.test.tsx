import { afterEach, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { FormField } from './FormField'
import { Input } from './ui/input'

afterEach(cleanup)

it('associates label and error with its control', () => {
  render(<FormField label="浏览器内核" error="请选择浏览器内核" htmlFor="kernel"><Input id="kernel" /></FormField>)
  expect(screen.getByLabelText('浏览器内核')).toHaveAttribute('id', 'kernel')
  expect(screen.getByRole('alert')).toHaveAttribute('id', 'kernel-error')
  expect(screen.getByLabelText('浏览器内核')).toHaveAttribute('aria-describedby', 'kernel-error')
  expect(screen.getByLabelText('浏览器内核')).toHaveAttribute('aria-invalid', 'true')
})
