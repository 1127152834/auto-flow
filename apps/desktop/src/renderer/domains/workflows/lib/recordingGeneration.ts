// Source: frozen WebRPA RecorderPanel conversion; extracted unchanged except explicit review overrides.
import { nanoid } from 'nanoid'
import type { ModuleType } from '../types/workflow'
import type { Node, Edge } from '@xyflow/react'
import type { NodeData } from '../editor-store'
import { moduleTypeLabels } from '../editor-store'
export interface RecEvent {
  variableName?: string
  needsValue?: boolean
  navigation?: 'source' | 'open' | 'ignore'
  filePath?: string
  sequence?: number
  type: 'navigate' | 'click' | 'dblclick' | 'input' | 'select' | 'check' | 'keypress' | 'drag' | 'upload' | 'scroll'
  selector?: string
  targetSelector?: string
  hints?: Record<string, unknown>
  targetHints?: Record<string, unknown>
  value?: unknown
  values?: string[]
  text?: string
  url?: string
  key?: string
  fileName?: string
  endX?: number
  endY?: number
  dy?: number
  y?: number
  ts?: number
  sensitive?: boolean
  _frame?: { main?: boolean; index?: number; name?: string; selector?: string }
}

export function buildRecordedNodes(evs: RecEvent[], autoWait: boolean) {
    const newNodes: Node<NodeData>[] = []
    const newEdges: Edge[] = []
    let prevId: string | null = null
    let lastNavUrl: string | null = null
    let seenFirstNav = false      // 是否已生成过初始"打开网页"
    let lastActionTs = 0          // 最近一次可能触发跳转的交互(click/回车)时间戳
    let curFrameKey = '__main__'  // 当前所处 frame（回放上下文），'__main__' 表示主文档

    const mkNode = (moduleType: ModuleType, cfg: Record<string, unknown>, name?: string) => {
      const id = nanoid()
      const node: Node<NodeData> = {
        id,
        type: 'moduleNode',
        position: { x: 320, y: 100 + newNodes.length * 120 },
        data: {
          label: (moduleTypeLabels as Record<string, string>)[moduleType] || moduleType,
          moduleType,
          ...(name ? { name } : {}),
          ...cfg,
        },
      }
      newNodes.push(node)
      // 与项目默认连线一致：smoothstep + 流光动画（否则直接注入的边会渲染成默认实线）
      if (prevId) newEdges.push({ id: `e-${prevId}-${id}`, source: prevId, target: id, type: 'smoothstep', animated: true })
      prevId = id
      return node
    }

    // frame 身份 key：selector 最稳，其次 name，其次 index
    const frameKeyOf = (ev: RecEvent): string => {
      const f = ev._frame
      if (!f || f.main) return '__main__'
      if (f.selector) return 'sel:' + f.selector
      if (f.name) return 'name:' + f.name
      if (typeof f.index === 'number' && f.index >= 0) return 'idx:' + f.index
      return '__main__'
    }
    // 若事件所属 frame 与当前上下文不同，插入 switch_iframe / switch_to_main 节点
    const ensureFrame = (ev: RecEvent) => {
      const key = frameKeyOf(ev)
      if (key === curFrameKey) return
      if (key === '__main__') {
        mkNode('switch_to_main', {})
      } else {
        const f = ev._frame!
        if (f.selector) mkNode('switch_iframe', { locateBy: 'selector', iframeSelector: f.selector }, 'iframe')
        else if (f.name) mkNode('switch_iframe', { locateBy: 'name', iframeName: f.name }, 'iframe')
        else mkNode('switch_iframe', { locateBy: 'index', iframeIndex: f.index ?? 0 }, 'iframe')
      }
      curFrameKey = key
    }

    for (let idx = 0; idx < evs.length; idx++) {
      const ev = evs[idx]
      // 自动插入等待：与上一步时间间隔较大时补一个延迟节点
      if (autoWait && idx > 0) {
        const prevTs = evs[idx - 1].ts || 0
        const gap = (ev.ts || 0) - prevTs
        if (gap >= 1500) {
          // 传秒（wait 执行器新字段单位为秒），并限幅到 3 秒——
          // 元素级等待已由执行器 auto-wait 保证，不必把用户思考的停顿全等上
          mkNode('wait', { duration: Math.min(Math.max(1, Math.round(gap / 1000)), 3) })
        }
      }
      if (ev.type === 'navigate') {
        if (ev.navigation === 'ignore') continue
        if (ev.navigation === 'open') { mkNode('open_page', { url: ev.url || '' }); seenFirstNav = true; lastNavUrl = ev.url || ''; curFrameKey = '__main__'; continue }
        // iframe 内导航是页面内部行为，忽略
        if (ev._frame && !ev._frame.main) continue
        const u = ev.url || ''
        if (!u || u.startsWith('about:')) continue
        if (seenFirstNav && u === lastNavUrl) continue  // 同 URL 重复导航
        lastNavUrl = u
        curFrameKey = '__main__'  // 页面变化后回放上下文回到主文档
        if (!seenFirstNav) {
          // 首个导航 = 录制起始页面 → 生成"打开网页"
          seenFirstNav = true
          mkNode('open_page', { url: u })
        } else if (lastActionTs && (ev.ts || 0) - lastActionTs < 10000) {
          // 由点击/回车等交互引起的跳转（含重定向链）→ 不单独生成节点，
          // 点击节点回放时会自然触发跳转（新标签页由后续节点 switch_to_latest 处理）
          continue
        } else {
          // 与任何交互无因果关系的导航（如用户在地址栏主动输入 URL）→ 生成"打开网页"
          mkNode('open_page', { url: u })
        }
      } else if (ev.type === 'click') {
        if (!ev.selector) continue
        ensureFrame(ev)
        lastActionTs = ev.ts || 0
        mkNode('click_element', { selector: ev.selector, ...(ev.hints ? { selectorHints: ev.hints } : {}) }, ev.text ? ev.text.slice(0, 20) : undefined)
      } else if (ev.type === 'dblclick') {
        if (!ev.selector) continue
        ensureFrame(ev)
        lastActionTs = ev.ts || 0
        mkNode('click_element', { selector: ev.selector, clickType: 'double', ...(ev.hints ? { selectorHints: ev.hints } : {}) }, ev.text ? ev.text.slice(0, 20) : undefined)
      } else if (ev.type === 'input') {
        if (!ev.selector) continue
        ensureFrame(ev)
        // typeSequential：逐字键入，忠实还原用户打字触发的联想/校验等行为
        mkNode('input_text', { selector: ev.selector, text: ev.variableName ? `{${ev.variableName}}` : String(ev.value ?? ''), typeSequential: true, ...(ev.hints ? { selectorHints: ev.hints } : {}) })
      } else if (ev.type === 'select') {
        if (!ev.selector) continue
        ensureFrame(ev)
        const selCfg = Array.isArray(ev.values) && ev.values.length > 1
          ? { selector: ev.selector, values: ev.values }                       // 多选下拉：选中全部
          : { selector: ev.selector, value: String(ev.value ?? '') }
        mkNode('select_dropdown', { ...selCfg, ...(ev.hints ? { selectorHints: ev.hints } : {}) }, ev.text ? ev.text.slice(0, 20) : undefined)
      } else if (ev.type === 'check') {
        if (!ev.selector) continue
        ensureFrame(ev)
        mkNode('set_checkbox', { selector: ev.selector, checked: !!ev.value, ...(ev.hints ? { selectorHints: ev.hints } : {}) })
      } else if (ev.type === 'drag') {
        if (!ev.selector) continue
        ensureFrame(ev)
        lastActionTs = ev.ts || 0
        // 源与目标是同一元素(如滑块) → 用坐标拖拽(targetPosition)，否则元素到元素拖拽
        const sameEl = !ev.targetSelector || ev.selector === ev.targetSelector
        const dragCfg = sameEl && ev.endX != null
          ? { sourceSelector: ev.selector, targetPosition: { x: ev.endX, y: ev.endY ?? 0 }, ...(ev.hints ? { selectorHints: ev.hints } : {}) }
          : {
              sourceSelector: ev.selector,
              targetSelector: ev.targetSelector,
              ...(ev.hints ? { selectorHints: ev.hints } : {}),
              ...(ev.targetHints ? { targetSelectorHints: ev.targetHints } : {}),
            }
        mkNode('drag_element', dragCfg, ev.text ? ev.text.slice(0, 20) : undefined)
      } else if (ev.type === 'upload') {
        if (!ev.selector) continue
        ensureFrame(ev)
        // 浏览器安全限制拿不到真实路径，生成占位节点（filePath 留空，用户补填）
        mkNode('upload_file', { selector: ev.selector, filePath: ev.filePath || '', ...(ev.hints ? { selectorHints: ev.hints } : {}) }, ev.fileName ? ev.fileName.slice(0, 20) : undefined)
      } else if (ev.type === 'scroll') {
        ensureFrame(ev)
        const dir = (ev.dy ?? 0) >= 0 ? 'down' : 'up'
        mkNode('scroll_page', { direction: dir, distance: Math.abs(ev.dy ?? 300) || 300 })
      } else if (ev.type === 'keypress') {
        if (!ev.key) continue
        ensureFrame(ev)
        // 回车/Tab 可能触发表单提交跳转，视为"可致跳转的交互"
        if (ev.key === 'Enter' || ev.key === 'Tab' || /Enter$/.test(ev.key)) lastActionTs = ev.ts || 0
        // 若按键发生在具体输入元素上，用 element 目标模式（先聚焦该元素再按键），忠实还原作用目标
        const keyCfg = ev.selector ? { keySequence: ev.key, targetType: 'element', selector: ev.selector } : { keySequence: ev.key }
        mkNode('keyboard_action', keyCfg, ev.key)
      }
    }

  return { nodes: newNodes, edges: newEdges }
}
