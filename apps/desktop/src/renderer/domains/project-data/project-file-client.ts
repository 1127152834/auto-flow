import type { ProjectFileBridge } from '../../../shared/project-files'
import type { ApiRequestInit, StreamingApiClient } from '../../shared/api/client'

export function createProjectFileClient(client: StreamingApiClient, desktop: Partial<ProjectFileBridge>, projectId: string, current: () => boolean) {
  const guard = () => { if (!current()) throw new Error('项目或服务上下文已切换，请重新选择文件') }
  const chooseInput = async () => {
    guard()
    if (!desktop.chooseExcelInput) throw new Error('当前窗口无法选择 Excel 文件')
    const result = await desktop.chooseExcelInput(projectId)
    guard()
    if (!result.ok) throw new Error(result.error.message)
    return result.value
  }
  const chooseOutput = async (filename: string) => {
    guard()
    if (!desktop.chooseXlsxOutput) throw new Error('当前窗口无法选择导出位置')
    const result = await desktop.chooseXlsxOutput(projectId, filename)
    guard()
    if (!result.ok) throw new Error(result.error.message)
    return result.value
  }
  const request = async <T>(path: string, init?: ApiRequestInit): Promise<T> => {
    guard()
    if (!desktop.getProjectFileContext) throw new Error('当前窗口无法访问项目文件')
    const proof = await desktop.getProjectFileContext()
    guard()
    if (!proof.ok) throw new Error(proof.error.message)
    if (!proof.value) throw new Error('文件授权已失效，请重新选择文件')
    const headers = new Headers(init?.headers)
    headers.set('x-autoflow-file-window-id', String(proof.value.windowId))
    headers.set('x-autoflow-file-window-token', proof.value.windowToken)
    const result = await client.request<T>(path, { ...init, headers: Object.fromEntries(headers.entries()) })
    guard()
    return result
  }
  return { chooseInput, chooseOutput, request }
}
