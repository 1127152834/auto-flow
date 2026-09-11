# AutoFlow 跨平台基础骨架实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 subagent-driven-development（推荐）或 executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在空仓库中建立可在 Windows 和 macOS 启动、测试和打包的 Electron + React + Python FastAPI sidecar 最小闭环。

**架构：** Electron main 负责桌面生命周期和 sidecar 监督，preload 只暴露窄能力 API，React renderer 只通过本机 HTTP 访问 FastAPI。后端从第一天按 bootstrap、adapters、application、domain、infrastructure 分层；本计划不迁移旧业务，也不复制 WebRPA 代码。

**技术栈：** Electron、React、TypeScript、Vite、Vitest、FastAPI、Pydantic 2、Uvicorn、Python 3.11、pytest、Ruff、mypy、npm workspaces、PyInstaller。

**规格：** [`docs/architecture/README.md`](../../architecture/README.md)；迁移边界见 [`docs/migration/README.md`](../../migration/README.md)。

## 全局约束

- 目标平台：Windows x64、macOS Apple Silicon、macOS Intel。
- Python 运行时：`>=3.11,<3.12`；升级版本必须单独完成兼容性验证。
- sidecar 只绑定 loopback，使用随机端口和 instance token。
- Electron main 不包含领域逻辑；React 不访问文件系统、数据库或 Electron Node API。
- Python domain 不 import FastAPI、SQLAlchemy、Electron 或操作系统专用包。
- 前后端健康数据通过 OpenAPI 生成的 TypeScript 类型消费。
- 每个任务结束都运行该任务列出的验证命令并提交独立 commit。
- 本计划不引入 WebRPA 运行时、协议兼容层、外部服务或 WebRPA 源码。

---

### 任务 1：建立仓库工具链和结构检查

**文件：**
- 创建：`package.json`
- 创建：`apps/desktop/package.json`
- 创建：`apps/backend/pyproject.toml`
- 创建：`.gitignore`
- 创建：`.editorconfig`
- 创建：`scripts/structure.test.mjs`
- 修改：`README.md`，补充开发命令入口

- [ ] **步骤 1：编写失败的结构检查**

```js
// scripts/structure.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'

for (const path of [
  'apps/desktop/src/main',
  'apps/desktop/src/preload',
  'apps/desktop/src/renderer',
  'apps/backend/src/autoflow',
  'apps/backend/tests',
]) {
  test(`required path exists: ${path}`, () => assert.equal(existsSync(path), true))
}

test('root scripts expose the foundation checks', () => {
  const packageJson = JSON.parse(readFileSync('package.json', 'utf8'))
  assert.equal(typeof packageJson.scripts['test:structure'], 'string')
  assert.equal(typeof packageJson.scripts['typecheck'], 'string')
})
```

- [ ] **步骤 2：运行检查确认失败**

运行：`node --test scripts/structure.test.mjs`

预期：FAIL，报告目录和 `package.json` 尚不存在。

- [ ] **步骤 3：编写最小工具链配置**

`package.json` 使用 npm workspaces：

```json
{
  "name": "autoflow",
  "private": true,
  "workspaces": ["apps/desktop"],
  "scripts": {
    "test:structure": "node --test scripts/structure.test.mjs",
    "dev": "npm --workspace @autoflow/desktop run dev",
    "test": "npm --workspace @autoflow/desktop test",
    "typecheck": "npm --workspace @autoflow/desktop run typecheck",
    "lint": "npm --workspace @autoflow/desktop run lint"
  }
}
```

`apps/desktop/package.json` 固定包名 `@autoflow/desktop`，提供 `dev`、`build`、`test`、`typecheck`、`lint` 脚本；依赖只加入 Electron、React、React DOM、Vite、TypeScript、Vitest 和 Electron Vite 所需包。

