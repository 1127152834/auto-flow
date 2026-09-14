import { beforeEach, expect, it, vi } from 'vitest'
import { readTableView, tableViewKey } from './record-return-state'
beforeEach(() => { const values = new Map<string,string>(); vi.stubGlobal('sessionStorage',{getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>values.set(key,value)}) })
it('defaults direct addresses to page one without inventing a record target',()=>{
  expect(readTableView(tableViewKey('w','p','t'))).toMatchObject({page:1,scrollY:0,visibleFieldIds:null})
  expect(readTableView(tableViewKey('w','p','t')).originRowKey).toBeUndefined()
})
it('isolates workspace preferences and preserves typed focus identity without an arbitrary return URL',()=>{
  const identity={workspaceKey:'w',projectId:'p',tableId:'t',datasetGeneration:'g'},key=tableViewKey('w','p','t')
  sessionStorage.setItem(key,JSON.stringify({identity,page:3,scrollY:420,visibleFieldIds:['f'],originRowKey:{type:'text',value:'001'},query:{filter:{type:'all',items:[]},orderBy:[]},returnUrl:'https://invalid.example'}))
  expect(readTableView(key)).toMatchObject({identity,page:3,scrollY:420,originRowKey:{type:'text',value:'001'}})
  expect(readTableView(key)).not.toHaveProperty('returnUrl')
  expect(readTableView(tableViewKey('other','p','t')).page).toBe(1)
})
it('rejects corrupt paging, query shape, scroll and noncanonical focus identities',()=>{
  const key=tableViewKey('w','p','t');sessionStorage.setItem(key,JSON.stringify({page:-1,scrollY:-2,originRowKey:{type:'integer',value:'001'},query:{filter:{type:'anything'},orderBy:[]}}))
  expect(readTableView(key)).toMatchObject({page:1,scrollY:0,query:{filter:{type:'all',items:[]},orderBy:[]}})
  expect(readTableView(key).originRowKey).toBeUndefined()
})
