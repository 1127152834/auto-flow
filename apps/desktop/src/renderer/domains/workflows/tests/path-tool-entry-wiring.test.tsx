import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => data.set(key, value),
    removeItem: (key: string) => data.delete(key),
  })
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1440 })
})

vi.mock('../components/controls/path-input', () => ({
  PathInput: ({ value, onChange, type = 'both' }: { value: string; onChange: (value: string) => void; type?: string }) => (
    <button type="button" data-testid="path-input" data-value={value} data-path-type={type} onClick={() => onChange(`/picked/${value.split('/').at(-1)}`)}>
      选择路径
    </button>
  ),
}))

import { ConfigPanel } from '../components/ConfigPanel'
import { useWorkflowStore as store } from '../editor-store'
import type { ModuleType } from '../types/workflow'

type Entry = { type: ModuleType; field: string; extra?: Record<string, unknown>; pathType?: 'file' | 'folder' | 'both' }

const entries: Entry[] = [
  { type: 'upload_file', field: 'filePath', pathType: 'file' },
  { type: 'extract_table_data', field: 'excelPath', extra: { exportToExcel: true }, pathType: 'file' },
  { type: 'save_image', field: 'savePath', pathType: 'file' },
  { type: 'download_file', field: 'savePath', pathType: 'folder' },
  { type: 'file_watcher_trigger', field: 'watchPath', pathType: 'both' },
  { type: 'base64', field: 'filePath', extra: { operation: 'file_to_base64' }, pathType: 'file' },
  { type: 'base64', field: 'outputPath', extra: { operation: 'base64_to_file' }, pathType: 'folder' },
  { type: 'list_export', field: 'outputPath', pathType: 'file' },
  { type: 'table_export', field: 'savePath', pathType: 'folder' },
  { type: 'ai_generate_video', field: 'savePath', pathType: 'file' },
  { type: 'ssh_connect', field: 'keyFile', pathType: 'file' },
  { type: 'ssh_upload_file', field: 'localPath', pathType: 'file' },
  { type: 'ssh_download_file', field: 'localPath', pathType: 'file' },
  { type: 'share_folder', field: 'folderPath', pathType: 'folder' },
  { type: 'share_file', field: 'filePath', pathType: 'file' },
  { type: 'export_log', field: 'outputPath', pathType: 'file' },
  { type: 'python_script', field: 'scriptPath', extra: { scriptMode: 'file' }, pathType: 'file' },
  { type: 'python_script', field: 'pythonPath', extra: { scriptMode: 'content', useBuiltinPython: false }, pathType: 'file' },
  { type: 'python_script', field: 'workingDir', pathType: 'folder' },
  { type: 'allure_init', field: 'resultsDir', pathType: 'both' },
  { type: 'allure_add_attachment', field: 'filePath', pathType: 'both' },
  { type: 'allure_generate_report', field: 'reportDir', pathType: 'both' },
]

beforeEach(() => store.getState().clearWorkflow())
afterEach(cleanup)

it.each(entries)('NODE.$type $field wires the actual panel field to PathInput and document history', ({ type, field, extra, pathType }) => {
  const before = `/before/${field}`
  store.getState().addNode(type, { x: 0, y: 0 }, { [field]: before, ...extra })
  const id = store.getState().nodes[0].id
  render(<ConfigPanel selectedNodeId={id} />)

  const input = screen.getAllByTestId('path-input').find(candidate => candidate.getAttribute('data-value') === before)
  expect(input, `${type}.${field} did not render its PathInput`).toBeDefined()
  expect(input!.getAttribute('data-path-type')).toBe(pathType)
  fireEvent.click(input!)
  expect(store.getState().nodes[0].data[field]).toBe(`/picked/${field}`)

  act(() => store.getState().undo())
  expect(store.getState().nodes[0].data[field]).toBe(before)
  act(() => store.getState().redo())
  expect(store.getState().nodes[0].data[field]).toBe(`/picked/${field}`)

  const exported = store.getState().exportWorkflow()
  act(() => {
    store.getState().clearWorkflow()
    expect(store.getState().importWorkflow(exported)).toBe(true)
  })
  expect(store.getState().nodes.find(node => node.id === id)!.data[field]).toBe(`/picked/${field}`)
})
