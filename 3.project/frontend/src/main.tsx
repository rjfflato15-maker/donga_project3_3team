import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'
import './sidebar-ui.css'
import './compare-ui.css'
import './compare-runtime.css'
import './components/review-workspace.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
