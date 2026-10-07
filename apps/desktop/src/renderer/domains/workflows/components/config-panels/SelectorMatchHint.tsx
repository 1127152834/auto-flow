import { useSelectorMatchCount } from '../../hooks/useSelectorMatchCount'

type Props = { selector: string; hints?: Record<string, unknown>; running: boolean }

/** 选择器旁常驻的匹配数；运行中不检查，也不会自动启动浏览器。 */
export function SelectorMatchHint({ selector, hints, running }: Props) {
  const state = useSelectorMatchCount(selector, hints, !running)
  const text = {
    idle: '',
    checking: '正在检查匹配数…',
    disabled: '运行中不检查',
    noBrowser: '未连接浏览器',
    error: '检查失败，可点击测试重试',
    ok: state.status === 'ok' ? `当前页面匹配 ${state.count} 个元素` : '',
  }[state.status]
  if (!text) return null
  const warn = state.status === 'error' || (state.status === 'ok' && state.count === 0)
  return <p role="status" className={`text-xs ${warn ? 'text-warning' : 'text-muted-foreground'}`}>{text}</p>
}
