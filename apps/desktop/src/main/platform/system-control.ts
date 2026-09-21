import type { StudioPlatformAction } from '../../shared/studio-platform'

type SystemControl = Extract<StudioPlatformAction,{action:'system_control'}>
type Run = (file:string,args:string[])=>Promise<string>

export function createSystemControlActions(platform:NodeJS.Platform,run:Run){
  return {
    execute(request:SystemControl):Promise<string>{
      if(platform!=='win32')return Promise.resolve('此功能仅支持 Windows 系统')
      if(request.operation==='sleep')return run('powershell.exe',['-NoProfile','-NonInteractive','-Command',"Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)"])
      const args=request.operation==='shutdown'?['/s','/t',String(request.delay)]
        :request.operation==='restart'?['/r','/t',String(request.delay)]
          :request.operation==='logout'?['/l']
            :['/h']
      if(request.force&&['shutdown','restart'].includes(request.operation))args.push('/f')
      return run('shutdown.exe',args)
    },
    lock():Promise<string>{
      return platform==='win32'
        ?run('rundll32.exe',['user32.dll,LockWorkStation'])
        :Promise.resolve('此功能仅支持 Windows 系统')
    },
  }
}
