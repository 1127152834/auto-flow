import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const index = readFileSync(join(__dirname, 'index.css'), 'utf8')
const controls = readFileSync(join(__dirname, 'controls.css'), 'utf8')
const webrpa = readFileSync(join(__dirname, '../domains/workflows/styles/webrpa.css'), 'utf8')
const rule = (mode: string, selector: string) => index.split('\n').find(line => line.includes(`:root[data-motion="${mode}"] ${selector}`) && line.includes('{')) ?? ''

describe('data-motion CSS contract', () => {
  it('does not let the OS media query decide the motion level', () => {
    for (const css of [index, controls, webrpa]) expect(css).not.toContain('prefers-reduced-motion')
  })

  it('reduce keeps short transitions and stops looping animations', () => {
    const base = rule('reduce', '*')
    expect(base).toContain('transition-duration: var(--motion-fast) !important')
    expect(base).toContain('animation-iteration-count: 1 !important')
  })

  it('off zeroes animation and transition', () => {
    const base = rule('off', '*')
    expect(base).toContain('animation-duration: 0.001ms !important')
    expect(base).toContain('transition-duration: 0.001ms !important')
    expect(base).toContain('animation-iteration-count: 1 !important')
    expect(base).toContain('scroll-behavior: auto !important')
  })

  it.each(['reduce', 'off'])('%s disables every looping animation class', mode => {
    for (const selector of ['.animate-pulse', '.animate-spin', '.animate-ping', '.animate-pulse-ring', '.animate-soft-float', '.animate-spin-smooth', '.af-spinner', '.spinner', '.skeleton', '.skeleton-wave', '.status-dot-running', '.progress-indeterminate::after', '.webrpa-logo-r-pill', '[style*="infinite"]']) {
      expect(index, selector).toContain(`:root[data-motion="${mode}"] ${selector}`)
    }
    expect(rule(mode, '.animate-spin')).toContain('animation: none !important')
  })

  it('every infinite animation in webrpa.css is covered by a suppression selector', () => {
    const covered = ['.animate-pulse-ring', '.animate-soft-float', '.animate-spin-smooth', '.skeleton', '.skeleton-wave', '.status-dot-running', '.progress-indeterminate::after', '.spinner', '.webrpa-logo-letter-w', '.webrpa-logo-letter-e', '.webrpa-logo-letter-b', '.webrpa-logo-r-pill']
    const infinite = [...webrpa.replace(/\/\*[\s\S]*?\*\//g, '').matchAll(/([^{}]+)\{[^{}]*infinite[^{}]*\}/g)].flatMap(m => m[1].split(',').map(s => s.trim()).filter(Boolean))
    for (const selector of infinite) expect(covered, selector).toContain(selector)
  })
})
