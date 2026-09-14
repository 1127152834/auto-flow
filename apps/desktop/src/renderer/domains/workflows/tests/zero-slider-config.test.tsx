import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
import {TextToSpeechConfig} from '../components/config-panels/BasicModuleConfigs'
import {SoundTriggerConfig} from '../components/config-panels/TriggerModuleConfigs'
import {useWorkflowStore,type NodeData} from '../editor-store'
afterEach(()=>{cleanup();useWorkflowStore.getState().clearWorkflow()})
it.each([0,0.5,1])('speech volume %s is labelled and preserved',volume=>{
 const onChange=vi.fn();const data:NodeData={moduleType:'text_to_speech',label:'朗读',volume}
 const view=render(<TextToSpeechConfig data={data} onChange={onChange}/>)
 const input=screen.getByRole('slider',{name:`音量 (${Math.round(volume*100)}%)`}) as HTMLInputElement
 expect(input.value).toBe(String(volume));expect(onChange).not.toHaveBeenCalled()
 fireEvent.change(input,{target:{value:'0'}})
 if(volume!==0)expect(onChange).toHaveBeenCalledWith('volume',0)
 view.rerender(<TextToSpeechConfig data={{...data,volume:0}} onChange={onChange}/>);expect((screen.getByRole('slider',{name:'音量 (0%)'}) as HTMLInputElement).value).toBe('0')
})
it.each([0,50,100])('sound threshold %s is labelled and preserved',volumeThreshold=>{
 const onChange=vi.fn();const data:NodeData={moduleType:'sound_trigger',label:'触发',volumeThreshold}
 const view=render(<SoundTriggerConfig data={data} onChange={onChange}/>)
 const input=screen.getByRole('slider',{name:'音量阈值 (%)'}) as HTMLInputElement
 expect(input.value).toBe(String(volumeThreshold));expect(onChange).not.toHaveBeenCalled()
 fireEvent.change(input,{target:{value:'0'}})
 if(volumeThreshold!==0)expect(onChange).toHaveBeenCalledWith('volumeThreshold',0)
 view.rerender(<SoundTriggerConfig data={{...data,volumeThreshold:0}} onChange={onChange}/>);expect((screen.getByRole('slider',{name:'音量阈值 (%)'}) as HTMLInputElement).value).toBe('0')
})
it('applies missing speech defaults without writing to the draft and names all sliders',()=>{
 const onChange=vi.fn();render(<TextToSpeechConfig data={{label:'朗读',moduleType:'text_to_speech'}} onChange={onChange}/>)
 for(const name of ['语速 (1x)','音调 (1)','音量 (100%)'])expect((screen.getByRole('slider',{name}) as HTMLInputElement).value).toBe('1')
 expect(onChange).not.toHaveBeenCalled()
})
it('applies only the missing sound threshold default',()=>{
 const onChange=vi.fn();render(<SoundTriggerConfig data={{label:'触发',moduleType:'sound_trigger'}} onChange={onChange}/>)
 expect((screen.getByRole('slider',{name:'音量阈值 (%)'}) as HTMLInputElement).value).toBe('50');expect(onChange).not.toHaveBeenCalled()
})
it.each([['text_to_speech','volume',0.5],['sound_trigger','volumeThreshold',50]] as const)('%s zero survives undo, redo and serialization', (type,field,initial)=>{
 const store=useWorkflowStore.getState();store.addNode(type,{x:0,y:0},{[field]:initial});const id=useWorkflowStore.getState().nodes[0].id
 store.updateNodeData(id,{[field]:0});store.undo();expect(useWorkflowStore.getState().nodes[0].data[field]).toBe(initial)
 store.redo();expect(useWorkflowStore.getState().nodes[0].data[field]).toBe(0)
 const saved=store.exportWorkflow();store.clearWorkflow();expect(store.importWorkflow(saved)).toBe(true);expect(useWorkflowStore.getState().nodes[0].data[field]).toBe(0)
})
