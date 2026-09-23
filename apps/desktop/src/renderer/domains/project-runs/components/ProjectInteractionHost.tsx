import './interaction-dialog.css'
import { useEffect, useMemo, useRef, useState } from 'react'
import { ApiClientError, type StreamingApiClient } from '../../../shared/api/client'
import { InputPromptDialog } from '../../workflows/components/InputPromptDialog'
import type { InputPromptRequest } from '../../workflows/types/workflow'
import { createProjectInteractions, executeProjectScript, type InteractionIdentity } from '../interactions'

/** Main-window owner: route changes must not dispose a claimed script or input. */
export function ProjectInteractionHost({ client, connected }: { client: StreamingApiClient; connected: boolean }) {
  const latest = useRef({ client, connected }); latest.current = { client, connected }
  const api = useMemo(() => createProjectInteractions(() => latest.current.client), [])
  const [prompt, setPrompt] = useState<InputPromptRequest | null>(null)
  const [error, setError] = useState<string>()
  const activeInput = useRef<InteractionIdentity | null>(null)
  const commandTargets = useRef(new Map<string, InteractionIdentity>())
  const commands = useMemo(() => ({
    async sendInputResult(requestId: string, value: string | null, commandId: string = crypto.randomUUID()) {
      const target = activeInput.current
      if (!target || target.requestId !== requestId || !latest.current.connected) return { commandId, success: false, error: '交互请求已失效或服务未连接，输入已保留' }
      commandTargets.current.set(commandId, target)
      try {
        const receipt = await api.submit(target, commandId, 'input_prompt_result', { requestId, value })
        return { commandId, success: receipt.status === 'applied', ...(receipt.status !== 'applied' ? { status: 'unconfirmed' } : {}) }
      } catch (caught) {
        if (caught instanceof ApiClientError && caught.status >= 400 && caught.status < 500 && caught.status !== 408) return { commandId, success: false, error: caught.message }
        return { commandId, success: false, status: 'unconfirmed' }
      }
    },
    async queryInputResult(commandId: string) {
      const target = commandTargets.current.get(commandId)
      if (!target) return { commandId, success: false, status: 'unconfirmed' }
      try {
        const receipt = await api.command(target, commandId)
        return { commandId, success: receipt.status === 'applied', ...(receipt.status !== 'applied' ? { status: 'unconfirmed' } : {}) }
      } catch { return { commandId, success: false, status: 'unconfirmed' } }
    },
  }), [api])
  const paths = useMemo(() => ({ selectFile: (title?: string) => api.selectPath('file', title), selectFolder: (title?: string) => api.selectPath('folder', title) }), [api])
  useEffect(() => {
    const controller = new AbortController()
    const scripts = new Map<string, AbortController>()
    let timer: ReturnType<typeof setTimeout>
    const identity = (target: InteractionIdentity) => JSON.stringify([target.projectId, target.taskId, target.runId, target.executionGeneration, target.requestId])
    const poll = async () => {
      try {
        if (!latest.current.connected) return
        const pending = await api.pending(controller.signal)
        if (controller.signal.aborted) return
        const keys = new Set(pending.map(identity))
        for (const [key, script] of scripts) if (!keys.has(key)) { script.abort(); scripts.delete(key) }
        const input = pending.find(target => target.type === 'execution:input_prompt')
        if (!input) { activeInput.current = null; setPrompt(null) }
        else if (!activeInput.current || identity(activeInput.current) !== identity(input)) {
          const request = await api.request(input, controller.signal)
          if (controller.signal.aborted) return
          if (request.status !== 'cancelled' && request.type === 'execution:input_prompt') {
            if (request.commandId) commandTargets.current.set(request.commandId, input)
            activeInput.current = input; setPrompt(request)
            void window.autoflow?.showProjectInteraction?.().catch(() => setError('无法显示项目输入窗口，请从 Dock 或任务栏打开 AutoFlow'))
          }
        }
        for (const target of pending.filter(item => item.type === 'execution:js_script')) {
          const key = identity(target)
          if (scripts.has(key)) continue
          const script = new AbortController()
          scripts.set(key, script)
          void executeProjectScript(api, target, script.signal).catch(caught => {
            if (!script.signal.aborted && !controller.signal.aborted) setError(caught instanceof Error ? caught.message : '项目脚本交互失败')
          })
        }
      } catch (caught) {
        if (!controller.signal.aborted && !(caught instanceof ApiClientError && [404, 410].includes(caught.status))) setError('项目交互连接中断，正在查询原请求；未重新执行脚本')
      } finally {
        if (!controller.signal.aborted) timer = setTimeout(() => void poll(), 1000)
      }
    }
    void poll()
    return () => { controller.abort(); clearTimeout(timer); for (const script of scripts.values()) script.abort(); activeInput.current = null }
  }, [api])
  return <>
    {error ? <div role="alert" className="fixed bottom-4 right-4 z-[10000] max-w-lg rounded-control border border-line bg-surface p-4 text-sm text-ink">{error}<button type="button" className="ml-3 underline" onClick={() => setError(undefined)}>关闭提示</button></div> : null}
    <InputPromptDialog request={prompt} commands={commands} paths={paths} />
  </>
}
