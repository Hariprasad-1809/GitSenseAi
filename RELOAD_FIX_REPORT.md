# Vercel SPA Routing & Bootstrap `/chat` Reload Redirection Technical Report

## 1. Executive Summary & Root Cause Analysis

### A. Vercel 404 Error Root Cause
When a user refreshed `https://git-sense-ai.vercel.app/chat`, Vercel attempted to serve a static file `/chat` or `/chat/index.html`. Since Vite is a Single Page Application (SPA) outputting a single `index.html` file, Vercel returned a static `404 NOT_FOUND` HTML response.

### B. Bootstrap Redirection Solution
To ensure refreshing on `/chat` immediately redirects the browser to `/` and initializes a new session without rendering `ChatPage`, a synchronous bootstrap route guard (`runBootstrapRouteGuard()`) was placed at the application's entry point (`main.tsx`) before React mounts.

---

## 2. Key Accomplishments & Technical Solutions

### 1. Vercel SPA Rewrite Configuration ([vercel.json](file:///d:/projects/GitSense_Ai/vercel.json))
Created `vercel.json` at root and frontend levels:
```json
{
  "rewrites": [
    {
      "source": "/(.*)",
      "destination": "/index.html"
    }
  ]
}
```
This instructs Vercel to route all deep subroutes (such as `/chat`) to `/index.html`, eliminating the Vercel 404 page.

### 2. Synchronous Bootstrap Route Guard ([session.ts](file:///d:/projects/GitSense_Ai/frontend/src/utils/session.ts))
Implemented `runBootstrapRouteGuard()`:
```typescript
export const runBootstrapRouteGuard = () => {
  if (typeof window === 'undefined') return;

  const pathname = window.location.pathname;
  const navEntries = typeof performance !== 'undefined' && performance.getEntriesByType 
    ? (performance.getEntriesByType('navigation') as PerformanceNavigationTiming[]) 
    : [];
  const isReload = navEntries.length > 0 && navEntries[0].type === 'reload';
  const hasSession = !!localStorage.getItem('gitsense_session_id');

  if (pathname === '/chat' && (isReload || !hasSession)) {
    console.log('[BOOTSTRAP_GUARD] /chat refresh or unauthenticated access detected. Clearing state and redirecting to /');
    clearSessionState();
    if (window.location.pathname !== '/') {
      window.history.replaceState(null, '', '/');
    }
  }
};
```

### 3. Application Bootstrap Execution ([main.tsx](file:///d:/projects/GitSense_Ai/frontend/src/main.tsx))
Executed `runBootstrapRouteGuard()` synchronously in `main.tsx` **before** `createRoot().render()`:
```typescript
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
```

---

## 3. Scenario Execution Matrix

| Scenario | Trigger / Action | Expected Result | Verification |
|---|---|---|---|
| **Scenario 1** | Open `https://git-sense-ai.vercel.app/` | Home page loads cleanly, creates new session | ✅ PASSED |
| **Scenario 2** | Click "Get Started" on `/` | SPA navigates `/` -> `/chat`, Chat page opens | ✅ PASSED |
| **Scenario 3** | Press Refresh while on `/chat` | Vercel routes `/index.html`, bootstrap guard clears state, URL becomes `/`, new session created | ✅ PASSED |
| **Scenario 4** | Paste `/chat` in new tab without session | Redirects to `/`, new session created | ✅ PASSED |
| **Scenario 5** | Backend / Database Code | 100% untouched & unmodified | ✅ PASSED |

---

## 4. Empirical Build Verification (`npm run build`)

```text
> frontend@0.0.0 build
> tsc -b && vite build

vite v8.1.5 building client environment for production...
transforming...✓ 2354 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.49 kB │ gzip:   0.32 kB
dist/assets/index-Co4zGA0x.css   33.56 kB │ gzip:   6.84 kB
dist/assets/index-LWHt-CcE.js   617.93 kB │ gzip: 194.23 kB

✓ built in 3.08s
```
