import type {components} from '../../../shared/api/generated'
import type {ApiResponse} from '../api'

type PathResult = components['schemas']['StudioPathSelectionResult']
const object = (value:unknown):value is Record<string,unknown> => !!value && typeof value==='object' && !Array.isArray(value)
export function isPathSelectionRequest(value:unknown,kind:'file'|'folder'):boolean {
  if(!object(value) || Object.keys(value).some(key=>!['title','initialDir',...(kind==='file'?['fileTypes']:[])].includes(key)))return false
  if(['title','initialDir'].some(key=>value[key]!==undefined && value[key]!==null && typeof value[key]!=='string'))return false
  if(kind==='folder' || value.fileTypes==null)return true
  return Array.isArray(value.fileTypes) && value.fileTypes.every(pair=>Array.isArray(pair) && pair.length===2 && pair.every(part=>typeof part==='string'))
}
export function checkedPathSelection(result:ApiResponse<unknown>):ApiResponse<PathResult> {
  if(!result.success)return {...result,data:undefined}
  const value=result.data
  const invalid=()=>({success:false,error:'路径选择响应格式错误'})
  if(!object(value) || typeof value.success!=='boolean')return invalid()
  if(!(value.path===null || typeof value.path==='string'))return {success:false,error:'服务返回了无效路径'}
  if(['message','error'].some(key=>value[key]!=null && typeof value[key]!=='string'))return invalid()
  if(value.success && value.error)return invalid()
  if(!value.success && (value.path!==null || !(typeof value.error==='string' && value.error.trim()) && value.message!=='用户取消选择'))return invalid()
  if(!value.success && typeof value.error==='string' && value.error.trim())return {success:false,error:value.error}
  return {...result,data:{...value,success:value.success,path:value.path,message:typeof value.message==='string'?value.message:null,error:typeof value.error==='string'?value.error:null}}
}
