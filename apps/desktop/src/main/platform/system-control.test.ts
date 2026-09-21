// @vitest-environment node
import { expect, it, vi } from 'vitest'
import { createSystemControlActions } from './system-control'

it('maps approved system operations to argument-safe Windows commands',async()=>{
  const run=vi.fn(async()=>''),actions=createSystemControlActions('win32',run)
  await actions.execute({action:'system_control',operation:'restart',delay:15,force:true})
  await actions.execute({action:'system_control',operation:'hibernate',delay:0,force:true})
  await actions.lock()
  expect(run).toHaveBeenNthCalledWith(1,'shutdown.exe',['/r','/t','15','/f'])
  expect(run).toHaveBeenNthCalledWith(2,'shutdown.exe',['/h'])
  expect(run).toHaveBeenNthCalledWith(3,'rundll32.exe',['user32.dll,LockWorkStation'])
})

it('rejects source Windows-only actions on other platforms',async()=>{
  const run=vi.fn(async()=>''),actions=createSystemControlActions('darwin',run)
  await expect(actions.execute({action:'system_control',operation:'shutdown',delay:0,force:false})).resolves.toBe('此功能仅支持 Windows 系统')
  await expect(actions.lock()).resolves.toBe('此功能仅支持 Windows 系统')
  expect(run).not.toHaveBeenCalled()
})
