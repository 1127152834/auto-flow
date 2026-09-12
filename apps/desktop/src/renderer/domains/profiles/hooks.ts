import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useApi } from '../../app/ApiProvider'
import type { ProfileDuplicate, ProfileList, ProfileTestBrowserList, ProfileWrite } from '../../shared/api/types'

export const profileKeys = {
  all: (instanceId: string) => [instanceId, 'profiles'] as const,
  testBrowsers: (instanceId: string) => [instanceId, 'profile-test-browsers'] as const,
  proxyOptions: (instanceId: string) => [instanceId, 'proxy-options'] as const,
  environmentOptions: (instanceId: string) => [instanceId, 'profile-environment-options'] as const,
}

export function useProfiles() {
  const { profiles, instanceId } = useApi()
  return useQuery({ queryKey: profileKeys.all(instanceId), queryFn: profiles.list })
}

export function useProxyOptions() {
  const { proxyOptions, instanceId } = useApi()
  return useQuery({ queryKey: profileKeys.proxyOptions(instanceId), queryFn: proxyOptions.list })
}

export function useProfileEnvironmentOptions(enabled: boolean) {
  const { profiles, instanceId } = useApi()
  return useQuery({
    queryKey: profileKeys.environmentOptions(instanceId),
    queryFn: profiles.environmentOptions,
    enabled,
  })
}

function useInvalidateProfiles() {
  const queryClient = useQueryClient()
  const { instanceId } = useApi()
  return () => queryClient.invalidateQueries({ queryKey: profileKeys.all(instanceId) })
}

export function useCreateProfile() {
  const { profiles } = useApi()
  const invalidate = useInvalidateProfiles()
  return useMutation({ mutationFn: profiles.create, retry: false, onSuccess: invalidate })
}

export function useUpdateProfile() {
  const { profiles } = useApi()
  const invalidate = useInvalidateProfiles()
  return useMutation({
    mutationFn: ({ profileId, body }: { profileId: string; body: ProfileWrite }) => profiles.update(profileId, body),
    retry: false,
    onSuccess: invalidate,
  })
}

export function useRemoveProfile() {
  const { profiles } = useApi()
  const invalidate = useInvalidateProfiles()
  return useMutation({ mutationFn: profiles.remove, retry: false, onSuccess: invalidate })
}

export function useDuplicateProfile() {
  const { profiles } = useApi()
  const invalidate = useInvalidateProfiles()
  return useMutation({
    mutationFn: ({ profileId, body }: { profileId: string; body: ProfileDuplicate }) => profiles.duplicate(profileId, body),
    retry: false,
    onSuccess: invalidate,
  })
}

export function useRegenerateProfile() {
  const { profiles, instanceId } = useApi()
  const queryClient = useQueryClient()
  const key = profileKeys.all(instanceId)
  return useMutation({
    mutationFn: profiles.regenerate,
    retry: false,
    onSuccess: async (updated) => {
      await queryClient.cancelQueries({ queryKey: key })
      queryClient.setQueryData<ProfileList>(key, (current) => current && ({
        ...current, items: current.items.map((profile) => profile.id === updated.id ? updated : profile),
      }))
      void queryClient.invalidateQueries({ queryKey: key })
    },
  })
}

export function useTestBrowsers(enabled: boolean) {
  const { profiles, instanceId } = useApi()
  return useQuery({
    queryKey: profileKeys.testBrowsers(instanceId), queryFn: profiles.testBrowsers,
    enabled, retry: false, refetchInterval: 1000, refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
  })
}

export function useOpenTestBrowser() {
  const { profiles, instanceId } = useApi()
  const queryClient = useQueryClient()
  const key = profileKeys.testBrowsers(instanceId)
  return useMutation({
    mutationFn: profiles.openTestBrowser, retry: false,
    onSuccess: async (session) => {
      await queryClient.cancelQueries({ queryKey: key })
      queryClient.setQueryData<ProfileTestBrowserList>(key, (current) => ({ items: [
        ...(current?.items ?? []).filter((item) => item.profileId !== session.profileId),
        { profileId: session.profileId, sessionId: session.sessionId, state: 'running' },
      ] }))
    },
    onSettled: () => { void queryClient.invalidateQueries({ queryKey: key }) },
  })
}

export function useCloseTestBrowser() {
  const { profiles, instanceId } = useApi()
  const queryClient = useQueryClient()
  const key = profileKeys.testBrowsers(instanceId)
  return useMutation({
    mutationFn: profiles.closeTestBrowser, retry: false,
    onSuccess: async (_, profileId) => {
      await queryClient.cancelQueries({ queryKey: key })
      queryClient.setQueryData<ProfileTestBrowserList>(key, (current) => ({
        items: (current?.items ?? []).filter((item) => item.profileId !== profileId),
      }))
    },
    onSettled: () => { void queryClient.invalidateQueries({ queryKey: key }) },
  })
}
