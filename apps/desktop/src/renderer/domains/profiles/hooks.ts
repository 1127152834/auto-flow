import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useApi } from '../../app/ApiProvider'
import type { ProfileDuplicate, ProfileWrite } from '../../shared/api/types'

export const profileKeys = {
  all: (instanceId: string) => [instanceId, 'profiles'] as const,
  proxyOptions: (instanceId: string) => [instanceId, 'proxy-options'] as const,
}

export function useProfiles() {
  const { profiles, instanceId } = useApi()
  return useQuery({ queryKey: profileKeys.all(instanceId), queryFn: profiles.list })
}

export function useProxyOptions() {
  const { proxyOptions, instanceId } = useApi()
  return useQuery({ queryKey: profileKeys.proxyOptions(instanceId), queryFn: proxyOptions.list })
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
  const { profiles } = useApi()
  const invalidate = useInvalidateProfiles()
  return useMutation({ mutationFn: profiles.regenerate, retry: false, onSuccess: invalidate })
}
