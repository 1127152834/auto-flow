import type { DesktopResult } from './settings'

/** The renderer never receives Google credentials, only this one-time handover token. */
export type GoogleAuthorization = { authorizationToken: string; accountLabel: string; writable: boolean }

export type GoogleSheetsBridge = {
  connectGoogleSheets(projectId: string, accountLabel: string): Promise<DesktopResult<GoogleAuthorization | null>>
}
