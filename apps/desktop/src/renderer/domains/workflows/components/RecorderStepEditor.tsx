import {useState} from 'react'
import type {RecEvent} from '../lib/recordingGeneration'
import {VariableInput} from './controls/variable-input'

/** Approved recording review fields; generation still uses the frozen source converter. */
export function RecorderStepEditor({event,onApply,onCancel}:{event:RecEvent;onApply:(event:RecEvent)=>void;onCancel:()=>void}) {
  const [draft,setDraft]=useState(event)
  const [frame,setFrame]=useState(JSON.stringify(event._frame ?? {main:true}))
  const [values,setValues]=useState(JSON.stringify(event.values ?? []))
  const [error,setError]=useState('')
  const text=(field:'selector'|'targetSelector'|'url'|'key'|'filePath',label:string)=> <label className="block">{label}<VariableInput aria-label={label} value={draft[field]||''} onChange={value=>setDraft({...draft,[field]:value})}/></label>
  const apply=()=>{
    try {
      if(['click','dblclick','input','select','check','drag','upload'].includes(draft.type)&&!draft.selector?.trim())throw Error('元素选择器不能为空')
      if(draft.type==='navigate'&&draft.navigation!=='ignore'&&!draft.url?.trim())throw Error('页面地址不能为空')
      if(draft.type==='keypress'&&!draft.key?.trim())throw Error('按键不能为空')
      const parsed=JSON.parse(frame)
      if(!parsed || Array.isArray(parsed) || typeof parsed!=='object' || (parsed.index!==undefined&&(!Number.isSafeInteger(parsed.index)||parsed.index<0)) || (parsed.selector!==undefined&&typeof parsed.selector!=='string') || (parsed.name!==undefined&&typeof parsed.name!=='string') || (parsed.main!==undefined&&typeof parsed.main!=='boolean'))throw Error('框架配置格式无效')
      const selected=JSON.parse(values)
      if(!Array.isArray(selected)||selected.some(value=>typeof value!=='string'))throw Error('多选值必须是字符串数组')
      if(draft.variableName&&!/^[A-Za-z_\u4e00-\u9fa5][\w\u4e00-\u9fa5]*$/.test(draft.variableName))throw Error('变量名格式无效')
      onApply({...draft,_frame:parsed,...(draft.type==='select'?{values:selected}:{}),...(draft.type==='input'?{needsValue:false}:{})})
    }catch(cause){setError(cause instanceof Error?cause.message:String(cause))}
  }
  return <div role="dialog" aria-label="编辑录制步骤" className="p-3 space-y-2 border rounded bg-[hsl(var(--card))] text-xs">
    <strong>编辑录制步骤：{event.type}</strong>
    {!['navigate','scroll'].includes(draft.type)&&text('selector','元素选择器')}
    {draft.type==='navigate'&&<>{text('url','页面地址')}<label>导航生成方式<select aria-label="导航生成方式" value={draft.navigation||'source'} onChange={e=>setDraft({...draft,navigation:e.target.value as RecEvent['navigation']})}><option value="source">沿用原版判断</option><option value="open">明确生成打开网页</option><option value="ignore">不生成导航节点</option></select></label></>}
    {['input','select'].includes(draft.type)&&<label className="block">输入值<VariableInput multiline aria-label="录制输入值" value={String(draft.value??'')} onChange={value=>setDraft({...draft,value})}/></label>}
    {draft.type==='input'&&<label className="block">保存为新变量（可选）<input aria-label="录制变量名" value={draft.variableName||''} onChange={e=>setDraft({...draft,variableName:e.target.value})}/></label>}
    {draft.type==='select'&&<label className="block">多选值 JSON<textarea aria-label="多选值 JSON" value={values} onChange={e=>setValues(e.target.value)}/></label>}
    {draft.type==='check'&&<label><input type="checkbox" checked={Boolean(draft.value)} onChange={e=>setDraft({...draft,value:e.target.checked})}/>勾选状态</label>}
    {draft.type==='keypress'&&text('key','按键')}
    {draft.type==='upload'&&text('filePath','上传文件路径')}
    {draft.type==='drag'&&text('targetSelector','目标选择器')}
    {(draft.type==='drag'?['endX','endY'] as const:draft.type==='scroll'?['dy'] as const:[]).map(field=><label key={field}>{field}<input aria-label={field} type="number" value={draft[field]??''} onChange={e=>setDraft({...draft,[field]:e.target.value===''?undefined:Number(e.target.value)})}/></label>)}
    <label className="block">框架配置 JSON<textarea aria-label="框架配置 JSON" value={frame} onChange={e=>setFrame(e.target.value)}/></label>
    {draft.sensitive&&<p>原密码未保留，请明确补值或引用已有变量。</p>}
    {error&&<p role="alert">{error}</p>}
    <button onClick={apply}>应用步骤修改</button><button onClick={onCancel}>取消步骤修改</button>
  </div>
}
