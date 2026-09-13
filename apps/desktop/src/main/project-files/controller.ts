import { randomUUID } from 'node:crypto'
import { lstat, realpath } from 'node:fs/promises'
import { basename, dirname, extname, isAbsolute, join, normalize } from 'node:path'
import type { DesktopResult } from '../../shared/settings'
import type { ProjectFileContext, ProjectFileSelection } from '../../shared/project-files'
import {
  registerProjectFileSelection,
  type ProjectFileHost,
  type ProjectFilePurpose,
  type ProjectFileRegistration,
} from './registry'

type HostStatus = ProjectFileHost | { state: 'starting' | 'stopped' | 'failed' }
type InvokeEvent = { sender: { id: number; mainFrame: unknown }; senderFrame: unknown }
type OpenDialogResult = { canceled: boolean; filePaths: string[] }
type SaveDialogResult = { canceled: boolean; filePath?: string }

export type ProjectFilesDependencies = {
  allowedSenderId: number
  getHostStatus(): HostStatus
  showOpenDialog(options: object): Promise<OpenDialogResult>
  showSaveDialog(options: object): Promise<SaveDialogResult>
  register?(host: ProjectFileHost, selection: ProjectFileRegistration, windowToken: string): Promise<void>
  now?: () => Date
  randomUUID?: () => string
}

type FileErrorCode =
  | 'UNAUTHORIZED_WINDOW' | 'INVALID_PROJECT_ID' | 'INVALID_SUGGESTED_NAME' | 'SERVICE_UNAVAILABLE'
  | 'SERVICE_CHANGED' | 'INVALID_EXCEL_FILE' | 'INVALID_OUTPUT_PATH' | 'OUTPUT_ALREADY_EXISTS'
  | 'FILE_REGISTRATION_FAILED'

class ProjectFileError extends Error {
  constructor(readonly code: FileErrorCode, message: string) { super(message) }
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

function sameHost(left: ProjectFileHost, right: HostStatus): right is ProjectFileHost {
  return right.state === 'ready' && left.baseUrl === right.baseUrl && left.hostToken === right.hostToken && left.dataDir === right.dataDir
}

async function inputPath(path: string): Promise<string> {
  if (!isAbsolute(path) || extname(path).toLowerCase() !== '.xlsx') throw new ProjectFileError('INVALID_EXCEL_FILE', '请选择有效的 XLSX 文件')
  try {
    const info = await lstat(path)
    if (!info.isFile() || info.isSymbolicLink()) throw new Error()
    return await realpath(path)
  } catch { throw new ProjectFileError('INVALID_EXCEL_FILE', '请选择有效的 XLSX 文件') }
}

async function outputPath(path: string): Promise<string> {
  if (!isAbsolute(path) || extname(path).toLowerCase() !== '.xlsx') throw new ProjectFileError('INVALID_OUTPUT_PATH', '请选择新的 XLSX 文件路径')
  try { await lstat(path); throw new ProjectFileError('OUTPUT_ALREADY_EXISTS', '导出目标已存在，请选择新文件名') }
  catch (error) {
    if (error instanceof ProjectFileError) throw error
    if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw new ProjectFileError('INVALID_OUTPUT_PATH', '无法使用所选导出路径')
  }
  try {
    const parent = dirname(normalize(path))
    const canonicalParent = await realpath(parent)
    const info = await lstat(canonicalParent)
    if (!info.isDirectory() || info.isSymbolicLink()) throw new Error()
    return join(canonicalParent, basename(path))
  } catch { throw new ProjectFileError('INVALID_OUTPUT_PATH', '无法使用所选导出路径') }
}

export class ProjectFilesController {
  private proof: { host: ProjectFileHost; context: ProjectFileContext; registered: boolean } | undefined

  constructor(private readonly dependencies: ProjectFilesDependencies) {}

  async getProjectFileContext(event: InvokeEvent): Promise<DesktopResult<ProjectFileContext | null>> {
    if (!this.isAllowed(event)) return { ok: false, error: { code: 'UNAUTHORIZED_WINDOW', message: '此窗口不能读取项目文件授权' } }
    const host = this.dependencies.getHostStatus()
    if (!this.proof || !sameHost(this.proof.host, host)) {
      this.proof = undefined
      return { ok: true, value: null }
    }
    return { ok: true, value: this.proof.registered ? this.proof.context : null }
  }

