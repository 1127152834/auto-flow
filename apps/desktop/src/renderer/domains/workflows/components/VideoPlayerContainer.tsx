// Source: WebRPA@5ccb900e, components/workflow/VideoPlayerContainer.tsx; see SOURCE.md for license and adaptation boundaries.
import { useState, useEffect } from 'react'
import { VideoPlayerDialog, setVideoPlayerCallback } from './VideoPlayerDialog'

interface VideoPlayerProps {
  videoUrl: string
  requestId: string
  waitForEnd: boolean
  onClose: (success: boolean, error?: string) => void
}

export function VideoPlayerContainer() {
  const [playerProps, setPlayerProps] = useState<VideoPlayerProps | null>(null)

  useEffect(() => {
    setVideoPlayerCallback((props) => {
      setPlayerProps(props)
    })

    return () => {
      setVideoPlayerCallback(() => {})
    }
  }, [])

  if (!playerProps) return null

  return <VideoPlayerDialog {...playerProps} />
}
