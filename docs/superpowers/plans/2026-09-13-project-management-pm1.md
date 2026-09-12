# PM1 项目入口、管理表单与项目上下文执行卡

> **面向 AI 代理：** 使用 writing-plans 形成此卡，subagent-driven-development 实施；每包先做规格审查，再做工程质量审查；test-driven-development 与 verification-before-completion 用于实现及交付核验。用户已明确批准本计划和独立文件并行。

- 日期：2026-09-13；状态：confirmed / in_progress。
- 目标：真实创建、编辑、搜索、排序、分页、打开项目，保留最近访问，形成项目概览和六页签上下文。
- 架构：Electron/React + 单 FastAPI/SQLite；Studio 是唯一执行器。PM1 不提供数据表、自动化执行、统计、环境、归档、恢复或删除。
- 基线：正式主线 1f80f977aac427d137bbd5a1a3afeac52f42a82c，设计/PM0 9c361f4；控件源 1fb58e1；实施工作区 autoflow-project-management-pm1 / codex/project-management-pm1。其他工作区只读，不复制未提交内容。
- 规格：[功能结构](../../project-management/design/functional-structure.md)、[接口契约](../../project-management/implementation/api-contracts.md)、[总里程碑](2026-09-13-project-management-milestones.md)。本卡落实用户本轮批准的PM1细节；PM0历史报告保持不变。

## 固定规则与本轮澄清

1. 名称按Python strip去首尾空白后1–36 Unicode码点；描述0–120码点。前端按码点计数并与后端空白测试向量一致；name_key=规范名称.casefold，数据库唯一，归档仍占名，不增加NFC/NFKC。
2. ProjectSummary计数可省略，和Overview共享ProjectCapabilities六键automations/data/runs/environments/statistics/sync，PM1均notImplemented。概览仅显示真实项目资料，不补零。
3. POST省略defaultResources时服务端补{profileId:null,proxy:{mode:'sourceDefault'},modelProviderId:null}；显式传入仍验证组合并保存，引用资源缺失不拦保存；PATCH省略保留。UI只编辑名称/描述。
4. 项目创建revision=1；有效变化CAS后+1，无变化保持；空PATCH422。先按Idempotency-Key查同请求，再检查revision。相同key异请求409 OPERATION_PAYLOAD_MISMATCH；首次创建201，重复终态200。
5. 项目与project_operations结果同短事务提交，operation创建即关联projectId；结果是当时快照。失响应以原key查询，不换key盲提交。
6. 默认sort=-lastOpenedAt，NULLS LAST，updatedAt DESC/id ASC收尾；支持name/-name、updatedAt/-updatedAt、lastOpenedAt/-lastOpenedAt。默认page=1/pageSize=50，上限200，q查名称和描述。
7. edit只允许active；closing423，archived/deleting409，deleted404。GET可读deleting，open只允许active/closing/archived且仅改lastOpenedAt。复用QuiesceGate，不建空blocker框架。
8. 正式API仅10项：projects GET/POST；project GET/PATCH/open/overview；project operations list/get/by-key；workspace create operation by-key。无DELETE/archive/restore/impact/Run路由。
9. 首次公开资源选择组件在PM3，影响和生命周期弹窗在PM8；PM1不创建无消费者组件或假入口。
10. 查询按workspace/instance/project隔离；脏表单身份按workspace/project/draftSession，不随instance改变。同工作区重连保草稿；真实换工作区清状态。旧实例mutation先用新session原key核验，旧scope回调不得操作当前界面。

## 文件责任与依赖

| 范围 | 文件 / 责任 |
|---|---|
| 后端领域与用例 | 新增 apps/backend/src/autoflow/domain/projects/{models,ports}.py、application/projects/service.py；后端智能体 |
| 后端持久化与HTTP | infrastructure/database/projects.py、adapters/http/{projects,project_schemas}.py、项目测试；后端智能体。普通转发不另拆层 |
| ORM/迁移/装配 | infrastructure/database/models.py、migrations/versions/pm01_projects.py、bootstrap/app.py、统一错误集成；主协调统一接入 |
| 基础控件 | renderer/shared/components及styles/index.css，依赖及适配；主协调选择已有控件最小依赖闭包，不覆盖Studio会话代码 |
| 项目领域前端 | renderer/domains/projects/的api、types、form-schema、hooks、components、pages、tests；前端智能体 |
| 应用接入 | renderer/app/App.tsx、ApplicationHeader.tsx、项目路由/离开协调及测试、唯一generated.ts；主协调 |
| 验收 | scripts/smoke-project-management.mjs、docs/migration/project-management-pm1/、覆盖/账本/.ai；主协调 |

上表省略前缀：后端均apps/backend/src/autoflow；renderer均apps/desktop/src/renderer。迁移从已提交0005_workflow_documents派生，主协调开工复核heads；不改0001–0005。未实际需要的模块目录不创建。

## 包1：隔离基线与控件接入

- [x] 建立指定工作区，以正式主线合入PM0；保留Studio和项目文档两部分。
- [ ] 运行主线后端/前端基线测试并记录结果。
- [ ] 将本卡及契约勘误纳入文档，记录本轮PM0验收后进入PM1授权。
- [ ] 读取控件1fb58e1及父链，仅接入本阶段使用的Table/Pagination/Search/Select/ScrollArea/反馈及其依赖、tokens和widthfix；修改既有消费者仅为API兼容。
- [ ] 跑相关控件测试、类型检查和现有页面测试；规格审查→质量审查→提交。

