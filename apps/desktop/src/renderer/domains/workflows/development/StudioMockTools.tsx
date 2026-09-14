import { useState } from 'react'
import { localWorkflowApi } from '../api'
import { MockBrowserSurface } from '../components/MockBrowserSurface'
import { useAIAssistantStore } from '../hooks/stores/aiAssistantStore'
import { configureMock, configureMockBrowserPages, addMockRecordingEvent, selectMockElement, selectMockSimilarElements, seedMockRunHistory } from '../api/mock-server'
import { useWorkflowStore } from '../editor-store'

/** Explicit fixture controls, composed only by the current frontend preview entry. */
export function StudioMockTools() {
  const [mockPage, setMockPage] = useState(false)
  const [toolsOpen, setToolsOpen] = useState(false)
  const [message, setMessage] = useState('')
  const [executionOrder, setExecutionOrder] = useState('')
  const action = (fn: () => void) => { try { fn(); setMessage('已发送 Mock 场景') } catch (error) { setMessage(String(error)) } }
  return <>
    <div className="studio-mock-banner"><span>AutoFlow Studio <b>Mock 接口</b> · 浏览器、运行、录制为模拟事件，未执行真实网页操作</span><button onClick={() => setMockPage(!mockPage)}>Mock 测试页</button><button onClick={() => useAIAssistantStore.getState().togglePanel()}>AI 小助手</button><button onClick={() => setToolsOpen(!toolsOpen)}>接口场景 {toolsOpen ? '收起' : '展开'}</button></div>
    {toolsOpen && <div className="studio-mock-tools">
      <button onClick={async()=>setMessage(JSON.stringify(await localWorkflowApi.getDefaultFolder()))}>检查默认目录</button>
      <button onClick={() => action(() => configureMock({disconnect:true}))}>断开 SSE 并补读</button>
      <button onClick={() => action(() => configureMockBrowserPages([{pageId:'fixture-main',title:'受控主页面',url:'http://local.test/main'},{pageId:'fixture-popup',title:'受控弹出页',url:'http://local.test/popup'}],'fixture-main'))}>浏览器：两个页面</button>
      <button onClick={() => action(() => configureMockBrowserPages([{pageId:'fixture-main',title:'受控主页面',url:'http://local.test/main'}],null))}>浏览器：目标页关闭</button>
      <button onClick={() => action(() => configureMock({offline:true}))}>服务离线</button>
      <button onClick={() => action(() => configureMock({offline:false}))}>恢复连接</button>
      <button onClick={() => action(() => configureMock({failNextSave:true}))}>下次保存失败</button><button onClick={() => action(() => configureMock({failNextRun:true}))}>下次节点失败</button>
      <button onClick={() => action(() => addMockRecordingEvent({type:'navigate',url:'https://example.test/'}))}>录制：导航</button>
      <button onClick={() => action(() => addMockRecordingEvent({type:'input',selector:'#name',value:'AutoFlow'}))}>录制：输入</button>
      <button onClick={() => action(() => addMockRecordingEvent({type:'click',selector:'#submit'}))}>录制：点击</button>
      <button onClick={() => action(() => selectMockElement('#submit'))}>拾取：提交元素</button>
      <button onClick={() => action(() => configureMock({failNextPickerStop:true}))}>下次停止拾取失败</button>
      <button onClick={() => action(() => selectMockSimilarElements())}>拾取：四个相似元素</button>
      {([['none', '零匹配'], ['single', '单匹配'], ['multiple', '多匹配'], ['error', '服务失败']] as const).map(([scenario, label]) =>
        <button key={scenario} onClick={() => action(() => configureMock({ selectorTest: scenario }))}>定位：{label}</button>)}
      <button onClick={() => action(() => { configureMock({failNextRequiredFields:true}); window.dispatchEvent(new Event('studio:connection-restored')) })}>字段规则：刷新失败</button>
      <button onClick={() => action(() => configureMock({scriptTest:{result:{title:'模拟返回值',count:3}}}))}>脚本测试：返回对象</button>
      <button onClick={() => action(() => configureMock({scriptTest:{}}))}>脚本测试：无返回值</button>
      <button onClick={() => action(() => configureMock({scriptTest:{error:'模拟页面脚本失败'}}))}>脚本测试：失败</button>
      <button onClick={() => action(() => configureMock({scriptTest:{hold:true}}))}>脚本测试：等待取消</button>
      <label>下次 Mock 节点轨迹 <input aria-label="下次 Mock 节点轨迹" value={executionOrder} onChange={event => setExecutionOrder(event.target.value)} placeholder="节点ID，用逗号分隔；重复ID表示重复调度" /></label>
      <button onClick={() => action(() => {
        if (!executionOrder.trim()) throw new Error('请输入节点 ID；不会执行表达式或推断分支')
        configureMock({ executionOrder: executionOrder.split(/[,，]/).map(id => id.trim()) })
      })}>应用下次轨迹</button>
      <button onClick={() => action(() => configureMock({ executionOrder: null }))}>恢复顺序场景</button>
      <button onClick={() => action(() => {
        const state = useWorkflowStore.getState()
        const nodeA = state.nodes[0]?.id || 'browser-node-a'
        const nodeB = state.nodes[1]?.id || nodeA
        seedMockRunHistory({
          runId: 'browser-capacity-run', workflowId: 'browser-capacity-workflow', documentId: state.id, workflowName: '一万条日志验收',
          logs: Array.from({ length: 10_000 }, (_, index) => ({
            id: `browser-log-${index + 1}`, timestamp: new Date(Date.UTC(2026, 8, 14, 0, 0, index)).toISOString(),
            level: index % 100 === 0 ? 'error' : 'info', nodeId: index % 2 ? nodeB : nodeA,
            message: `${index % 100 === 0 ? '容量故障' : '容量调度'}-${String(index + 1).padStart(5, '0')}`,
          })),
        })
        useWorkflowStore.setState({ currentExecutionWorkflowId: 'browser-capacity-workflow', currentExecutionRunId: 'browser-capacity-run', bottomPanelTab: 'logs' })
      })}>日志容量：1万条</button>
      <span role="status">{message}</span>
    </div>}
    {mockPage && <MockBrowserSurface onClose={() => setMockPage(false)} />}
  </>
}
