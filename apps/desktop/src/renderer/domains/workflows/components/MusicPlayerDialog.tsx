// Source: WebRPA@5ccb900e, components/workflow/MusicPlayerDialog.tsx; see SOURCE.md for license and adaptation boundaries.
import { studioFetch } from '../api/transport'
import { useState, useEffect, useRef, useCallback } from 'react'
import { X, Play, Pause, Repeat, Volume2 } from 'lucide-react'
import { Button } from './controls/button'
import { Slider } from './controls/slider'
import { getBackendUrl } from '../api'
import { DialogPortal } from './controls/dialog-portal'

interface MusicPlayerDialogProps {
  audioUrl: string
  requestId: string
  waitForEnd: boolean
  onClose: (success: boolean, error?: string) => void
}

export function MusicPlayerDialog({ audioUrl, waitForEnd, onClose }: MusicPlayerDialogProps) {
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [isRepeat, setIsRepeat] = useState(false)
  const [volume, setVolume] = useState(1)
  const [error, setError] = useState<string | null>(null)
  const [convertedUrl, setConvertedUrl] = useState<string | null>(null)
  const hasEndedRef = useRef(false)

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
      if (audioRef.current) {
        audioRef.current.currentTime = 0
        audioRef.current.play()
      }
    } else {
      setIsPlaying(false)
      hasEndedRef.current = true
      // 播放结束，自动关闭弹窗
      setTimeout(() => {
        onClose(true)
      }, 500)
    }
  }, [isRepeat, onClose])

  // 转换音频格式
  useEffect(() => {
    const convertAudio = async () => {
      try {
        setIsLoading(true)
        setError(null)
        
        // 调用后端转换音频
        const response = await studioFetch(`${getBackendUrl()}/api/system/convert-audio`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ audioUrl })
        })
        
        const result = await response.json()
        
        if (result.success) {
          // 返回的是相对路径，需要加上后端地址
          setConvertedUrl(`${getBackendUrl()}${result.audioPath}`)
        } else {
          setError(result.error || '音频转换失败')
          setIsLoading(false)
        }
      } catch (err) {
        setError(`转换音频失败: ${err instanceof Error ? err.message : String(err)}`)
        setIsLoading(false)
      }
    }
    
    convertAudio()
  }, [audioUrl])

  // 初始化音频（在转换完成后）
  useEffect(() => {
    if (!convertedUrl) return
    
    const audio = new Audio(convertedUrl)
    audioRef.current = audio
    
    // 注册 audio ref 到全局，以便 hideMusicPlayer 可以停止播放
    setCurrentAudioRefFn?.(audio)

    audio.onloadedmetadata = () => {
      setDuration(audio.duration)
      setIsLoading(false)
    }

    audio.oncanplay = () => {
      setIsLoading(false)
      // 自动开始播放
      audio.play().then(() => {
        setIsPlaying(true)
      }).catch(err => {
        setError(`播放失败: ${err.message}`)
      })
    }

    audio.ontimeupdate = () => {
      setCurrentTime(audio.currentTime)
    }

    audio.onerror = () => {
      setError('音频加载失败')
      setIsLoading(false)
    }

    audio.volume = volume

    return () => {
      audio.pause()
      audio.src = ''
      audioRef.current = null
      setCurrentAudioRefFn?.(null)
    }
  }, [convertedUrl]) // 只依赖 convertedUrl，不依赖 volume 和 handleEnded

  // 更新 onended 回调
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.onended = handleEnded
    }
  }, [handleEnded])

  // 更新音量
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.volume = volume
    }
  }, [volume])

  // 播放/暂停
  const togglePlay = () => {
    if (!audioRef.current) return
    
    if (isPlaying) {
      audioRef.current.pause()
      setIsPlaying(false)
    } else {
      audioRef.current.play().then(() => {
        setIsPlaying(true)
      }).catch(err => {
        setError(`播放失败: ${err.message}`)
      })
    }
  }

  // 进度条拖动
  const handleSeek = (value: number[]) => {
    if (!audioRef.current) return
    const newTime = value[0]
    audioRef.current.currentTime = newTime
    setCurrentTime(newTime)
  }

  // 音量调节
  const handleVolumeChange = (value: number[]) => {
    const newVolume = value[0]
    setVolume(newVolume)
    if (audioRef.current) {
      audioRef.current.volume = newVolume
    }
  }

  // 关闭弹窗
  const handleClose = () => {
    if (audioRef.current) {
      audioRef.current.pause()
    }
    // 如果还没播放完就关闭，根据 waitForEnd 决定返回结果
    if (!hasEndedRef.current && waitForEnd) {
      onClose(false, '用户关闭了播放器')
    } else {
      onClose(true)
    }
  }

  // 从URL中提取文件名
  const getFileName = () => {
    try {
      const url = new URL(audioUrl)
      const path = decodeURIComponent(url.pathname)
      const fileName = path.split('/').pop() || '未知音频'
      // 截断过长的文件名
      return fileName.length > 40 ? fileName.substring(0, 37) + '...' : fileName
    } catch {
      return '音频播放'
    }
  }

  return (
    <DialogPortal>
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 animate-fade-in"
      style={{ zIndex: 2147483640 }}
    >
      <div className="bg-white text-black border border-gray-200 rounded-xl shadow-2xl w-full max-w-md overflow-hidden animate-scale-in">
        {/* 头部 */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <Volume2 className="w-5 h-5 text-blue-500" />
            <span className="font-semibold text-gray-900 truncate max-w-[280px]">{getFileName()}</span>
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

        {/* 内容 */}
        <div className="p-5">
          {error ? (
            <div className="text-center text-red-500 py-4">{error}</div>
          ) : isLoading ? (
            <div className="text-center text-gray-500 py-4">
              <div className="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full mx-auto mb-2" />
              加载中...
            </div>
          ) : (
            <>
              {/* 进度条 */}
              <div className="mb-4">
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
              <div className="flex items-center justify-center gap-4">
                {/* 循环播放 */}
                <Button
                  variant="ghost"
                  size="icon"
                  className={`h-10 w-10 rounded-full ${isRepeat ? 'text-blue-600 bg-blue-100' : 'text-gray-500 hover:bg-gray-100'}`}
                  onClick={() => setIsRepeat(!isRepeat)}
                  title={isRepeat ? '关闭循环' : '循环播放'}
                >
                  <Repeat className="w-5 h-5" />
                </Button>

                {/* 播放/暂停 */}
                <Button
                  variant="default"
                  size="icon"
                  className="h-14 w-14 rounded-full bg-blue-600 hover:bg-blue-700 text-white shadow-lg"
                  onClick={togglePlay}
                >
                  {isPlaying ? (
                    <Pause className="w-6 h-6" />
                  ) : (
                    <Play className="w-6 h-6 ml-1" />
                  )}
                </Button>

                {/* 音量 */}
                <div className="flex items-center gap-2 w-24">
                  <Volume2 className="w-4 h-4 text-gray-500 flex-shrink-0" />
                  <Slider
                    value={[volume]}
                    max={1}
                    step={0.01}
                    onValueChange={handleVolumeChange}
                    className="cursor-pointer"
                  />
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
    </DialogPortal>
  )
}

// 全局状态管理 - 使用 window 对象存储以确保跨模块共享
declare global {
  interface Window {
    __musicPlayerCallback?: ((props: MusicPlayerDialogProps | null) => void) | null
    __currentAudioRef?: HTMLAudioElement | null
  }
}

// 前向声明
let setCurrentAudioRefFn: ((ref: HTMLAudioElement | null) => void) | null = null

export function setMusicPlayerCallback(callback: (props: MusicPlayerDialogProps | null) => void) {
  window.__musicPlayerCallback = callback
}

export function setCurrentAudioRef(ref: HTMLAudioElement | null) {
  console.log('[MusicPlayer] setCurrentAudioRef called:', ref ? 'audio element' : 'null')
  window.__currentAudioRef = ref
}

// 连接内部函数
setCurrentAudioRefFn = setCurrentAudioRef

export function showMusicPlayer(props: Omit<MusicPlayerDialogProps, 'onClose'>, onClose: (success: boolean, error?: string) => void) {
  if (window.__musicPlayerCallback) {
    window.__musicPlayerCallback({
      ...props,
      onClose: (success, error) => {
        window.__musicPlayerCallback?.(null)
        onClose(success, error)
      }
    })
  }
}

export function hideMusicPlayer() {
  console.log('[MusicPlayer] hideMusicPlayer called, currentAudioRef:', window.__currentAudioRef ? 'exists' : 'null')
  // 先停止音频播放
  if (window.__currentAudioRef) {
    console.log('[MusicPlayer] Stopping audio playback')
    window.__currentAudioRef.pause()
    window.__currentAudioRef.src = ''
    window.__currentAudioRef = null
  }
  if (window.__musicPlayerCallback) {
    window.__musicPlayerCallback(null)
  }
}
