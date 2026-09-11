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
  'apps/desktop/package.json',
  'apps/backend/pyproject.toml',
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

预期：FAIL，报告所需配置文件尚不存在。

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

```json
{
  "name": "@autoflow/desktop",
  "private": true,
  "main": "./out/main/index.js",
  "scripts": {
    "dev": "electron-vite dev",
    "build": "electron-vite build",
    "test": "vitest run",
    "typecheck": "tsc --noEmit",
    "lint": "eslint ."
  }
}
```

`apps/backend/pyproject.toml` 固定 `requires-python = ">=3.11,<3.12"`，生产依赖只包含 FastAPI、Pydantic、Uvicorn；开发依赖包含 httpx、pytest、pytest-asyncio、ruff、mypy。

- [ ] **步骤 4：运行检查确认通过**

运行：

```bash
npm install
npm run test:structure
uv --directory apps/backend lock
```

预期：结构测试和依赖锁定通过；后端测试从任务 2 开始运行。

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
- 创建：`apps/backend/src/autoflow/bootstrap/ready.py`
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

运行：`uv --directory apps/backend run pytest tests/unit/test_ready.py tests/unit/test_health.py -q`

预期：FAIL，模块和 `create_app` 尚不存在。

- [ ] **步骤 3：实现最小 bootstrap**

`Settings` 只接收 `data_dir`、`instance_id`、`instance_token`、`parent_pid` 和 `api_version`；`create_app(settings)` 注册 `/health`，并在请求头 `x-autoflow-token` 不匹配时对 `/api/v1/*` 返回 401。

就绪协议的序列化实现固定为：

```python
# apps/backend/src/autoflow/bootstrap/ready.py
import json


def ready_line(*, port: int, api_version: str, instance_id: str) -> str:
    if not 1 <= port <= 65535:
        raise ValueError('invalid port')
    payload = {'apiVersion': api_version, 'instanceId': instance_id, 'port': port}
    return 'AUTOFLOW_READY ' + json.dumps(payload, sort_keys=True, separators=(',', ':'))
```

`__main__.py` 接收 `--host 127.0.0.1`、`--port 0`、`--instance-id` 和 `--parent-pid`，启动 Uvicorn，在实际端口确定后输出一行 `AUTOFLOW_READY <compact-json>`。就绪输出只能来自启动入口，不能由业务路由拼接。

- [ ] **步骤 4：运行测试确认通过**

运行：`uv --directory apps/backend run pytest -q`

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

  it('rejects a readiness line with an invalid port', () => {
    expect(() => parseReadyLine('AUTOFLOW_READY {"apiVersion":"v1","instanceId":"x","port":-1}'))
      .toThrow('invalid port')
  })
})
```

```ts
// apps/desktop/src/main/sidecar/supervisor.test.ts
import { describe, expect, it } from 'vitest'
import { applySidecarEvent, initialSidecarStatus } from './supervisor'

describe('sidecar status transitions', () => {
  it('only exposes a ready status after a valid ready event', () => {
    const starting = applySidecarEvent(initialSidecarStatus(), { type: 'spawned' })
    expect(starting).toEqual({ state: 'starting' })
    expect(applySidecarEvent(starting, {
      type: 'ready', apiVersion: 'v1', instanceId: 'x', port: 43127,
      baseUrl: 'http://127.0.0.1:43127', token: 'secret'
    })).toEqual({
      state: 'ready', apiVersion: 'v1', instanceId: 'x', port: 43127,
      baseUrl: 'http://127.0.0.1:43127', token: 'secret'
    })
  })
})
```

- [ ] **步骤 2：运行测试确认失败**

运行：`npm --workspace @autoflow/desktop test -- src/main/sidecar/ready-protocol.test.ts`

预期：FAIL，解析器和 supervisor 状态尚不存在。

- [ ] **步骤 3：实现 Electron foundation**

`ready-protocol.ts` 只负责校验前缀、JSON 字段、端口范围 1–65535 和 `apiVersion`；不启动进程。

```ts
export type SidecarReady = { apiVersion: 'v1'; instanceId: string; port: number }

