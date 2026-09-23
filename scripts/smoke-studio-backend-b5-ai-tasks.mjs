import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { createHash, randomUUID } from 'node:crypto'
import { mkdir, mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises'
import { createServer } from 'node:http'
import { tmpdir } from 'node:os'
import { basename, dirname, join, resolve } from 'node:path'

import { connectCdp, launchElectron, wait, waitFor } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')
const sourceKernel = process.env.AUTOFLOW_B1_KERNEL_DIR
  ?? '/Users/zhangtiancheng/Library/Application Support/@autoflow/desktop/data/kernels/chromium-145.0.7632.109.2'
const kernelVersion = basename(sourceKernel).replace(/^chromium-/, '')
const evidenceRoot = join(root, 'docs/migration/studio-backend-migration/evidence/b5')
const evidenceDir = await mkdtemp(join(await mkdir(evidenceRoot, { recursive: true }).then(() => evidenceRoot), 'formal-ai-tasks-electron-'))
const userData = await mkdtemp(join(tmpdir(), 'autoflow-studio-b5-ai-tasks-'))
const projectModels = process.env.AUTOFLOW_PROJECT_MODELS === '1'
let projectId = null
const workflowName = 'B5 AI 数据任务与对话正式闭环'
const checks = []
const model = await startModel()
const modules = [
  { type: 'ai_extract', label: 'AI信息抽取', inputs: [['textarea[placeholder^="要处理的文本"]', '姓名张三'], ['input[placeholder^="如 姓名"]', '姓名'], ['input[placeholder="结果变量名"]', 'extract_result']] },
  { type: 'ai_classify', label: 'AI文本分类', inputs: [['textarea[placeholder^="要处理的文本"]', '我要退款'], ['input[placeholder^="如 投诉"]', '退款,咨询'], ['input[placeholder="结果变量名"]', 'classify_result']] },
  { type: 'ai_summarize', label: 'AI文本摘要', inputs: [['textarea[placeholder^="要处理的文本"]', '这是一段需要生成摘要的长文本'], ['input[placeholder="结果变量名"]', 'summary_result']] },
  { type: 'ai_translate', label: 'AI翻译', inputs: [['textarea[placeholder^="要处理的文本"]', '你好'], ['input[placeholder^="如 英文"]', '英文'], ['input[placeholder="结果变量名"]', 'translate_result']] },
  { type: 'ai_sentiment', label: 'AI情感分析', inputs: [['textarea[placeholder^="要处理的文本"]', '非常满意'], ['input[placeholder="结果变量名"]', 'sentiment_result']] },
  { type: 'ai_normalize', label: 'AI数据规整', inputs: [['textarea[placeholder^="要处理的文本"]', '2026年9月21日'], ['input[placeholder="结果变量名"]', 'normalize_result']] },
  { type: 'ai_dedup_semantic', label: 'AI语义去重', inputs: [['textarea[placeholder^="数组变量"]', '["苹果","Apple","香蕉"]'], ['input[placeholder="结果变量名"]', 'dedup_result']] },
  { type: 'ai_route', label: 'AI智能路由', inputs: [['textarea[placeholder^="要处理的文本"]', '我要退款'], ['textarea[placeholder^="每行一个"]', '退款:用户要求退钱\n咨询:用户询问信息'], ['input[placeholder="结果变量名"]', 'route_result']] },
  { type: 'ai_chat', label: 'AI对话', inputs: [['textarea[placeholder^="设定AI的角色"]', '对话助手'], ['textarea[placeholder^="发送给AI的内容"]', '请回复验收结果'], ['input[placeholder="变量名"]', 'chat_result']] },
  { type: 'ai_generate_image', label: 'AI生成图片', inputs: [['textarea[placeholder^="一只可爱的猫咪"]', '生成验收图片'], ['input[placeholder="C:/images/output.png"]', 'generated/image.png']] },
  { type: 'ai_generate_video', label: 'AI生成视频', inputs: [['textarea[placeholder^="一只猫咪在草地"]', '生成验收视频'], ['input[placeholder="C:/videos/output.mp4"]', 'generated/video.mp4']] },
  { type: 'open_page', label: '打开网页', model: false, inputs: [['input[placeholder="https://example.com"]', model.pageUrl]] },
  { type: 'ai_vision', label: '图像识别', selects: [['图片来源', '当前页面截图']], inputs: [['textarea[placeholder^="请描述这张图片"]', '视觉验收'], ['input[placeholder="变量名"]', 'vision_result']] },
  { type: 'ai_vision_act', label: 'AI视觉操作', selects: [['执行动作', '单击']], inputs: [['textarea[placeholder^="用自然语言描述"]', '点击页面中央验收按钮'], ['input[placeholder^="结果变量名"]', 'vision_act_result']] },
]
let desktop, main, studio

await writeFile(join(userData, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
await mkdir(join(userData, 'data', 'kernels'), { recursive: true })
execFileSync('cp', ['-cR', sourceKernel, join(userData, 'data', 'kernels', basename(sourceKernel))])

try {
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${userData}`] })
  main = desktop.cdp
  await main.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(main, "document.body?.innerText.includes('本地服务正常')", 'main service readiness', 30_000)
  const runtime = await main.evaluate('window.autoflow.getRuntimeContext()')
  const profile = await api(runtime, '/v1/profiles', {
    method: 'POST',
    body: {
      name: 'B5 AI任务验收配置', description: '临时工作区；视觉节点使用真实浏览器', startUrl: 'about:blank',
      locale: 'zh-CN', timezone: 'Asia/Shanghai', geoip: false, headless: true, humanize: false,
      humanPreset: 'default', userAgent: null, viewportJson: null, colorScheme: 'light', extensionPathsJson: [], expertArgsJson: [],
      browserVersion: kernelVersion, browserEdition: 'public', releaseChannel: 'stable', proxyMode: 'none', proxyId: null, proxyPoolId: null,
    },
  })
  const provider = await api(runtime, '/v1/model-providers/connect', {
    method: 'POST',
    body: {
      provider: { name: 'B5 AI任务受控模型', presetId: 'custom-openai-compatible', providerKind: 'openai-compatible', baseUrl: model.baseUrl, apiKey: '', enabled: true, description: '正式 UI 受控验收' },
      selectedModels: [{ modelKey: 'ai-task-fixture', displayName: 'B5 AI Task Fixture', tagsJson: ['chat'], contextWindow: 32768, enabled: true, description: '' }],
    },
  })
  const modelId = provider.models[0].id
  let defaultModelId = modelId
  if (projectModels) {
    const defaultProvider = await api(runtime, '/v1/model-providers/connect', {method:'POST', body:{
      provider:{name:'Z 项目默认模型',presetId:'custom-openai-compatible',providerKind:'openai-compatible',baseUrl:model.baseUrl,apiKey:'',enabled:true,description:'隔离项目默认模型验收'},
      selectedModels:[{modelKey:'project-default-fixture',displayName:'Z 项目默认模型',tagsJson:['chat'],enabled:true,description:''}],
    }})
    defaultModelId = defaultProvider.models[0].id
    const options = (await api(runtime, '/v1/models/options')).items
    assert.equal(options[0].id, modelId)
    assert.equal(options[1].id, defaultModelId)
    await click(main,'项目','a,button'); await click(main,'新建项目')
    await setInput(main,'#project-name','Studio 项目模型验收'); await click(main,'创建项目')
    await waitFor(main,"document.body.innerText.includes('Studio 项目模型验收')",'created project')
    if (!await main.evaluate('Boolean(document.querySelector(\'[aria-label="项目功能"]\'))')) await click(main,'Studio 项目模型验收','[role="button"],button')
    await waitFor(main,'Boolean(document.querySelector(\'[aria-label="项目功能"]\'))','project detail')
    projectId = (await main.evaluate('location.hash')).match(/projects\/([^/]+)/)?.[1]
    assert.ok(projectId)
    const project = await api(runtime,`/v1/projects/${projectId}`)
    await api(runtime,`/v1/projects/${projectId}`,{method:'PATCH',body:{expectedManagementRevision:project.managementRevision,defaultResources:{...project.defaultResources,profileId:profile.id,modelProviderId:defaultProvider.id}}})
    await click(main,'自动化','[aria-label="项目功能"] button,[aria-label="项目功能"] [role="tab"]')
    checkpoint('正式项目入口使用主应用第二个模型提供商作为默认值，第一项仍可显式覆盖')
  }
  assert.deepEqual(cloakProcesses(userData), [])

  studio = await openStudioFromMain(main, desktop.debugOrigin)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 2560, height: 1600, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库') && document.body.innerText.includes('213')", 'formal Studio', 30_000)
  await waitFor(studio, `document.querySelector('[aria-label="运行浏览器配置"]')?.value === ${JSON.stringify(profile.id)}`, 'managed Profile selection')
  checkpoint('主窗口真实点击打开正式 Studio；动作库为 213，运行配置和模型均来自主应用')

  await click(studio, '新建')
  await setInput(studio, 'input[placeholder="工作流名称"]', workflowName)

  const nodeIds = []
  for (let index = 0; index < modules.length; index++) {
    const module = modules[index]
    const nodeId = await addNode(studio, module.label, module.type)
    nodeIds.push(nodeId)
    for (const [selector, value] of module.inputs) await setInput(studio, selector, value)
    for (const [label, option] of module.selects ?? []) await chooseSelectOption(studio, label, option)
    if (module.model !== false) {
      if (!projectModels || module.type === 'ai_chat') await chooseFirstModel(studio)
      else await waitFor(studio, "[...document.querySelectorAll('[role=combobox]')].some(e=>e.textContent.includes('Z 项目默认模型'))", 'inherited default model label')
    }
  }
  for (let index = 0; index < nodeIds.length - 1; index++) await connectNodes(studio, nodeIds[index], nodeIds[index + 1])
  await waitFor(studio, `document.querySelectorAll('.react-flow__edge').length === ${modules.length - 1}`, 'workflow edges')
  checkpoint('通过画布、属性面板和主应用模型选择器完成八个 AI 数据任务、对话、图片视频生成及视觉节点编排')

  await click(studio, '保存')
  await waitFor(studio, `document.body?.innerText.includes(${JSON.stringify(`工作流已保存: ${workflowName}`)})`, 'workflow save')
  const saved = (await api(runtime, '/workflows')).find(item => item.name === workflowName)
  assert.ok(saved)
  assert.deepEqual(saved.nodes.map(node => node.data.moduleType), modules.map(item => item.type))
  assert.equal(saved.edges.length, modules.length - 1)
  assert.ok(saved.nodes.filter(node => node.data.moduleType !== 'open_page').every(node =>
    projectModels && node.data.moduleType !== 'ai_chat' ? !node.data.modelId : node.data.modelId === modelId))
  if(projectModels) assert.equal(saved.projectId,projectId)
  assert.equal(JSON.stringify(saved).includes(model.baseUrl), false)
  checkpoint(`正式保存 ${modules.length} 个节点及 ${modules.length-1} 条连线；模型选择仅保存稳定ID或继承空值，不保存地址或密钥`)

  if (projectModels) {
    execFileSync('osascript',['-e','tell application "System Events"','-e',`tell (first application process whose unix id is ${desktop.child.pid})`,'-e','set frontmost to true','-e','click (first button of (first window whose name contains "工作流工作台") whose subrole is "AXCloseButton")','-e','end tell','-e','end tell'])
    studio.close(); studio = undefined
    await waitForValue(async()=>!(await(await fetch(`${desktop.debugOrigin}/json/list`)).json()).some(x=>x.type==='page'&&x.url.includes('studio.html')), 'native Studio close',30000)
    studio = await openStudioFromMain(main, desktop.debugOrigin)
    await studio.command('Emulation.setDeviceMetricsOverride',{width:2560,height:1600,deviceScaleFactor:1,mobile:false})
    await waitFor(studio,"document.body.innerText.includes('模块库')",'Studio reopened')
    await click(studio,'打开'); await click(studio,`打开工作流 ${workflowName}`,'[role="button"]')
    await waitFor(studio,`document.querySelectorAll('.react-flow__node').length === ${modules.length}`,'restored nodes')
    const restored = await api(runtime,`/workflows/${saved.id}`)
    assert.deepEqual(restored.nodes,saved.nodes)
    checkpoint('模型继承与显式覆盖随真实保存、原生关窗和重开恢复；文档节点未被默认解析改写')
  }

  await click(studio, '运行 (F5)', '[aria-label="运行 (F5)"]')
  await click(studio, '运行 (F5)', '[role="menuitem"]')
  const run = await waitForValue(async () => (await api(runtime, `/workflow-runs?documentId=${encodeURIComponent(saved.id)}&cursor=0&limit=20`)).items[0], 'run creation', 20_000)
  const terminal = await waitForValue(async () => {
    const value = await api(runtime, `/workflow-runs/${encodeURIComponent(run.runId)}`)
    return ['completed', 'failed', 'stopped', 'interrupted'].includes(value.status) ? value : null
  }, 'terminal run', 60_000)
  assert.equal(terminal.status, 'completed')
  await waitFor(studio, "document.body?.innerText.includes('执行完成')", 'rendered completion', 10_000)

  const results = await api(runtime, `/workflow-runs/${encodeURIComponent(run.runId)}/results?cursor=0&limit=20`)
  const byNode = Object.fromEntries(results.items.map(item => [item.nodeId, item.values]))
  assert.deepEqual(byNode[nodeIds[0]], { result: { 姓名: '张三' } })
  assert.equal(byNode[nodeIds[1]].category, '退款')
  assert.equal(byNode[nodeIds[2]].summary, '简短摘要')
  assert.deepEqual(byNode[nodeIds[3]], { translation: 'Hello', targetLang: '英文' })
  assert.equal(byNode[nodeIds[4]].sentiment, '正面')
  assert.deepEqual(byNode[nodeIds[5]], { result: '2026-09-21', type: 'date' })
  assert.deepEqual(byNode[nodeIds[6]], { result: ['苹果', '香蕉'], removed: 1 })
  assert.equal(byNode[nodeIds[7]].route, '退款')
  assert.equal(byNode[nodeIds[8]].response, '对话验收通过')
  assert.equal(byNode[nodeIds[9]].paths.length, 1)
  assert.equal(typeof byNode[nodeIds[10]].path, 'string')
  assert.equal(byNode[nodeIds[12]].response, '视觉识别通过')
  assert.equal(byNode[nodeIds[12]].image_source, 'screenshot')
  assert.equal(model.clicked, 1)
  assert.ok(model.lastClick && model.lastClick.width > 0 && model.lastClick.height > 0)
  assert.equal(byNode[nodeIds[13]].x, Math.floor(model.lastClick.width / 2))
  assert.equal(byNode[nodeIds[13]].y, Math.floor(model.lastClick.height / 2))
  assert.equal(model.lastClick.x, byNode[nodeIds[13]].x)
  assert.equal(model.lastClick.y, byNode[nodeIds[13]].y)
  const chatRequests = model.requests.filter(request => request.path === '/v1/chat/completions')
  assert.equal(chatRequests.length, 11)
  if (projectModels) {
    assert.equal(chatRequests.filter(request=>request.body.model==='ai-task-fixture').length,1)
    assert.equal(chatRequests.filter(request=>request.body.model==='project-default-fixture').length,10)
    assert.equal(terminal.profileSnapshot.resolvedDefaultModelId,defaultModelId)
    assert.ok(terminal.documentSnapshot.nodes.filter(node=>node.data.moduleType!=='ai_chat').every(node=>!node.data.config?.modelId && !node.data.modelId))
    checkpoint('真实worker使用项目默认模型执行十次对话，显式模型仅用于AI对话节点；原始运行快照不写回默认值')
  } else assert.ok(chatRequests.every(request => request.body.model === 'ai-task-fixture'))
  const visionRequest = chatRequests.find(request => JSON.stringify(request.body.messages).includes('视觉验收'))
  assert.ok(JSON.stringify(visionRequest?.body.messages).includes('data:image/png;base64,'))
  assert.equal(model.requests.filter(request => request.path === '/v1/images/generations').length, 1)
  assert.equal(model.requests.filter(request => request.path === '/v1/generations').length, 1)
  assert.equal(model.requests.filter(request => request.path === '/v1/generations/video-job').length, 1)
  checkpoint(`真实 worker 经主应用模型绑定完成 ${chatRequests.length} 次对话和两次媒体生成；受控模型服务的页面截图与视觉坐标协议结果逐项匹配`)

  const artifacts = await api(runtime, `/workflow-runs/${encodeURIComponent(run.runId)}/artifacts?cursor=0&limit=20`)
  assert.equal(artifacts.items.length, 2)
  const imageArtifact = artifacts.items.find(item => item.nodeId === nodeIds[9])
  const videoArtifact = artifacts.items.find(item => item.nodeId === nodeIds[10])
  assert.ok(imageArtifact && videoArtifact)
  assert.deepEqual(await artifactBytes(runtime, run.runId, imageArtifact.artifactId), Buffer.from('PNG'))
  assert.deepEqual(await artifactBytes(runtime, run.runId, videoArtifact.artifactId), Buffer.from('MP4'))
  checkpoint('图片和视频均通过工作区产物边界落盘、登记并可由正式产物接口读取')

  await wait(500)
  assert.deepEqual(cloakProcesses(userData), [])
  checkpoint('AI视觉与视觉操作使用主应用 Profile 启动 CloakBrowser，真实点击受控页面按钮，运行结束后浏览器和worker均已清理')

  await capture(studio, join(evidenceDir, 'completed.png'))
  if (projectModels) {
    await click(studio, 'AI 小助手')
    await waitFor(studio, "document.querySelector('button[title=\"切换模型\"],button[data-tip=\"切换模型\"]')?.textContent.includes('Z 项目默认模型')", 'assistant inherits project model')
    await setInput(studio, 'textarea[placeholder^="告诉我你想做什么"]', '项目模型默认问候')
    await click(studio,'发送消息')
    await waitFor(studio,"document.body.innerText.includes('项目默认调用确认')",'assistant default response')
    await click(studio,'','button[title="切换模型"],button[data-tip="切换模型"]')
    await click(studio,'B5 AI Task Fixture','button')
    await setInput(studio, 'textarea[placeholder^="告诉我你想做什么"]', '项目模型显式问候')
    await click(studio,'发送消息')
    await waitFor(studio,"document.body.innerText.includes('项目覆盖调用确认')",'assistant explicit response')
    const assistantRequests = model.requests.filter(x=>x.body?.stream)
    assert.deepEqual(assistantRequests.map(x=>x.body.model), ['project-default-fixture','ai-task-fixture'])
    checkpoint('正式小助手通过LangGraph以项目默认模型发送，再真实点击跨提供商显式覆盖；受控SSE响应与实际请求一致')
    await capture(studio, join(evidenceDir,'project-assistant-models.png'))
  }

  const report = {
    evidenceId: 'BE-B5-ai-task-chat-media-formal-electron', checkedAt: new Date().toISOString(),
    gitHead: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
    result: 'passed', platform: `${process.platform}-${process.arch}`, entry: desktop.packaged ? 'packaged-directory' : 'development-build',
    workflowId: saved.id, profileId: profile.id, modelId, defaultModelId, projectId, runId: run.runId, checks,
    nodes: modules.map((module, index) => ({ moduleType: module.type, nodeId: nodeIds[index], result: byNode[nodeIds[index]] })),
    providerRequestCount: model.requests.length, artifactIds: [imageArtifact.artifactId, videoArtifact.artifactId],
    buildSha256: await buildHash(),
    buildArtifacts: desktop.packaged ? await packagedBuildHashes() : null,
    boundaries: {
      workspace: 'ephemeral', userDatabaseTouched: false, browserLaunch: 'real CloakBrowser for page and visual nodes',
      model: 'local controlled OpenAI-compatible HTTP fixture configured through main application model management',
      interaction: 'formal Electron via CDP mouse and keyboard; public sidecar APIs only for fixture setup and evidence reads; no Store or page-internal business function access',
      externalWaiting: 'third-party production model providers remain separately unverified',
    },
  }
  await writeFile(join(evidenceDir, 'result.json'), JSON.stringify(report, null, 2) + '\n')
  console.log(JSON.stringify({ evidenceDir, ...report }, null, 2))
} catch (error) {
  if (studio) await capture(studio, join(evidenceDir, 'failure.png')).catch(() => undefined)
  await writeFile(join(evidenceDir, 'failure.json'), JSON.stringify({ checkedAt: new Date().toISOString(), checks, error: error instanceof Error ? error.stack : String(error) }, null, 2) + '\n')
  throw error
} finally {
  studio?.close(); main?.close(); await stop(desktop?.child)
  await model.close()
  await rm(userData, { recursive: true, force: true })
}

function checkpoint(message) { checks.push(message); console.log(message) }

async function startModel() {
  const requests = []
  const responses = new Map([
    ['信息抽取引擎', '{"姓名":"张三"}'],
    ['文本分类器', '{"category":"退款"}'],
    ['摘要助手', '简短摘要'],
    ['专业翻译', 'Hello'],
    ['情感分析引擎', '{"sentiment":"正面"}'],
    ['数据规整引擎', '"2026-09-21"'],
    ['语义去重引擎', '[0,2]'],
    ['智能路由决策器', '{"route":"退款"}'],
    ['对话助手', '对话验收通过'],
  ])
  const server = createServer(async (request, response) => {
    const url = new URL(request.url, 'http://127.0.0.1')
    if (request.method === 'GET' && url.pathname === '/v1/models') return json(response, { data: [{ id: 'ai-task-fixture', context_length: 32768 }, {id:'project-default-fixture',context_length:32768}] })
    if (request.method === 'GET' && url.pathname === '/v1/generations/video-job') {
      requests.push({ method: request.method, path: url.pathname })
      return json(response, { status: 'completed', url: `http://127.0.0.1:${server.address().port}/media.mp4` })
    }
    if (request.method === 'GET' && url.pathname === '/media.mp4') {
      requests.push({ method: request.method, path: url.pathname })
      const content = Buffer.from('MP4')
      response.writeHead(200, { 'content-type': 'video/mp4', 'content-length': content.length })
      return response.end(content)
    }
    if (request.method === 'GET' && url.pathname === '/page') {
      const content = Buffer.from('<!doctype html><html><body><h1>AutoFlow AI视觉验收页面</h1><button style="position:absolute;left:calc(50vw - 50px);top:calc(50vh - 50px);width:100px;height:100px" onclick="fetch(\'/clicked?x=\'+event.clientX+\'&y=\'+event.clientY+\'&width=\'+innerWidth+\'&height=\'+innerHeight)">验收按钮</button></body></html>')
      response.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'content-length': content.length })
      return response.end(content)
    }
    if (request.method === 'GET' && url.pathname === '/clicked') { requests.push({ method: request.method, path: url.pathname }); server.clicked += 1; server.lastClick = Object.fromEntries(['x','y','width','height'].map(key=>[key,Number(url.searchParams.get(key))])); return json(response, { ok: true }) }
    let raw = ''
    for await (const chunk of request) raw += chunk
    const body = raw ? JSON.parse(raw) : {}
    requests.push({ method: request.method, path: url.pathname, body })
    if (body.stream) {
      response.writeHead(200, {'content-type':'text/event-stream'})
      const content = body.model === 'project-default-fixture' ? '项目默认调用确认' : '项目覆盖调用确认'
      response.end(`data: ${JSON.stringify({choices:[{delta:{content}}]})}\n\ndata: [DONE]\n\n`)
      return
    }
    if (request.method === 'POST' && url.pathname === '/v1/images/generations') return json(response, { data: [{ b64_json: Buffer.from('PNG').toString('base64') }] })
    if (request.method === 'POST' && url.pathname === '/v1/generations') return json(response, { id: 'video-job' })
    if (request.method !== 'POST' || url.pathname !== '/v1/chat/completions') return json(response, { error: { message: 'not found' } }, 404)
    const messages = JSON.stringify(body.messages ?? [])
    const content = messages.includes('目标：') ? '{"found":true,"x":500,"y":500,"reason":"验收按钮"}' : messages.includes('视觉验收') ? '视觉识别通过' : [...responses].find(([marker]) => messages.includes(marker))?.[1]
    if (!content) return json(response, { error: { message: 'unknown prompt' } }, 422)
    return json(response, { choices: [{ message: { content } }] })
  })
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve) })
  server.clicked = 0
  return {
    baseUrl: `http://127.0.0.1:${server.address().port}/v1`, pageUrl: `http://127.0.0.1:${server.address().port}/page`, requests,
    get clicked() { return server.clicked },
    get lastClick() { return server.lastClick },
    close: () => new Promise(resolve => { server.close(resolve); server.closeAllConnections() }),
  }
}

