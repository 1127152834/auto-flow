// Source: WebRPA@5ccb900e, components/workflow/__tests__/MissingPacksDialog.test.tsx; see SOURCE.md for license and adaptation boundaries.
/**
 * 缺少功能模块包弹窗 —— 交互回归测试
 *
 * 背景：用户反馈「运行工作流后只在日志里看到一句『已弹窗提示下载与安装方式』，
 * 但实际压根没弹窗」。真实浏览器复现表明弹窗本身能正常渲染，
 * 但它的遮罩铺满全屏且绑了 onClick 关闭 —— 运行被中止后用户随手点一下画布，
 * 弹窗就没了，只剩那行"已弹窗"的日志，看起来就像从未弹过。
 *
 * 本测试锁定修复后的行为：
 * - 点遮罩不再关闭（阻断性提示只能从明确入口关闭）
 * - X 与「稍后再说」仍能关闭
 * - 遮罩点击不向外冒泡（本弹窗会被渲染在别的对话框的 React 子树里）
 * - 后端未给出功能包详情时，不渲染空白块，仍有可用下载入口
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MissingPacksDialog, type MissingPackGroup } from '../MissingPacksDialog'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

let container: HTMLDivElement
let root: Root

beforeEach(() => {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

const GROUP: MissingPackGroup = {
  alternatives: [{ id: 'pack_web', name: '网页自动化', size_mb: 512 }],
  module_types: ['click_element'],
}

function mount(props: Partial<Parameters<typeof MissingPacksDialog>[0]> = {}) {
  const onClose = vi.fn()
  const onOpenManager = vi.fn()
  act(() => {
    root.render(
      <MissingPacksDialog
        open
        missing={[GROUP]}
        onClose={onClose}
        onOpenManager={onOpenManager}
        {...props}
      />
    )
  })
  return { onClose, onOpenManager }
}

/** 取遮罩层（portal 到 body 的最外层 fixed 容器） */
function overlay(): HTMLElement {
  const el = document.querySelector('body > div.fixed.inset-0') as HTMLElement | null
  if (!el) throw new Error('未找到弹窗遮罩')
  return el
}

function click(el: Element) {
  act(() => {
    el.dispatchEvent(new MouseEvent('click', { bubbles: true }))
  })
}

function findByText(text: string): HTMLElement | null {
  const all = Array.from(document.body.querySelectorAll('button, h2, p'))
  return (all.find((e) => e.textContent?.trim() === text) as HTMLElement) || null
}

describe('MissingPacksDialog', () => {
  it('open 为 false 时不渲染任何内容', () => {
    act(() => {
      root.render(
        <MissingPacksDialog open={false} missing={[GROUP]} onClose={vi.fn()} onOpenManager={vi.fn()} />
      )
    })
    expect(document.querySelector('body > div.fixed.inset-0')).toBeNull()
  })

  it('open 为 true 时渲染标题、缺失包与受影响模块', () => {
    mount()
    const text = document.body.textContent || ''
    expect(text).toContain('缺少功能模块包')
    expect(text).toContain('网页自动化')
    expect(text).toContain('512 MB')
    // 受影响模块用中文模块名而不是内部类型名
    expect(text).toContain('点击元素')
    expect(text).not.toContain('click_element')
  })

  it('点遮罩不关闭弹窗（避免随手一点就消失，看起来像没弹过）', () => {
    const { onClose } = mount()
    click(overlay())
    expect(onClose).not.toHaveBeenCalled()
  })

  it('遮罩点击不向外冒泡，避免连带关闭外层对话框', () => {
    const outer = vi.fn()
    container.addEventListener('click', outer)
    mount()
    click(overlay())
    expect(outer).not.toHaveBeenCalled()
  })

  it('点「稍后再说」可关闭', () => {
    const { onClose } = mount()
    const btn = findByText('稍后再说')
    expect(btn).not.toBeNull()
    click(btn!)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('点右上角关闭按钮可关闭', () => {
    const { onClose } = mount()
    // 头部的图标按钮：遮罩内第一个无文本的 button
    const iconBtn = Array.from(document.body.querySelectorAll('button'))
      .find((b) => (b.textContent || '').trim() === '')
    expect(iconBtn).toBeDefined()
    click(iconBtn!)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('点「打开功能包管理器」触发回调', () => {
    const { onOpenManager } = mount()
    const btn = findByText('打开功能包管理器')
    expect(btn).not.toBeNull()
    click(btn!)
    expect(onOpenManager).toHaveBeenCalledTimes(1)
  })

  it('后端未给出功能包详情时给出兜底下载入口，而不是空白块', () => {
    mount({ missing: [{ alternatives: [], module_types: ['excel_read_range'] }] })
    const text = document.body.textContent || ''
    expect(text).toContain('未能取到该功能包的详细信息')
    const downloads = Array.from(document.body.querySelectorAll('button'))
      .filter((b) => (b.textContent || '').includes('下载'))
    expect(downloads.length).toBeGreaterThan(0)
  })

  it('多个备选包时提示任装其一', () => {
    mount({
      missing: [{
        alternatives: [
          { id: 'a', name: '包A', size_mb: 10 },
          { id: 'b', name: '包B', size_mb: 20 },
        ],
        module_types: ['click_element'],
      }],
    })
    expect(document.body.textContent).toContain('以下功能包任装其一即可满足')
  })
})
