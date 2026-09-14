import type {ImageAsset} from '../types'

/** Validate list responses before they become shared cache or selectable resources. */
export function isImageAssetList(value: unknown): value is ImageAsset[] {
  return Array.isArray(value) && value.every(asset => asset && typeof asset === 'object' &&
    ['id','name','originalName','uploadedAt','folder','extension'].every(key => typeof asset[key] === 'string') &&
    typeof asset.size === 'number' && Number.isFinite(asset.size) && asset.size >= 0 &&
    (asset.path === null || typeof asset.path === 'string'))
}
