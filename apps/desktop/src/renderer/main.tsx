import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './app/App'
import './styles/index.css'

const root = document.getElementById('root')

if (!root) throw new Error('renderer root element is missing')

const reactRoot = createRoot(root)
if (import.meta.env.DEV && location.hash === '#/__ui') {
  void import('./shared/ui-lab/UiLabPage').then(({ UiLabPage }) => {
    reactRoot.render(<StrictMode><UiLabPage /></StrictMode>)
  })
} else {
  reactRoot.render(<StrictMode><App /></StrictMode>)
}