function json(response, body, status = 200) {
  const encoded = Buffer.from(JSON.stringify(body))
  response.writeHead(status, { 'content-type': 'application/json', 'content-length': encoded.length })
  response.end(encoded)
}

async function api(runtime, path, options = {}) {
  const response = await fetch(`${runtime.sidecar.baseUrl}/api${path}`, {
    method: options.method ?? 'GET',
    headers: { 'x-autoflow-token': runtime.sidecar.token, 'content-type': 'application/json', 'Idempotency-Key': randomUUID() },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  })
  if (!response.ok) throw new Error(`${options.method ?? 'GET'} /api${path}: ${response.status} ${await response.text()}`)
  return response.status === 204 ? undefined : response.json()
}

async function artifactBytes(runtime, runId, artifactId) {
  const response = await fetch(`${runtime.sidecar.baseUrl}/api/workflow-runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(artifactId)}`, { headers: { 'x-autoflow-token': runtime.sidecar.token } })
  if (!response.ok) throw new Error(`artifact read: ${response.status} ${await response.text()}`)
  return Buffer.from(await response.arrayBuffer())
}

async function openStudioFromMain(cdp, origin) {
  await click(cdp, '工作流工作台')
  const target = await waitForValue(async () => (await (await fetch(`${origin}/json/list`)).json()).find(item => item.type === 'page' && item.url.includes('studio.html')), 'Studio target', 20_000)
  return connectCdp(target.webSocketDebuggerUrl)
}

