import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import type { components } from '../../../shared/api/generated'
import { TaskEvidence } from './TaskEvidence'

afterEach(cleanup)
type Schema = components['schemas']
const detail = {
  automationName: '采集', parameterDefinitions: [], nodeNames: { 'node-02': '打开页面' },
  task: { taskId: 'task', taskOrdinal: 1, projectId: 'project', batchId: 'batch', runId: 'run', runRequestId: 'request', status: 'failed' as const, statusRevision: 2, inputSnapshotId: 'snapshot', createdAt: '', completedAt: '' },
  inputSnapshot: { inputSnapshotId: 'snapshot', taskId: 'task', batchId: 'batch', parameters: {}, inputs: [], capturedAt: '' },
  run: { runId: 'run', runRequestId: 'request', status: 'failed' as const, statusRevision: 2, executionGeneration: 1, preparedContentId: 'content', capabilityBindings: [], resourceRequest: {}, lastSequence: 2, terminal: true, error: { code: 'FAILED' }, startedAt: '', finishedAt: '' },
} satisfies Schema['TaskDetail']
const base = { mode: 'evidence' as const, detail, attempts: { items: [], page: 1, pageSize: 100, total: 0, sort: 'createdAt' }, outputs: undefined, onLoadMoreAttempts: vi.fn(), onLoadMoreOutputs: vi.fn() }
const artifact = {
  artifactId: 'artifact-1', kind: 'screenshot' as const, purpose: 'error' as const, availability: 'available' as const,
  nodeId: 'node-02', nodeName: '旧节点名', nodeVisitId: 'visit', eventSequence: 2, executionGeneration: 1, mediaType: 'image/png' as const,
  byteSize: 3072, sha256: 'a'.repeat(64), createdAt: '2026-09-15T01:02:03Z', contentUrl: '/content',
} satisfies Schema['RunArtifactView']

const outputPage = (items: Schema['RunOutputView'][]): Schema['RunOutputPage'] => ({ items, page: 1, pageSize: 100, total: items.length, sort: 'createdAt' })
const artifactPage = (items: Schema['RunArtifactView'][]): Schema['RunArtifactPage'] => ({ items, page: 1, pageSize: 100, total: items.length, sort: 'createdAt' })

it('shows controlled failure screenshots and reports the selected artifact', async () => {
  const onOpenArtifact = vi.fn()
  render(<TaskEvidence {...base} artifacts={{ items: [artifact], page: 1, pageSize: 100, total: 1, sort: 'createdAt' }} onOpenArtifact={onOpenArtifact}/>)

  expect(screen.getByText('打开页面')).toBeVisible()
  expect(screen.queryByText('旧节点名')).not.toBeInTheDocument()
  expect(screen.queryByText('node-02')).not.toBeInTheDocument()
  expect(screen.getByText(/3 KB/)).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: '查看失败截图：打开页面' }))
  expect(onOpenArtifact).toHaveBeenCalledWith(artifact)
})

it('states when capture is unavailable and does not invent an attachment action', () => {
  const unavailable = { ...artifact, availability: 'unavailable' as const, mediaType: null, byteSize: null, sha256: null, contentUrl: null, unavailableReason: 'SCREENSHOT_CAPTURE_FAILED' }
  render(<TaskEvidence {...base} artifacts={{ items: [unavailable], page: 1, pageSize: 100, total: 1, sort: 'createdAt' }} onOpenArtifact={vi.fn()}/>)

  expect(screen.getByText('截图捕获失败')).toBeVisible()
  expect(screen.queryByRole('button', { name: /查看失败截图/ })).not.toBeInTheDocument()
})

it('keeps final output, node output and evidence attachments as separate fixed regions', () => {
  const finalOutput = { outputId: 'final', kind: 'value' as const, name: '最终结果', value: '已完成', runId: 'run', sequence: 4, createdAt: '' } satisfies Schema['RunOutputView']
  const nodeOutput = { ...finalOutput, outputId: 'node-output', name: '页面标题', value: 'AutoFlow', nodeId: 'node-02', nodeName: '旧节点名' } satisfies Schema['RunOutputView']
  const { rerender } = render(<TaskEvidence {...base} mode="io" outputs={outputPage([finalOutput, nodeOutput])} artifacts={artifactPage([artifact])}/>)

  expect(screen.getByRole('heading', { name: '最终业务输出' })).toBeVisible()
  expect(screen.getByRole('heading', { name: '节点中间输出' })).toBeVisible()
  expect(screen.getByRole('heading', { name: '证据附件' })).toBeVisible()
  expect(screen.getByText('最终结果').closest('section')).toHaveAccessibleName('最终业务输出')
  expect(screen.getByText('页面标题').closest('section')).toHaveAccessibleName('节点中间输出')
  expect(screen.getByText('打开页面').closest('section')).toHaveAccessibleName('证据附件')

  rerender(<TaskEvidence {...base} mode="io" outputs={outputPage([])} artifacts={artifactPage([])}/>)
  expect(screen.getByText('没有最终业务输出。')).toBeVisible()
  expect(screen.getByText('没有节点中间输出。')).toBeVisible()
  expect(screen.getByText('没有证据附件。')).toBeVisible()
})

