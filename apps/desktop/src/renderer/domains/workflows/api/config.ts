import { setStudioTransport, type StudioTransport } from './transport'

let backendOrigin: string | undefined

/** Compose before mounting Studio; disconnect existing event clients before replacing. */
export function configureStudioConnection(origin: string, transport: StudioTransport): () => void {
  const normalizedOrigin = normalizeStudioOrigin(origin)
  const previous = backendOrigin
  const restoreTransport = setStudioTransport(transport)
  backendOrigin = normalizedOrigin
  return () => { backendOrigin = previous; restoreTransport() }
}

/** AutoFlow owns connection selection; no source-project discovery or credentials. */
export const getBackendBaseUrl = () => {
  if (!backendOrigin) throw new Error('Studio connection has not been configured')
  return backendOrigin
}
export const getBackendPort = () => new URL(getBackendBaseUrl()).port
export const getFrontendPort = () => location.port
export const setBackendPort = (_port: number | string) => { throw new Error('Studio connection is managed by AutoFlow') }
export const preloadConfig = async () => { getBackendBaseUrl() }

/** Shared validation for connection composition and authenticated HTTP transport. */
export function normalizeStudioOrigin(origin: string): string {
  const url = new URL(origin)
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password ||
      url.pathname !== '/' || url.search || url.hash) {
    throw new Error('Studio connection requires an HTTP origin without credentials or path')
  }
  return url.origin
}