`apps/backend/pyproject.toml` 固定 `requires-python = ">=3.11,<3.12"`，生产依赖只包含 FastAPI、Pydantic、Uvicorn；开发依赖包含 pytest、pytest-asyncio、ruff、mypy。

- [ ] **步骤 4：运行检查确认通过**

运行：

```bash
npm install
npm run test:structure
cd apps/backend && uv lock && uv run pytest
```

预期：结构测试通过；后端尚未有测试时 pytest 输出 `no tests ran` 不作为最终门槛，任务 2 完成后重新运行后端测试。

- [ ] **步骤 5：Commit**

```bash
git add package.json apps/desktop/package.json apps/backend/pyproject.toml .gitignore .editorconfig scripts/structure.test.mjs README.md package-lock.json apps/backend/uv.lock
git commit -m "chore: establish monorepo toolchain"
```

### 任务 2：建立 FastAPI sidecar 启动、健康检查和就绪协议

**文件：**
- 创建：`apps/backend/src/autoflow/__init__.py`
- 创建：`apps/backend/src/autoflow/__main__.py`
- 创建：`apps/backend/src/autoflow/bootstrap/config.py`
- 创建：`apps/backend/src/autoflow/bootstrap/app.py`
- 创建：`apps/backend/src/autoflow/adapters/http/health.py`
- 创建：`apps/backend/src/autoflow/adapters/http/ready.py`
- 创建：`apps/backend/tests/unit/test_config.py`
- 创建：`apps/backend/tests/unit/test_health.py`
- 创建：`apps/backend/tests/unit/test_ready.py`

- [ ] **步骤 1：编写配置、健康和就绪协议测试**

```python
# apps/backend/tests/unit/test_ready.py
from autoflow.bootstrap.ready import ready_line


def test_ready_line_is_machine_readable():
    assert ready_line(port=43127, api_version="v1", instance_id="test") == (
        'AUTOFLOW_READY {"apiVersion":"v1","instanceId":"test","port":43127}'
    )
```

```python
# apps/backend/tests/unit/test_health.py
from fastapi.testclient import TestClient
from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings


def test_health_returns_instance_metadata():
    client = TestClient(create_app(Settings(data_dir="/tmp/autoflow-test", instance_id="test")))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "apiVersion": "v1",
        "instanceId": "test",
    }
```

- [ ] **步骤 2：运行测试确认失败**

运行：`cd apps/backend && uv run pytest tests/unit/test_ready.py tests/unit/test_health.py -q`

预期：FAIL，模块和 `create_app` 尚不存在。

- [ ] **步骤 3：实现最小 bootstrap**

`Settings` 只接收 `data_dir`、`instance_id`、`instance_token`、`parent_pid` 和 `api_version`；`create_app(settings)` 注册 `/health`，并在请求头 `x-autoflow-token` 不匹配时对 `/api/v1/*` 返回 401。

`__main__.py` 接收 `--host 127.0.0.1`、`--port 0`、`--instance-token`、`--instance-id` 和 `--parent-pid`，启动 Uvicorn，在实际端口确定后输出一行 `AUTOFLOW_READY <compact-json>`。就绪输出只能来自启动入口，不能由业务路由拼接。

- [ ] **步骤 4：运行测试确认通过**

运行：`cd apps/backend && uv run pytest -q`

预期：配置、健康、就绪和 token 测试全部 PASS。

- [ ] **步骤 5：Commit**

```bash
git add apps/backend
 git commit -m "feat: add FastAPI sidecar foundation"
```

### 任务 3：建立 Electron main、preload 和 sidecar supervisor

**文件：**
- 创建：`apps/desktop/electron.vite.config.ts`
- 创建：`apps/desktop/tsconfig.json`
- 创建：`apps/desktop/src/main/index.ts`
- 创建：`apps/desktop/src/main/sidecar/supervisor.ts`
- 创建：`apps/desktop/src/main/sidecar/ready-protocol.ts`
- 创建：`apps/desktop/src/main/platform/paths.ts`
- 创建：`apps/desktop/src/preload/index.ts`
- 创建：`apps/desktop/src/main/sidecar/ready-protocol.test.ts`
- 创建：`apps/desktop/src/main/sidecar/supervisor.test.ts`

