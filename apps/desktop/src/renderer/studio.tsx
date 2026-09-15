import { configureStudioConnection } from './domains/workflows/api/config'
import { mockRequest } from './domains/workflows/api/mock-server'
import { StudioMockTools } from './domains/workflows/development/StudioMockTools'
import { createRoot } from 'react-dom/client'
import { StudioErrorBoundary } from './domains/workflows/components/StudioErrorBoundary'
import { StudioApp } from './app/StudioApp'
import { StudioHostConnection } from './app/StudioHostConnection'
import './domains/workflows/styles/webrpa.css'
import './domains/workflows/styles/autoflow.css'
const root = document.getElementById('root')
if (!root) throw new Error('Studio root missing')
const electronHost = typeof window.autoflow?.getRuntimeContext === 'function'
if (!electronHost) configureStudioConnection('http://autoflow-studio.mock', mockRequest)
createRoot(root).render(<StudioErrorBoundary>{electronHost
  ? <StudioHostConnection><StudioApp /></StudioHostConnection>
  : <StudioApp tools={<StudioMockTools />} />
}</StudioErrorBoundary>)
