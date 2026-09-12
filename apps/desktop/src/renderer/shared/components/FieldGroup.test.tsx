import { afterEach, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { FieldGroup } from './FieldGroup'
afterEach(cleanup)
it('puts the description on the named group without assigning duplicate input ids', () => {
  render(<FieldGroup legend="选择资源" error="至少选择一个"><label><input type="checkbox" id="a" />资源 A</label><label><input type="checkbox" id="b" />资源 B</label></FieldGroup>)
  expect(screen.getByRole('group', { name: '选择资源' })).toHaveAccessibleDescription('至少选择一个')
  expect(screen.getAllByRole('checkbox').map(el => el.id)).toEqual(['a', 'b'])
})
it('supports native group disabling and hint without an error announcement', () => {
  render(<FieldGroup legend="只查看" hint="暂不可编辑" disabled><input type="checkbox" aria-label="资源" /></FieldGroup>)
  expect(screen.getByRole('checkbox')).toBeDisabled()
  expect(screen.getByRole('group')).toHaveAccessibleDescription('暂不可编辑')
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})