async function waitForValue(read, description, timeoutMs) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const value = await read()
    if (value) return value
    await wait(200)
  }
  throw new Error(`timed out waiting for ${description}`)
}

async function point(cdp, selector, text = '') {
  return waitFor(cdp, `(()=>{const rows=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>e.getClientRects().length),text=${JSON.stringify(text)};const e=!text?rows[0]:rows.find(e=>e.getAttribute('aria-label')===text)||rows.find(e=>e.textContent.trim()===text)||rows.find(e=>e.textContent.includes(text));if(!e||e.disabled)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return e.contains(document.elementFromPoint(x,y))?{x,y}:null})()`, `unobscured ${text || selector}`)
}

async function click(cdp, text, selector = 'button') {
  const p = await point(cdp, selector, text)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...p })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 1 })
  await wait(100)
}

async function setInput(cdp, selector, value) {
  const p = await point(cdp, selector)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 3 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 3 })
  await cdp.command('Input.insertText', { text: value })
  await cdp.command('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 })
  await cdp.command('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 })
  await wait(100)
}

async function chooseFirstModel(cdp) {
  const picker = `(()=>{const label=[...document.querySelectorAll('label')].find(e=>e.textContent.includes('主应用模型'));const e=label?.parentElement?.querySelector('[role="combobox"]');if(!e)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return e.contains(document.elementFromPoint(x,y))?{x,y}:null})()`
  let p = await cdp.evaluate(picker)
  if (!p) {
    await click(cdp, 'AI 模型设置', 'summary')
    p = await waitFor(cdp, picker, 'managed model select')
  }
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...p })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 1 })
  await waitFor(cdp, `([...document.querySelectorAll('[role="combobox"]')].some(e=>e.getClientRects().length&&e.dataset.state==='open'))`, 'open managed model select')
  const option = await waitFor(cdp, `(()=>{const e=[...document.querySelectorAll('[role="option"]')].find(e=>e.textContent.includes('B5 AI Task Fixture'));if(!e)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`, 'managed model option')
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...option })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...option, button: 'left', clickCount: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...option, button: 'left', clickCount: 1 })
  await waitFor(cdp, `([...document.querySelectorAll('[role="combobox"]')].some(e=>e.getClientRects().length&&e.textContent.includes('B5 AI Task Fixture')))`, 'selected managed model')
}