## 包2：项目事务与HTTP（PM1-A/C后端）

- [ ] 在tests/contract/test_projects.py先写下列测试并运行确认404失败；补仓储并发/迁移和领域边界测试。

```python
def test_create_retry_and_lookup_return_one_project(client):
    key = '10000000-0000-4000-8000-000000000001'
    headers = {'Idempotency-Key': key}
    payload = {'name': '业务 A', 'description': '项目测试'}
    first = client.post('/api/v1/projects', json=payload, headers=headers)
    assert first.status_code == 201
    again = client.post('/api/v1/projects', json=payload, headers=headers)
    assert again.status_code == 200
    assert again.json() == first.json()
    op = client.get(f'/api/v1/workspace/operations/by-idempotency-key/{key}').json()
    assert op['status'] == 'succeeded'
    assert op['result']['projectId'] == first.json()['projectId']
    assert client.get('/api/v1/projects').json()['total'] == 1
```

- [ ] 实现projects与project_operations两个真实表、事务仓储、用例、10项HTTP；不复用代理专用操作结构，不建后台调度器。
- [ ] 注册ORM、pm01迁移及App路由，沿现有错误封装；错误details含domainCode/retryable，revision冲突给最新项目。
- [ ] 测试同key/不同key竞争、同名casefold、无变化CAS、非法引用组合、操作跨项目404、停写、重启持久、open不改updatedAt。
- [ ] 跑定向pytest/ruff/mypy，规格审查→质量审查→提交；真实handler后生成唯一OpenAPI类型。

## 包3：领域组件与项目页面（PM1-A/B前端）

- [ ] 先写ProjectFormDialog、ProjectDirectory、ProjectTabs测试，覆盖码点长度、错误定位、保存中、Escape和未保存确认。
- [ ] 先完成FormDialog、列表、Header、Tabs、CapabilityState，再组DirectoryPage/OverviewPage。服务端类型只引用generated.ts；表单值可以是独立UI类型。
- [ ] api通过现有client，读取传AbortSignal，持久命令原key重查恢复，禁止生产mock。组件样例仅在测试中。
- [ ] 验证409/后台刷新保草稿、未知结果查询、请求迟到的scope/form epoch保护、目录无匹配和刷新失败。
- [ ] 跑领域Vitest与类型检查；规格审查→质量审查→提交。

## 包4：导航与隔离集成（PM1-B/C）

- [ ] 先写路由解析/序列化、返回目录、hashchange/back/forward离开取消测试。
- [ ] App唯一hash owner；顶部新增项目，路径#/projects与#/projects/{projectId}/{tab}。六页签概览真实，其余共享“暂未开放”状态无假动作。
- [ ] 目录状态保留q/lifecycleState/sort/page/pageSize/滚动位置；成功加载后恢复滚动，页码失效落最近有效页。
- [ ] ProjectFormDialog未保存离开提供保存后离开/放弃/继续编辑，保存失败留原处；取消恢复规范hash。提交中不可关闭。
- [ ] 使用现有useDesktopSession/ApiProvider，不新建第二查询上下文；workspaceChanging禁提交，实际切换清项目路由，同工作区重连保草稿。
- [ ] 真实API联调后运行全套门禁，规格与工程审查均完成才进入真实验收。

## 包5：真实应用、证据与阶段收口

- [ ] 扩展现有Electron CDP/sidecar helper创建项目冒烟脚本，测试工作区及userData均为本轮临时目录，不触碰用户数据。
- [ ] 实际执行新建A/B→编辑→搜索分页→打开→返回→409外部编辑→重连→重启再开，另一个工作区验证隔离。
- [ ] 验收Tab/Enter/Escape/焦点、200%缩放、长名称、下拉宽度；现有浏览器/代理/模型/设置/Studio入口回归。
- [ ] 保存脱敏截图和机器事实。未运行Windows/其他CPU架构/安装包明确标未执行，不以源码测试替代。
- [ ] 更新覆盖仅把PM-02标完整，PM-01/03/OV-01标本阶段部分交付；PM2+证据不填。保留PM0静态报告及校验器的历史用途，不拿其“仅文档变更”约束检查PM1业务代码。
- [ ] 同步执行账本、结构和.ai，提交阶段验收报告，保留分支，不合并主目录、不推送、不自动进入PM2。

## 验证命令

```bash
uv run --directory apps/backend pytest tests/contract/test_projects.py tests/integration/test_project_repository.py tests/integration/test_project_migrations.py -q
uv run --directory apps/backend pytest -q
uv run --directory apps/backend ruff check .
uv run --directory apps/backend mypy src
npm --workspace @autoflow/desktop test -- src/renderer/domains/projects
npm run openapi:generate
npm run openapi:check
npm test
npm run typecheck
npm run lint
npm run build
npm run test:scripts
npm run test:structure
node scripts/smoke-project-management.mjs
git diff --check
```

每条命令须确认退出码并记录证据，测试不存在不能视为通过。真实应用独立记录，最终覆盖集合仍为48/178/18/7；PM1不宣称后续业务或平台已通过。
