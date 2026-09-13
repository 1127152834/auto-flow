import { Component, type ReactNode } from 'react'
import { useWorkflowStore } from '../editor-store'
export class StudioErrorBoundary extends Component<{children:ReactNode},{error:Error|null}> {
  state:{error:Error|null}={error:null}
  static getDerivedStateFromError(error:Error){return {error}}
  render(){
    if(!this.state.error)return this.props.children
    return <section role="alert" className="p-6"><h1>Studio 页面发生错误</h1><p>{this.state.error.message}</p><p>当前草稿仍保留在内存中，可以先导出。</p><button onClick={()=>{
      const href=URL.createObjectURL(new Blob([useWorkflowStore.getState().exportWorkflow()],{type:'application/json'}))
      const a=document.createElement('a');a.href=href;a.download='studio-draft.json';a.click();setTimeout(()=>URL.revokeObjectURL(href),1000)
    }}>导出当前草稿</button><button onClick={()=>this.setState({error:null})}>重新渲染</button></section>
  }
}