async function chooseSelectOption(cdp, labelText, optionText) {
  const p = await waitFor(cdp, `(()=>{const label=[...document.querySelectorAll('label')].find(e=>e.textContent.includes(${JSON.stringify(labelText)}));const e=label?.parentElement?.querySelector('[role="combobox"]');if(!e||e.dataset.disabled!==undefined)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return e.contains(document.elementFromPoint(x,y))?{x,y}:null})()`, `${labelText} select`)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...p })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 1 })
  await click(cdp, optionText, '[role="option"]')
}

async function addNode(cdp, label, moduleType) {
  const pane = await waitFor(cdp, `(()=>{const e=document.querySelector('.react-flow__pane');if(!e)return null;const r=e.getBoundingClientRect(),nodes=[...document.querySelectorAll('.react-flow__node')];for(const yf of [.16,.37,.58,.79])for(const xf of [.10,.32,.54,.76]){const x=r.x+r.width*xf,y=r.y+r.height*yf,clear=nodes.every(node=>{const n=node.getBoundingClientRect();return Math.abs((n.left+n.right)/2-x)>170||Math.abs((n.top+n.bottom)/2-y)>90});if(clear&&document.elementFromPoint(x,y)===e)return{x,y}}return null})()`, 'workflow canvas')
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...pane, button: 'right', clickCount: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...pane, button: 'right', clickCount: 1 })
  await setInput(cdp, 'input[placeholder="搜索模块（支持拼音）"]', label)
  await click(cdp, label, '[role="button"]')
  const nodeId = await waitFor(cdp, `(()=>{const rows=[...document.querySelectorAll('.react-flow__node')].filter(e=>e.textContent.includes(${JSON.stringify(label)}));return rows.at(-1)?.dataset.id||null})()`, `${moduleType} node`)
  await selectNode(cdp, nodeId, moduleType)
  return nodeId
}

