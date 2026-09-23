import {afterEach, expect, it, vi} from 'vitest'
vi.hoisted(() => {
  const values = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key),
  })
})
import {modelApi} from '../api'
import {configureStudioConnection} from '../api/config'

let restore: (() => void) | undefined

afterEach(() => {
  restore?.()
  window.history.replaceState({}, '', '/studio.html')
})

function connect(providerId: string | null, items: unknown) {
  window.history.replaceState({}, '', '/studio.html?projectId=project')
  restore = configureStudioConnection('http://model.test', async input => {
    const url = new URL(String(input))
    return Response.json(url.pathname.endsWith('/options') ? {items} : {
      defaultResources: {profileId: null, modelProviderId: providerId},
    })
  })
}

it('resolves only the selected project provider using the existing option order', async () => {
  connect('selected', [
    {id:'global-first',providerId:'other'},
    {id:'selected-first',providerId:'selected'},
    {id:'selected-second',providerId:'selected'},
  ])
  await expect(modelApi.projectDefault()).resolves.toEqual({success:true,data:{modelId:'selected-first'}})
})

it.each([null, 'deleted'])('does not substitute another provider when default is %s', async providerId => {
  connect(providerId,[{id:'global-first',providerId:'other'}])
  await expect(modelApi.projectDefault()).resolves.toMatchObject({success:false})
})

it.each([null, {}, [null], [{providerId:'selected'}]])('rejects malformed options %j', async items => {
  connect('selected',items)
  await expect(modelApi.projectDefault()).resolves.toMatchObject({success:false,error:'主应用模型列表响应无效'})
})

it('standalone has no project default and performs no project request', async () => {
  window.history.replaceState({}, '', '/studio.html')
  restore = configureStudioConnection('http://model.test',async()=>{throw new Error('unexpected request')})
  await expect(modelApi.projectDefault()).resolves.toEqual({success:true,data:null})
})
