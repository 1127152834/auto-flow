import { createRoot } from 'react-dom/client'
import { ProxyManagementPage } from './domains/proxies'
import { createApiClient } from './shared/api/client'
import './styles/index.css'

// Served only by scripts/preview-proxies.mjs, against an isolated real sidecar.
const api = createApiClient({ baseUrl: window.location.origin, token: 'preview' })
const root = document.getElementById('root')
if (!root) throw new Error('preview root element is missing')

createRoot(root).render(
  <>
    <div className="flex items-center justify-between border-b border-line bg-surface px-8 py-4">
      <span className="text-lg font-semibold tracking-tight text-ink">AutoFlow</span>
      <span className="text-xs text-muted">代理管理独立预览 · 本地数据独立保存</span>
    </div>
    <ProxyManagementPage api={api} />
  </>,
)
