// Source: WebRPA@5ccb900e, components/workflow/ImageAssetsPanel.tsx; see SOURCE.md for license and adaptation boundaries.
import { ImageAssetPreview } from './controls/image-asset-preview'
import { studioFetch, getStudioTransportRevision } from '../api/transport'
import { readImageAssetList } from '../lib/imageAssetContract'
import { useState, useRef, useCallback, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { useWorkflowStore } from '../editor-store'
import { imageAssetApi } from '../api'
import { useConfirm } from './controls/confirm-dialog'
import { Button } from './controls/button'
import { Input } from './controls/input'
import { ScrollArea } from './controls/scroll-area'
import {
  Upload,
  Folder,
  Image as ImageIcon,
  Trash2,
  Edit2,
  Plus,
  ChevronRight,
} from 'lucide-react'
import { cn } from '../lib/utils'
import { getBackendBaseUrl } from '../api/config'
import type { ImageAsset } from '../types/index'

export function ImageAssetsPanel() {
  const { imageAssets, setImageAssets, addImageAsset, deleteImageAsset } = useWorkflowStore()
  const { confirm, alert, ConfirmDialog } = useConfirm()
  
  const [folders, setFolders] = useState<string[]>([])
  const [currentPath, setCurrentPath] = useState<string>('')  // 当前所在路径
  const [isCreatingFolder, setIsCreatingFolder] = useState(false)
  const [newFolderName, setNewFolderName] = useState('')
  const [editingFolder, setEditingFolder] = useState<string | null>(null)
  const [editFolderName, setEditFolderName] = useState('')
  const [editingAsset, setEditingAsset] = useState<string | null>(null)
  const [editAssetName, setEditAssetName] = useState('')
  const [dragOverFolder, setDragOverFolder] = useState<string | null>(null)
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; folder: string; isFile?: boolean; assetId?: string; isBlank?: boolean } | null>(null)
  const [previewAsset, setPreviewAsset] = useState<ImageAsset | null>(null)
  
  const fileInputRef = useRef<HTMLInputElement>(null)

  // 暴露上传函数给父组件使用
  useEffect(() => {
    // 将上传函数挂载到全局，供LogPanel调用
    (window as any).__imageUploadTrigger = () => {
      fileInputRef.current?.click()
    }
    return () => {
      delete (window as any).__imageUploadTrigger
    }
  }, [])

  const [loadError, setLoadError] = useState('')
  const [loading, setLoading] = useState(true)
  const loadSequence = useRef(0)
  const mounted = useRef(true)
  const reloadAssets = useCallback(async () => {
    if (!mounted.current) return false
    const sequence = ++loadSequence.current
    const revision = getStudioTransportRevision()
    const previousAssets = useWorkflowStore.getState().imageAssets
    const current = () => mounted.current && sequence === loadSequence.current && revision === getStudioTransportRevision()
    setLoading(true)
    setLoadError('')
    try {
      const [assetsResult, foldersResult] = await Promise.all([imageAssetApi.list(), imageAssetApi.listFolders()])
      if (!current()) return false
      const assets = readImageAssetList(assetsResult.data)
      if (!assetsResult.success || !foldersResult.success || !assets ||
          !Array.isArray(foldersResult.data) || !foldersResult.data.every(folder => typeof folder === 'string')) {
        throw new Error(assetsResult.error || foldersResult.error || '图像资源或文件夹响应格式错误')
      }
      // 初始读取不得覆盖期间完成的上传、删除或其他消费者刷新。
      setFolders(foldersResult.data)
      if (useWorkflowStore.getState().imageAssets === previousAssets) setImageAssets(assets)
      return true
    } catch (error) {
      if (current()) setLoadError(`加载图像资源失败：${error instanceof Error ? error.message : String(error)}`)
      return false
    } finally {
      if (current()) setLoading(false)
    }
  }, [setImageAssets])

  useEffect(() => {
    mounted.current = true
    const refresh = () => { void reloadAssets() }
    refresh()
    window.addEventListener('refresh:image-assets', refresh)
    window.addEventListener('studio:transport-changed', refresh)
    return () => {
      mounted.current = false
      loadSequence.current++
      window.removeEventListener('refresh:image-assets', refresh)
      window.removeEventListener('studio:transport-changed', refresh)
    }
  }, [reloadAssets])

  // 监听全局截图快捷键事件
  useEffect(() => {
    const handleScreenshot = async () => {
      try {
        // 调用系统截图API（使用Python的PIL库）
        const response = await studioFetch(`${getBackendBaseUrl()}/api/system/screenshot`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ folder: currentPath || undefined })
        })
        
        if (!response.ok) {
          const error = await response.json().catch(() => ({ detail: '截图失败' }))
          await alert(error.detail || '截图失败')
          return
        }
        
        const result = await response.json()
        if (result.asset) {
          // 添加到图像资源列表
          addImageAsset(result.asset)
          // 显示成功提示（简短的toast提示）
          const toast = document.createElement('div')
          toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
            z-index: 10000;
            font-size: 14px;
            font-weight: 500;
            animation: slideInRight 0.3s ease-out;
          `
          toast.textContent = `截图已保存: ${result.asset.originalName}`
          document.body.appendChild(toast)
          
          setTimeout(() => {
            toast.style.animation = 'slideOutRight 0.3s ease-out'
            setTimeout(() => toast.remove(), 300)
          }, 2000)
        }
      } catch (error) {
        console.error('截图失败:', error)
        await alert(`截图失败: ${error}`)
      }
    }
    
    window.addEventListener('hotkey:screenshot', handleScreenshot)
    return () => window.removeEventListener('hotkey:screenshot', handleScreenshot)
  }, [currentPath, addImageAsset, alert])

  // 获取当前路径下的子文件夹和文件
  const getCurrentItems = useCallback(() => {
    // 获取当前路径下的直接子文件夹
    const subfolders = folders.filter(f => {
      if (!currentPath) {
        // 根目录：只显示一级文件夹
        return !f.includes('/')
      } else {
        // 子目录：显示直接子文件夹
        const prefix = currentPath + '/'
        return f.startsWith(prefix) && !f.substring(prefix.length).includes('/')
      }
    })

    // 获取当前路径下的文件
    const files = imageAssets.filter(a => a.folder === currentPath)

    return { subfolders, files }
  }, [folders, imageAssets, currentPath])

  const { subfolders, files } = getCurrentItems()

  // 面包屑导航
  const breadcrumbs = currentPath ? currentPath.split('/') : []

  // 导航到指定路径
  const navigateTo = (path: string) => {
    setCurrentPath(path)
  }

  // 双击进入文件夹
  const handleFolderDoubleClick = (folderPath: string) => {
    setCurrentPath(folderPath)
  }

  // 创建文件夹
  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) return
    
    // 在当前路径下创建文件夹
    const result = await imageAssetApi.createFolder(newFolderName.trim(), currentPath || undefined)
    if (result.error) {
      await alert(result.error)
    } else {
      await reloadAssets()
      setIsCreatingFolder(false)
      setNewFolderName('')
    }
  }

  // 重命名文件夹
  const handleRenameFolder = async (folderPath: string) => {
    if (!editFolderName.trim() || editFolderName === folderPath.split('/').pop()) {
      setEditingFolder(null)
      return
    }
    
    const result = await imageAssetApi.renameFolder(folderPath, editFolderName.trim())
    if (result.error) {
      await alert(result.error)
    } else {
      await reloadAssets()
    }
    setEditingFolder(null)
  }

  // 重命名文件
  const handleRenameAsset = async (assetId: string) => {
    if (!editAssetName.trim()) {
      setEditingAsset(null)
      return
    }
    
    const result = await imageAssetApi.rename(assetId, editAssetName.trim())
    if (result.error) {
      await alert(result.error)
    } else if (result.data?.asset) {
      // 更新本地状态
      await reloadAssets()
    }
    setEditingAsset(null)
  }

  // 删除文件夹
  const handleDeleteFolder = async (folderPath: string) => {
    const folderName = folderPath.split('/').pop() || folderPath
    const confirmed = await confirm(
      `确定要删除文件夹"${folderName}"及其所有内容吗？`,
      { type: 'warning', title: '删除文件夹' }
    )
    if (!confirmed) return
    
    const result = await imageAssetApi.deleteFolder(folderPath)
    if (result.error) {
      await alert(result.error)
    } else {
      await reloadAssets()
    }
  }

  // 批量上传处理
  const handleBatchFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || [])
    if (files.length === 0) return

    const allowedExts = ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'svg', 'ico']
    const imageFiles = files.filter(f => {
      const ext = f.name.split('.').pop()?.toLowerCase()
      return ext && allowedExts.includes(ext)
    })
    
    if (imageFiles.length === 0) {
      await alert('没有找到图像文件')
      return
    }

    try {
      // 逐个上传文件
      const results = await Promise.all(
        imageFiles.map(file => imageAssetApi.upload(file, currentPath || undefined))
      )
      
      let successCount = 0
      let errorCount = 0
      
      results.forEach(result => {
        if (result.data?.asset) {
          addImageAsset(result.data.asset)
          successCount++
        } else {
          errorCount++
        }
      })
      
      if (errorCount > 0) {
        await alert(`上传完成：成功 ${successCount} 个，失败 ${errorCount} 个`)
      }
    } catch (error) {
      await alert(`批量上传失败: ${error}`)
    } finally {
      event.target.value = ''
    }
  }

  // 删除当前目录所有文件
  const handleDeleteAllFiles = async () => {
    const currentFiles = imageAssets.filter(a => a.folder === currentPath)
    if (currentFiles.length === 0) {
      await alert('当前目录没有文件')
      return
    }

    const confirmed = await confirm(
      `确定要删除当前目录中的所有 ${currentFiles.length} 个文件吗？此操作不可恢复！`,
      { type: 'warning', title: '删除所有文件' }
    )
    if (!confirmed) return

    let successCount = 0
    let errorCount = 0

    for (const asset of currentFiles) {
      const result = await imageAssetApi.delete(asset.id)
      if (result.error) {
        errorCount++
      } else {
        deleteImageAsset(asset.id)
        successCount++
      }
    }

    if (errorCount > 0) {
      await alert(`删除完成：成功 ${successCount} 个，失败 ${errorCount} 个`)
    }
  }

  // 删除文件
  const handleDeleteAsset = async (id: string) => {
    const confirmed = await confirm('确定要删除此图像吗？', { type: 'warning', title: '删除图像' })
    if (!confirmed) return
    
    const result = await imageAssetApi.delete(id)
    if (!result.error) {
      deleteImageAsset(id)
    }
  }

  // 拖拽处理
  const handleDragStart = (e: React.DragEvent, asset: ImageAsset) => {
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('assetId', asset.id)
    e.dataTransfer.setData('assetType', 'image')
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    e.dataTransfer.dropEffect = 'move'
    setDragOverFolder(currentPath)
  }

  const handleDragLeave = () => {
    setDragOverFolder(null)
  }

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragOverFolder(null)

    // 处理文件拖拽导入
    if (e.dataTransfer.files.length > 0) {
      const allowedExts = ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'svg', 'ico']
      const files = Array.from(e.dataTransfer.files).filter(f => {
        const ext = f.name.split('.').pop()?.toLowerCase()
        return ext && allowedExts.includes(ext)
      })
      
      if (files.length === 0) return

      try {
        // 逐个上传文件
        const results = await Promise.all(
          files.map(file => imageAssetApi.upload(file, currentPath || undefined))
        )
        
        results.forEach(result => {
          if (result.data?.asset) {
            addImageAsset(result.data.asset)
          }
        })
      } catch (error) {
        await alert(`导入失败: ${error}`)
      }
      return
    }

    // 处理资源移动
    const assetId = e.dataTransfer.getData('assetId')
    const assetType = e.dataTransfer.getData('assetType')
    
    if (assetId && assetType === 'image') {
      const result = await imageAssetApi.moveAsset(assetId, currentPath || undefined)
      if (result.error) {
        await alert(result.error)
      } else {
        await reloadAssets()
      }
    }
  }

  // 右键菜单
  const handleContextMenu = (e: React.MouseEvent, folder?: string, assetId?: string) => {
    e.preventDefault()
    const isBlank = folder === undefined && assetId === undefined
    setContextMenu({ 
      x: e.clientX, 
      y: e.clientY, 
      folder: assetId ? '' : (folder !== undefined ? folder : currentPath),
      isFile: !!assetId,
      assetId,
      isBlank
    })
  }

  useEffect(() => {
    const handleClick = () => setContextMenu(null)
    document.addEventListener('click', handleClick)
    return () => document.removeEventListener('click', handleClick)
  }, [])

  // 渲染文件夹卡片（更小尺寸）
  const renderFolderCard = (folderPath: string) => {
    const folderName = folderPath.split('/').pop() || folderPath
    const isEditing = editingFolder === folderPath
    const folderAssets = imageAssets.filter(a => a.folder === folderPath)
    const isDragOver = dragOverFolder === folderPath

    return (
      <div
        key={folderPath}
        className={cn(
          'relative group cursor-pointer transition-all duration-200',
          'bg-white rounded-lg border p-2',
          'hover:shadow-md hover:scale-102 hover:-translate-y-0.5',
          isDragOver ? 'border-blue-400 bg-blue-50 ring-2 ring-blue-200' : 'border-purple-200 hover:border-purple-300'
        )}
        onClick={() => handleFolderDoubleClick(folderPath)}
        onContextMenu={(e) => {
          e.stopPropagation()
          handleContextMenu(e, folderPath)
        }}
        onDragOver={(e) => {
          e.preventDefault()
          e.stopPropagation()
          setDragOverFolder(folderPath)
        }}
        onDragLeave={(e) => {
          e.preventDefault()
          e.stopPropagation()
          setDragOverFolder(null)
        }}
        onDrop={async (e) => {
          e.preventDefault()
          e.stopPropagation()
          setDragOverFolder(null)

          const assetId = e.dataTransfer.getData('assetId')
          const assetType = e.dataTransfer.getData('assetType')
          
          if (assetId && assetType === 'image') {
            const result = await imageAssetApi.moveAsset(assetId, folderPath)
            if (result.error) {
              await alert(result.error)
            } else {
              await reloadAssets()
            }
          }
        }}
      >
        <div className="flex flex-col items-center gap-1">
          <div className="relative">
            <Folder className="w-10 h-10 text-purple-500" />
            {folderAssets.length > 0 && (
              <div className="absolute -top-1 -right-1 bg-purple-500 text-white text-xs font-bold rounded-full w-4 h-4 flex items-center justify-center">
                {folderAssets.length}
              </div>
            )}
          </div>
          
          {isEditing ? (
            <Input
              value={editFolderName}
              onChange={(e) => setEditFolderName(e.target.value)}
              className="h-6 text-xs text-center bg-white border-purple-300"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleRenameFolder(folderPath)
                if (e.key === 'Escape') setEditingFolder(null)
              }}
              onBlur={() => handleRenameFolder(folderPath)}
              onClick={(e) => e.stopPropagation()}
            />
          ) : (
            <p className="text-xs font-medium text-gray-700 text-center truncate w-full px-1" title={folderName}>
              {folderName}
            </p>
          )}
        </div>
      </div>
    )
  }

  // 渲染图片卡片（小预览图，与 Excel 卡片大小一致）
  const renderImageCard = (asset: ImageAsset) => {
    const isEditing = editingAsset === asset.id

    return (
      <div
        key={asset.id}
        className={cn(
          'relative group cursor-pointer transition-all duration-200 bg-white rounded-lg border p-2 hover:shadow-md hover:scale-102 hover:-translate-y-0.5',
          'border-purple-200 hover:border-purple-300'
        )}
        draggable
        onDragStart={(e) => handleDragStart(e, asset)}
        onClick={() => !isEditing && setPreviewAsset(asset)}
        onContextMenu={(e) => {
          e.stopPropagation()
          handleContextMenu(e, undefined, asset.id)
        }}
      >
        <div className="flex flex-col items-center gap-1">
          {/* 小预览图 */}
          <div className="bg-[hsl(var(--card))] w-10 h-10 rounded flex items-center justify-center overflow-hidden">
            <ImageAssetPreview asset={asset} className="w-full h-full object-cover" />
          </div>
          
          {isEditing ? (
            <Input
              value={editAssetName}
              onChange={(e) => setEditAssetName(e.target.value)}
              className="h-6 text-xs text-center bg-white border-purple-300"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleRenameAsset(asset.id)
                if (e.key === 'Escape') setEditingAsset(null)
              }}
              onBlur={() => handleRenameAsset(asset.id)}
              onClick={(e) => e.stopPropagation()}
            />
          ) : (
            <p className="text-xs font-medium text-gray-700 text-center truncate w-full px-1" title={asset.originalName}>
              {asset.originalName}
            </p>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="bg-[hsl(var(--card))] h-full flex flex-col relative">
      {loading && <div role="status" className="px-3 py-2 text-sm">正在加载图像资源…</div>}
      {loadError && <div role="alert" className="px-3 py-2 text-sm text-red-700">{loadError} <button onClick={() => void reloadAssets()}>重试加载图像资源</button></div>}
      {/* 面包屑导航 */}
      {currentPath && (
        <div
          className="flex items-center gap-1 px-3 py-1.5 border-b border-[hsl(var(--border))] text-[11px]"
          style={{ background: 'linear-gradient(180deg, hsl(var(--warning-50) / 0.4), hsl(var(--card)))' }}
        >
          <Button
            variant="tonal-warning"
            size="xs"
            onClick={() => navigateTo('')}
          >
            <Folder className="w-3 h-3" />
            根目录
          </Button>
          {breadcrumbs.map((crumb, index) => {
            const path = breadcrumbs.slice(0, index + 1).join('/')
            const isLast = index === breadcrumbs.length - 1
            return (
              <div key={path} className="flex items-center gap-1">
                <ChevronRight className="w-3 h-3 text-[hsl(var(--muted-foreground))]" />
                <button
                  className={`h-6 px-2 rounded-[5px] text-[11px] font-medium transition-colors duration-150 active:scale-95 ${
                    isLast
                      ? 'bg-[hsl(var(--warning-100))] text-[hsl(var(--warning-700))]'
                      : 'text-[hsl(var(--slate-700))] hover:bg-[hsl(var(--warning-50))] hover:text-[hsl(var(--warning-700))]'
                  }`}
                  onClick={() => navigateTo(path)}
                >
                  {crumb}
                </button>
              </div>
            )
          })}
        </div>
      )}

      {/* 文件列表 */}
      <ScrollArea className="flex-1">
        <div
          className={cn(
            'p-3 min-h-full transition-all duration-200',
            (imageAssets.length === 0 && folders.length === 0) || (subfolders.length === 0 && files.length === 0)
              ? 'h-full flex items-center justify-center'
              : '',
            dragOverFolder === currentPath && 'bg-[hsl(var(--brand-50))] ring-2 ring-dashed ring-[hsl(var(--brand-500))] ring-inset'
          )}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onContextMenu={(e) => handleContextMenu(e)}
        >
          {(loading || loadError) && subfolders.length === 0 && files.length === 0 ? null : imageAssets.length === 0 && folders.length === 0 ? (
            <div className="empty-state !py-0">
              <div className="empty-state-icon" style={{ background: 'linear-gradient(135deg, hsl(var(--warning-50)), hsl(var(--warning-100)))', color: 'hsl(var(--warning-500))', borderColor: 'hsl(var(--warning-500) / 0.2)' }}>
                <ImageIcon className="w-7 h-7" strokeWidth={1.6} />
              </div>
              <div className="empty-state-title">暂无图像文件</div>
              <div className="empty-state-desc">点击上方按钮上传，或将图片直接拖拽到此处</div>
            </div>
          ) : subfolders.length === 0 && files.length === 0 ? (
            <div className="empty-state !py-0">
              <div className="empty-state-icon" style={{ background: 'linear-gradient(135deg, hsl(var(--warning-50)), hsl(var(--warning-100)))', color: 'hsl(var(--warning-500))', borderColor: 'hsl(var(--warning-500) / 0.2)' }}>
                <Folder className="w-7 h-7" strokeWidth={1.6} />
              </div>
              <div className="empty-state-title">此文件夹为空</div>
              <div className="empty-state-desc">点击上传或将图片拖拽到此处</div>
            </div>
          ) : (
            <div
              className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 lg:grid-cols-10 xl:grid-cols-12 gap-2.5"
            >
              {subfolders.map(folder => renderFolderCard(folder))}
              {files.map(asset => renderImageCard(asset))}
            </div>
          )}
        </div>
      </ScrollArea>

      {/* 隐藏的文件输入 */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        multiple
        onChange={handleBatchFileUpload}
        className="hidden"
      />

      {/* 新建文件夹对话框 */}
      {isCreatingFolder && createPortal(
        <div className="fixed inset-0 bg-[hsl(217_45%_15%_/_0.55)] backdrop-blur-[3px] flex items-center justify-center animate-fade-in" style={{ zIndex: 2147483646 }} onClick={() => setIsCreatingFolder(false)}>
          <div className="modern-dialog w-96 animate-scale-in-bounce" onClick={(e) => e.stopPropagation()}>
            <div className="modern-dialog-header">
              <div className="modern-dialog-header-icon modern-dialog-header-icon-warning">
                <Folder className="w-5 h-5" strokeWidth={2.2} />
              </div>
              <div className="flex-1">
                <h3 className="modern-dialog-title">新建文件夹</h3>
                <div className="modern-dialog-subtitle">为图像分类创建新位置</div>
              </div>
            </div>
            <div className="px-5 py-4">
              <Input
                value={newFolderName}
                onChange={(e) => setNewFolderName(e.target.value)}
                placeholder="请输入文件夹名称"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleCreateFolder()
                  if (e.key === 'Escape') {
                    setIsCreatingFolder(false)
                    setNewFolderName('')
                  }
                }}
              />
            </div>
            <div className="dialog-footer-bar">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setIsCreatingFolder(false)
                  setNewFolderName('')
                }}
              >
                取消
              </Button>
              <Button
                variant="success"
                size="sm"
                onClick={handleCreateFolder}
              >
                创建
              </Button>
            </div>
          </div>
        </div>,
        document.body,
      )}

      {/* 右键菜单 */}
      {contextMenu && (
        <div
          className="fixed bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-[10px] shadow-pop-xl py-1.5 z-[9999] min-w-[160px] animate-scale-in"
          style={{ left: contextMenu.x, top: contextMenu.y }}
          onClick={(e) => e.stopPropagation()}
        >
          {contextMenu.isFile ? (
            <>
              {/* 文件右键菜单：重命名、删除 */}
              <button
                className="bg-[hsl(var(--card))] hover:bg-[hsl(var(--muted))] w-full px-4 py-2 text-sm text-left flex items-center gap-2.5 transition-all duration-150 text-gray-700 hover:text-orange-700"
                onClick={() => {
                  if (contextMenu.assetId) {
                    const asset = imageAssets.find(a => a.id === contextMenu.assetId)
                    if (asset) {
                      setEditingAsset(asset.id)
                      setEditAssetName(asset.originalName)
                    }
                  }
                  setContextMenu(null)
                }}
              >
                <Edit2 className="w-4 h-4" />
                重命名
              </button>
              <div className="h-px bg-gray-200 my-1 mx-2"></div>
              <button
                className="bg-[hsl(var(--card))] hover:bg-[hsl(var(--muted))] w-full px-4 py-2 text-sm text-left flex items-center gap-2.5 transition-all duration-150 text-red-600 hover:text-red-700"
                onClick={() => {
                  if (contextMenu.assetId) handleDeleteAsset(contextMenu.assetId)
                  setContextMenu(null)
                }}
              >
                <Trash2 className="w-4 h-4" />
                删除
              </button>
            </>
          ) : contextMenu.isBlank ? (
            <>
              {/* 空白区域右键菜单：上传、新建文件夹、删除所有文件 */}
              <button
                className="bg-[hsl(var(--card))] hover:bg-[hsl(var(--muted))] w-full px-4 py-2 text-sm text-left flex items-center gap-2.5 transition-all duration-150 text-gray-700 hover:text-purple-700"
                onClick={() => {
                  fileInputRef.current?.click()
                  setContextMenu(null)
                }}
              >
                <Upload className="w-4 h-4" />
                上传图像
              </button>
              <button
                className="bg-[hsl(var(--card))] hover:bg-[hsl(var(--muted))] w-full px-4 py-2 text-sm text-left flex items-center gap-2.5 transition-all duration-150 text-gray-700 hover:text-green-700"
                onClick={() => {
                  setIsCreatingFolder(true)
                  setContextMenu(null)
                }}
              >
                <Plus className="w-4 h-4" />
                新建文件夹
              </button>
              <div className="h-px bg-gray-200 my-1 mx-2"></div>
              <button
                className="bg-[hsl(var(--card))] hover:bg-[hsl(var(--muted))] w-full px-4 py-2 text-sm text-left flex items-center gap-2.5 transition-all duration-150 text-red-600 hover:text-red-700"
                onClick={() => {
                  handleDeleteAllFiles()
                  setContextMenu(null)
                }}
              >
                <Trash2 className="w-4 h-4" />
                删除所有文件
              </button>
            </>
          ) : (
            <>
              {/* 文件夹右键菜单：上传到此文件夹、重命名、删除 */}
              <button
                className="bg-[hsl(var(--card))] hover:bg-[hsl(var(--muted))] w-full px-4 py-2 text-sm text-left flex items-center gap-2.5 transition-all duration-150 text-gray-700 hover:text-purple-700"
                onClick={() => {
                  const targetFolder = contextMenu.folder
                  const originalHandler = fileInputRef.current?.onchange
                  if (fileInputRef.current) {
                    fileInputRef.current.onchange = async (e) => {
                      const input = e.target as HTMLInputElement
                      const files = Array.from(input.files || [])
                      if (files.length === 0) return

                      const allowedExts = ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'svg', 'ico']
                      const imageFiles = files.filter(f => {
                        const ext = f.name.split('.').pop()?.toLowerCase()
                        return ext && allowedExts.includes(ext)
                      })
                      
                      if (imageFiles.length === 0) {
                        await alert('没有找到图像文件')
                        return
                      }

                      try {
                        // 逐个上传文件
                        const results = await Promise.all(
                          imageFiles.map(file => imageAssetApi.upload(file, targetFolder || undefined))
                        )
                        
                        let successCount = 0
                        let errorCount = 0
                        
                        results.forEach(result => {
                          if (result.data?.asset) {
                            addImageAsset(result.data.asset)
                            successCount++
                          } else {
                            errorCount++
                          }
                        })
                        
                        if (errorCount > 0) {
                          await alert(`上传完成：成功 ${successCount} 个，失败 ${errorCount} 个`)
                        }
                      } catch (error) {
                        await alert(`批量上传失败: ${error}`)
                      } finally {
                        input.value = ''
                        if (fileInputRef.current && originalHandler) {
                          fileInputRef.current.onchange = originalHandler
                        }
                      }
                    }
                  }
                  fileInputRef.current?.click()
                  setContextMenu(null)
                }}
              >
                <Upload className="w-4 h-4" />
                上传到此文件夹
              </button>
              <button
                className="bg-[hsl(var(--card))] hover:bg-[hsl(var(--muted))] w-full px-4 py-2 text-sm text-left flex items-center gap-2.5 transition-all duration-150 text-gray-700 hover:text-orange-700"
                onClick={() => {
                  setEditingFolder(contextMenu.folder)
                  setEditFolderName(contextMenu.folder.split('/').pop() || '')
                  setContextMenu(null)
                }}
              >
                <Edit2 className="w-4 h-4" />
                重命名
              </button>
              <div className="h-px bg-gray-200 my-1 mx-2"></div>
              <button
                className="bg-[hsl(var(--card))] hover:bg-[hsl(var(--muted))] w-full px-4 py-2 text-sm text-left flex items-center gap-2.5 transition-all duration-150 text-red-600 hover:text-red-700"
                onClick={() => {
                  handleDeleteFolder(contextMenu.folder)
                  setContextMenu(null)
                }}
              >
                <Trash2 className="w-4 h-4" />
                删除
              </button>
            </>
          )}
        </div>
      )}

      {/* 图片预览对话框 */}
      {previewAsset && createPortal(
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center" style={{ zIndex: 2147483646 }} onClick={() => setPreviewAsset(null)}>
          <div className="relative max-w-[90vw] max-h-[90vh] animate-in fade-in zoom-in duration-200" onClick={(e) => e.stopPropagation()}>
            <button
              className="absolute -top-10 right-0 text-white hover:text-gray-300 transition-colors"
              onClick={() => setPreviewAsset(null)}
            >
              <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
            <ImageAssetPreview asset={previewAsset} variant="file" className="max-w-full max-h-[90vh] object-contain rounded-lg shadow-2xl" />
          </div>
        </div>,
        document.body,
      )}

      <ConfirmDialog />
    </div>
  )
}
