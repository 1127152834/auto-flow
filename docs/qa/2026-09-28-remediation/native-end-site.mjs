// Real local HTTP page for native End save/run acceptance; no substituted API responses.
import { createServer } from 'node:http'
import { mkdtemp, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
const output = await mkdtemp(join(import.meta.dirname, 'native-end-site-'))
const requests = []
const html = '<!doctype html><html lang="zh"><meta charset="utf-8"><title>AutoFlow 原生 End 验收</title><body><h1>本次真实生成验收网页</h1><p id="state">native-end-page-read</p></body></html>'
await writeFile(join(output, 'page.html'), html, { flag: 'wx' })
const server = createServer((request, response) => {
  requests.push({ time: new Date().toISOString(), method: request.method, path: request.url })
  response.setHeader('Content-Type', 'text/html; charset=utf-8')
  response.setHeader('Set-Cookie', 'native-end=session-created-by-real-http; Path=/; HttpOnly; SameSite=Lax')
  response.end(html)
})
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
const ready = { pid: process.pid, url: `http://127.0.0.1:${server.address().port}/native-end`, output, startedAt: new Date().toISOString() }
await writeFile(join(output, 'ready.json'), JSON.stringify(ready, null, 2), { flag: 'wx' })
console.log(JSON.stringify(ready))
await new Promise(resolve => { process.once('SIGINT', resolve); process.once('SIGTERM', resolve) })
await new Promise(resolve => server.close(resolve))
await writeFile(join(output, 'result.json'), JSON.stringify({ ...ready, closedAt: new Date().toISOString(), requests }, null, 2), { flag: 'wx' })
console.log(JSON.stringify({ output, closed: true, requests: requests.length }))
