import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { OverviewCounts } from './OverviewCounts'

afterEach(cleanup)

it('renders the four real counts and the recorded data changes', () => {
  render(<OverviewCounts counts={{ automations: 2, tables: 3, batches: 5, environments: 1 }} dataChanges={{ timezone: 'Asia/Shanghai', dayStart: '2026-09-19T00:00:00+08:00', newRecords: 3, updatedRecords: 2 }} />)
  const strip = screen.getByLabelText('项目计数')
  expect(strip).toHaveTextContent('自动化')
  expect(strip).toHaveTextContent('数据表')
  expect(strip).toHaveTextContent('运行批次')
  expect(strip).toHaveTextContent('环境')
  expect(strip).toHaveTextContent('新增 3 · 更新 2')
  expect(strip).toHaveTextContent('统计口径：Asia/Shanghai')
  expect(strip.querySelectorAll('dd')[0]).toHaveTextContent('2')
})

it('shows zeros and an explicit empty note instead of prototype sample numbers', () => {
  render(<OverviewCounts counts={{}} />)
  const strip = screen.getByLabelText('项目计数')
  expect(screen.getAllByText('0')).toHaveLength(4)
  expect(strip).toHaveTextContent('暂无数据')
  expect(strip).not.toHaveTextContent('225')
  expect(strip).not.toHaveTextContent('98.7')
})
