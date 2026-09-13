import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createHash } from 'node:crypto'
import { verifyGalleryBaseline } from './verify-gallery-baseline.mjs'

async function fixture(t) {
 const root=await mkdtemp(join(tmpdir(),'gallery-verification-'));t.after(()=>rm(root,{recursive:true,force:true}));
 const source=join(root,'source'),evidence=join(root,'evidence');await mkdir(source);await mkdir(evidence);
 const png=Buffer.alloc(24);Buffer.from('89504e470d0a1a0a','hex').copy(png);png.writeUInt32BE(1440,16);png.writeUInt32BE(1024,20);await writeFile(join(source,'screen.png'),png);await writeFile(join(source,'gallery.html'),'gallery');
 const hash=value=>createHash('sha256').update(value).digest('hex');
 return {manifest:{sourceRoot:source,gallery:'gallery.html',gallerySha256:hash('gallery'),entries:[{source:'screen.png',sha256:hash(png),width:1440,height:1024}]},maps:[{sourceRoot:source,pages:[{id:'records',source:'screen.png',evidence:null}],supplementalStates:[{id:'loading',evidence:null}]}],evidenceRoot:evidence,root};
}
test('checks sources without inventing application or visual acceptance',async t=>{const data=await fixture(t),result=await verifyGalleryBaseline(data);assert.deepEqual(result.errors,[]);assert.equal(result.sourcesChecked,1);assert.equal(result.pendingEvidence,2);assert.equal(result.applicationAcceptance,'not-evaluated')})
test('rejects source hash drift, dimensions and unknown mapped sources',async t=>{const data=await fixture(t);data.manifest.entries[0].width=10;data.manifest.entries[0].sha256='wrong';data.maps[0].pages.push({id:'unknown',source:'missing.png'});const result=await verifyGalleryBaseline(data);assert.equal(result.errors.length,3)})
test('does not allow a passed page without real evidence or missing required states',async t=>{const data=await fixture(t);data.maps[0].pages[0].status='passed';data.requiredStates=['saving'];const result=await verifyGalleryBaseline(data);assert.ok(result.errors.some(x=>x.includes('passed without evidence')));assert.ok(result.errors.some(x=>x.includes('saving')))})
test('rejects duplicate source and page identities and evidence traversal',async t=>{const data=await fixture(t);data.manifest.entries.push(data.manifest.entries[0]);data.maps[0].pages.push({...data.maps[0].pages[0],evidence:'../escape.png'});const result=await verifyGalleryBaseline(data);assert.ok(result.errors.some(x=>x.includes('duplicate source')));assert.ok(result.errors.some(x=>x.includes('duplicate page')));assert.ok(result.errors.some(x=>x.includes('outside evidence root')))})
test('requires actual evidence files instead of an existing directory or blank path',async t=>{const data=await fixture(t);data.maps[0].pages[0].evidence=['.',''];const result=await verifyGalleryBaseline(data);assert.ok(result.errors.some(x=>x.includes('not a file')));assert.ok(result.errors.some(x=>x.includes('invalid evidence')))})