it('shows frozen project inputs and explicit task data writes in the io view', () => {
  const dataDetail: Schema['TaskDetail'] = {
    ...detail,
    inputSnapshot: {
      ...detail.inputSnapshot,
      inputs: [{ alias: '邮箱', tableDisplay: '邮箱表', recordRef: { recordKey: { type: 'text', value: '001' } }, values: [{ fieldName: '地址', value: 'pm4@example.test' }] }],
    },
    dataWrites: [{ kind: 'statusChange', tableDisplay: '邮箱表', recordDisplay: 'text · 001', outcome: 'succeeded', previousStatus: '待使用', nextStatus: '已使用' }],
  }
  render(<TaskEvidence {...base} detail={dataDetail} mode="io" outputs={outputPage([])} artifacts={artifactPage([])}/>)
  expect(screen.getByRole('heading', { name: '原始数据输入' })).toBeVisible()
  expect(screen.getByText('pm4@example.test', { selector: 'td span' })).toBeVisible()
  expect(screen.getByText('text · 001')).toBeVisible()
  expect(screen.getByText('地址：pm4@example.test')).toBeVisible()
  expect(screen.getByRole('heading', { name: '任务数据写入' })).toBeVisible()
  expect(screen.getByText('待使用 → 已使用')).toBeVisible()
})

it('keeps an unavailable optional input visible as frozen task evidence', () => {
  const dataDetail: Schema['TaskDetail'] = {
    ...detail,
    inputSnapshot: {
      ...detail.inputSnapshot,
      inputs: [{
        alias: '备用邮箱',
        tableDisplay: '邮箱表',
        required: false,
        recordRef: null,
        unavailableReason: 'no_match',
        values: [],
      }],
    },
  }

  render(<TaskEvidence {...base} detail={dataDetail} mode="io" outputs={outputPage([])} artifacts={artifactPage([])}/>)

  expect(screen.getByText('备用邮箱')).toBeVisible()
  expect(screen.getByText('可选输入未找到')).toBeVisible()
  expect(screen.getByText('不会阻止本次启动')).toBeVisible()
  expect(screen.queryByText('可以使用')).not.toBeInTheDocument()
})

it('presents the isolated executor boundary as product language', () => {
  render(<TaskEvidence {...base} mode="io" outputs={outputPage([{
    outputId: 'boundary',
    kind: 'value',
    runId: detail.run.runId,
    sequence: 1,
    nodeId: null,
    nodeName: null,
    name: '测试执行边界',
    value: { executor: 'fake', browser: 'notExecuted', studio: 'notExecuted' },
    createdAt: '2026-09-15T01:02:03Z',
  }])} artifacts={artifactPage([])}/>)

  expect(screen.getByText('隔离测试执行器 · 未调用浏览器 · 未调用 Studio')).toBeVisible()
  expect(screen.queryByText(/notExecuted/)).not.toBeInTheDocument()
})

it('shows an inline failure screenshot and keeps the artifact action for enlargement', async () => {
  const onOpenArtifact = vi.fn()
  render(<TaskEvidence {...base} artifacts={artifactPage([artifact])} inlineScreenshotUrl="blob:failure" inlineScreenshotLabel="点击元素失败时页面" onOpenArtifact={onOpenArtifact}/>)

  expect(screen.getByRole('img', { name: '点击元素失败时页面' })).toHaveAttribute('src', 'blob:failure')
  await userEvent.click(screen.getByRole('button', { name: '放大失败截图：点击元素失败时页面' }))
  expect(onOpenArtifact).toHaveBeenCalledWith(artifact)
})

it('presents a safe specific failure summary and locates its log', async () => {
  const onLocateLog = vi.fn()
  const failedAttempt = { nodeVisitId: 'visit', nodeId: 'node-02', nodeName: '旧节点名', attempt: 2, status: 'failed' as const, startedAt: '', completedAt: '2026-09-15T01:02:03Z', error: { code: 'E_PAGE_TIMEOUT', message: 'raw backend details' } } satisfies Schema['NodeAttemptView']
  render(<TaskEvidence {...base} detail={{ ...detail, run: { ...detail.run, error: { code: 'E_PAGE_TIMEOUT', message: 'raw backend details' } } }} attempts={{ items: [failedAttempt], page: 1, pageSize: 100, total: 1, sort: 'createdAt' }} onLocateLog={onLocateLog}/>)

  expect(screen.getByRole('heading', { name: '读取页面超时' })).toBeVisible()
  expect(screen.getByText('发生节点').parentElement).toHaveTextContent('打开页面')
  expect(screen.getByText('尝试次数').parentElement).toHaveTextContent('第 2 次尝试')
  expect(screen.queryByText('raw backend details')).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: '定位对应日志' }))
  expect(onLocateLog).toHaveBeenCalledWith('node-02')
})
