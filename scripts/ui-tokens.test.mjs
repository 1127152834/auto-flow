import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'

const path = new URL('../apps/desktop/src/renderer/styles/tokens.css', import.meta.url)
const css = existsSync(path) ? readFileSync(path, 'utf8') : ''
const values = Object.fromEntries([...css.matchAll(/--([\w-]+):\s*(#[\da-f]{6});/gi)].map(([, key, value]) => [key, value]))
function luminance(hex) {
  return [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4)
    .reduce((sum, v, i) => sum + v * [.2126, .7152, .0722][i], 0)
}
function contrast(a, b) {
  const [lo, hi] = [luminance(a), luminance(b)].sort((x, y) => x - y)
  return (hi + .05) / (lo + .05)
}
for (const [foreground, background, minimum] of [
  ['ink', 'surface', 4.5], ['muted', 'surface', 4.5], ['on-accent', 'clay', 4.5],
  ['danger', 'danger-soft', 4.5], ['success', 'success-soft', 4.5], ['warning', 'warning-soft', 4.5],
  ['control-border', 'surface', 3], ['control-border', 'canvas', 3], ['focus', 'surface', 3],
]) {
  test(`${foreground} against ${background} meets ${minimum}:1`, () => {
    assert.ok(values[`color-${foreground}`], `missing color-${foreground}`)
    assert.ok(values[`color-${background}`], `missing color-${background}`)
    assert.ok(contrast(values[`color-${foreground}`], values[`color-${background}`]) >= minimum)
  })
}
test('tokens define shared density, focus, scrolling and overlay motion', () => {
  for (const name of ['control-sm', 'control-md', 'focus-width', 'focus-offset', 'scrollbar-rail', 'scrollbar-thumb', 'motion-overlay', 'layer-modal', 'layer-step']) {
    assert.match(css, new RegExp(`--${name}:`), `missing ${name}`)
  }
})
