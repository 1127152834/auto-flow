import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, expect, it } from 'vitest'
import { ManualResumeFields, parseManualInputs } from './ManualResumeFields'

afterEach(cleanup)
it('requires declared values, preserves leading zero strings, and rejects invalid JSON numbers', () => {
  const fields = [{ name: 'code', type: 'string' as const, required: true }, { name: 'count', type: 'integer' as const, required: false }]
  function Form() {
    const [draft, setDraft] = useState<Record<string, string>>({})
    const parsed = parseManualInputs(fields, draft)
    return <><ManualResumeFields fields={fields} draft={draft} onChange={setDraft} disabled={false}/><output>{JSON.stringify(parsed.values)}</output><button disabled={Boolean(parsed.error)}>继续</button></>
  }
  render(<Form/>)
  expect(screen.getByRole('button', { name: '继续' })).toBeDisabled()
  fireEvent.change(screen.getByLabelText('code'), { target: { value: '001' } })
  expect(screen.getByRole('button', { name: '继续' })).toBeEnabled()
  expect(screen.getByRole('status')).toHaveTextContent('"code":"001"')
  fireEvent.change(screen.getByLabelText('count'), { target: { value: '1.5' } })
  expect(screen.getByRole('button', { name: '继续' })).toBeDisabled()
  expect(screen.getByRole('alert')).toHaveTextContent('count')
  expect(parseManualInputs([{ name: 'object', type: 'object', required: true }], { object: '[]' }).error).toBeTruthy()
})
