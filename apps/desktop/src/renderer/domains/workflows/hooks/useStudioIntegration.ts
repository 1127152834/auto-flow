import { registerDocumentLeaveResource } from '../lib/documentLeave'
import {readImageAssetList} from '../lib/imageAssetContract'
import {getStudioTransportRevision} from '../api/transport'
import { installGlobalTooltip } from '../lib/globalTooltip'
import { useEffect, useRef } from 'react'
import { currentPickerSession, elementPickerApi, imageAssetApi, systemApi } from '../api'
import { useWorkflowStore } from '../editor-store'
import { socketService } from '../events'
import { useGlobalConfigStore } from './stores/globalConfigStore'
import { eventToCombo, SHORTCUT_ACTION_MAP } from '../lib/customShortcuts'

export function useStudioIntegration() {
  useEffect(installGlobalTooltip, [])
  useEffect(() => registerDocumentLeaveResource(() => {
    const sessionId = currentPickerSession()
    if (!sessionId) return null
    const revision = getStudioTransportRevision()
    return { id: `picker:${revision}:${sessionId}`, label: '元素拾取', release: async () => {
      if (revision !== getStudioTransportRevision() || sessionId !== currentPickerSession()) return false
      const response = await elementPickerApi.stop()
      return response.success && response.data?.active === false
    } }
  }), [])
  const hotkeyError = useRef<string | null>(null)
  const shortcuts=useGlobalConfigStore(s=>s.config.shortcuts)
  const theme=useGlobalConfigStore(s=>s.config.display?.theme || 'default')
  useEffect(()=>{
    if(theme==='default')document.documentElement.removeAttribute('data-webrpa-theme')
    else document.documentElement.setAttribute('data-webrpa-theme',theme)
  },[theme])
  useEffect(()=>{
    let disposed=false
    let request=0
    let lastError:string|null=null
    const loadImages=async()=>{
      const sequence=++request
      const revision=getStudioTransportRevision()
      const previous=useWorkflowStore.getState().imageAssets
      const current=()=>!disposed && sequence===request && revision===getStudioTransportRevision() && previous===useWorkflowStore.getState().imageAssets
      try {
        const result=await imageAssetApi.list()
        if(!current())return
        if(!result.success)throw new Error(result.error || '资源服务未确认加载')
        const assets=readImageAssetList(result.data)
        if(!assets)throw new Error('图像资源列表格式错误')
        useWorkflowStore.getState().setImageAssets(assets)
        if(lastError){useWorkflowStore.getState().addLog({level:'info',message:'图像资源加载已恢复'});lastError=null}
      }catch(error){
        if(!current())return
        const message=error instanceof Error?error.message:'图像资源加载失败'
        if(lastError!==message){useWorkflowStore.getState().addLog({level:'error',message:`图像资源加载失败: ${message}`});lastError=message}
      }
    }
    const events=['socket:reconnected','refresh:image-assets','studio:transport-changed']
    for(const event of events)window.addEventListener(event,loadImages)
    socketService.connect()
    void loadImages()
    return ()=>{
      disposed=true
      for(const event of events)window.removeEventListener(event,loadImages)
      socketService.disconnect()
    }
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
    let disposed = false
    let request = 0
    const register = async () => {
      const current = ++request
      const isCurrent = () => !disposed && current === request
      try {
        const result = await systemApi.setCustomHotkeys(shortcuts || {})
        if (!isCurrent()) return
        if (!result.success) throw new Error(result.error || '服务未确认注册')
        if (hotkeyError.current) {
          useWorkflowStore.getState().addLog({ level: 'info', message: '全局快捷键注册已恢复' })
          hotkeyError.current = null
        }
      } catch (error) {
        if (!isCurrent()) return
        const message = error instanceof Error ? error.message : String(error)
        if (hotkeyError.current !== message) {
          useWorkflowStore.getState().addLog({ level: 'error', message: `全局快捷键注册失败: ${message}` })
          hotkeyError.current = message
        }
      }
    }
    register()
    window.addEventListener('socket:reconnected', register)
    return () => {
      disposed = true
      window.removeEventListener('socket:reconnected', register)
    }
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
