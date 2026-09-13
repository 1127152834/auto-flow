export type ProjectFilePurpose = 'inspectExcel' | 'exportXlsx'

export type ProjectFileRegistration = {
  selectionToken: string
  path: string
  projectId: string
  windowId: number
  purpose: ProjectFilePurpose
  expiresAt: string
}

export type ProjectFileHost = {
  state: 'ready'
  baseUrl: string
  hostToken: string
  dataDir: string
}

function endpoint(host: ProjectFileHost): string {
  let url: URL
  try { url = new URL(host.baseUrl) } catch { throw new Error('project file service is unavailable') }
  if (
    url.protocol !== 'http:' || url.hostname !== '127.0.0.1' || !url.port || url.pathname !== '/'
    || url.username || url.password || url.search || url.hash || !host.hostToken || !host.dataDir
  ) throw new Error('project file service is unavailable')
  return `${url.origin}/internal/project-files/selections`
}

export async function registerProjectFileSelection(
  host: ProjectFileHost,
  selection: ProjectFileRegistration,
  windowToken: string,
  request: typeof fetch = fetch,
): Promise<void> {
  if (!windowToken) throw new Error('project file service is unavailable')
  let response: Response
  try {
    response = await request(endpoint(host), {
      method: 'POST', cache: 'no-store', redirect: 'error', signal: AbortSignal.timeout(10_000),
      headers: {
        accept: 'application/json', 'content-type': 'application/json',
        'x-autoflow-host-token': host.hostToken,
        'x-autoflow-file-window-token': windowToken,
      },
      body: JSON.stringify(selection),
    })
  } catch (error) {
    if (error instanceof Error && error.message === 'project file service is unavailable') throw error
    throw new Error('project file registration failed')
  }
  if (!response.ok) throw new Error('project file registration failed')
}