export function parseReadyLine(line: string): SidecarReady {
  if (!line.startsWith('AUTOFLOW_READY ')) throw new Error('invalid readiness prefix')
  const value: unknown = JSON.parse(line.slice('AUTOFLOW_READY '.length))
  if (!value || typeof value !== 'object') throw new Error('invalid readiness payload')
  const data = value as Record<string, unknown>
  if (!Number.isInteger(data.port) || Number(data.port) < 1 || Number(data.port) > 65535)
    throw new Error('invalid port')
  if (data.apiVersion !== 'v1' || typeof data.instanceId !== 'string' || !data.instanceId)
    throw new Error('invalid instance metadata')
  return { apiVersion: 'v1', instanceId: data.instanceId, port: Number(data.port) }
}
```

`supervisor.ts` 使用以下对外状态，base URL 和 token 仅在 ready 状态存在；状态与 preload 返回类型必须保持一致：

```ts
export type SidecarStatus =
  | { state: 'starting' | 'stopped' }
  | { state: 'failed'; message: string }
  | { state: 'ready'; apiVersion: 'v1'; instanceId: string; port: number; baseUrl: string; token: string }
```

`initialSidecarStatus()` 返回 `{ state: 'stopped' }`；`applySidecarEvent()` 只接受 `spawned`、`ready`、`failed` 和 `stopped` 事件，并执行状态转换。真实进程监督器复用这一纯函数，保证状态测试不需要 Electron。

监督器负责：

- 开发模式启动 `python -m autoflow`，生产模式启动打包后的 sidecar；
- 生成随机 instance token 并通过 `AUTOFLOW_INSTANCE_TOKEN` 环境变量传入；日志和就绪行不输出 token；
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
- 修改：`apps/desktop/package.json`，加入 @testing-library/react、@testing-library/jest-dom、jsdom、eslint、typescript-eslint
- 创建：`apps/desktop/vitest.config.ts`，测试默认 jsdom，main 测试以文件头指定 node 环境
- 创建：`apps/desktop/eslint.config.js`，使用 ESLint 和 typescript-eslint 推荐规则，禁止未用变量和隐式 any
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
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { App } from './App'

beforeEach(() => {
  vi.stubGlobal('autoflow', {
    getSidecarStatus: vi.fn(async () => ({ state: 'ready', apiVersion: 'v1', port: 43127, baseUrl: 'http://127.0.0.1:43127', token: 'test', instanceId: 'test' })),
    restartSidecar: vi.fn(async () => undefined),
  })
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it('shows sidecar health after the API responds', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
    status: 'ok', apiVersion: 'v1', instanceId: 'test'
  }), { status: 200, headers: { 'content-type': 'application/json' } })))
  render(<App />)
  expect(await screen.findByText('服务已连接')).toBeInTheDocument()
})

it('shows recovery action when the API is unavailable', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('network error') }))
  render(<App />)
  expect(await screen.findByRole('button', { name: '重新连接' })).toBeInTheDocument()
})
```

- [ ] **步骤 2：运行测试确认失败**

运行：`npm --workspace @autoflow/desktop test -- src/renderer/app/App.test.tsx`

预期：FAIL，renderer、API client 和状态组件尚不存在。

- [ ] **步骤 3：实现最小 renderer**

API client 从 `window.autoflow.getSidecarStatus()` 取得 loopback base URL 和 token，所有请求统一附带 `x-autoflow-token`。`App` 只实现健康查询、服务已连接、服务离线和重新连接四种状态；页面路由和业务领域不在本任务中创建。

React 测试使用 Vitest 的 `vi.stubGlobal('fetch', ...)` 模拟 `/health`，不启动真实 Electron 和 Python 进程。

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
- 修改：`apps/desktop/src/main/platform/paths.ts`
- 创建：`apps/desktop/src/main/platform/paths.test.ts`
- 修改：`apps/backend/src/autoflow/bootstrap/config.py`
- 修改：`apps/desktop/src/main/sidecar/supervisor.ts`

