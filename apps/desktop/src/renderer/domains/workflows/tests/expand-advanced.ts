import { fireEvent, screen } from '@testing-library/react'

/** 配置面板的高级区默认折叠；需要操作高级字段的测试先展开。 */
export function expandAdvanced() {
  const toggle = screen.queryByRole('button', { name: /高级设置/ })
  if (toggle?.getAttribute('aria-expanded') === 'false') fireEvent.click(toggle)
}
