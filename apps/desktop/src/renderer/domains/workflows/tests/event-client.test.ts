import { afterEach, expect, it, vi } from 'vitest'
import { StudioEventClient } from '../api/event-client'
import { configureMock, emitMockEvent, mockSnapshot } from '../api/mock-server'
afterEach(()=>configureMock({offline:false,disconnect:true}))
it('continues from its sequence after disconnect, without duplicate listener calls or a fake completed event',async()=>{
  const client=new StudioEventClient('http://autoflow-studio.mock')
  const received=vi.fn(),completed=vi.fn()
  client.on('test:resume',received);client.on('test:resume',received);client.on('execution:completed',completed)
  try {
    await vi.waitFor(()=>expect(client.connected).toBe(true))
    emitMockEvent('test:resume',{sequence:mockSnapshot().sequence+1})
    await vi.waitFor(()=>expect(received).toHaveBeenCalledTimes(1))
    configureMock({disconnect:true});emitMockEvent('test:resume',{value:'during disconnect'})
    await vi.waitFor(()=>expect(received).toHaveBeenCalledTimes(2),{timeout:2500})
    expect(completed).not.toHaveBeenCalled()
    client.off('test:resume',received);emitMockEvent('test:resume',{})
    await new Promise(resolve=>setTimeout(resolve,10));expect(received).toHaveBeenCalledTimes(2)
  } finally {client.disconnect()}
})