async function selectNode(cdp, nodeId, moduleType) {
  const p = await waitFor(cdp, `(()=>{const e=document.querySelector('.react-flow__node[data-id=${JSON.stringify(nodeId)}]');if(!e)return null;const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`, `node ${nodeId}`)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 1 })
  await waitFor(cdp, `[...document.querySelectorAll('span')].some(e=>e.getClientRects().length&&e.textContent.trim()===${JSON.stringify(moduleType)}&&e.classList.contains('badge'))`, `${moduleType} config`)
}

async function connectNodes(cdp, sourceId, targetId) {
  const points = await waitFor(cdp, `(()=>{const a=document.querySelector('.react-flow__node[data-id=${JSON.stringify(sourceId)}] .react-flow__handle.source:not([data-handleid])'),b=document.querySelector('.react-flow__node[data-id=${JSON.stringify(targetId)}] .react-flow__handle.target');if(!a||!b)return null;const ar=a.getBoundingClientRect(),br=b.getBoundingClientRect();return{a:{x:ar.x+ar.width/2,y:ar.y+ar.height/2},b:{x:br.x+br.width/2,y:br.y+br.height/2}}})()`, `handles ${sourceId} -> ${targetId}`)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...points.a, button: 'left', buttons: 1, clickCount: 1 })
  for (let step = 1; step <= 10; step++) await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', x: points.a.x + (points.b.x - points.a.x) * step / 10, y: points.a.y + (points.b.y - points.a.y) * step / 10, button: 'left', buttons: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...points.b, button: 'left', buttons: 0, clickCount: 1 })
  await wait(120)
}

function cloakProcesses(workspace) {
  return execFileSync('ps', ['-axo', 'command='], { encoding: 'utf8' }).split('\n').filter(line => line.includes(workspace) && /Chromium|CloakBrowser/.test(line))
}

async function capture(cdp, path) {
  const { data } = await cdp.command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  await writeFile(path, data, 'base64')
}

async function buildHash() {
  const hash = createHash('sha256')
  for (const file of (await readdir(join(root, 'apps/desktop/out'), { recursive: true })).filter(file => /\.(js|css|html)$/.test(file)).sort()) hash.update(file).update(await readFile(join(root, 'apps/desktop/out', file)))
  return hash.digest('hex')
}

async function packagedBuildHashes() {
  const executableIndex = process.argv.indexOf('--executable')
  assert.notEqual(executableIndex, -1)
  const resources = resolve(dirname(resolve(process.argv[executableIndex + 1])), '../Resources')
  return {
    appAsarSha256: await fileHash(join(resources, 'app.asar')),
    backendExecutableSha256: await fileHash(join(resources, 'backend', 'autoflow-backend')),
  }
}

async function fileHash(path) {
  return createHash('sha256').update(await readFile(path)).digest('hex')
}
