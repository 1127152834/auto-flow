import { readFile, stat } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { resolve, relative, isAbsolute, join } from 'node:path'
import { pathToFileURL } from 'node:url'

const hash=value=>createHash('sha256').update(value).digest('hex')
const outside=(root,path)=>{const part=relative(root,path);return part==='..'||part.startsWith('../')||isAbsolute(part)}

// Structural provenance checks only. Business assertions and visual review remain separate gates.
export async function verifyGalleryBaseline({manifest,maps,evidenceRoot,requiredStates=[]}) {
 const errors=[],sources=new Map(),pages=new Set(),states=new Set();let sourcesChecked=0,pendingEvidence=0;
 try {if(hash(await readFile(resolve(manifest.sourceRoot,manifest.gallery)))!==manifest.gallerySha256)errors.push('gallery hash mismatch')}catch{errors.push('gallery missing')}
 for(const entry of manifest.entries){
  const path=resolve(manifest.sourceRoot,entry.source);
  if(sources.has(path)){errors.push(`duplicate source: ${entry.source}`);continue}
  sources.set(path,entry);if(outside(manifest.sourceRoot,path)){errors.push(`outside source root: ${entry.source}`);continue}
  try{const bytes=await readFile(path);sourcesChecked++;if(hash(bytes)!==entry.sha256)errors.push(`source hash mismatch: ${entry.source}`);if(bytes.length<24||bytes.subarray(0,8).toString('hex')!=='89504e470d0a1a0a'||bytes.readUInt32BE(16)!==entry.width||bytes.readUInt32BE(20)!==entry.height)errors.push(`source dimensions mismatch: ${entry.source}`)}catch{errors.push(`source missing: ${entry.source}`)}
 }
 for(const map of maps){
  for(const page of [...map.pages,...(map.supplementalStates??[])]){
   if(pages.has(page.id))errors.push(`duplicate page: ${page.id}`);pages.add(page.id);states.add(page.id);
   if(page.source&&!sources.has(resolve(map.sourceRoot??manifest.sourceRoot,page.source)))errors.push(`unknown source: ${page.source}`);
   const evidence=page.evidence==null?[]:Array.isArray(page.evidence)?page.evidence:[page.evidence];
   if(evidence.length===0){pendingEvidence++;if(page.status==='passed')errors.push(`passed without evidence: ${page.id}`)}
   for(const item of evidence){if(typeof item!=='string'||!item.trim()){errors.push(`invalid evidence reference: ${page.id}`);continue}const path=resolve(evidenceRoot,item);if(outside(evidenceRoot,path)){errors.push(`outside evidence root: ${item}`);continue}try{if(!(await stat(path)).isFile())errors.push(`evidence not a file: ${item}`)}catch{errors.push(`evidence missing: ${item}`)}}
  }
 }
 for(const state of requiredStates)if(!states.has(state))errors.push(`required state missing: ${state}`);
 return {kind:'source-and-evidence-structure',sourcesChecked,pagesChecked:pages.size,pendingEvidence,applicationAcceptance:'not-evaluated',errors};
}

if(process.argv[1]&&import.meta.url===pathToFileURL(resolve(process.argv[1])).href){
 const root=resolve(import.meta.dirname,'..'),base=join(root,'docs/project-management/design-alignment');
 const manifest=JSON.parse(await readFile(join(base,'gallery-baseline/source-manifest.json'),'utf8'));
 const stage=process.argv[2]??'gallery-r1';if(!/^gallery-r[123]$/.test(stage))throw new Error('expected gallery-r1, gallery-r2 or gallery-r3');
 const evidenceRoot=join(base,'acceptance',stage),map=JSON.parse(await readFile(join(evidenceRoot,'page-map.json'),'utf8'));
 const requiredStates=stage==='gallery-r1'?['projects-recent','projects-all','data-directory','records','filter','create-table','loading','empty','no-match','refresh-error','query-validation','sort','columns','operation-recovery']:[];
 const result=await verifyGalleryBaseline({manifest,maps:[map],evidenceRoot,requiredStates});console.log(JSON.stringify(result,null,2));process.exitCode=result.errors.length?1:0;
}
