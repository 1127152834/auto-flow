import type {components} from '../../../shared/api/generated'
import {jsonCopy} from './jsScript'
export type BrowserScriptTarget=components['schemas']['StudioBrowserScriptTarget']
export type BrowserScriptContext=components['schemas']['StudioBrowserScriptContext']
export type BrowserScriptRequest=components['schemas']['StudioBrowserScriptRequest']
export type BrowserScriptState=components['schemas']['StudioBrowserScriptState']
const record=(value:unknown):value is Record<string,unknown>=>!!value && typeof value==='object' && !Array.isArray(value)
const text=(value:unknown):value is string=>typeof value==='string' && !!value.trim()
export function isBrowserScriptTarget(value:unknown):value is BrowserScriptTarget {
 return record(value) && text(value.browserSessionId) && text(value.pageId) && Number.isSafeInteger(value.revision) && Number(value.revision)>=0
}
export function sameScriptTarget(a:BrowserScriptTarget,b:BrowserScriptTarget){return a.browserSessionId===b.browserSessionId && a.pageId===b.pageId && a.revision===b.revision}
export function isBrowserScriptContext(value:unknown):value is BrowserScriptContext {
 return record(value) && typeof value.url==='string' && (value.activeRequestId===null || text(value.activeRequestId)) && isBrowserScriptTarget(value)
}
export function checkedBrowserScriptRequest(value:unknown):BrowserScriptRequest {
 if(!record(value) || !text(value.requestId) || !text(value.code) || !isBrowserScriptTarget(value.context) || !record(value.variables))throw new Error('脚本测试请求格式错误')
 if(Object.keys(value).some(key=>!['requestId','context','code','variables'].includes(key)) || Object.keys(value.context).some(key=>!['browserSessionId','pageId','revision'].includes(key)))throw new Error('脚本测试请求包含未知字段')
 const copied=jsonCopy(value)
 if(new TextEncoder().encode(JSON.stringify(copied)).byteLength>1024*1024)throw new Error('脚本测试请求超过1MiB，未执行')
 return copied as BrowserScriptRequest
}
export function isBrowserScriptState(value:unknown):value is BrowserScriptState {
 if(!record(value) || !text(value.requestId) || !isBrowserScriptTarget(value.context) || !['running','completed','failed','cancelled','expired'].includes(String(value.status)) || typeof value.hasResult!=='boolean' || !Object.hasOwn(value,'result') || !['browser','mock'].includes(String(value.executionKind)))return false
 if(value.status==='failed' || value.status==='expired'){if(!text(value.error))return false}else if(value.error!==null)return false
 if(value.status!=='completed' && value.hasResult)return false
 if(!value.hasResult && value.result!==null)return false
 try{jsonCopy(value.result)}catch{return false}
 return true
}
