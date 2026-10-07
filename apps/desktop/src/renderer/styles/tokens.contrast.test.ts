import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const css = readFileSync(join(__dirname, 'tokens.css'), 'utf8')

function token(name: string): string {
  const m = css.match(new RegExp(String.raw`--${name}:\s*(#[0-9a-fA-F]{6})\s*;`))
  if (!m) throw new Error(`tokens.css 缺少颜色令牌 --${name}`)
  return m[1]
}

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

const surfaces = ['color-canvas', 'color-surface', 'color-surface-subtle', 'color-surface-hover']
const texts = ['color-ink', 'color-muted', 'color-subtle']
const statuses = ['danger', 'warning', 'success', 'info']

describe('令牌对比度（浅色）', () => {
  for (const t of texts) {
    for (const s of surfaces) {
      it(`--${t} 在 --${s} 上 >= 4.5:1`, () => {
        const ratio = contrast(token(t), token(s))
        expect(ratio, `--${t} 对 --${s} 仅 ${ratio.toFixed(2)}:1`).toBeGreaterThanOrEqual(4.5)
      })
    }
  }
  for (const k of statuses) {
    for (const t of [`color-${k}`, `color-${k}-strong`]) {
      it(`--${t} 在 --color-${k}-soft 上 >= 4.5:1`, () => {
        const ratio = contrast(token(t), token(`color-${k}-soft`))
        expect(ratio, `--${t} 对 --color-${k}-soft 仅 ${ratio.toFixed(2)}:1`).toBeGreaterThanOrEqual(4.5)
      })
    }
  }
  it('动效令牌齐全', () => {
    for (const m of ['motion-fast: 120ms', 'motion-base: 180ms', 'motion-slow: 280ms', 'motion-loop: 1.2s', 'ease-standard:'])
      expect(css).toContain(`--${m}`)
  })
})