- [ ] **步骤 1：编写路径规则测试**

```python
# apps/backend/tests/unit/test_paths.py
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
uv --directory apps/backend run pytest tests/unit/test_paths.py -q
npm --workspace @autoflow/desktop test -- src/main/platform/paths.test.ts
```

预期：两个测试均因 `AppPaths` 和 `resolveBackendEnvironment` 不存在而失败。

- [ ] **步骤 3：实现注入式路径服务**

后端 `AppPaths.from_data_dir()` 只接受 Electron 或 CLI 注入的绝对路径，并派生 `data`、`logs`、`workspace`、`cache`、`tmp` 子目录；创建目录集中在 bootstrap，不在 domain 中创建。

```python
# apps/backend/src/autoflow/infrastructure/filesystem/paths.py
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    data_dir: Path
    database: Path
    logs: Path
    workspace: Path
    cache: Path
    temp: Path

    @classmethod
    def from_data_dir(cls, root: Path) -> 'AppPaths':
        if not root.is_absolute():
            raise ValueError('data directory must be absolute')
        return cls(root, root / 'data' / 'autoflow.sqlite3', root / 'logs',
                   root / 'workspace', root / 'cache', root / 'tmp')
```

Electron 使用 `app.getPath('userData')` 计算数据目录，通过环境变量 `AUTOFLOW_DATA_DIR` 传入 sidecar。后端独立运行时必须要求显式 `--data-dir`，避免把测试数据写进源码目录。

- [ ] **步骤 4：运行测试确认通过**

运行：

```bash
uv --directory apps/backend run pytest -q
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
const baseUrl = process.env.AUTOFLOW_BASE_URL
const token = process.env.AUTOFLOW_INSTANCE_TOKEN
if (!baseUrl || !token) throw new Error('sidecar readiness environment is missing')
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
    os: [windows-2022, macos-15-intel, macos-15]
```

