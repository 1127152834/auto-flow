import { installGlobalTooltip } from '../lib/globalTooltip'
import { useEffect } from 'react'
import { imageAssetApi, systemApi } from '../api'
import { useWorkflowStore } from '../editor-store'
import { socketService } from '../events'
import { useGlobalConfigStore } from './stores/globalConfigStore'
import { eventToCombo, SHORTCUT_ACTION_MAP } from '../lib/customShortcuts'

export function useStudioIntegration() {
  useEffect(installGlobalTooltip, [])
  const shortcuts=useGlobalConfigStore(s=>s.config.shortcuts)
  const theme=useGlobalConfigStore(s=>s.config.display?.theme || 'default')
  useEffect(()=>{
    if(theme==='default')document.documentElement.removeAttribute('data-webrpa-theme')
    else document.documentElement.setAttribute('data-webrpa-theme',theme)
  },[theme])
  useEffect(()=>{
    let disposed=false
    socketService.connect()
    void imageAssetApi.list().then(images=>{
      if(disposed)return
      if(Array.isArray(images.data))useWorkflowStore.getState().setImageAssets(images.data)
    })
    return ()=>{disposed=true;socketService.disconnect()}
  },[])
  useEffect(()=>{
    const handler=(event:KeyboardEvent)=>{
      const target=event.target
      if(target instanceof Element && target.closest('input,textarea,[contenteditable]:not([contenteditable="false"]),[role="textbox"]'))return
      const combo=eventToCombo(event)
      const id=Object.entries(shortcuts || {}).find(([,value])=>value===combo)?.[0]
      if(event.repeat)return
      if(id && SHORTCUT_ACTION_MAP[id]){event.preventDefault();SHORTCUT_ACTION_MAP[id].run()}
    }
    window.addEventListener('keydown',handler)
    return ()=>window.removeEventListener('keydown',handler)
  },[shortcuts])
  useEffect(() => {
    const register = () => { void systemApi.setCustomHotkeys(shortcuts || {}) }
    register()
    window.addEventListener('socket:reconnected', register)
    return () => window.removeEventListener('socket:reconnected', register)
  }, [shortcuts])
  useEffect(() => {
    const handler = (event: Event) => {
      const actionId: unknown = (event as CustomEvent<{ actionId?: unknown }>).detail?.actionId
      if (typeof actionId === 'string' && Object.hasOwn(SHORTCUT_ACTION_MAP, actionId)) {
        SHORTCUT_ACTION_MAP[actionId].run()
      }
    }
    window.addEventListener('hotkey:custom_action', handler)
    return () => window.removeEventListener('hotkey:custom_action', handler)
  }, [])

}