  chooseExcelInput(event: InvokeEvent, projectId: unknown): Promise<DesktopResult<ProjectFileSelection | null>> {
    return this.choose(event, projectId, 'inspectExcel', async _host => {
      const result = await this.dependencies.showOpenDialog({
        title: '选择 Excel 文件', properties: ['openFile'], filters: [{ name: 'Excel 工作簿', extensions: ['xlsx'] }],
      })
      return result.canceled ? null : inputPath(result.filePaths[0] ?? '')
    })
  }

  chooseXlsxOutput(event: InvokeEvent, projectId: unknown, suggestedName: unknown): Promise<DesktopResult<ProjectFileSelection | null>> {
    return this.choose(event, projectId, 'exportXlsx', async _host => {
      if (typeof suggestedName !== 'string' || basename(suggestedName) !== suggestedName || extname(suggestedName).toLowerCase() !== '.xlsx') {
        throw new ProjectFileError('INVALID_SUGGESTED_NAME', '建议文件名必须是安全的 XLSX 文件名')
      }
      const result = await this.dependencies.showSaveDialog({
        title: '导出 XLSX 文件', defaultPath: suggestedName, filters: [{ name: 'Excel 工作簿', extensions: ['xlsx'] }],
      })
      return result.canceled ? null : outputPath(result.filePath ?? '')
    })
  }

  private async choose(
    event: InvokeEvent,
    projectId: unknown,
    purpose: ProjectFilePurpose,
    select: (host: ProjectFileHost) => Promise<string | null>,
  ): Promise<DesktopResult<ProjectFileSelection | null>> {
    try {
      if (!this.isAllowed(event)) {
        throw new ProjectFileError('UNAUTHORIZED_WINDOW', '此窗口不能选择项目文件')
      }
      if (typeof projectId !== 'string' || !UUID.test(projectId)) throw new ProjectFileError('INVALID_PROJECT_ID', '项目标识无效')
      const host = this.dependencies.getHostStatus()
      if (host.state !== 'ready') throw new ProjectFileError('SERVICE_UNAVAILABLE', '本地项目文件服务尚未就绪')
      const path = await select(host)
      if (path === null) return { ok: true, value: null }
      if (!sameHost(host, this.dependencies.getHostStatus())) throw new ProjectFileError('SERVICE_CHANGED', '工作区或本地服务已切换，请重新选择文件')
      const expiresAt = new Date((this.dependencies.now?.() ?? new Date()).getTime() + 5 * 60_000).toISOString()
      const selectionToken = (this.dependencies.randomUUID ?? randomUUID)()
      if (!this.proof || !sameHost(this.proof.host, host)) {
        this.proof = {
          host,
          context: { windowId: event.sender.id, windowToken: (this.dependencies.randomUUID ?? randomUUID)() },
          registered: false,
        }
      }
      const registration = { selectionToken, path, projectId, windowId: event.sender.id, purpose, expiresAt }
      try { await (this.dependencies.register ?? registerProjectFileSelection)(host, registration, this.proof.context.windowToken) }
      catch { throw new ProjectFileError('FILE_REGISTRATION_FAILED', '文件授权登记失败，请重试') }
      this.proof.registered = true
      if (!sameHost(host, this.dependencies.getHostStatus())) throw new ProjectFileError('SERVICE_CHANGED', '工作区或本地服务已切换，请重新选择文件')
      return { ok: true, value: {
        selectionToken, displayName: basename(path), kind: purpose === 'inspectExcel' ? 'excelInput' : 'xlsxOutput', expiresAt,
      } }
    } catch (error) {
      const failure = error instanceof ProjectFileError
        ? error
        : new ProjectFileError('INVALID_EXCEL_FILE', '项目文件选择失败，请重试')
      return { ok: false, error: { code: failure.code, message: failure.message } }
    }
  }

  private isAllowed(event: InvokeEvent): boolean {
    return event.sender.id === this.dependencies.allowedSenderId && Boolean(event.senderFrame) && event.senderFrame === event.sender.mainFrame
  }
}
