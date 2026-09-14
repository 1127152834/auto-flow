import {afterEach, expect, it} from 'vitest'
import {useWorkflowStore as store} from '../editor-store'
const originalLimit=store.getState().maxLogCount
const row={level:'info' as const,message:'同一节点循环输出',timestamp:'2020-01-02T03:04:05Z',nodeId:'node'}
afterEach(()=>{store.setState({logs:[],maxLogCount:originalLimit})})
it('preserves service identity and first payload across duplicate batches',()=>{
 store.setState({logs:[]})
 store.getState().addLogBatch([{...row,id:'service-1',details:{value:1}},{...row,id:'service-1'}])
 store.getState().addLogBatch([{...row,id:'service-1',message:'迟到变更'}])
 expect(store.getState().logs).toEqual([{...row,id:'service-1',details:{value:1}}])
})
it('retains distinct loop executions with identical contents and timestamps',()=>{
 store.setState({logs:[]})
 store.getState().addLogBatch([{...row,id:'iteration-1'},{...row,id:'iteration-2'}])
 expect(store.getState().logs.map(log=>log.id)).toEqual(['iteration-1','iteration-2'])
})
it('does not deduplicate legacy or local entries without service identity',()=>{
 store.setState({logs:[]})
 store.getState().addLogBatch([row,row,{...row,id:''}])
 expect(new Set(store.getState().logs.map(log=>log.id)).size).toBe(3)
})
it('deduplicates retained rows before capacity trimming and allows replay after clear',()=>{
 store.setState({logs:[],maxLogCount:2})
 store.getState().addLogBatch([{...row,id:'a'},{...row,id:'b'}])
 store.getState().addLogBatch([{...row,id:'a'},{...row,id:'c'}])
 expect(store.getState().logs.map(log=>log.id)).toEqual(['b','c'])
 store.getState().clearLogs()
 store.getState().addLogBatch([{...row,id:'a'}])
 expect(store.getState().logs.map(log=>log.id)).toEqual(['a'])
})
