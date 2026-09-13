import { useEffect } from 'react'
import { dataAssetApi, imageAssetApi } from '../api'
import { useWorkflowStore } from '../editor-store'
import { socketService } from '../events'
import { useGlobalConfigStore } from './stores/globalConfigStore'
import { eventToCombo, SHORTCUT_ACTION_MAP } from '../lib/customShortcuts'

export function useStudioIntegration() {
  const shortcuts=useGlobalConfigStore(s=>s.config.shortcuts)
  const theme=useGlobalConfigStore(s=>s.config.display?.theme || 'default')
  useEffect(()=>{
    if(theme==='default')document.documentElement.removeAttribute('data-webrpa-theme')
    else document.documentElement.setAttribute('data-webrpa-theme',theme)
  },[theme])
  useEffect(()=>{
    let disposed=false
    socketService.connect()
    void Promise.all([dataAssetApi.list(),imageAssetApi.list()]).then(([data,images])=>{
      if(disposed)return
      if(Array.isArray(data.data))useWorkflowStore.getState().setDataAssets(data.data)
      if(Array.isArray(images.data))useWorkflowStore.getState().setImageAssets(images.data)
    })
    return ()=>{disposed=true;socketService.disconnect()}
  },[])
  useEffect(()=>{
    const handler=(event:KeyboardEvent)=>{
      const target=event.target as HTMLElement
      if(target?.matches('input,textarea,[contenteditable="true"]'))return
      const combo=eventToCombo(event)
      const id=Object.entries(shortcuts || {}).find(([,value])=>value===combo)?.[0]
      if(id && SHORTCUT_ACTION_MAP[id]){event.preventDefault();SHORTCUT_ACTION_MAP[id].run()}
    }
    window.addEventListener('keydown',handler)
    return ()=>window.removeEventListener('keydown',handler)
  },[shortcuts])
}
