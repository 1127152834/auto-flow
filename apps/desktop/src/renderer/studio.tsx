import { configureStudioConnection } from './domains/workflows/api/config'
import { mockRequest } from './domains/workflows/api/mock-server'
import { StudioMockTools } from './domains/workflows/development/StudioMockTools'
import { createRoot } from 'react-dom/client'
import { StudioErrorBoundary } from './domains/workflows/components/StudioErrorBoundary'
import { StudioApp } from './app/StudioApp'
import './domains/workflows/styles/webrpa.css'
import './domains/workflows/styles/autoflow.css'
configureStudioConnection('http://autoflow-studio.mock', mockRequest)
const root = document.getElementById('root')
if (!root) throw new Error('Studio root missing')
createRoot(root).render(<StudioErrorBoundary><StudioApp tools={<StudioMockTools />} /></StudioErrorBoundary>)