- [ ] **步骤 1：编写就绪行解析和 supervisor 状态测试**

```ts
// apps/desktop/src/main/sidecar/ready-protocol.test.ts
import { describe, expect, it } from 'vitest'
import { parseReadyLine } from './ready-protocol'

describe('parseReadyLine', () => {
  it('parses the backend readiness line', () => {
    expect(parseReadyLine('AUTOFLOW_READY {"apiVersion":"v1","instanceId":"x","port":43127}'))
      .toEqual({ apiVersion: 'v1', instanceId: 'x', port: 43127 })
  })

  it('rejects a readiness line with a non-loopback port payload', () => {
    expect(() => parseReadyLine('AUTOFLOW_READY {"apiVersion":"v1","instanceId":"x","port":-1}'))
      .toThrow('invalid port')
  })
})
```

- [ ] **步骤 2：运行测试确认失败**

运行：`npm --workspace @autoflow/desktop test -- src/main/sidecar/ready-protocol.test.ts`

预期：FAIL，解析器和 supervisor 状态尚不存在。

- [ ] **步骤 3：实现 Electron foundation**

`ready-protocol.ts` 只负责校验前缀、JSON 字段、端口范围 1–65535 和 `apiVersion`；不启动进程。

`supervisor.ts` 定义 `SidecarStatus = 'starting' | 'ready' | 'failed' | 'stopped'`，负责：

- 开发模式启动 `python -m autoflow`，生产模式启动打包后的 sidecar；
- 生成随机 instance token 并通过参数传入；
- 读取 stdout 就绪行；
- 对 sidecar 退出、超时和坏 JSON 返回结构化错误；
- `stop()` 发送 SIGTERM，超时后在 Windows 使用 `taskkill`，在 macOS 使用 SIGKILL；
- 监听 Electron `before-quit`，保证只调用一次 stop。

`preload/index.ts` 只暴露 `window.autoflow.getSidecarStatus()`、`restartSidecar()` 和 `getPlatformPaths()`，不暴露 `ipcRenderer`。

- [ ] **步骤 4：运行测试确认通过**

运行：

```bash
npm --workspace @autoflow/desktop test -- src/main/sidecar/ready-protocol.test.ts src/main/sidecar/supervisor.test.ts
npm --workspace @autoflow/desktop run typecheck
```

预期：协议和状态测试 PASS，TypeScript 无错误。

- [ ] **步骤 5：Commit**

```bash
git add apps/desktop
 git commit -m "feat: supervise local backend from Electron"
```

### 任务 4：建立 React renderer、API client 和服务恢复状态

**文件：**
- 创建：`apps/desktop/src/renderer/index.html`
- 创建：`apps/desktop/src/renderer/main.tsx`
- 创建：`apps/desktop/src/renderer/app/App.tsx`
- 创建：`apps/desktop/src/renderer/app/app-state.ts`
- 创建：`apps/desktop/src/renderer/shared/api/client.ts`
- 创建：`apps/desktop/src/renderer/shared/api/types.ts`
- 创建：`apps/desktop/src/renderer/shared/components/State.tsx`
- 创建：`apps/desktop/src/renderer/styles/index.css`
- 创建：`apps/desktop/src/renderer/app/App.test.tsx`
- 创建：`apps/desktop/src/renderer/shared/api/client.test.ts`

- [ ] **步骤 1：编写健康加载和失败恢复测试**

