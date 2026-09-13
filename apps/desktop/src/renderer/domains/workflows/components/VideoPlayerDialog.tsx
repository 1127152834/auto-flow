// Source: WebRPA@5ccb900e, components/workflow/VideoPlayerDialog.tsx; see SOURCE.md for license and adaptation boundaries.
import { studioFetch } from '../api/transport'
import { useState, useEffect, useRef, useCallback } from 'react'
import { X, Play, Pause, Repeat, Volume2, VolumeX, Maximize, Minimize } from 'lucide-react'
import { Button } from './controls/button'
import { Slider } from './controls/slider'
import { getBackendUrl } from '../api'
import { DialogPortal } from './controls/dialog-portal'

interface VideoPlayerDialogProps {
  videoUrl: string
  requestId: string
  waitForEnd: boolean
  onClose: (success: boolean, error?: string) => void
}

// 前向声明
let setCurrentVideoRefFn: ((ref: HTMLVideoElement | null) => void) | null = null

export function VideoPlayerDialog({ videoUrl, waitForEnd, onClose }: VideoPlayerDialogProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [loadingMessage, setLoadingMessage] = useState('加载中...')
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [isRepeat, setIsRepeat] = useState(false)
  const [volume, setVolume] = useState(1)
  const [isMuted, setIsMuted] = useState(false)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isConverting, setIsConverting] = useState(false)
  const hasEndedRef = useRef(false)
  const retryCountRef = useRef(0)
  
  // 检查是否已停止的辅助函数
  const isStopped = useCallback(() => window.__videoPlayerStopped === true, [])

  // 格式化时间
  const formatTime = (time: number) => {
    if (isNaN(time) || !isFinite(time)) return '0:00'
    const minutes = Math.floor(time / 60)
    const seconds = Math.floor(time % 60)
    return `${minutes}:${seconds.toString().padStart(2, '0')}`
  }

  // 处理播放结束
  const handleEnded = useCallback(() => {
    if (isRepeat) {
      if (videoRef.current) {
        videoRef.current.currentTime = 0
        videoRef.current.play()
      }
    } else {
      setIsPlaying(false)
      hasEndedRef.current = true
      setTimeout(() => {
        onClose(true)
      }, 500)
    }
  }, [isRepeat, onClose])

  // 转换视频格式（使用后端 FFmpeg）
  const convertVideo = useCallback(async (url: string): Promise<string | null> => {
    setIsConverting(true)
    setLoadingMessage('正在转换视频格式...')
    
    try {
      const response = await studioFetch(`${getBackendUrl()}/api/system/convert-video`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ videoUrl: url })
      })
      
      const result = await response.json()
      
      if (result.success) {
        return `${getBackendUrl()}${result.videoPath}`
      } else {
        console.error('[VideoPlayer] 转换失败:', result.error)
        return null
      }
    } catch (err) {
      console.error('[VideoPlayer] 转换请求失败:', err)
      return null
    } finally {
      setIsConverting(false)
    }
  }, [])

  // 获取视频 URL（处理本地路径和网络 URL）
  const getVideoUrl = useCallback((url: string): string => {
    if (url.match(/^[A-Za-z]:[\\\/]/)) {
      // Windows 绝对路径
      return `${getBackendUrl()}/api/system/local-file?path=${encodeURIComponent(url)}`
    } else if (url.startsWith('/') && !url.startsWith('//')) {
      // Unix 绝对路径
      return `${getBackendUrl()}/api/system/local-file?path=${encodeURIComponent(url)}`
    }
    return url
  }, [])

  // 初始化视频
  useEffect(() => {
    if (!videoUrl) return

    const video = videoRef.current
    if (!video) return

    // 重置停止标志
    window.__videoPlayerStopped = false

    // 注册 video ref 到全局，以便 hideVideoPlayer 可以停止播放
    setCurrentVideoRefFn?.(video)

    console.log('[VideoPlayer] 原始 URL:', videoUrl)
    
    const initialUrl = getVideoUrl(videoUrl)
    console.log('[VideoPlayer] 初始 URL:', initialUrl)
    setLoadingMessage('加载中...')
    
    video.src = initialUrl

    video.onloadedmetadata = () => {
      if (isStopped()) return // 已停止，不处理
      console.log('[VideoPlayer] 视频元数据加载完成, 时长:', video.duration)
      setDuration(video.duration)
      setIsLoading(false)
    }

    video.oncanplay = () => {
      if (isStopped()) return // 已停止，不处理
      console.log('[VideoPlayer] 视频可以播放')
      setIsLoading(false)
      video.play().then(() => {
        if (isStopped()) {
          // 如果在 play() 完成时已经被停止，立即暂停
          video.pause()
          return
        }
        setIsPlaying(true)
      }).catch(err => {
        if (isStopped()) return // 已停止，忽略错误
        console.error('[VideoPlayer] 播放失败:', err)
        setError(`播放失败: ${err.message}`)
      })
    }

    video.ontimeupdate = () => {
      if (isStopped()) return // 已停止，不处理
      setCurrentTime(video.currentTime)
    }

    video.onerror = async () => {
      if (isStopped()) return // 已停止，不处理
      console.error('[VideoPlayer] 视频加载错误:', video.error)
      
      // 如果是格式不支持的错误，尝试转码
      if (video.error?.code === 4 && retryCountRef.current === 0) {
        retryCountRef.current++
        console.log('[VideoPlayer] 尝试使用 FFmpeg 转码...')
        
        const convertedUrl = await convertVideo(videoUrl)
        if (isStopped()) return // 转码期间被停止
        if (convertedUrl) {
          console.log('[VideoPlayer] 转码成功，使用新 URL:', convertedUrl)
          setLoadingMessage('加载转码后的视频...')
          video.src = convertedUrl
          video.load()
          return
        }
      }
      
      let errorMsg = '视频加载失败'
      if (video.error) {
        const errorMessages: Record<number, string> = {
          1: '视频加载被中止',
          2: '网络错误，无法加载视频',
          3: '视频解码失败',
          4: '视频格式不支持，转码也失败了'
        }
        errorMsg = errorMessages[video.error.code] || `视频加载失败: ${video.error.code}`
      }
      setError(errorMsg)
      setIsLoading(false)
    }

    video.volume = volume

    return () => {
      // 标记为已停止
      window.__videoPlayerStopped = true
      // 清除所有事件处理器
      video.onloadedmetadata = null
      video.oncanplay = null
      video.ontimeupdate = null
      video.onerror = null
      video.onended = null
      // 停止播放
      video.pause()
      video.src = ''
      video.load() // 强制重置视频元素
    }
  }, [videoUrl, getVideoUrl, convertVideo, isStopped])

  // 更新 onended 回调
  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.onended = handleEnded
    }
  }, [handleEnded])

  // 更新音量
  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.volume = volume
      videoRef.current.muted = isMuted
    }
  }, [volume, isMuted])

  // 监听全屏变化
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement)
    }
    document.addEventListener('fullscreenchange', handleFullscreenChange)
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange)
  }, [])

  // 播放/暂停
  const togglePlay = () => {
    if (!videoRef.current) return
    
    if (isPlaying) {
      videoRef.current.pause()
      setIsPlaying(false)
    } else {
      videoRef.current.play().then(() => {
        setIsPlaying(true)
      }).catch(err => {
        setError(`播放失败: ${err.message}`)
      })
    }
  }

  // 进度条拖动
  const handleSeek = (value: number[]) => {
    if (!videoRef.current) return
    const newTime = value[0]
    videoRef.current.currentTime = newTime
    setCurrentTime(newTime)
  }

  // 音量调节
  const handleVolumeChange = (value: number[]) => {
    const newVolume = value[0]
    setVolume(newVolume)
    if (newVolume > 0) setIsMuted(false)
  }

  // 切换静音
  const toggleMute = () => {
    setIsMuted(!isMuted)
  }

  // 切换全屏
  const toggleFullscreen = () => {
    if (!containerRef.current) return
    
    if (isFullscreen) {
      document.exitFullscreen()
    } else {
      containerRef.current.requestFullscreen()
    }
  }

  // 关闭弹窗
  const handleClose = () => {
    if (videoRef.current) {
      videoRef.current.pause()
      videoRef.current.src = ''
    }
    if (!hasEndedRef.current && waitForEnd) {
      onClose(false, '用户关闭了播放器')
    } else {
      onClose(true)
    }
  }

  // 从URL中提取文件名
  const getFileName = () => {
    try {
      const url = new URL(videoUrl)
      const path = decodeURIComponent(url.pathname)
      const fileName = path.split('/').pop() || '未知视频'
      return fileName.length > 40 ? fileName.substring(0, 37) + '...' : fileName
    } catch {
      return '视频播放'
    }
  }

  return (
    <DialogPortal>
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 animate-fade-in" style={{ zIndex: 2147483646 }}>
      <div 
        ref={containerRef}
        className="bg-white text-black border border-gray-200 rounded-xl shadow-2xl w-full max-w-2xl overflow-hidden animate-scale-in"
      >
        {/* 头部 */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <Play className="w-5 h-5 text-blue-500" />
            <span className="font-semibold text-gray-900 truncate max-w-[400px]">{getFileName()}</span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-gray-600 hover:text-gray-900 hover:bg-gray-100"
            onClick={handleClose}
          >
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* 视频区域 */}
        <div className="relative bg-black">
          {error ? (
            <div className="flex items-center justify-center h-64 text-red-500">{error}</div>
          ) : isLoading ? (
            <div className="flex flex-col items-center justify-center h-64 text-gray-400">
              <div className="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full" />
              <span className="mt-2 text-sm">{loadingMessage}</span>
              {isConverting && (
                <span className="mt-1 text-xs text-gray-500">视频转码中，请稍候...</span>
              )}
            </div>
          ) : null}
          <video
            ref={videoRef}
            className={`w-full max-h-[60vh] ${isLoading || error ? 'hidden' : ''}`}
            onClick={togglePlay}
          />
        </div>

        {/* 控制栏 */}
        <div className="p-4 space-y-3">
          {/* 进度条 */}
          <div>
            <Slider
              value={[currentTime]}
              max={duration || 100}
              step={0.1}
              onValueChange={handleSeek}
              className="cursor-pointer"
            />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>{formatTime(currentTime)}</span>
              <span>{formatTime(duration)}</span>
            </div>
          </div>

          {/* 控制按钮 */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {/* 播放/暂停 */}
              <Button
                variant="default"
                size="icon"
                className="h-10 w-10 rounded-full bg-blue-600 hover:bg-blue-700 text-white"
                onClick={togglePlay}
              >
                {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5 ml-0.5" />}
              </Button>

              {/* 循环播放 */}
              <Button
                variant="ghost"
                size="icon"
                className={`h-9 w-9 rounded-full ${isRepeat ? 'text-blue-600 bg-blue-100' : 'text-gray-500 hover:bg-gray-100'}`}
                onClick={() => setIsRepeat(!isRepeat)}
                title={isRepeat ? '关闭循环' : '循环播放'}
              >
                <Repeat className="w-4 h-4" />
              </Button>

              {/* 音量 */}
              <Button
                variant="ghost"
                size="icon"
                className="h-9 w-9 rounded-full text-gray-500 hover:bg-gray-100"
                onClick={toggleMute}
              >
                {isMuted || volume === 0 ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
              </Button>
              <div className="w-20">
                <Slider
                  value={[isMuted ? 0 : volume]}
                  max={1}
                  step={0.01}
                  onValueChange={handleVolumeChange}
                  className="cursor-pointer"
                />
              </div>
            </div>

            {/* 全屏 */}
            <Button
              variant="ghost"
              size="icon"
              className="h-9 w-9 rounded-full text-gray-500 hover:bg-gray-100"
              onClick={toggleFullscreen}
            >
              {isFullscreen ? <Minimize className="w-4 h-4" /> : <Maximize className="w-4 h-4" />}
            </Button>
          </div>
        </div>
      </div>
    </div>
    </DialogPortal>
  )
}

// 全局状态管理 - 使用 window 对象存储以确保跨模块共享
declare global {
  interface Window {
    __videoPlayerCallback?: ((props: VideoPlayerDialogProps | null) => void) | null
    __currentVideoRef?: HTMLVideoElement | null
    __videoPlayerStopped?: boolean // 全局停止标志
  }
}

export function setVideoPlayerCallback(callback: (props: VideoPlayerDialogProps | null) => void) {
  window.__videoPlayerCallback = callback
}

export function setCurrentVideoRef(ref: HTMLVideoElement | null) {
  console.log('[VideoPlayer] setCurrentVideoRef called:', ref ? 'video element' : 'null')
  window.__currentVideoRef = ref
  if (ref) {
    window.__videoPlayerStopped = false // 新视频开始时重置停止标志
  }
}

// 连接内部函数
setCurrentVideoRefFn = setCurrentVideoRef

export function showVideoPlayer(props: Omit<VideoPlayerDialogProps, 'onClose'>, onClose: (success: boolean, error?: string) => void) {
  window.__videoPlayerStopped = false // 重置停止标志
  if (window.__videoPlayerCallback) {
    window.__videoPlayerCallback({
      ...props,
      onClose: (success, error) => {
        window.__videoPlayerCallback?.(null)
        onClose(success, error)
      }
    })
  }
}

export function hideVideoPlayer() {
  console.log('[VideoPlayer] hideVideoPlayer called, currentVideoRef:', window.__currentVideoRef ? 'exists' : 'null')
  // 设置全局停止标志
  window.__videoPlayerStopped = true
  // 先停止视频播放
  if (window.__currentVideoRef) {
    console.log('[VideoPlayer] Stopping video playback')
    const video = window.__currentVideoRef
    // 清除所有事件处理器
    video.onloadedmetadata = null
    video.oncanplay = null
    video.ontimeupdate = null
    video.onerror = null
    video.onended = null
    // 停止播放
    video.pause()
    video.src = ''
    video.load() // 强制重置
    window.__currentVideoRef = null
  }
  if (window.__videoPlayerCallback) {
    window.__videoPlayerCallback(null)
  }
}

// 检查是否已停止（供组件内部使用）
export function isVideoPlayerStopped(): boolean {
  return window.__videoPlayerStopped === true
}
