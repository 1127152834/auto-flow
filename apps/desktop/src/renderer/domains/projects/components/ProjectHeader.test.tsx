import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import type { ProjectView } from '../types'
import { ProjectHeader } from './ProjectHeader'
import { ProjectTabs } from './ProjectTabs'

const project = { projectId: 'p1', name: '内容采集项目', description: '自动采集电商平台商品信息', lifecycleState: 'active' } as ProjectView

afterEach(cleanup)

it('uses project context instead of another page heading in compact density', () => {
  render(<ProjectHeader project={project} density="compact" disabled={false} onBack={vi.fn()} onEdit={vi.fn()} />)
  expect(screen.queryByRole('heading')).not.toBeInTheDocument()
  expect(screen.getByText('内容采集项目')).toBeVisible()
  expect(screen.getByText('内容采集项目')).toHaveAttribute('title', '内容采集项目')
  expect(screen.queryByText('自动采集电商平台商品信息')).not.toBeInTheDocument()
  expect(screen.getByRole('banner')).toHaveAttribute('data-project-header-density', 'compact')
  expect(screen.getByRole('button', { name: '返回项目目录' })).toBeVisible()
  expect(screen.getByRole('button', { name: '编辑项目' })).toBeEnabled()
})

it('keeps the default page heading and disables editing an archived project', () => {
  render(<ProjectHeader project={{ ...project, lifecycleState: 'archived' }} disabled={false} onBack={vi.fn()} onEdit={vi.fn()} />)
  expect(screen.getByRole('heading', { level: 1, name: '内容采集项目' })).toBeVisible()
  expect(screen.getByText('自动采集电商平台商品信息')).toBeVisible()
  expect(screen.getByText('已归档')).toBeVisible()
  expect(screen.getByRole('button', { name: '编辑项目' })).toBeDisabled()
})

it('keeps the six project tabs in the approved order', () => {
  render(<ProjectTabs value="overview" onChange={vi.fn()} />)
  expect(screen.getByRole('navigation', { name: '项目功能' }).querySelectorAll('button')).toHaveLength(6)
  expect(screen.getAllByRole('button').map(button => button.textContent)).toEqual(['概览', '自动化', '运行记录', '统计', '数据', '环境'])
  expect(screen.getByRole('button', { name: '概览' })).toHaveAttribute('aria-current', 'page')
})
