import { useEffect, useState } from 'react'
import { addMockRecordingEvent, mockSnapshot, selectMockElement } from '../api/mock-server'
import { browserApi } from '../api'
/** A visible protocol fixture, never an embedded browser or a production page picker. */
export function MockBrowserSurface({ onClose }: { onClose(): void }) {
  const [status, setStatus] = useState(mockSnapshot)
  const [address, setAddress] = useState('https://example.test/')
  const [value, setValue] = useState('')
  const [message, setMessage] = useState('')
  useEffect(() => { const timer = setInterval(() => setStatus(mockSnapshot()), 300); return () => clearInterval(timer) }, [])
  function capture(type: string, selector: string, extra: Record<string, string | boolean> = {}) {
    try {
      if (status.picking) { selectMockElement(selector); setMessage(`已选中 ${selector}`) }
      else if (status.recording) { addMockRecordingEvent({type,selector,...extra}); setMessage(`已发送 ${type} 事件`) }
      else setMessage('普通模拟浏览；在录制或拾取面板开始后，操作会产生对应事件。')
    } catch (error) { setMessage(String(error)) }
  }
  return <aside className="studio-mock-page" aria-label="Mock 浏览器测试页">
    <header><b>Mock 浏览器测试页</b><button onClick={onClose} aria-label="收起 Mock 测试页">×</button></header>
    <p>此处仅产生测试事件，不会访问输入的网址。</p>
    <div className="flex gap-1"><input aria-label="Mock 页面网址" value={address} onChange={e=>setAddress(e.target.value)}/><button onClick={async()=> { const r=await browserApi.navigate(address); if (r.error) setMessage(r.error); else { if(status.recording)addMockRecordingEvent({type:'navigate',url:address});setMessage('Mock 导航已确认') } }}>导航</button></div>
    <label>名称 <input aria-label="Mock 名称" value={value} onChange={e=> {setValue(e.target.value); capture('input','#name',{value:e.target.value})}} onClick={()=>{if(status.picking)capture('click','#name')}}/></label>
    <button onClick={()=>capture('click','#submit')} onDoubleClick={()=>capture('dblclick','#submit')}>提交测试按钮</button>
    <label><input type="checkbox" onChange={e=>capture('check','#enabled',{value:e.target.checked})}/>启用</label>
    <select aria-label="Mock 选项" onChange={e=>capture('select','#option',{value:e.target.value})}><option value="a">选项 A</option><option value="b">选项 B</option></select>
    <p>{status.recording ? '正在采集 Mock 事件' : status.picking ? '等待 Mock 元素选择' : '普通 Mock 浏览'}</p><p role="status">{message}</p>
  </aside>
}
