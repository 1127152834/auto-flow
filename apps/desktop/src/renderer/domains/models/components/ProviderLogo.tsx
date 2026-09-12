import { PlugsConnected } from '@phosphor-icons/react'
import { useState } from 'react'
import { findProviderPreset } from '../provider-catalog'

export function ProviderLogo({ presetId, size = 'medium' }: { presetId?: string | null; name: string; size?: 'small' | 'medium' | 'large' }) {
  const preset = findProviderPreset(presetId)
  const [failedSource, setFailedSource] = useState<string>()
  const source = preset?.iconPath
  const dimensions = size === 'large' ? 'h-14 w-14' : size === 'small' ? 'h-8 w-8' : 'h-10 w-10'
  // These official SVGs include clear space; avoid adding a second inset.
  const inset = preset?.id === 'openai' || preset?.id === 'siliconflow'
    ? 'p-0'
    : size === 'large' ? 'p-2.5' : size === 'small' ? 'p-1.5' : 'p-2'
  return <span aria-hidden className={`${dimensions} ${inset} inline-flex shrink-0 items-center justify-center rounded-xl border border-line bg-white text-muted`}>
    {source && failedSource !== source
      ? <img key={source} src={source} alt="" className="h-full w-full object-contain" onError={() => setFailedSource(source)} />
      : <PlugsConnected className="h-full w-full" />}
  </span>
}