```tsx
// apps/desktop/src/renderer/app/App.test.tsx
it('shows sidecar health after the API responds', async () => {
  server.use(http.get('/health', () => HttpResponse.json({
    status: 'ok', apiVersion: 'v1', instanceId: 'test'
  })))
  render(<App />)
  expect(await screen.findByText('服务已连接')).toBeInTheDocument()
})

it('shows recovery action when the API is unavailable', async () => {
  server.use(http.get('/health', () => HttpResponse.error()))
  render(<App />)
  expect(await screen.findByRole('button', { name: '重新连接' })).toBeInTheDocument()
})
```

- [ ] **步骤 2：运行测试确认失败**

运行：`npm --workspace @autoflow/desktop test -- src/renderer/app/App.test.tsx`

预期：FAIL，renderer、API client 和状态组件尚不存在。

- [ ] **步骤 3：实现最小 renderer**

API client 从 `window.autoflow.getSidecarStatus()` 取得 loopback base URL 和 token，所有请求统一附带 `x-autoflow-token`。`App` 只实现健康查询、服务已连接、服务离线和重新连接四种状态；页面路由和业务领域不在本任务中创建。

React 测试使用 MSW 或现有的 fetch mock 工具模拟 `/health`，不启动真实 Electron 和 Python 进程。

- [ ] **步骤 4：运行测试确认通过**

运行：

```bash
npm --workspace @autoflow/desktop test -- src/renderer/app/App.test.tsx src/renderer/shared/api/client.test.ts
npm --workspace @autoflow/desktop run typecheck
npm --workspace @autoflow/desktop run lint
```

预期：健康、离线、重连和 token 测试 PASS，TypeScript 和 ESLint 无错误。

- [ ] **步骤 5：Commit**

```bash
git add apps/desktop/src/renderer
 git commit -m "feat: add renderer health shell"
```

### 任务 5：建立跨平台路径服务和 backend/desktop 启动配置

**文件：**
- 创建：`apps/backend/src/autoflow/infrastructure/filesystem/paths.py`
- 创建：`apps/backend/tests/unit/test_paths.py`
- 创建：`apps/desktop/src/main/platform/paths.ts`
- 创建：`apps/desktop/src/main/platform/paths.test.ts`
- 修改：`apps/backend/src/autoflow/bootstrap/config.py`
- 修改：`apps/desktop/src/main/sidecar/supervisor.ts`

- [ ] **步骤 1：编写路径规则测试**

```python
# apps/backend/tests/unit/test_paths.py
from pathlib import PurePath
from autoflow.infrastructure.filesystem.paths import AppPaths


def test_paths_are_children_of_injected_data_dir(tmp_path):
    paths = AppPaths.from_data_dir(tmp_path)
    assert paths.database == tmp_path / 'data' / 'autoflow.sqlite3'
    assert paths.logs == tmp_path / 'logs'
    assert paths.workspace == tmp_path / 'workspace'
```

```ts
// apps/desktop/src/main/platform/paths.test.ts
it('passes the Electron userData directory instead of guessing an OS path', () => {
  expect(resolveBackendEnvironment('/Users/test/Library/Application Support/AutoFlow'))
    .toEqual({ AUTOFLOW_DATA_DIR: '/Users/test/Library/Application Support/AutoFlow' })
})
```

- [ ] **步骤 2：运行测试确认失败**

运行：

```bash
cd apps/backend && uv run pytest tests/unit/test_paths.py -q
npm --workspace @autoflow/desktop test -- src/main/platform/paths.test.ts
```

预期：两个测试均因 `AppPaths` 和 `resolveBackendEnvironment` 不存在而失败。

- [ ] **步骤 3：实现注入式路径服务**

后端 `AppPaths.from_data_dir()` 只接受 Electron 或 CLI 注入的绝对路径，并派生 `data`、`logs`、`workspace`、`cache`、`tmp` 子目录；创建目录集中在 bootstrap，不在 domain 中创建。

Electron 使用 `app.getPath('userData')` 计算数据目录，通过环境变量 `AUTOFLOW_DATA_DIR` 传入 sidecar。后端独立运行时必须要求显式 `--data-dir`，避免把测试数据写进源码目录。

