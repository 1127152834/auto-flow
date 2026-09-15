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

vi.mock('../components/controls/image-path-input', () => ({
  ImagePathInput: ({ value, onChange }: { value: string; onChange: (value: string) => void }) => (
    <button type="button" data-testid="image-path-input" data-value={value} onClick={() => onChange(`/picked/${value.split('/').at(-1)}`)}>选择图像</button>
  ),
}))
vi.mock('../components/controls/slider', () => ({
  Slider: ({ value, onValueChange }: { value: number[]; onValueChange: (value: number[]) => void }) => (
    <button type="button" data-testid="slider" data-value={String(value[0])} onClick={() => onValueChange([0.42])}>调整滑块</button>
  ),
}))
vi.mock('../components/controls/coordinate-input', () => ({
  CoordinateInput: ({ xValue, yValue, onXChange, onYChange }: { xValue: string; yValue: string; onXChange: (value: string) => void; onYChange: (value: string) => void }) => (
    <button type="button" data-testid="coordinate-input" data-x={xValue} data-y={yValue} onClick={() => { onXChange('101'); onYChange('202') }}>拾取坐标</button>
  ),
}))
vi.mock('../components/controls/dual-coordinate-input', () => ({
  DualCoordinateInput: ({ label, onBothChange }: { label: string; onBothChange?: (x: number, y: number) => void }) => (
    <button type="button" data-testid="dual-coordinate-input" data-label={label} onClick={() => onBothChange?.(101, 202)}>拾取区域</button>
  ),
}))

import { ConfigPanel } from '../components/ConfigPanel'
import { useWorkflowStore as store } from '../editor-store'
import type { ModuleType } from '../types/workflow'

type ImageEntry = { type: ModuleType; field: string; extra?: Record<string, unknown> }
const imageEntries: ImageEntry[] = [
  { type: 'set_clipboard', field: 'imagePath', extra: { contentType: 'image' } },
  { type: 'image_trigger', field: 'imagePath' },
  { type: 'face_trigger', field: 'targetFaceImage' },
  { type: 'ai_vision', field: 'imageUrl', extra: { imageSource: 'url' } },
  { type: 'ai_generate_image', field: 'savePath' },
  { type: 'face_recognition', field: 'sourceImage' },
  { type: 'face_recognition', field: 'targetImage' },
  { type: 'image_ocr', field: 'imagePath', extra: { ocrMode: 'file' } },
]

type SliderEntry = { type: ModuleType; field: string; value: number }
const sliderEntries: SliderEntry[] = [
  { type: 'image_trigger', field: 'confidence', value: 0.8 },
  { type: 'sound_trigger', field: 'volumeThreshold', value: 50 },
  { type: 'face_trigger', field: 'tolerance', value: 0.6 },
  { type: 'gesture_trigger', field: 'confidenceThreshold', value: 0.7 },
  { type: 'text_to_speech', field: 'rate', value: 0.7 },
  { type: 'text_to_speech', field: 'pitch', value: 1.3 },
  { type: 'text_to_speech', field: 'volume', value: 0.4 },
]

beforeEach(() => store.getState().clearWorkflow())
afterEach(cleanup)

it.each(imageEntries)('NODE.$type $field wires its ImagePathInput to the document', ({ type, field, extra }) => {
  const before = `/before/${field}`
  store.getState().addNode(type, { x: 0, y: 0 }, { [field]: before, ...extra })
  const id = store.getState().nodes[0].id
  render(<ConfigPanel selectedNodeId={id} />)
  const input = screen.getAllByTestId('image-path-input').find(candidate => candidate.getAttribute('data-value') === before)
  expect(input, `${type}.${field} did not render ImagePathInput`).toBeDefined()
  fireEvent.click(input!)
  expect(store.getState().nodes[0].data[field]).toBe(`/picked/${field}`)
  act(() => store.getState().undo())
  expect(store.getState().nodes[0].data[field]).toBe(before)
  act(() => store.getState().redo())
  expect(store.getState().nodes[0].data[field]).toBe(`/picked/${field}`)
})

it.each(sliderEntries)('NODE.$type $field wires its Slider to the document', ({ type, field, value }) => {
  store.getState().addNode(type, { x: 0, y: 0 }, { [field]: value })
  render(<ConfigPanel selectedNodeId={store.getState().nodes[0].id} />)
  const renderedValue = type === 'gesture_trigger' ? value * 100 : value
  const slider = screen.getAllByTestId('slider').find(candidate => candidate.getAttribute('data-value') === String(renderedValue))
  expect(slider, `${type}.${field} did not render Slider`).toBeDefined()
  fireEvent.click(slider!)
  const expected = type === 'gesture_trigger' ? 0.0042 : 0.42
  expect(store.getState().nodes[0].data[field]).toBe(expected)
  act(() => store.getState().undo())
  expect(store.getState().nodes[0].data[field]).toBe(value)
})

it.each([
  { marker: 'start', xField: 'startX', yField: 'startY', x: '11', y: '12' },
  { marker: 'end', xField: 'endX', yField: 'endY', x: '21', y: '22' },
])('NODE.image_ocr CoordinateInput writes the $marker pair without touching the other pair', ({ xField, yField, x, y }) => {
  store.getState().addNode('image_ocr', { x: 0, y: 0 }, { ocrMode: 'region', startX: '11', startY: '12', endX: '21', endY: '22' })
  render(<ConfigPanel selectedNodeId={store.getState().nodes[0].id} />)
  const coordinate = screen.getAllByTestId('coordinate-input').find(candidate => candidate.getAttribute('data-x') === x && candidate.getAttribute('data-y') === y)
  expect(coordinate).toBeDefined()
  fireEvent.click(coordinate!)
  expect(store.getState().nodes[0].data).toMatchObject({ [xField]: '101', [yField]: '202' })
})

it.each([
  { label: '左上角坐标', expected: { x: 101, y: 202, x2: 30, y2: 40 } },
  { label: '右下角坐标', expected: { x: 10, y: 20, x2: 101, y2: 202 } },
])('NODE.image_trigger DualCoordinateInput preserves the opposite corner for $label', ({ label, expected }) => {
  store.getState().addNode('image_trigger', { x: 0, y: 0 }, { searchRegion: { x: 10, y: 20, x2: 30, y2: 40 } })
  render(<ConfigPanel selectedNodeId={store.getState().nodes[0].id} />)
  const control = screen.getAllByTestId('dual-coordinate-input').find(candidate => candidate.getAttribute('data-label') === label)
  expect(control).toBeDefined()
  fireEvent.click(control!)
  expect(store.getState().nodes[0].data.searchRegion).toEqual(expected)
  act(() => store.getState().undo())
  expect(store.getState().nodes[0].data.searchRegion).toEqual({ x: 10, y: 20, x2: 30, y2: 40 })
})
