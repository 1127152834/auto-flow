export type ProfilePreset = { value: string; label: string }

export const LOCALE_PRESETS: ProfilePreset[] = [
  { value: 'zh-CN', label: '简体中文 · zh-CN' },
  { value: 'zh-TW', label: '繁体中文 · zh-TW' },
  { value: 'en-US', label: '英语（美国）· en-US' },
  { value: 'en-GB', label: '英语（英国）· en-GB' },
  { value: 'ja-JP', label: '日语 · ja-JP' },
  { value: 'ko-KR', label: '韩语 · ko-KR' },
  { value: 'de-DE', label: '德语 · de-DE' },
  { value: 'fr-FR', label: '法语 · fr-FR' },
  { value: 'es-ES', label: '西班牙语 · es-ES' },
  { value: 'pt-BR', label: '葡萄牙语（巴西）· pt-BR' },
]

export const TIMEZONE_PRESETS: ProfilePreset[] = [
  { value: 'Asia/Shanghai', label: '中国标准时间 · 上海' },
  { value: 'Asia/Hong_Kong', label: '香港时间 · 香港' },
  { value: 'Asia/Tokyo', label: '日本标准时间 · 东京' },
  { value: 'Asia/Seoul', label: '韩国标准时间 · 首尔' },
  { value: 'America/Los_Angeles', label: '太平洋时间 · 洛杉矶' },
  { value: 'America/New_York', label: '东部时间 · 纽约' },
  { value: 'Europe/London', label: '英国时间 · 伦敦' },
  { value: 'Europe/Berlin', label: '中欧时间 · 柏林' },
  { value: 'Australia/Sydney', label: '澳大利亚东部时间 · 悉尼' },
]

export const VIEWPORT_PRESETS: ProfilePreset[] = [
  { value: '1280x800', label: '紧凑桌面 · 1280 × 800' },
  { value: '1366x768', label: '常见笔记本 · 1366 × 768' },
  { value: '1440x900', label: '宽屏桌面 · 1440 × 900' },
  { value: '1536x864', label: '缩放桌面 · 1536 × 864' },
  { value: '1920x1080', label: '全高清 · 1920 × 1080' },
  { value: '2560x1440', label: '2K 桌面 · 2560 × 1440' },
]

export const COLOR_SCHEME_PRESETS: ProfilePreset[] = [
  { value: '', label: '跟随系统（推荐）' },
  { value: 'light', label: '浅色' },
  { value: 'dark', label: '深色' },
  { value: 'no-preference', label: '无偏好' },
]

export const HUMAN_PRESETS: ProfilePreset[] = [
  { value: 'default', label: '标准节奏（推荐）' },
  { value: 'careful', label: '谨慎节奏（更慢）' },
]

export function getViewportPreset(width: string, height: string): string {
  const value = `${width}x${height}`
  return VIEWPORT_PRESETS.some((preset) => preset.value === value) ? value : ''
}

export function buildChromiumUserAgentPresets(browserVersion: string): ProfilePreset[] {
  const major = browserVersion.match(/^\d+/)?.[0]
  const followingBrowser = [{ value: '', label: '跟随浏览器（推荐）' }]
  if (!major) return followingBrowser

  const chrome = `Chrome/${major}.0.0.0 Safari/537.36`
  return [
    ...followingBrowser,
    {
      value: `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) ${chrome}`,
      label: `Windows 桌面 · Chromium ${major}`,
    },
    {
      value: `Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) ${chrome}`,
      label: `macOS 桌面 · Chromium ${major}`,
    },
    {
      value: `Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) ${chrome}`,
      label: `Linux 桌面 · Chromium ${major}`,
    },
  ]
}
