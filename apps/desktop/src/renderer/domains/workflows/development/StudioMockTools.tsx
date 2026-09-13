import { useState } from 'react'
import { localWorkflowApi } from '../api'
import { MockBrowserSurface } from '../components/MockBrowserSurface'
import { useAIAssistantStore } from '../hooks/stores/aiAssistantStore'
import { configureMock, addMockRecordingEvent, selectMockElement } from '../api/mock-server'

/** Explicit fixture controls, composed only by the current frontend preview entry. */
export function StudioMockTools() {
  const [mockPage, setMockPage] = useState(false)
  const [toolsOpen, setToolsOpen] = useState(false)
  const [message, setMessage] = useState('')
  const action = (fn: () => void) => { try { fn(); setMessage('已发送 Mock 场景') } catch (error) { setMessage(String(error)) } }
  return <>
    <div className="studio-mock-banner"><span>AutoFlow Studio <b>Mock 接口</b> · 浏览器、运行、录制为模拟事件，未执行真实网页操作</span><button onClick={() => setMockPage(!mockPage)}>Mock 测试页</button><button onClick={() => useAIAssistantStore.getState().togglePanel()}>AI 小助手</button><button onClick={() => setToolsOpen(!toolsOpen)}>接口场景 {toolsOpen ? '收起' : '展开'}</button></div>
    {toolsOpen && <div className="studio-mock-tools">
      <button onClick={async()=>setMessage(JSON.stringify(await localWorkflowApi.getDefaultFolder()))}>检查默认目录</button>
      <button onClick={() => action(() => configureMock({disconnect:true}))}>断开 SSE 并补读</button>
      <button onClick={() => action(() => configureMock({offline:true}))}>服务离线</button>
      <button onClick={() => action(() => configureMock({offline:false}))}>恢复连接</button>
      <button onClick={() => action(() => configureMock({failNextSave:true}))}>下次保存失败</button><button onClick={() => action(() => configureMock({failNextRun:true}))}>下次节点失败</button>
      <button onClick={() => action(() => addMockRecordingEvent({type:'navigate',url:'https://example.test/'}))}>录制：导航</button>
      <button onClick={() => action(() => addMockRecordingEvent({type:'input',selector:'#name',value:'AutoFlow'}))}>录制：输入</button>
      <button onClick={() => action(() => addMockRecordingEvent({type:'click',selector:'#submit'}))}>录制：点击</button>
      <button onClick={() => action(() => selectMockElement('#submit'))}>拾取：提交元素</button>
      <span role="status">{message}</span>
    </div>}
    {mockPage && <MockBrowserSurface onClose={() => setMockPage(false)} />}
  </>
}
