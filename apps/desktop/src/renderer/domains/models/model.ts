import type { components } from '../../shared/api/generated'

type Schemas = components['schemas']

export type ModelProviderRead = Schemas['ModelProviderRead']
export type ModelProviderListRead = Schemas['ModelProviderListRead']
export type ModelProviderCreateInput = Schemas['ModelProviderCreateInput']
export type ModelProviderConnectInput = Schemas['ModelProviderConnectInput']
export type ModelProviderMetadataUpdateInput = Schemas['ModelProviderMetadataUpdateInput']
export type ModelProviderConnectionUpdateInput = Schemas['ModelProviderConnectionUpdateInput']
export type ModelDiscoveryRead = Schemas['ModelDiscoveryRead']
export type ModelInput = Schemas['ModelInput']
export type ModelRead = Schemas['ModelRead']
export type ModelTestInput = Schemas['ModelTestInput']
export type ModelTestRead = Schemas['ModelTestRead']
export type ModelOptionListRead = Schemas['ModelOptionListRead']
export type ModelProvider = ModelProviderRead
export type AiModel = ModelRead
export type ModelDiscoveryResult = ModelDiscoveryRead
export type ModelTestResult = ModelTestRead

export type ProviderDraft = ModelProviderCreateInput & {
  apiKey: string
  apiKeyTouched: boolean
}

export const modelKeys = {
  providers: (instanceId: string) => ['model-providers', instanceId] as const,
  discovery: (instanceId: string, providerId: string) =>
    ['model-provider-discovery', instanceId, providerId] as const,
  options: (instanceId: string) => ['model-options', instanceId] as const,
}
