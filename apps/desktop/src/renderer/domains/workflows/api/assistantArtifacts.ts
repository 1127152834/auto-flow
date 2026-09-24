import { getBackendBaseUrl, scopeStudioUrl } from './config'
import { studioFetch } from './transport'

const REFERENCE = /^(assistant-(attachment|artifact)):\/\/([^/]+)$/

function artifactUrl(reference: string): string {
  const match = REFERENCE.exec(reference)
  if (!match) throw new Error('小助手产物标识无效')
  const kind = match[2] === 'attachment' ? 'attachment' : 'artifact'
  return scopeStudioUrl(`${getBackendBaseUrl()}/api/ai-assistant/artifacts/${kind}/${encodeURIComponent(match[3])}`)
}

export async function readAssistantArtifact(reference: string): Promise<Blob> {
  const response = await studioFetch(artifactUrl(reference))
  if (!response.ok) throw new Error(`小助手产物读取失败（HTTP ${response.status}）`)
  return response.blob()
}

export async function hydrateAssistantArtifacts<T>(value: T): Promise<T> {
  if (Array.isArray(value)) return Promise.all(value.map(hydrateAssistantArtifacts)) as Promise<T>
  if (!value || typeof value !== 'object') return value
  const record = value as Record<string, unknown>
  if (typeof record.artifactRef === 'string' && record.artifactRef.startsWith('assistant-artifact://')) {
    const blob = await readAssistantArtifact(record.artifactRef)
    return (record.mediaType === 'application/json' ? JSON.parse(await blob.text()) : await blob.text()) as T
  }
  return Object.fromEntries(await Promise.all(
    Object.entries(record).map(async ([key, item]) => [key, await hydrateAssistantArtifacts(item)]),
  )) as T
}
