import { useWorkflowStore } from '../editor-store'
import { decryptWorkflow, isEncryptedEnvelope } from './workflowCrypto'
import type { usePasswordPrompt } from '../components/controls/password-prompt'
import type { useConfirm } from '../components/controls/confirm-dialog'

type ImportDialogs = {
  promptPassword: ReturnType<typeof usePasswordPrompt>['promptPassword']
  alert: ReturnType<typeof useConfirm>['alert']
}

/** Read files in drop order so encrypted files cannot replace each other's password prompts. */
export async function importDroppedWorkflows(files: File[], position: { x: number; y: number }, dialogs: ImportDialogs): Promise<void> {
  const originId = useWorkflowStore.getState().id
  let invalidated = false
  const unsubscribe = useWorkflowStore.subscribe(state => { if (state.id !== originId) invalidated = true })
  const log = useWorkflowStore.getState().addLog
  const current = () => {
    if (!invalidated) return true
    log({ level: 'warning', message: '流程已切换，已取消尚未完成的文件导入，请在目标流程中重新拖入。' })
    return false
  }
  try {
    for (const [index, file] of files.entries()) {
      if (!current()) return
      let payload: string
      try { payload = await file.text() }
      catch {
        if (!current()) return
        log({ level: 'error', message: `读取文件失败: ${file.name}` })
        continue
      }
      if (!current()) return
      let parsed: unknown
      try { parsed = JSON.parse(payload) } catch { /* The existing importer reports damaged JSON. */ }
      if (isEncryptedEnvelope(parsed)) {
        const password = await dialogs.promptPassword({ title: '导入加密分享包', message: `「${parsed.name || file.name}」是加密分享包，请输入密码`, confirmText: '解密导入' })
        if (!current()) return
        if (!password) {
          log({ level: 'warning', message: `已取消导入加密包: ${file.name}` })
          continue
        }
        try { payload = await decryptWorkflow(parsed, password) }
        catch {
          if (!current()) return
          log({ level: 'error', message: `解密失败：密码错误或文件已损坏（${file.name}）` })
          await dialogs.alert(`无法解密「${file.name}」。密码错误或文件已损坏，请确认密码后重试。`, { title: '解密失败', confirmText: '我知道了' })
          continue
        }
        if (!current()) return
      }
      const success = useWorkflowStore.getState().mergeWorkflow(payload, { x: position.x, y: position.y + index * 150 })
      log(success
        ? { level: 'success', message: `已导入工作流: ${file.name}` }
        : { level: 'error', message: `导入失败: ${file.name}，文件格式无效` })
    }
  } finally { unsubscribe() }
}