- [ ] **步骤 4：运行测试确认通过**

运行：

```bash
cd apps/backend && uv run pytest -q
npm --workspace @autoflow/desktop test -- src/main/platform/paths.test.ts
npm --workspace @autoflow/desktop run typecheck
```

预期：路径服务测试 PASS；Windows 风格和 macOS 风格的注入路径不会被业务代码重新解析或硬编码。

- [ ] **步骤 5：Commit**

```bash
git add apps/backend apps/desktop/src/main/platform apps/desktop/src/main/sidecar/supervisor.ts
 git commit -m "feat: inject platform data paths"
```

### 任务 6：加入 OpenAPI 导出、类型生成和跨平台 CI

**文件：**
- 创建：`apps/backend/src/autoflow/adapters/http/openapi.py`
- 创建：`scripts/generate-api.mjs`
- 创建：`.github/workflows/ci.yml`
- 创建：`scripts/smoke-sidecar.mjs`
- 修改：`package.json`
- 修改：`apps/desktop/package.json`
- 修改：`apps/backend/pyproject.toml`

- [ ] **步骤 1：编写契约和 smoke 命令的失败检查**

```js
// scripts/smoke-sidecar.mjs
const response = await fetch(`${baseUrl}/health`, {
  headers: { 'x-autoflow-token': token },
})
if (!response.ok) throw new Error(`health check failed: ${response.status}`)
const body = await response.json()
if (body.apiVersion !== 'v1') throw new Error('unexpected API version')
```

- [ ] **步骤 2：运行检查确认失败**

运行：`npm run openapi:check && node scripts/smoke-sidecar.mjs`

预期：FAIL，因为 OpenAPI 生成、sidecar 启动和 smoke 参数尚不存在。

- [ ] **步骤 3：实现契约和 CI**

后端导出 `/openapi.json`；`scripts/generate-api.mjs` 使用 `openapi-typescript` 生成 `apps/desktop/src/renderer/shared/api/generated.ts`，并在 CI 中检查生成文件无差异。

`smoke-sidecar.mjs` 启动开发 sidecar，读取就绪行，访问健康接口，然后发送关闭信号并确认进程退出。

`.github/workflows/ci.yml` 使用 Windows 和 macOS runner 矩阵执行：

```yaml
strategy:
  matrix:
    os: [windows-latest, macos-13, macos-14]
```

每个平台执行 Python lock 安装、pytest、Ruff、mypy、npm install、类型检查、Vitest、OpenAPI 检查和 sidecar smoke；CI 不执行签名，签名只在发布工作流中配置。

- [ ] **步骤 4：运行验证确认通过**

运行：

```bash
npm run openapi:generate
npm run openapi:check
npm run typecheck
npm test
cd apps/backend && uv run ruff check . && uv run mypy src && uv run pytest -q
node scripts/smoke-sidecar.mjs
```

预期：生成文件无差异、前后端测试通过、静态检查通过、sidecar 启动和退出成功。

- [ ] **步骤 5：Commit**

```bash
git add package.json apps/desktop/package.json apps/backend/pyproject.toml scripts .github apps/desktop/src/renderer/shared/api/generated.ts
 git commit -m "ci: verify cross-platform foundation"
```

## 计划自检

- 架构规格的 Electron、preload、React、FastAPI、sidecar、路径服务、OpenAPI、Windows/macOS 构建和质量门槛分别由任务 2–6 覆盖。
- 工作流 IR、执行器注册表、WebRPA 源码移植未混入基础骨架，单独属于工作流计划。
- 全局资源迁移未混入基础骨架，单独属于资源迁移计划。
- 计划中的文件、命令、测试和类型名称已统一为 `SidecarStatus`、`parseReadyLine`、`AppPaths`、`resolveBackendEnvironment` 和 `Workflow IR`。
- 未使用 `TODO`、`TBD`、`待定` 或未定义的“适当处理”步骤。
