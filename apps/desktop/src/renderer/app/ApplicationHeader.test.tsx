import '@testing-library/jest-dom/vitest'
import {cleanup,render,screen} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {afterEach,it,expect,vi} from 'vitest'
import {ApplicationHeader} from './ApplicationHeader'
afterEach(cleanup)
it('preserves the active route and keyboard navigation through the shared buttons',async()=>{
 const navigate=vi.fn(),user=userEvent.setup()
 const {rerender}=render(<ApplicationHeader route="profiles" onNavigate={navigate} status="connected"/> )
 expect(screen.getByRole('button',{name:'浏览器配置'})).toHaveAttribute('aria-current','page')
 const settings=screen.getByRole('button',{name:'设置'});settings.focus();await user.keyboard('{Enter}')
 expect(navigate).toHaveBeenCalledExactlyOnceWith('settings')
 rerender(<ApplicationHeader route="settings" onNavigate={navigate} status="offline"/> )
 expect(settings).toHaveAttribute('aria-current','page')
 expect(screen.getByRole('button',{name:'浏览器配置'})).not.toHaveAttribute('aria-current')
 expect(screen.getByRole('status')).toHaveTextContent('本地服务未连接')
})
