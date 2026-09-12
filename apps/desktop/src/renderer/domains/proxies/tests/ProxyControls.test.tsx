import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, it, expect, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { LocationPicker } from '../components/ProxyDetailDrawer'
import { choiceTestEnvironment } from '../../../shared/testing/choice-user'
choiceTestEnvironment();afterEach(cleanup)
it('groups location choices, preserves the stable id and blocks unavailable choices',async()=>{
 const user=userEvent.setup(),submit=vi.fn()
 render(<LocationPicker open onOpenChange={()=>{}} busy={false} onSubmit={submit} locations={{stale:false,items:[{id:'tokyo',city:'东京',availability:'available'},{id:'osaka',city:'大阪',availability:'unavailable'}]}}/>)
 expect(screen.getByRole('radiogroup',{name:'可用地点'})).toBeInTheDocument()
 expect(screen.getByRole('radio',{name:/大阪/})).toBeDisabled()
 await user.click(screen.getByRole('radio',{name:/东京/}));await user.click(screen.getByRole('button',{name:'切换地点'}));expect(submit).toHaveBeenCalledWith('tokyo')
})
