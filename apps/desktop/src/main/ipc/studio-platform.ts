import { isAbsolute } from 'node:path'
import type { StudioPlatformAction, StudioPlatformActionResult } from '../../shared/studio-platform'
import type { DesktopResult } from '../../shared/settings'

type Event = { sender: { id: number; mainFrame: object }; senderFrame: object | null }
type Dependencies = {
  allowed(event: Event): boolean
  writeText(value: string): void
  readText(): string
  writeImage(path: string): boolean
  beep(): void
  notify(request: Extract<StudioPlatformAction, {action:'notification'}>): void
  openPath(path: string): Promise<string>
}

const failure = (code:string,message:string):DesktopResult<StudioPlatformActionResult> => ({ok:false,error:{code,message}})

export function createStudioPlatformActionHandler(dependencies:Dependencies) {
  return async (event:Event, raw:unknown):Promise<DesktopResult<StudioPlatformActionResult>> => {
    if (!dependencies.allowed(event)) return failure('UNAUTHORIZED_WINDOW','当前窗口不能执行工作台平台操作。')
    if (!raw || typeof raw !== 'object' || Array.isArray(raw) || typeof (raw as {action?:unknown}).action !== 'string') return failure('INVALID_PLATFORM_ACTION','平台操作参数无效。')
    const request=raw as Record<string,unknown>, action=request.action
    try {
      if(action==='clipboard_write_text'){
        if(typeof request.text!=='string'||!request.text)return failure('INVALID_PLATFORM_ACTION','剪贴板文本不能为空。')
        dependencies.writeText(request.text);return {ok:true,value:{}}
      }
      if(action==='clipboard_read_text')return {ok:true,value:{value:dependencies.readText()}}
      if(action==='clipboard_write_image'){
        if(typeof request.path!=='string'||!isAbsolute(request.path)||!dependencies.writeImage(request.path))return failure('INVALID_PLATFORM_ACTION','剪贴板图片路径无效或无法读取。')
        return {ok:true,value:{}}
      }
      if(action==='beep'){
        if(!Number.isSafeInteger(request.count)||Number(request.count)<0||Number(request.count)>100||typeof request.interval!=='number'||!Number.isFinite(request.interval)||request.interval<0||request.interval>60)return failure('INVALID_PLATFORM_ACTION','提示音参数无效。')
        for(let index=0;index<Number(request.count);index++){
          dependencies.beep()
          if(index+1<Number(request.count)&&request.interval>0)await new Promise(resolve=>setTimeout(resolve,request.interval as number*1000))
        }
        return {ok:true,value:{}}
      }
      if(action==='notification'){
        if(typeof request.title!=='string'||!request.title||typeof request.message!=='string'||!request.message||typeof request.duration!=='number'||!Number.isFinite(request.duration)||request.duration<=0||request.duration>3600||typeof request.playSound!=='boolean')return failure('INVALID_PLATFORM_ACTION','系统通知参数无效。')
        dependencies.notify(request as Extract<StudioPlatformAction,{action:'notification'}>)
        return {ok:true,value:{}}
      }
      if(action==='open_path'){
        if(typeof request.path!=='string'||!isAbsolute(request.path))return failure('INVALID_PLATFORM_ACTION','打开路径无效。')
        const error=await dependencies.openPath(request.path)
        return error?failure('PLATFORM_ACTION_FAILED',error):{ok:true,value:{}}
      }
      return failure('INVALID_PLATFORM_ACTION','不支持的平台操作。')
    }catch{return failure('PLATFORM_ACTION_FAILED','系统未能完成平台操作。')}
  }
}
