"""Real CloakBrowser M3 picker/locator/executor checks in a temporary workspace."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import tempfile
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from uuid import uuid4

from autoflow.domain.workflows.catalog import node_catalog
from autoflow.infrastructure.filesystem.workflow_artifacts import WorkflowArtifacts
from autoflow.providers.browser.inspection import BrowserInspection
from autoflow.providers.browser.inspection_script import PICKER_SCRIPT
from autoflow.providers.browser.workflow_executor import WorkflowExecutor

ROOT = Path(__file__).resolve().parents[1]

class Fixture:
    def __init__(self):
        fixture = self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                html = '''<!doctype html><meta charset=utf-8><title>M3 inspection fixture</title><style>iframe{width:650px;height:380px} button,input{margin:8px}body{min-height:700px}</style>
                <script>window.actions=0;window.addEventListener('click',()=>window.actions++);</script>
                <a id="link" href="/changed">link</a><form onsubmit="window.actions+=100;return false"><button id="submit">submit</button><input id="check" type="checkbox"></form>
                <input id="entry" value="initial"><button id="button" onclick="document.querySelector('#result').textContent=document.querySelector('#entry').value">update</button><p id="result">expected</p>
                <p class="many">one</p><p class="many">two</p><p id="hidden" hidden>hidden</p><button id="special:id">special</button><button id="dup">first</button><button id="dup">second</button>
                <div id="shadow"></div><script>const s=document.querySelector('#shadow').attachShadow({mode:'open'});s.innerHTML='<button id="inside">shadow value</button>';</script>'''
                if self.path == '/':
                    html += f'<iframe id="outer" src="http://localhost:{fixture.server.server_port}/outer"></iframe>'
                elif self.path == '/outer':
                    html = f'<iframe id="inner" src="http://127.0.0.1:{fixture.server.server_port}/inner" style="width:620px;height:340px"></iframe>'
                data = html.encode()
                self.send_response(200); self.send_header('Content-Type','text/html;charset=utf-8'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
            def log_message(self, *_args): pass
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        Thread(target=self.server.serve_forever,daemon=True).start()
        self.url=f'http://127.0.0.1:{self.server.server_port}'
    def close(self): self.server.shutdown(); self.server.server_close()

async def main(args, report):
    from cloakbrowser import launch_context_async
    fixture=Fixture()
    with tempfile.TemporaryDirectory(prefix='autoflow-m3-browser-') as directory:
        os.environ['CLOAKBROWSER_BINARY_PATH']=str(args.executable.resolve(strict=True))
        os.environ['CLOAKBROWSER_CACHE_DIR']=directory
        context=await launch_context_async(headless=False)
        try:
            await context.add_init_script(PICKER_SCRIPT)
            inspector=BrowserInspection(context)
            page=await context.new_page(); await page.goto(fixture.url)
            page_id=next(key for key,value in inspector.pages.items() if value is page)
            inspector.target=page_id
            await page.frame_locator('#outer').frame_locator('#inner').locator('#entry').wait_for()
            async def pick(locator):
                await locator.scroll_into_view_if_needed()
                request_id=str(uuid4())
                await inspector.command({'action':'pick','requestId':request_id,'pageId':page_id})
                # Actual browser input, not a fabricated picker result.
                await locator.click(force=True)
                snapshot=await inspector.snapshot()
                result=snapshot['pick']; assert result['state']=='selected',result
                return result['result']
            for selector in ['#link','#submit','#check']:
                before=await page.evaluate('actions')
                await pick(page.locator(selector))
                assert await page.evaluate('actions')==before
                assert page.url==fixture.url+'/'
                assert not await page.locator('#check').is_checked()
            report['checks'].append('real picking intercepts link/submit/checkbox without page action')
            await page.locator('#check').click(); assert await page.locator('#check').is_checked()
            await page.locator('#check').click()
            report['checks'].append('ordinary input restored after picking')
            for locator in [page.locator('[id="special:id"]'),page.locator('#dup').nth(1),page.locator('#shadow #inside')]:
                result=await pick(locator)
                assert await page.locator(result['selector']).count()==1
            report['checks'].append('escaped identifiers, duplicate ids, open shadow generate unique executable selectors')
            inner=page.frame_locator('#outer').frame_locator('#inner')
            selected=await pick(inner.locator('#entry'))
            assert len(selected['framePath'])==2,selected
            results=[]
            for selector,count in [('#entry',1),('.many',2),('#missing',0),('xpath=//input[@id="entry"]',1),('#hidden',1)]:
                result=await inspector.command({'action':'test','pageId':page_id,'selector':selector,'framePath':selected['framePath']})
                assert result['count']==count,result
                if selector=='#hidden': assert not result['first']['visible']
                results.append(result)
            for path in [['#missing'],['.many'],['#entry']]:
                try: await inspector.command({'action':'test','pageId':page_id,'selector':'body','framePath':path})
                except Exception: pass
                else: raise AssertionError('invalid frame accepted')
            report['checks'].append('cross-origin nested iframe picker and CSS/XPath zero/one/multiple/hidden locator tests')
            request_id=str(uuid4()); await inspector.command({'action':'pick','requestId':request_id,'pageId':page_id})
            await page.keyboard.press('Escape'); assert (await inspector.snapshot())['pick']['state']=='cancelled'
            request_id=str(uuid4()); await inspector.command({'action':'pick','requestId':request_id,'pageId':page_id})
            await page.reload(); assert (await inspector.snapshot())['pick']['state']=='failed'
            report['checks'].append('Escape cancels; navigation invalidates picking')
            await page.evaluate("() => { const list=document.createElement('div');list.id='large-list';list.innerHTML='<span>item</span>'.repeat(105);document.body.appendChild(list);const special=document.createElement('button');special.id='{literal}';special.textContent='literal';document.body.appendChild(special) }")
            large=await inspector.command({'action':'test','pageId':page_id,'selector':'#large-list span','framePath':[]})
            assert large['count']==105 and large['truncated']
            assert await page.locator('[data-autoflow-overlay="test"]').count()==1
            await asyncio.sleep(3.2)
            assert await page.locator('[data-autoflow-overlay="test"]').count()==0
            literal=await pick(page.locator('[id="{literal}"]'))
            assert '{literal}' not in literal['selector'] and literal['positional']
            try: await inspector.command({'action':'test','pageId':page_id,'selector':'[','framePath':[]})
            except Exception: pass
            else: raise AssertionError('invalid selector accepted')
            report['checks'].append('105 matches counted without truncation; highlighter limit/expiry; placeholder-like IDs use structural fallback; invalid CSS rejected')
            await page.evaluate("url => { const f=document.createElement('iframe');f.id='same';f.src=url+'/inner';document.body.appendChild(f) }",fixture.url)
            await page.frame_locator('#same').locator('#entry').wait_for()
            same=await pick(page.frame_locator('#same').locator('#entry'))
            assert same['framePath']==['#same']
            previous=inspector.last_pick
            await page.reload()
            assert (await inspector.command({'action':'get-pick','requestId':previous}))['state']=='failed'
            request_id=str(uuid4());await inspector.command({'action':'pick','requestId':request_id,'pageId':page_id})
            await page.locator('#outer').evaluate('el=>el.remove()')
            assert (await inspector.snapshot())['pick']['state']=='failed'
            other=await context.new_page();await other.goto(fixture.url+'/inner')
            assert inspector.target==page_id
            await page.close()
            snapshot=await inspector.snapshot()
            assert snapshot['targetPageId'] is None and len(snapshot['pages'])==1
            report['checks'].append('same-origin iframe; selected result invalid after navigation; iframe detach invalidates request; new/closed tabs never silently retarget')
            # Fresh context proves picker login/page state is not required to execute saved selectors.
            await context.close()
            context=await launch_context_async(headless=False)
            catalog={item['type']:item['defaultConfig'] for item in node_catalog()}
            steps=[('open_page',{'url':fixture.url}),('input_text',{'selector':selected['selector'],'framePath':selected['framePath'],'text':'M3 real value'}),
                   ('click_element',{'selector':'#button','framePath':selected['framePath']}),('wait_element',{'selector':'#result','framePath':selected['framePath']}),
                   ('get_element_info',{'selector':'#result','framePath':selected['framePath']}),('screenshot',{'selector':'#result','framePath':selected['framePath'],'screenshotType':'element'})]
            nodes=[{'id':f'n{i}','type':kind,'config':{**catalog[kind],**config}} for i,(kind,config) in enumerate(steps)]
            variables={}; events=[]
            executor=WorkflowExecutor(context,WorkflowArtifacts(Path(directory)/'runs','real-run'),variables,events.append)
            outcome=await executor.run({'nodes':nodes},[n['id'] for n in nodes])
            assert outcome['state']=='succeeded',(outcome,events)
            assert variables['element_value']=='M3 real value'
            assert Path(variables['screenshot_path']).read_bytes().startswith(b'\x89PNG')
            report['checks'].append('fresh independent browser executes all six nodes using picked iframe target; real extraction and PNG verified')
        finally:
            await context.close(); fixture.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--executable',type=Path,required=True); parser.add_argument('--report',type=Path,required=True); args=parser.parse_args()
    report={'timestamp':datetime.now(UTC).isoformat(),'platform':platform.platform(),'checks':[]}
    try: asyncio.run(main(args,report)); report['passed']=True
    finally: args.report.parent.mkdir(parents=True,exist_ok=True); args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False,indent=2))
