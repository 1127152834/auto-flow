import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { CreateCustomModuleDialog } from '../components/CreateCustomModuleDialog'
import { useCustomModuleStore } from '../hooks/stores/customModuleStore'
import type { CustomModule, CustomModuleParameter } from '../types/customModule'
afterEach(() => { cleanup(); vi.restoreAllMocks() })
it.each([{ type: 'number', value: 0 }, { type: 'boolean', value: false }])('preserves a $type default while editing only module metadata', async ({ type, value }) => {
  const module = { id: 'fixture', name: 'fixture_module', display_name: '模块参数验收', description: '', icon: '', color: '#123456', category: '自定义', tags: [], parameters: [{ name: 'value', label: '值', type, default_value: value, required: false, placeholder: '', description: '', options: [] } as CustomModuleParameter], outputs: [], workflow: { nodes: [], edges: [] } } as unknown as CustomModule
  const save = vi.spyOn(useCustomModuleStore.getState(), 'updateModule').mockResolvedValue(module)
  render(<CreateCustomModuleDialog open onClose={vi.fn()} editingModule={module} />)
  expect((screen.getByPlaceholderText('默认值') as HTMLInputElement).value).toBe(String(value))
  fireEvent.click(screen.getByRole('button', { name: '保存修改' }))
  await waitFor(() => expect(save).toHaveBeenCalledOnce())
  expect(save.mock.calls[0][1].parameters?.[0].default_value).toBe(value)
})
