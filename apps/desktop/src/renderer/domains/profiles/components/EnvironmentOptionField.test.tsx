import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, it, expect, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { FormProvider, useForm } from 'react-hook-form'
import { EnvironmentOptionField } from './EnvironmentOptionField'
import type { ProfileFormValues } from '../form-schema'
beforeEach(()=>{vi.stubGlobal('ResizeObserver',class{observe(){} unobserve(){} disconnect(){}});Element.prototype.scrollIntoView=vi.fn()})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
it('searches the supplied directory and keeps custom editing with focus return',async()=>{
 const user=userEvent.setup()
 function Example(){const form=useForm<ProfileFormValues>({defaultValues:{locale:''}});return <FormProvider {...form}><EnvironmentOptionField name="locale" label="语言" hint="本地目录" options={[{value:'zh-CN',label:'简体中文'}]}/><output>{form.watch('locale')}</output></FormProvider>}
 render(<Example/>);const input=screen.getByRole('combobox',{name:'语言'});expect(input.tagName).toBe('INPUT')
 await user.clear(input);await user.type(input,'中文');await user.click(screen.getByRole('option',{name:'简体中文'}));expect(screen.getByRole('status')).toHaveTextContent('zh-CN')
 await user.clear(input);await user.type(input,'自定义');await user.click(screen.getByRole('option',{name:'自定义…'}));expect(screen.getByRole('textbox',{name:'语言'})).toHaveFocus()
 await user.clear(screen.getByRole('textbox'));await user.type(screen.getByRole('textbox'),'x-custom');await user.click(screen.getByRole('button',{name:'选择语言预设'}));expect(screen.getByRole('combobox')).toHaveFocus();expect(screen.getByRole('status')).toHaveTextContent('x-custom')
})
