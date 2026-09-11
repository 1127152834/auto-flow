import { PlugsConnected } from '@phosphor-icons/react'
import { useState } from 'react'
import { findProviderPreset } from '../provider-catalog'

export function ProviderLogo({ presetId, name: _name, size = 'medium' }: { presetId?: string | null; name: string; size?: 'small' | 'medium' | 'large' }) {
  const preset = findProviderPreset(presetId)
  const [failed, setFailed] = useState(false)
  const dimensions = size === 'large' ? 'h-14 w-14 text-lg' : size === 'small' ? 'h-8 w-8 text-xs' : 'h-10 w-10 text-sm'
  return <span aria-hidden className={`${dimensions} inline-flex shrink-0 items-center justify-center overflow-hidden rounded-xl font-bold text-white`} style={{ backgroundColor: preset?.accent ?? '#9a684f' }}>{preset?.iconPath && !failed ? <img src={preset.iconPath} alt="" className="h-full w-full object-contain p-1.5" onError={() => setFailed(true)} /> : <PlugsConnected size="55%" />}</span>
}
