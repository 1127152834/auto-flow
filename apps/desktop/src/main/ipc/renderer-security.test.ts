// @vitest-environment node
import { expect, it } from 'vitest'
import { isTrustedRenderer } from './renderer-security'

it.each([
  ['file:///Applications/AutoFlow/index.html', 'file:///Applications/AutoFlow/index.html#/projects', true],
  ['file:///Applications/AutoFlow/studio.html', 'file:///Applications/AutoFlow/studio.html?projectId=qa#workflow', true],
  ['http://localhost:5173/', 'http://localhost:5173/?view=main#/projects', true],
  ['http://localhost:5173/studio.html', 'http://localhost:5173/studio.html?view=automation-studio', true],
  ['http://localhost:5173/', 'http://localhost:5174/', false],
  ['http://localhost:5173/', 'http://localhost.evil.invalid:5173/', false],
  ['http://localhost:5173/', 'http://user:secret@localhost:5173/', false],
  ['file:///Applications/AutoFlow/index.html', 'file:///Applications/AutoFlow/studio.html', false],
  ['file:///Applications/AutoFlow/index.html', 'file:///Applications/AutoFlow/index.html/../other.html', false],
  ['file:///Applications/AutoFlow/index.html', 'file:///Applications/AutoFlow/index.html%00', false],
  ['file:///Applications/AutoFlow/index.html', 'about:blank', false],
  ['file:///Applications/AutoFlow/index.html', 'invalid-url', false],
])('checks the exact entry document %s vs %s', (entry, url, allowed) => {
  const frame = { url }
  const event = { sender: { id: 1, mainFrame: frame }, senderFrame: frame }
  expect(isTrustedRenderer(event, entry)).toBe(allowed)
  expect(isTrustedRenderer({ ...event, senderFrame: { url } }, entry)).toBe(false)
  expect(isTrustedRenderer({ ...event, senderFrame: null }, entry)).toBe(false)
})