Runner 标签依据 [GitHub 官方清单](https://docs.github.com/en/actions/reference/runners/github-hosted-runners) 核对；`macos-15-intel` 为 x64，`macos-15` 为 arm64。工作流定义不等于远端测试已运行，验收必须附实际 job 结果。

每个平台执行 Python lock 安装、pytest、Ruff、mypy、npm ci、类型检查、Vitest、OpenAPI 检查和 sidecar smoke；CI 不执行签名，签名只在发布工作流中配置。

- [ ] **步骤 4：运行验证确认通过**

运行：

```bash
npm run openapi:generate
npm run openapi:check
npm run typecheck
npm test
uv --directory apps/backend run ruff check .
uv --directory apps/backend run mypy src
uv --directory apps/backend run pytest -q
node scripts/smoke-sidecar.mjs
```

预期：生成文件无差异、前后端测试通过、静态检查通过、sidecar 启动和退出成功。

- [ ] **步骤 5：Commit**

```bash
git add package.json apps/desktop/package.json apps/backend/pyproject.toml scripts .github apps/desktop/src/renderer/shared/api/generated.ts
git commit -m "ci: verify cross-platform foundation"
```

### 任务 7：验证分平台打包后的基础闭环

**文件：**
- 创建：`apps/backend/autoflow-backend.spec`
- 创建：`apps/desktop/electron-builder.yml`
- 创建：`scripts/build-backend.mjs`
- 修改：`scripts/smoke-sidecar.mjs`，支持 `--executable <path>`
- 修改：`apps/desktop/src/main/sidecar/supervisor.ts`，确定生产可执行路径
- 修改：`package.json` 和 `apps/desktop/package.json`，加入 backend:build、package:dir
- 修改：`.github/workflows/ci.yml`，加入按平台打包和产物检查

- [ ] **步骤 1：编写生产路径测试**

```ts
import { expect, it } from 'vitest'
import { packagedSidecarPath } from './ready-protocol'

it('resolves the Windows executable suffix', () => {
  expect(packagedSidecarPath('/resources', 'win32'))
    .toBe('/resources/backend/autoflow-backend.exe')
})
it('resolves the macOS executable name', () => {
  expect(packagedSidecarPath('/resources', 'darwin'))
    .toBe('/resources/backend/autoflow-backend')
})
```

- [ ] **步骤 2：运行路径测试确认失败**

运行：`npm --workspace @autoflow/desktop test -- src/main/sidecar/ready-protocol.test.ts`

预期：生产路径函数尚未导出。

- [ ] **步骤 3：实现目录打包配置**

路径函数使用运行平台的 `path.join`；测试使用 `path.join('/resources', 'backend', expectedName)` 断言，避免 Windows 测试硬编码正斜杠。实现定义如下：

```ts
import path from 'node:path'

export function packagedSidecarPath(resourcesPath: string, platform: NodeJS.Platform): string {
  return path.join(resourcesPath, 'backend',
    platform === 'win32' ? 'autoflow-backend.exe' : 'autoflow-backend')
}
```

PyInstaller 使用 onedir 模式，入口为 `src/autoflow/__main__.py`，`pathex` 包含 `src`，输出目录固定为 `apps/backend/dist/autoflow-backend`。完整复制该目录进入 Electron `resources/backend`，保留 Python 收集的数据文件与共享库。不要只复制单个可执行文件。

```yaml
# apps/desktop/electron-builder.yml
appId: dev.autoflow.desktop
productName: AutoFlow
files:
  - out/**
extraResources:
  - from: ../backend/dist/autoflow-backend
    to: backend
win:
  target: nsis
mac:
  target: dmg
  category: public.app-category.productivity
```

`build-backend.mjs` 使用 `spawnSync('uv', ['--directory', 'apps/backend', 'run', 'pyinstaller', '--noconfirm', 'autoflow-backend.spec'], { stdio: 'inherit' })`，透传失败退出码。构建依赖在后端 pyproject 的 build 组固定 PyInstaller，构建前同步该组。

- [ ] **步骤 4：运行真实产物检查**

运行：

```bash
npm run backend:build
npm --workspace @autoflow/desktop run build
npm run package:dir
node scripts/smoke-sidecar.mjs --executable <本平台打包资源中的真实sidecar绝对路径>
```

`package:dir` 使用 electron-builder 的目录模式。smoke 脚本必须校验路径存在、启动该可执行文件、等待就绪、获取健康响应、关闭并检查子进程退出。CI 用打包输出定位该真实路径并作为参数传入，不能回退到开发 Python。目录模式产物验证后，再生成对应 NSIS/DMG 产物。

验收证据包含：平台、CPU 架构、Python/Electron 版本、产物路径、健康响应和退出码。本机只能声称本机架构通过；其他两平台以 CI 或对应机器结果为准。公开发布的签名/notarization 在发布阶段配置，本任务只生成内部测试产物。

- [ ] **步骤 5：Commit**

```bash
git add apps/backend apps/desktop scripts package.json .github/workflows/ci.yml
git commit -m "build: verify bundled sidecar per platform"
```

## 计划自检

- 架构规格的 Electron、preload、React、FastAPI、sidecar、路径服务、OpenAPI、Windows/macOS 构建和质量门槛分别由任务 2–7 覆盖。
- 工作流 IR、执行器注册表、WebRPA 源码移植未混入基础骨架，单独属于工作流计划。
- 全局资源迁移未混入基础骨架，单独属于资源迁移计划。
- 计划中的文件、命令、测试和类型名称已统一为 `SidecarStatus`、`parseReadyLine`、`AppPaths`、`resolveBackendEnvironment` 和 `Workflow IR`。
- 所有步骤均有具体文件、操作、验证命令和验收结果。
