import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { BatchConfigurationSnapshot } from './BatchDetail'

afterEach(cleanup)
it.each([false, true])('shows explicit unlimited and the frozen failure policy %s', continueAfterFailure => {
  render(<BatchConfigurationSnapshot value={{ maxTasks: null, concurrency: 2, automation: { runPolicy: { continueAfterFailure } } }}/>)
  expect(screen.getByText('任务数').closest('tr')).toHaveTextContent('不限次数')
  expect(screen.getByText('失败策略').closest('tr')).toHaveTextContent(continueAfterFailure ? '失败后继续领取' : '首次确认失败后停止领取新任务')
})
