import { setupEditorI18n } from './domains/workflows/lib/uiI18n'
import { createRoot } from 'react-dom/client'
import { StudioErrorBoundary } from './domains/workflows/components/StudioErrorBoundary'
import { StudioApp } from './app/StudioApp'
import './domains/workflows/styles/webrpa.css'
import './domains/workflows/styles/autoflow.css'
setupEditorI18n()
const root = document.getElementById('root')
if (!root) throw new Error('Studio root missing')
createRoot(root).render(<StudioErrorBoundary><StudioApp /></StudioErrorBoundary>)
