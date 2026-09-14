// Source: WebRPA@5ccb900e, components/ui/image-path-input.tsx; see SOURCE.md for license and adaptation boundaries.
import { useState, useEffect, useCallback, useRef } from 'react'
import { FolderOpen, ChevronRight, Folder, Image } from 'lucide-react'
import { cn } from '../../lib/utils'
import { Button } from './button'
import { systemApi, imageAssetApi } from '../../api'
import { readImageAssetList } from '../../lib/imageAssetContract'
import { getStudioTransportRevision } from '../../api/transport'
import { ImageAssetPreview } from './image-asset-preview'
import type { ImageAsset } from '../../types/index'

interface ImagePathInputProps {
  value: string
  onChange: (value: string) => void
  className?: string
  placeholder?: string
}

export function ImagePathInput({ value, onChange, className, placeholder = '输入图片路径或从资源选择' }: ImagePathInputProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [assets, setAssets] = useState<ImageAsset[]>([])
  const [folders, setFolders] = useState<string[]>([])
  const [currentPath, setCurrentPath] = useState<string>('')
  const [breadcrumbs, setBreadcrumbs] = useState<string[]>([])
  const containerRef = useRef<HTMLDivElement>(null)

  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [fileError, setFileError] = useState('')
  const [selecting, setSelecting] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const fileRequest = useRef(0)
  const filePending = useRef(false)
  const mounted = useRef(false)

  useEffect(() => {
    mounted.current = true
    const invalidate = () => {
      fileRequest.current++
      setFileError('')
      setAssets([])
      setFolders([])
      setAttempt(current => current + 1)
    }
    window.addEventListener('studio:transport-changed', invalidate)
    return () => { window.removeEventListener('studio:transport-changed', invalidate); fileRequest.current++; mounted.current = false }
  }, [])
  useEffect(() => {
    fileRequest.current++
    setFileError('')
  }, [value])

  useEffect(() => {
    if (!isOpen) return
    let disposed = false
    const revision = getStudioTransportRevision()
    const current = () => !disposed && revision === getStudioTransportRevision()
    setLoading(true)
    setLoadError('')
    void (async () => {
      try {
        const [assetsResult, foldersResult] = await Promise.all([imageAssetApi.list(), imageAssetApi.listFolders()])
        if (!current()) return
        if (!assetsResult.success || !foldersResult.success) throw new Error(assetsResult.error || foldersResult.error || '资源服务未确认加载')
        const loadedAssets = readImageAssetList(assetsResult.data)
        if (!loadedAssets ||
          !Array.isArray(foldersResult.data) || !foldersResult.data.every(folder => typeof folder === 'string')) {
          throw new Error('图像资源列表格式错误')
        }
        setAssets(loadedAssets)
        setFolders(foldersResult.data)
      } catch (error) {
        if (current()) setLoadError(error instanceof Error ? error.message : '图像资源加载失败')
      } finally { if (current()) setLoading(false) }
    })()
    return () => { disposed = true }
  }, [isOpen, attempt])

  // 获取当前路径下的项目
  const getCurrentItems = useCallback(() => {
    const subfolders = folders.filter(f => {
      if (!currentPath) {
        return !f.includes('/')
      } else {
        const prefix = currentPath + '/'
        return f.startsWith(prefix) && !f.substring(prefix.length).includes('/')
      }
    })
    const files = assets.filter(a => a.folder === currentPath)
    return { subfolders, files }
  }, [folders, assets, currentPath])

  const { subfolders, files } = getCurrentItems()

  // 更新面包屑
  useEffect(() => {
    setBreadcrumbs(currentPath ? currentPath.split('/') : [])
  }, [currentPath])

  // 导航到指定路径
  const navigateTo = (path: string) => {
    setCurrentPath(path)
  }

  // 选择文件
  const selectFile = (asset: ImageAsset) => {
    const assetWithPath = asset as ImageAsset & { path?: string }
    onChange(assetWithPath.path || asset.originalName)
    setIsOpen(false)
  }

  // 文件对话框只回填发起时的字段；取消及迟到响应不改草稿。
  const handleFileSelect = async () => {
    if (filePending.current) return
    filePending.current = true
    const request = ++fileRequest.current
    const revision = getStudioTransportRevision()
    const current = () => request === fileRequest.current && revision === getStudioTransportRevision()
    setSelecting(true)
    setFileError('')
    try {
      const result = await systemApi.selectFile('选择图片', undefined, [
        ['图片文件', '*.png;*.jpg;*.jpeg;*.gif;*.bmp;*.webp'],
        ['所有文件', '*.*']
      ])
      if (!current()) return
      if (!result.success) throw new Error(result.error || '选择图片失败')
      if (typeof result.data?.success !== 'boolean') throw new Error('图片选择响应格式错误')
      if (result.data.success) {
        if (result.data.path === null || result.data.path === '') return
        if (typeof result.data.path !== 'string') throw new Error('图片选择响应缺少有效路径')
        onChange(result.data.path)
      } else if (typeof result.data.error === 'string' && result.data.error) throw new Error(result.data.error)
    } catch (error) {
      if (current()) setFileError(error instanceof Error ? error.message : '选择图片失败')
    } finally {
      filePending.current = false
      if (mounted.current) setSelecting(false)
    }
  }

  // 点击外部关闭下拉框
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])


  return (
    <div ref={containerRef} className={cn('relative', className)}>
      {/* 输入框和按钮 */}
      <div className="flex gap-2">
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onFocus={() => {
            // 已填写路径且资源库为空时，不再自动弹出空下拉（避免"一直提示暂无图像"的骚扰）；
            // 资源库有图或尚未填写时才自动展开，方便快速选取。
            if (!value || assets.length > 0) setIsOpen(true)
          }}
          placeholder={placeholder}
          className={cn(
            'flex-1 px-3 py-2 text-sm',
            'bg-white border border-gray-300 rounded-md',
            'hover:border-gray-400 focus:outline-none focus:ring-2 focus:ring-green-500',
            'transition-colors duration-150',
            'placeholder:text-gray-400'
          )}
        />
        <Button
          type="button"
          variant="tonal-warning"
          size="icon"
          aria-label="从电脑选择图片"
          disabled={selecting}
          onClick={handleFileSelect}
          className="shrink-0"
        >
          <FolderOpen className="w-4 h-4" />
        </Button>
        <Button type="button" variant="outline" size="icon" aria-label="选择图像资源" onClick={() => setIsOpen(open => !open)}><Image className="w-4 h-4" /></Button>
      </div>

      {fileError && <p role="alert" className="text-xs text-red-600">{fileError}</p>}

      {/* 下拉面板 */}
      {isOpen && (
        <div className="absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-xl max-h-80 flex flex-col animate-in fade-in zoom-in-95 duration-150">
          {/* 面包屑导航 */}
          {currentPath && (
            <div className="flex items-center gap-1 px-3 py-2 bg-gray-50 border-b text-xs overflow-x-auto">
              <button
                className="flex items-center gap-1 px-2 py-1 hover:bg-white rounded transition-colors whitespace-nowrap"
                onClick={() => navigateTo('')}
              >
                <Folder className="w-3 h-3 text-green-600" />
                <span>根目录</span>
              </button>
              {breadcrumbs.map((crumb, index) => {
                const path = breadcrumbs.slice(0, index + 1).join('/')
                return (
                  <div key={path} className="flex items-center gap-1">
                    <ChevronRight className="w-3 h-3 text-gray-400" />
                    <button
                      className="px-2 py-1 hover:bg-white rounded transition-colors whitespace-nowrap"
                      onClick={() => navigateTo(path)}
                    >
                      {crumb}
                    </button>
                  </div>
                )
              })}
            </div>
          )}

          {/* 文件和文件夹列表 */}
          <div className="overflow-y-auto flex-1 p-2">
            {loading ? <p role="status" className="p-3 text-sm">正在加载图像资源…</p> : loadError ? (
              <div role="alert" className="p-3 text-sm"><p>{loadError}</p><Button type="button" onClick={() => setAttempt(current => current + 1)}>重试加载图像资源</Button></div>
            ) : subfolders.length === 0 && files.length === 0 ? (
              <div className="text-center py-8 text-gray-400 text-sm">
                {assets.length === 0 ? (
                  <>
                    <Image className="w-12 h-12 mx-auto mb-2 opacity-30" />
                    <p>图像资源库为空（可选）</p>
                    <p className="text-xs mt-1 px-3 leading-relaxed">可直接在上方输入框填写图片路径，或点右侧按钮从电脑选择；也可到「图像」面板上传常用图片，方便下次快速选取。</p>
                  </>
                ) : (
                  <>
                    <Folder className="w-12 h-12 mx-auto mb-2 opacity-30" />
                    <p>此文件夹为空</p>
                  </>
                )}
              </div>
            ) : (
              <div className="space-y-1">
                {/* 文件夹 */}
                {subfolders.map(folderPath => {
                  const folderName = folderPath.split('/').pop() || folderPath
                  const folderAssets = assets.filter(a => a.folder === folderPath || a.folder.startsWith(folderPath + '/'))
                  return (
                    <button
                      key={folderPath}
                      type="button"
                      className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-green-50 rounded-md transition-colors text-left group"
                      onClick={() => navigateTo(folderPath)}
                    >
                      <Folder className="w-4 h-4 text-green-600 flex-shrink-0" />
                      <span className="flex-1 truncate font-medium text-gray-700 group-hover:text-green-700">
                        {folderName}
                      </span>
                      {folderAssets.length > 0 && (
                        <span className="text-xs text-gray-400 group-hover:text-green-600">
                          {folderAssets.length}
                        </span>
                      )}
                      <ChevronRight className="w-4 h-4 text-gray-400 group-hover:text-green-600 flex-shrink-0" />
                    </button>
                  )
                })}

                {/* 文件 */}
                {files.map(asset => {
                  const assetWithPath = asset as ImageAsset & { path?: string }
                  const assetPath = assetWithPath.path || asset.originalName
                  return (
                    <button
                      key={asset.id}
                      type="button"
                      className={cn(
                        'w-full flex items-center gap-2 px-3 py-2 text-sm rounded-md transition-colors text-left',
                        value === assetPath
                          ? 'bg-green-100 text-green-700'
                          : 'hover:bg-gray-50 text-gray-700'
                      )}
                      onClick={() => selectFile(asset)}
                    >
                      <div className="w-8 h-8 rounded bg-gray-100 flex items-center justify-center overflow-hidden flex-shrink-0">
                        <ImageAssetPreview asset={asset} className="w-full h-full object-cover" />
                      </div>
                      <span className="flex-1 truncate">
                        {asset.originalName}
                      </span>
                      {value === assetPath && (
                        <div className="w-2 h-2 bg-green-600 rounded-full flex-shrink-0" />
                      )}
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
