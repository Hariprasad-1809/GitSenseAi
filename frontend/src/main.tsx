import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { runBootstrapRouteGuard } from './utils/session'

// Execute bootstrap route guard synchronously BEFORE React mounts
runBootstrapRouteGuard();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
