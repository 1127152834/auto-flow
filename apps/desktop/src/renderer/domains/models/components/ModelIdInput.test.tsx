import {useState} from 'react'
import {cleanup,render,screen} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {afterEach,it,expect,vi} from 'vitest'
import '@testing-library/jest-dom/vitest'
import {ModelIdInput} from './ModelIdInput'
import {choiceTestEnvironment} from '../../../shared/testing/choice-user'
choiceTestEnvironment();afterEach(cleanup)
it('renders accessible suggestions and follows parent resets instead of retaining a stale query',async()=>{
 const user=userEvent.setup(),change=vi.fn()
 const {rerender}=render(<ModelIdInput value="old" options={[]} onChange={change}/>)
 expect(screen.getByRole('combobox',{name:'模型标识'})).toHaveValue('old')
 rerender(<ModelIdInput value="new" options={[]} onChange={change}/>);expect(screen.getByRole('combobox')).toHaveValue('new')
 function Controlled(){const [value,setValue]=useState('');return <ModelIdInput value={value} options={[]} onChange={next=>{setValue(next);change(next)}}/>}
 rerender(<Controlled/>);await user.type(screen.getByRole('combobox'),'manual');expect(change).toHaveBeenLastCalledWith('manual')
})
