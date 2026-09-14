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

/** Only a confirmed, well-formed write receipt may update local resources. */
export async function checkedImageWrite<T>(
  request: Promise<import('../api').ApiResponse<T>>,
  field?: 'asset' | 'path' | 'newPath' | 'deletedCount' | 'newFolder',
  requireSuccess = true,
): Promise<import('../api').ApiResponse<T>> {
  const result = await request
  if (!result.success) return result
  const value = result.data
  const invalid = () => ({ success: false, error: '图像资源操作未返回有效确认，请刷新资源后核对' })
  if (!value || typeof value !== 'object' || Array.isArray(value)) return invalid()
  const data = value as Record<string, unknown>
  if ((requireSuccess && data.success !== true) ||
      (data.success !== undefined && data.success !== true) || data.error) return invalid()
  if (field === 'asset') {
    const assets = readImageAssetList([data.asset])
    if (!assets) return invalid()
    return { ...result, data: { ...data, asset: assets[0] } as T }
  }
  if (field === 'deletedCount') {
    if (typeof data.deletedCount !== 'number' || !Number.isInteger(data.deletedCount) || data.deletedCount < 0) return invalid()
  } else if (field && typeof data[field] !== 'string') return invalid()
  return result
}
