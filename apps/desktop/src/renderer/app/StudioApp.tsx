import { StudioConnectionNotice } from '../domains/workflows/components/StudioConnectionNotice'
import { localWorkflowApi } from '../domains/workflows/api'
import { useEffect, useState } from 'react'
import { MockBrowserSurface } from '../domains/workflows/components/MockBrowserSurface'
import { AIAssistantPanel } from '../domains/workflows/components/assistant/AIAssistantPanel'
import { useLayoutStore } from '../domains/workflows/hooks/stores/layoutStore'
import { useAIAssistantStore } from '../domains/workflows/hooks/stores/aiAssistantStore'
import { WorkflowEditor } from '../domains/workflows/components/WorkflowEditor'
import { InputPromptDialog } from '../domains/workflows/components/InputPromptDialog'
import { MusicPlayerContainer } from '../domains/workflows/components/MusicPlayerContainer'
import { VideoPlayerContainer } from '../domains/workflows/components/VideoPlayerContainer'
import { ImageViewerContainer } from '../domains/workflows/components/ImageViewerContainer'
import { useStudioIntegration } from '../domains/workflows/hooks/useStudioIntegration'
import { useWorkflowStore } from '../domains/workflows/editor-store'
import { configureMock, addMockRecordingEvent, selectMockElement } from '../domains/workflows/api/mock-server'

export function StudioApp() {
  useStudioIntegration()
  const aiPanelOpen = useAIAssistantStore(state => state.isPanelOpen)
  const aiPanelWidth = useLayoutStore(state => state.aiAssistantWidth)
  const [mockPage, setMockPage] = useState(false)
  const [toolsOpen, setToolsOpen] = useState(false)
  const [message, setMessage] = useState('')
  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (useWorkflowStore.getState().hasUnsavedChanges) { event.preventDefault(); event.returnValue = '' }
    }
    window.addEventListener('beforeunload', beforeUnload)
    return () => { window.removeEventListener('beforeunload', beforeUnload) }
  }, [])
  const action = (fn: () => void) => { try { fn(); setMessage('已发送 Mock 场景') } catch (error) { setMessage(String(error)) } }
  return <main aria-label="工作流工作台" className="studio-shell" style={{ paddingRight: aiPanelOpen ? aiPanelWidth : 0, transition: 'padding-right 200ms ease' }}>
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
    <StudioConnectionNotice />
    <div className="studio-editor @container"><WorkflowEditor /></div>
    <AIAssistantPanel />{mockPage && <MockBrowserSurface onClose={()=>setMockPage(false)} />}<InputPromptDialog /><MusicPlayerContainer /><VideoPlayerContainer /><ImageViewerContainer />
  </main>
}
