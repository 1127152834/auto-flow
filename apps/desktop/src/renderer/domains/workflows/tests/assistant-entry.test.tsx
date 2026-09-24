import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

vi.hoisted(() => {
  const storage = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => storage.get(key) ?? null,
    setItem: (key: string, value: string) => storage.set(key, value),
    removeItem: (key: string) => storage.delete(key),
  })
})

import { Toolbar } from '../components/Toolbar'
import { useStudioIntegration } from '../hooks/useStudioIntegration'
import { useAIAssistantStore } from '../hooks/stores/aiAssistantStore'
import { useGlobalConfigStore } from '../hooks/stores/globalConfigStore'

function Integration() {
  useStudioIntegration()
  return null
}

beforeEach(() => {
  useAIAssistantStore.setState({ isPanelOpen: false })
  useGlobalConfigStore.setState(state => ({
    config: { ...state.config, system: { ...state.config.system, showAIAssistantButton: true } },
  }))
})

afterEach(cleanup)

it('opens the production assistant from the toolbar and built-in shortcut', () => {
  render(<><Toolbar /><Integration /></>)
  fireEvent.click(screen.getByRole('button', { name: 'AI 小助手' }))
  expect(useAIAssistantStore.getState().isPanelOpen).toBe(true)
  fireEvent.keyDown(window, { key: 'k', metaKey: true })
  expect(useAIAssistantStore.getState().isPanelOpen).toBe(false)
})

it('honors the configured assistant entry visibility without disabling the shortcut', () => {
  useGlobalConfigStore.setState(state => ({
    config: { ...state.config, system: { ...state.config.system, showAIAssistantButton: false } },
  }))
  render(<><Toolbar /><Integration /></>)
  expect(screen.queryByRole('button', { name: 'AI 小助手' })).toBeNull()
  fireEvent.keyDown(window, { key: 'k', ctrlKey: true })
  expect(useAIAssistantStore.getState().isPanelOpen).toBe(true)
})
