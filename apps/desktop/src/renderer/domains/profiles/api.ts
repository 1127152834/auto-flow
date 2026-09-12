import type { ApiClient } from '../../shared/api/client'
import type {
  ProfileDuplicate,
  ProfileEnvironmentOptions,
  ProfileList,
  ProfileRead,
  ProfileWrite,
  ProxyOptionsRead,
} from '../../shared/api/types'

const apiPath = (path: string) => `/api/v1${path}`
const segment = (value: string) => encodeURIComponent(value)

export function createProfilesApi(client: ApiClient) {
  return {
    list: () => client.request<ProfileList>(apiPath('/profiles')),
    environmentOptions: () => client.request<ProfileEnvironmentOptions>(apiPath('/profiles/environment-options')),
    create: (body: ProfileWrite) => client.request<ProfileRead>(apiPath('/profiles'), {
      method: 'POST', body,
    }),
    update: (profileId: string, body: ProfileWrite) => client.request<ProfileRead>(
      apiPath(`/profiles/${segment(profileId)}`),
      { method: 'PUT', body },
    ),
    remove: (profileId: string) => client.request<void>(
      apiPath(`/profiles/${segment(profileId)}`),
      { method: 'DELETE' },
    ),
    duplicate: (profileId: string, body: ProfileDuplicate) => client.request<ProfileRead>(
      apiPath(`/profiles/${segment(profileId)}/duplicate`),
      { method: 'POST', body },
    ),
    regenerate: (profileId: string) => client.request<ProfileRead>(
      apiPath(`/profiles/${segment(profileId)}/regenerate-fingerprint`),
      { method: 'POST' },
    ),
  }
}

export function createProxyOptionsApi(client: ApiClient) {
  return {
    list: () => client.request<ProxyOptionsRead>(apiPath('/proxy-options')),
  }
}

export type ProfilesApi = ReturnType<typeof createProfilesApi>
export type ProxyOptionsApi = ReturnType<typeof createProxyOptionsApi>
