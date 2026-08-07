import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { apiService } from '../services/api';
import { ProjectMetadata, SessionResponse, FileEntry, ChatHistoryEntry } from '../types';
import { toast } from 'sonner';

interface AppContextType {
  sessionId: string | null;
  projects: ProjectMetadata[];
  currentProject: ProjectMetadata | null;
  fileTree: FileEntry[];
  chatHistory: ChatHistoryEntry[];
  isLoadingProjects: boolean;
  isLoadingFiles: boolean;
  isLoadingChat: boolean;
  isIngesting: boolean;
  ingestionProjectId: string | null;
  refreshProjects: () => Promise<void>;
  selectProject: (project: ProjectMetadata | null) => Promise<void>;
  startNewSession: () => Promise<void>;
  deleteProject: (projectId: string) => Promise<void>;
  setIngestionState: (projectId: string | null, isIngesting: boolean) => void;
  setChatHistory: React.Dispatch<React.SetStateAction<ChatHistoryEntry[]>>;
  sessionError: string | null;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

// Shared promise to deduplicate parallel createSession calls
let activeSessionCreationPromise: Promise<SessionResponse> | null = null;
let isInitializationStarted = false;
let sessionRecoveryAttempts = 0;

const logWithTimestamp = (msg: string) => {
  console.log(`[${new Date().toISOString()}] ${msg}`);
};

export function AppProvider({ children }: { children: ReactNode }) {
  const [sessionId, setSessionId] = useState<string | null>(() => {
    const storedId = localStorage.getItem('gitsense_session_id');
    const expiresAtStr = localStorage.getItem('gitsense_session_expires_at');
    if (storedId && expiresAtStr) {
      const isExpired = new Date(expiresAtStr) <= new Date();
      if (!isExpired) return storedId;
    }
    return null;
  });
  const [projects, setProjects] = useState<ProjectMetadata[]>([]);
  const [currentProject, setCurrentProject] = useState<ProjectMetadata | null>(null);
  const [fileTree, setFileTree] = useState<FileEntry[]>([]);
  const [chatHistory, setChatHistory] = useState<ChatHistoryEntry[]>([]);
  
  const [isLoadingProjects, setIsLoadingProjects] = useState(false);
  const [isLoadingFiles, setIsLoadingFiles] = useState(false);
  const [isLoadingChat, setIsLoadingChat] = useState(false);
  const [isIngesting, setIsIngesting] = useState<boolean>(() => {
    return localStorage.getItem('gitsense_is_ingesting') === 'true';
  });
  const [ingestionProjectId, setIngestionProjectId] = useState<string | null>(() => {
    return localStorage.getItem('gitsense_ingestion_project_id');
  });
  
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [isInitialized, setIsInitialized] = useState(false);

  // Initialize or restore session
  const initializeSession = useCallback(async () => {
    if (isInitializationStarted) {
      logWithTimestamp('Session initialization already in progress, skipping duplicate call');
      return;
    }
    isInitializationStarted = true;
    
    logWithTimestamp('Initializing session');
    setSessionError(null);
    setIsInitialized(false);
    
    let storedId = localStorage.getItem('gitsense_session_id');
    let expiresAtStr = localStorage.getItem('gitsense_session_expires_at');
    const now = new Date();
    let isExpired = expiresAtStr ? new Date(expiresAtStr) <= now : true;

    // Retry helper with exponential backoff
    const callWithRetry = async <T,>(fn: () => Promise<T>, retries = 3, delay = 1000): Promise<T> => {
      try {
        return await fn();
      } catch (err: any) {
        if (retries <= 1) throw err;
        if (err.response?.status === 410) throw err; // Don't retry if session is explicitly expired
        
        console.warn(`[${new Date().toISOString()}] API call failed. Retrying in ${delay}ms... (${retries - 1} attempts left). Error:`, err.message || err);
        await new Promise(resolve => setTimeout(resolve, delay));
        return callWithRetry(fn, retries - 1, delay * 2);
      }
    };
    
    try {
      if (storedId) {
        logWithTimestamp(`Existing session found: ${storedId}`);
      }
      
      // If session is expired or not found
      if (!storedId || isExpired) {
        if (isExpired && storedId) {
          logWithTimestamp('Session expired');
          logWithTimestamp('Removing expired session');
          localStorage.removeItem('gitsense_session_id');
          localStorage.removeItem('gitsense_session_expires_at');
        }
        
        logWithTimestamp('Creating new session');
        logWithTimestamp('Session request sent');
        
        if (!activeSessionCreationPromise) {
          activeSessionCreationPromise = callWithRetry(() => apiService.createSession());
        }
        const newSession = await activeSessionCreationPromise;
        
        logWithTimestamp('Session response received');
        
        localStorage.setItem('gitsense_session_id', newSession.session_id);
        localStorage.setItem('gitsense_session_expires_at', newSession.expires_at);
        logWithTimestamp('Session stored');
        logWithTimestamp(`Session created successfully: ${newSession.session_id}`);
        
        storedId = newSession.session_id;
        setSessionId(newSession.session_id);
      } else {
        setSessionId(storedId);
      }
      
      logWithTimestamp('API client configured');
      
      // Load projects/workspaces
      logWithTimestamp('Workspace loading started');
      try {
        const list = await callWithRetry(() => apiService.listProjects());
        setProjects(list);
        logWithTimestamp('Workspace loading completed');
        
        sessionRecoveryAttempts = 0; // Reset recovery counter on success
        setIsInitialized(true);
      } catch (err: any) {
        // Handle server-side session expiration dynamically
        if (err.response?.status === 410) {
          logWithTimestamp('Session expired');
          if (sessionRecoveryAttempts >= 2) {
            throw new Error('Session has repeatedly expired on server. Check database status.');
          }
          sessionRecoveryAttempts++;
          logWithTimestamp('Removing expired session');
          localStorage.removeItem('gitsense_session_id');
          localStorage.removeItem('gitsense_session_expires_at');
          setSessionId(null);
          
          logWithTimestamp('Automatically requesting a new session');
          isInitializationStarted = false; // Allow re-entry
          return initializeSession();
        } else {
          throw err;
        }
      }
    } catch (error: any) {
      isInitializationStarted = false; // Allow retry on failure
      console.error(`[${new Date().toISOString()}] Failed to initialize session after all retries:`, error);
      const message = error.response?.data?.detail || error.message || 'Could not connect to backend server.';
      setSessionError(message);
    } finally {
      activeSessionCreationPromise = null;
    }
  }, []);

  // Fetch session projects
  const refreshProjects = useCallback(async () => {
    if (!sessionId) return;
    setIsLoadingProjects(true);
    try {
      const list = await apiService.listProjects();
      setProjects(list);
    } catch (error: any) {
      if (error.response?.status === 410) {
        console.warn('Session expired (410 Gone). Resetting session.');
        localStorage.removeItem('gitsense_session_id');
        localStorage.removeItem('gitsense_session_expires_at');
        setSessionId(null);
        setProjects([]);
        setCurrentProject(null);
        setFileTree([]);
        setChatHistory([]);
        
        isInitializationStarted = false; // Reset lock to allow re-initialization
        await initializeSession();
      } else {
        console.error('Failed to fetch projects:', error);
      }
    } finally {
      setIsLoadingProjects(false);
    }
  }, [sessionId, initializeSession]);

  // Handle active project selection
  const selectProject = useCallback(async (project: ProjectMetadata | null) => {
    setCurrentProject(project);
    if (!project) {
      setFileTree([]);
      setChatHistory([]);
      return;
    }

    setIsLoadingFiles(true);
    setIsLoadingChat(true);

    try {
      const [filesData, chatData] = await Promise.all([
        apiService.getProjectFiles(project.project_id),
        apiService.getChatHistory(project.project_id),
      ]);
      setFileTree(filesData.files);
      setChatHistory(chatData);
    } catch (error) {
      console.error('Failed to load project files or chat logs:', error);
      toast.error('Failed to load project details.');
      setFileTree([]);
      setChatHistory([]);
    } finally {
      setIsLoadingFiles(false);
      setIsLoadingChat(false);
    }
  }, []);

  // Reset session manually
  const startNewSession = useCallback(async () => {
    localStorage.removeItem('gitsense_session_id');
    localStorage.removeItem('gitsense_session_expires_at');
    setSessionId(null);
    setProjects([]);
    setCurrentProject(null);
    setFileTree([]);
    setChatHistory([]);
    localStorage.removeItem('gitsense_ingestion_project_id');
    localStorage.removeItem('gitsense_is_ingesting');
    setIngestionProjectId(null);
    setIsIngesting(false);

    isInitializationStarted = false; // Reset lock to allow re-initialization
    await initializeSession();
    toast.success('Started a new clean session.');
  }, [initializeSession]);

  // Delete project
  const deleteProject = useCallback(async (projectId: string) => {
    try {
      await apiService.deleteProject(projectId);
      toast.success('Project deleted successfully.');
      if (currentProject?.project_id === projectId) {
        setCurrentProject(null);
        setFileTree([]);
        setChatHistory([]);
      }
      await refreshProjects();
    } catch (error) {
      console.error('Failed to delete project:', error);
      toast.error('Failed to delete the project.');
    }
  }, [currentProject, refreshProjects]);

  const setIngestionState = useCallback((projId: string | null, ingesting: boolean) => {
    if (projId && ingesting) {
      localStorage.setItem('gitsense_ingestion_project_id', projId);
      localStorage.setItem('gitsense_is_ingesting', 'true');
    } else {
      localStorage.removeItem('gitsense_ingestion_project_id');
      localStorage.removeItem('gitsense_is_ingesting');
    }
    setIngestionProjectId(projId);
    setIsIngesting(ingesting);
  }, []);

  useEffect(() => {
    console.log('App started');
    initializeSession();
  }, [initializeSession]);

  if (!isInitialized) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-[#0a0a0a] text-zinc-300 font-mono p-6">
        {sessionError ? (
          <div className="max-w-md w-full border border-red-500/20 bg-red-500/5 p-6 rounded shadow-lg">
            <span className="font-bold text-red-500 text-sm uppercase tracking-wider block mb-2">// SESSION_INIT_ERROR</span>
            <p className="text-xs text-zinc-400 leading-relaxed mb-6">{sessionError}</p>
            <button
              onClick={initializeSession}
              className="w-full bg-red-900/20 hover:bg-red-900/40 border border-red-500/30 text-red-400 hover:text-red-300 py-2.5 text-xs font-bold uppercase tracking-widest cursor-pointer transition-all focus:outline-none"
            >
              Retry Connection
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3">
            <div className="flex items-center gap-2 text-xs text-zinc-500">
              <svg className="animate-spin h-4 w-4 text-[#f5c542]" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <span className="font-bold uppercase tracking-widest text-[#f5c542]">INITIALIZING WORKSPACE...</span>
            </div>
            <p className="text-[10px] text-zinc-600 uppercase tracking-wider mt-1">checking credentials and connection status</p>
          </div>
        )}
      </div>
    );
  }

  return (
    <AppContext.Provider
      value={{
        sessionId,
        projects,
        currentProject,
        fileTree,
        chatHistory,
        isLoadingProjects,
        isLoadingFiles,
        isLoadingChat,
        isIngesting,
        ingestionProjectId,
        refreshProjects,
        selectProject,
        startNewSession,
        deleteProject,
        setIngestionState,
        setChatHistory,
        sessionError
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const context = useContext(AppContext);
  if (context === undefined) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
}
