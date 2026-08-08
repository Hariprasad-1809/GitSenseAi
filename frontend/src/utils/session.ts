// Centralized session storage and route guard helpers for GitSense AI

export const clearSessionState = () => {
  if (typeof localStorage !== 'undefined') {
    localStorage.removeItem('gitsense_session_id');
    localStorage.removeItem('gitsense_session_expires_at');
    localStorage.removeItem('gitsense_ingestion_project_id');
    localStorage.removeItem('gitsense_is_ingesting');
    localStorage.removeItem('gitsense_current_project_id');
  }
};

export const runBootstrapRouteGuard = () => {
  if (typeof window === 'undefined') return;

  const pathname = window.location.pathname;
  const navEntries = typeof performance !== 'undefined' && performance.getEntriesByType ? (performance.getEntriesByType('navigation') as PerformanceNavigationTiming[]) : [];
  const isReload = navEntries.length > 0 && navEntries[0].type === 'reload';
  const hasSession = !!localStorage.getItem('gitsense_session_id');

  // Requirement: Refresh while on /chat OR direct unauthenticated /chat access -> redirect to / immediately
  if (pathname === '/chat' && (isReload || !hasSession)) {
    console.log('[BOOTSTRAP_GUARD] Browser reload or direct unauthenticated access to /chat. Wiping session and redirecting to /');
    clearSessionState();
    if (window.location.pathname !== '/') {
      window.history.replaceState(null, '', '/');
    }
  }
};
