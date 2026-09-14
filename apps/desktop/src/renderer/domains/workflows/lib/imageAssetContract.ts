import type {ImageAsset} from '../types'

/** Validate list responses before they become shared cache or selectable resources. */
function isImageAssetList(value: unknown): value is ImageAsset[] {
  return Array.isArray(value) && value.every(asset => asset && typeof asset === 'object' &&
    ['id','name','originalName','uploadedAt','folder','extension'].every(key => typeof asset[key] === 'string') &&
    typeof asset.size === 'number' && Number.isSafeInteger(asset.size) && asset.size >= 0 &&
    ['id','name','originalName'].every(key => asset[key].length > 0) &&
    (asset.path === null || typeof asset.path === 'string'))
}

/** Match the DTO default without discarding source-specific metadata. */
export function readImageAssetList(value: unknown): ImageAsset[] | null {
  if (!Array.isArray(value)) return null
  const normalized = value.map(asset => asset && typeof asset === 'object' && !Array.isArray(asset)
    ? {path:null,...asset} : asset)
  return isImageAssetList(normalized) ? normalized : null
}
