import { cleanup, render, screen } from '@testing-library/react'
import type { ComponentProps } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const issues = vi.hoisted(() => ({ list: [] as { nodeId: string; code: string; message: string; severity: 'error' | 'warning' }[] }))

vi.mock('@xyflow/react', async (importOriginal) => {
  const original = await importOriginal<typeof import('@xyflow/react')>()
  return {
    ...original,
    Handle: () => null,
    useReactFlow: () => ({ fitView: vi.fn(), getNodes: vi.fn(() => []), setCenter: vi.fn() }),
  }
})
vi.mock('../lib/nodeIssues', () => ({ useNodeIssues: () => issues.list }))

import { ModuleNode } from '../components/ModuleNode'
import { getBlockRowColorClasses } from '../components/moduleColors'
import { useNodeRunStore } from '../hooks/stores/nodeRunStore'

const renderNode = (data: Record<string, unknown> = {}, id = 'n1') =>
  render(
    <ModuleNode
      {...({
        id,
        data: { label: '点击元素', moduleType: 'click_element', selector: '#submit', ...data },
        selected: false,
      } as unknown as ComponentProps<typeof ModuleNode>)}
    />,
  )
const setStatus = (status: string) => useNodeRunStore.setState({ statuses: { n1: status as never } })
const root = () => screen.getByTestId('module-node')

beforeEach(() => {
  issues.list = []
  useNodeRunStore.setState({ statuses: {} })
})
afterEach(() => cleanup())

describe('节点视觉', () => {
  it('两行结构：标题 14px、摘要 13px，分支标签不小于 12px', () => {
    renderNode()
    expect(screen.getByText('点击元素').className).toContain('text-sm')
    expect(screen.getByText('#submit').className).toContain('text-[13px]')
    cleanup()
    renderNode({ moduleType: 'condition', label: '判断' })
    expect(screen.getByText('是').className).toContain('text-xs')
    expect(document.body.innerHTML).not.toContain('9.5px')
  })

  it('类别色只出现在左侧细色条，节点本体用中性表面', () => {
    renderNode()
    const bar = screen.getByTestId('node-accent-bar')
    const { borderClass } = getBlockRowColorClasses('click_element')
    expect(bar.className).toContain('border-l-4')
    expect(bar.className).toContain(borderClass)
    expect(root().className).toContain('bg-surface')
    expect(root().className).not.toMatch(/bg-(blue|indigo|purple|violet|pink|rose|orange|amber|green|emerald|teal|cyan|sky|slate|gray)-\d/)
  })

  it('运行中：无整体 animate-pulse，只有一个外圈进度元素', () => {
    setStatus('running')
    renderNode()
    expect(root().className).not.toContain('animate-pulse')
    const ring = screen.getByTestId('node-run-ring')
    expect(ring.getAttribute('style')).toContain('--motion-loop')
    expect(ring.getAttribute('style')).toContain('--ease-standard')
    expect(screen.getAllByTestId('node-run-ring')).toHaveLength(1)
    expect(screen.getByLabelText('运行中')).toBeTruthy()
  })

  it('失败：只变色加角标，无任何动画', () => {
    setStatus('failed')
    renderNode()
    expect(screen.queryByTestId('node-run-ring')).toBeNull()
    expect(root().className).not.toMatch(/animate-|shadow-.*glow/)
    expect(root().className).toContain('border-danger')
    expect(screen.getByLabelText('运行失败')).toBeTruthy()
  })

  it('成功与跳过各有角标', () => {
    setStatus('success')
    renderNode()
    expect(screen.getByLabelText('已完成')).toBeTruthy()
    cleanup()
    setStatus('skipped')
    renderNode()
    expect(screen.getByLabelText('已跳过')).toBeTruthy()
  })

  it('配置问题：有问题显示警告角标并汇总文案，无问题不占位', () => {
    renderNode()
    expect(screen.queryByTestId('node-issue-badge')).toBeNull()
    cleanup()
    issues.list = [
      { nodeId: 'n1', code: 'a', message: '「网址」还没填写，请补全后再运行', severity: 'error' },
      { nodeId: 'n1', code: 'b', message: '「次数」不是数字', severity: 'error' },
    ]
    renderNode()
    const badge = screen.getByTestId('node-issue-badge')
    expect(badge.getAttribute('aria-label')).toBe('「网址」还没填写，请补全后再运行；「次数」不是数字')
    expect(badge.getAttribute('title')).toBe(badge.getAttribute('aria-label'))
  })
})
