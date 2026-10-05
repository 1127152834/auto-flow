import type { StreamingApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'

type Schema = components['schemas']
export type Identity = Schema['IdentityView']
export type IdentityPage = Schema['IdentityPage']

const encode = encodeURIComponent

/** Remediation M4 R4-09: one identity per account (its own fingerprint, region and login environment). */
export function createIdentityApi(client: StreamingApiClient, projectId: string) {
  const base = `/api/v1/projects/${encode(projectId)}/identities`
  return {
    list: (signal?: AbortSignal) => client.request<IdentityPage>(base, { signal }),
    create: (name: string, key: string) => client.request<Identity>(base, { method: 'POST', headers: { 'Idempotency-Key': key }, body: { name } }),
    rename: (identityId: string, name: string) => client.request<Identity>(`${base}/${encode(identityId)}`, { method: 'PATCH', body: { name } }),
    regenerateSeed: (identityId: string) => client.request<Identity>(`${base}/${encode(identityId)}/regenerate-seed`, { method: 'POST', body: { confirmRegenerate: true } }),
    resetHealth: (identityId: string) => client.request<Identity>(`${base}/${encode(identityId)}/reset-health`, { method: 'POST' }),
    remove: (identityId: string) => client.request<void>(`${base}/${encode(identityId)}`, { method: 'DELETE' }),
  }
}
