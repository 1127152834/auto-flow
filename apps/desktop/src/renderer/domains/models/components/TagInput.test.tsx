import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {afterEach,it,expect} from 'vitest'
import {useState} from 'react'
import '@testing-library/jest-dom/vitest'
import {TagInput} from './TagInput'
afterEach(cleanup)
it('commits separators and blur without consuming IME Enter or losing existing tags',async()=>{
 const user=userEvent.setup()
 function Example(){const [value,setValue]=useState(['已有']),[draft,setDraft]=useState('');return <><TagInput value={value} draft={draft} onValueChange={setValue} onDraftChange={setDraft} aria-label="标签"/><button>外部</button><output>{value.join('|')}</output></>}
 render(<Example/>);const input=screen.getByRole('textbox')
 await user.type(input,'中文，');expect(screen.getByRole('status')).toHaveTextContent('已有|中文')
 await user.type(input,'中文');await user.keyboard('{Enter}');expect(screen.getByRole('status')).toHaveTextContent(/^已有\|中文$/)
 await user.type(input,'输入中');fireEvent.keyDown(input,{key:'Enter',isComposing:true});expect(input).toHaveValue('输入中')
 await user.click(screen.getByRole('button',{name:'外部'}));expect(screen.getByRole('status')).toHaveTextContent('已有|中文|输入中')
})
