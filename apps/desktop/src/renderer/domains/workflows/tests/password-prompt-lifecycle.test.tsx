import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { usePasswordPrompt } from '../components/controls/password-prompt'
afterEach(cleanup)
it('resolves an outstanding password request as cancelled on unmount', async () => {
  const { result, unmount } = renderHook(usePasswordPrompt)
  let pending!: Promise<string | null>
  act(() => { pending = result.current.promptPassword() })
  unmount()
  await expect(pending).resolves.toBeNull()
})
it('cancels the previous caller when another prompt replaces it', async () => {
  const { result, unmount } = renderHook(usePasswordPrompt)
  let first!: Promise<string | null>, second!: Promise<string | null>
  act(() => { first = result.current.promptPassword({ title: '第一个包' }) })
  act(() => { second = result.current.promptPassword({ title: '第二个包' }) })
  await expect(first).resolves.toBeNull()
  unmount()
  await expect(second).resolves.toBeNull()
})
