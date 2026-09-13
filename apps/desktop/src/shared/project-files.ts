import type { DesktopResult } from './settings'

export type ProjectFileSelection = {
  selectionToken: string
  displayName: string
  kind: 'excelInput' | 'xlsxOutput'
  expiresAt: string
}

export type ProjectFileContext = { windowId: number; windowToken: string }

export type ProjectFileBridge = {
  chooseExcelInput(projectId: string): Promise<DesktopResult<ProjectFileSelection | null>>
  chooseXlsxOutput(projectId: string, suggestedName: string): Promise<DesktopResult<ProjectFileSelection | null>>
  getProjectFileContext(): Promise<DesktopResult<ProjectFileContext | null>>
}
