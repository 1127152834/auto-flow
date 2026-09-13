/** Mock file resource endpoints. Imported bytes stay in this browser's local mock storage. */
interface Asset { id: string; name: string; originalName: string; filename: string; folder: string; path: string; url: string; dataUrl: string; size: number; createdAt: string }
interface Library { assets: Asset[]; folders: string[] }
function read(kind: string): Library { return JSON.parse(localStorage.getItem(`autoflow:studio:mock:${kind}`) || '{"assets":[],"folders":[]}') }
function save(kind: string, library: Library) { localStorage.setItem(`autoflow:studio:mock:${kind}`, JSON.stringify(library)) }
export async function mockAssetRequest(path: string, method: string, params: URLSearchParams, body: Record<string, unknown>, form?: FormData): Promise<Response | undefined> {
  if (path === '/data-assets' || path.startsWith('/data-assets/')) return Response.json({ success: false, error: 'Excel 资源功能已从 AutoFlow Studio 移除' }, { status: 410 })
  const match = path.match(/^\/(image-assets)(?:\/(.*))?$/)
  if (!match) return undefined
  const [,kind,action=''] = match
  const library=read(kind)
  const json=(value:unknown,status=200)=>Response.json(value,{status})
  if (!action) return json(library.assets)
  if (action === 'folders') {
    if (method === 'GET') return json(library.folders)
    if (method === 'POST') {
      const folder=[body.parentPath,body.name].filter(Boolean).join('/')
      if (!body.name || library.folders.includes(folder)) return json({success:false,error:'文件夹名称为空或已存在'},409)
      library.folders.push(folder)
    } else if (method === 'DELETE') {
      const folder=String(body.folderPath)
      library.folders=library.folders.filter(f=>f!==folder&&!f.startsWith(folder+'/'))
      library.assets=library.assets.filter(a=>a.folder!==folder&&!a.folder.startsWith(folder+'/'))
    }
    save(kind,library); return json({success:true})
  }
  if (action === 'folders/rename') {
    const old=String(body.oldPath), renamed=old.split('/').slice(0,-1).concat(String(body.newName)).join('/')
    const rename=(p:string)=>p===old||p.startsWith(old+'/') ? renamed+p.slice(old.length):p
    library.folders=library.folders.map(rename); library.assets=library.assets.map(a=>({...a,folder:rename(a.folder)}));save(kind,library);return json({success:true})
  }
  if (action === 'upload') {
    const file=form?.get('file')
    if (!file || typeof file === 'string') return json({success:false,error:'请选择文件'},400)
    if (file.size > 2 * 1024 * 1024) return json({success:false,error:'Mock 单文件上限 2 MiB；真实后端接入后使用文件存储'},413)
    const dataUrl = typeof file.arrayBuffer === 'function' ? await (async () => {
      const bytes = new Uint8Array(await file.arrayBuffer())
      let binary = ''
      for (let offset = 0; offset < bytes.length; offset += 32768) binary += String.fromCharCode(...bytes.subarray(offset, offset + 32768))
      return `data:${file.type || 'application/octet-stream'};base64,${btoa(binary)}`
    })() : await new Promise<string>((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result));reader.onerror=()=>reject(reader.error);reader.readAsDataURL(file)})
    const id=crypto.randomUUID(),name=(file as File).name || id
    const asset={id,name,originalName:name,filename:name,folder:String(form?.get('folder') || ''),path:dataUrl,url:dataUrl,dataUrl,size:file.size,createdAt:new Date().toISOString(),uploadedAt:new Date().toISOString(),extension:name.split('.').at(-1) || ''}
    library.assets.push(asset);save(kind,library);return json(asset)
  }
  if (action === 'move') {
    library.assets=library.assets.map(a=>a.id===body.assetId?{...a,folder:String(body.targetFolder||'')}:a);save(kind,library);return json({success:true})
  }
  const [id,operation]=action.split('/')
  const asset=library.assets.find(a=>a.id===id)
  if (!asset) return json({success:false,error:'资源不存在'},404)
  if (method === 'DELETE') {library.assets=library.assets.filter(a=>a.id!==id);save(kind,library);return json({success:true})}
  if (operation === 'rename') {asset.name=params.get('newName')||asset.name;asset.originalName=asset.name;asset.filename=asset.name;save(kind,library);return json({success:true,...asset})}
  return json(asset)
}
