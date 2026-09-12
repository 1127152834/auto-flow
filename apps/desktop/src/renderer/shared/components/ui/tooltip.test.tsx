import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, it, expect } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { Tooltip, TooltipProvider, TooltipTrigger, TooltipContent } from './tooltip'
afterEach(cleanup)
it('opens on keyboard focus while retaining the trigger accessible name', async () => {
 const user = userEvent.setup()
 render(<TooltipProvider><Tooltip><TooltipTrigger aria-label="帮助">?</TooltipTrigger><TooltipContent>字段说明</TooltipContent></Tooltip></TooltipProvider>)
 await user.tab(); expect(await screen.findByRole('tooltip')).toHaveTextContent('字段说明')
 expect(screen.getByRole('button',{name:'帮助'})).toHaveFocus()
 await user.keyboard('{Escape}'); await waitFor(()=>expect(screen.queryByRole('tooltip')).not.toBeInTheDocument())
})
