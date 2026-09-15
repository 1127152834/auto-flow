import { createRoot } from 'react-dom/client'
import { StudioErrorBoundary } from './domains/workflows/components/StudioErrorBoundary'
import { StudioApp } from './app/StudioApp'
import { StudioHostConnection } from './app/StudioHostConnection'
import './domains/workflows/styles/webrpa.css'
import './domains/workflows/styles/autoflow.css'
const root = document.getElementById('root')
if (!root) throw new Error('Studio root missing')
const electronHost = typeof window.autoflow?.getRuntimeContext === 'function'
const reactRoot = createRoot(root)

if (electronHost) {
  reactRoot.render(<StudioErrorBoundary><StudioHostConnection><StudioApp /></StudioHostConnection></StudioErrorBoundary>)
} else if (import.meta.env.DEV) {
  void Promise.all([
    import('./domains/workflows/api/config'),
    import('./domains/workflows/api/mock-server'),
    import('./domains/workflows/development/StudioMockTools'),
  ]).then(([{ configureStudioConnection }, { mockRequest }, { StudioMockTools }]) => {
    configureStudioConnection('http://autoflow-studio.mock', mockRequest)
    reactRoot.render(<StudioErrorBoundary><StudioApp tools={<StudioMockTools />} /></StudioErrorBoundary>)
  })
} else {
  reactRoot.render(<StudioErrorBoundary><div role="alert">正式工作流工作台必须从 AutoFlow 主应用打开。</div></StudioErrorBoundary>)
}
