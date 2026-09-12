import { screen, waitFor } from '@testing-library/react'
import type userEvent from '@testing-library/user-event'
import { beforeEach, vi } from 'vitest'
/** jsdom lacks layout/pointer APIs; behavior is also checked in Electron. */
export function choiceTestEnvironment(){beforeEach(()=>{
 if (!globalThis.ResizeObserver) vi.stubGlobal('ResizeObserver',class{observe(){} unobserve(){} disconnect(){}})
 if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView=vi.fn()
 if (!Element.prototype.hasPointerCapture) Element.prototype.hasPointerCapture=()=>false
})}
export async function chooseOption(user:ReturnType<typeof userEvent.setup>, control:HTMLElement, value:string){
 control.focus()
 if(control instanceof HTMLInputElement){await user.clear(control);if(value)await user.type(control,value)}
 await user.keyboard('{ArrowDown}')
 const option=await waitFor(()=>{
  const found=screen.getAllByRole('option').find(item=>item.getAttribute('data-choice-value')===value)
  if(!found)throw new Error(`Visible choice not found: ${value}`)
  return found
 })
 await user.click(option)
}

export const choiceValue = (control: HTMLElement) => control.hasAttribute('data-choice-value') ? control.getAttribute('data-choice-value') : (control as HTMLInputElement).value
