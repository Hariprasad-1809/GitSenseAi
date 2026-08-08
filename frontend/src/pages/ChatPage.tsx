import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useApp } from '../context/AppContext';
import { apiService } from '../services/api';
import { MarkdownRenderer } from '../components/ui/MarkdownRenderer';
import { Button } from '../components/ui/Button';
import { Modal } from '../components/ui/Modal';
import {
  Sparkles,
  GitFork,
  UploadCloud,
  FileCode,
  Trash2,
  Download,
  Send,
  MessageSquare,
  Loader2,
  FolderOpen,
  ArrowRight,
  Code2,
  Clock,
  LogOut,
  Terminal,
  Activity
} from 'lucide-react';
import { toast } from 'sonner';
import { SourceCitation } from '../types';

export function ChatPage() {
  const {
    sessionId,
    projects,
    currentProject,
    fileTree,
    chatHistory,
    isLoadingProjects,
    isLoadingFiles,
    isIngesting,
    ingestionProjectId,
    refreshProjects,
    selectProject,
    startNewSession,
    deleteProject,
    setIngestionState,
    setChatHistory,
    sessionError
  } = useApp();

  const navigate = useNavigate();

  // Requirement 12: Redirect to / if session is missing or reset
  useEffect(() => {
    if (!sessionId) {
      navigate('/');
    }
  }, [sessionId, navigate]);

  const [githubUrl, setGithubUrl] = useState('');
  const [isSubmittingGithub, setIsSubmittingGithub] = useState(false);
  const [selectedZip, setSelectedZip] = useState<File | null>(null);
  const [isSubmittingZip, setIsSubmittingZip] = useState(false);

  const [pollingStatus, setPollingStatus] = useState<string>('queued');
  const [lastActiveStatus, setLastActiveStatus] = useState<string>('queued');
  const [filesProcessed, setFilesProcessed] = useState(0);
  const [totalFiles, setTotalFiles] = useState(0);
  const [percentage, setPercentage] = useState<number>(0);
  const [ingestionError, setIngestionError] = useState<string | null>(null);

  const [question, setQuestion] = useState('');
  const [isSendingQuery, setIsSendingQuery] = useState(false);

  const [selectedCitation, setSelectedCitation] = useState<SourceCitation | null>(null);

  const chatBottomRef = useRef<HTMLDivElement>(null);
  
  // Requirement 4 & 8: Dedicated poller refs to enforce EXACTLY ONE active polling loop
  const pollingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollingAbortControllerRef = useRef<AbortController | null>(null);
  const activePollingProjectIdRef = useRef<string | null>(null);
  
  // Requirement 9: Completion handler single execution guard
  const completionHandledRef = useRef<string | null>(null);

  const stopPolling = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
    if (pollingAbortControllerRef.current) {
      pollingAbortControllerRef.current.abort();
      pollingAbortControllerRef.current = null;
    }
    activePollingProjectIdRef.current = null;
  }, []);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory, isSendingQuery]);

  const calculateStageProgress = (status: string, processed: number, total: number): number => {
    const s = status.toLowerCase().trim();
    if (s === 'completed') return 100;
    if (s === 'queued' || s === 'failed') return 0;

    let baseMin = 0;
    let baseMax = 99;

    if (s === 'cloning') {
      baseMin = 5;
      baseMax = 15;
    } else if (s === 'parsing' || s === 'processing') {
      baseMin = 15;
      baseMax = 60;
    } else if (s === 'generating embeddings' || s === 'generating_embeddings') {
      baseMin = 60;
      baseMax = 90;
    } else if (s === 'saving') {
      baseMin = 90;
      baseMax = 99;
    }

    if (total > 0 && (s === 'parsing' || s === 'processing')) {
      const ratio = Math.min(Math.max(processed / total, 0), 1);
      return Math.min(Math.round(baseMin + ratio * (baseMax - baseMin)), 59);
    }

    return Math.min(baseMax, 99);
  };

  useEffect(() => {
    // Requirements 4 & 11: Stop polling immediately if not ingesting or no project ID
    if (!isIngesting || !ingestionProjectId) {
      stopPolling();
      return;
    }

    // Requirement 8: Prevent duplicate polling loop for the same project
    if (activePollingProjectIdRef.current === ingestionProjectId && pollingIntervalRef.current !== null) {
      return;
    }

    stopPolling();
    activePollingProjectIdRef.current = ingestionProjectId;

    const checkStatus = async () => {
      if (!ingestionProjectId || activePollingProjectIdRef.current !== ingestionProjectId) return;

      const controller = new AbortController();
      pollingAbortControllerRef.current = controller;

      try {
        const statusRes = await apiService.getIngestionStatus(ingestionProjectId, controller.signal);

        // If poller was stopped or target project changed while HTTP call was in-flight
        if (activePollingProjectIdRef.current !== ingestionProjectId) return;

        const computedPct = calculateStageProgress(statusRes.status, statusRes.files_processed, statusRes.total_files);

        setPollingStatus(statusRes.status);
        setFilesProcessed(statusRes.files_processed);
        setTotalFiles(statusRes.total_files);
        setPercentage(computedPct);
        setIngestionError(statusRes.error || null);

        if (statusRes.status !== 'failed') {
          setLastActiveStatus(statusRes.status);
        }

        // Requirement 9: Completion handler executes EXACTLY ONCE per project
        if (statusRes.status === 'completed') {
          if (completionHandledRef.current === ingestionProjectId) {
            stopPolling();
            return;
          }
          completionHandledRef.current = ingestionProjectId;

          stopPolling();
          setPercentage(100);
          setPollingStatus('completed');
          setLastActiveStatus('completed');

          toast.success('Indexing completed successfully!');

          await refreshProjects();

          const list = await apiService.listProjects();
          let targetProj = list.find(p => p.project_id === ingestionProjectId);
          if (!targetProj) {
            targetProj = {
              project_id: ingestionProjectId,
              project_name: 'Ingested Codebase',
              language_summary: {},
              file_count: statusRes.total_files || statusRes.files_processed,
              ingestion_date: new Date().toISOString(),
              status: 'completed'
            };
          }

          await selectProject(targetProj);
          setIngestionState(null, false);

        } else if (statusRes.status === 'failed') {
          stopPolling();
          console.error(`[INGESTION_FAILED] project_id: ${ingestionProjectId}, error: ${statusRes.error}`);
          toast.error(`Indexing failed: ${statusRes.error || 'Unknown error'}`);
          setIngestionState(null, false);
          await refreshProjects();
        }
      } catch (error: any) {
        if (axios.isCancel(error) || error.name === 'CanceledError' || error.name === 'AbortError') return;

        // REQUIREMENT 5: 404 MUST STOP POLLING IMMEDIATELY
        if (error.response?.status === 404) {
          console.warn(`[INGESTION_404] Ingestion project ${ingestionProjectId} no longer exists. Stopping polling immediately.`);
          stopPolling();
          setIngestionState(null, false);
          setPollingStatus('failed');
          setPercentage(0);
          setIngestionError(null);
          await refreshProjects();
          return;
        }

        console.error('[INGESTION_STATUS_ERROR] Error polling status for project:', ingestionProjectId, error);
      }
    };

    checkStatus();
    pollingIntervalRef.current = setInterval(checkStatus, 1500);

    return () => {
      stopPolling();
    };
  }, [isIngesting, ingestionProjectId, refreshProjects, selectProject, setIngestionState, stopPolling]);

  const handleGithubSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!githubUrl.trim()) return;

    setIsSubmittingGithub(true);
    completionHandledRef.current = null;
    try {
      const res = await apiService.ingestGithub({ repo_url: githubUrl.trim() });
      toast.success(res.message);
      setGithubUrl('');
      setIngestionState(res.project_id, true);
      setPollingStatus('queued');
      setLastActiveStatus('queued');
      setFilesProcessed(0);
      setTotalFiles(0);
      setPercentage(0);
      setIngestionError(null);
    } catch (error: any) {
      console.error(error);
      if (error.response?.status === 401 || error.response?.status === 410) {
        toast.error('Session expired or invalid. Creating a new session...');
        await startNewSession();
      } else {
        const errMsg = error.response?.data?.detail || 'Ingestion request failed.';
        toast.error(errMsg);
      }
    } finally {
      setIsSubmittingGithub(false);
    }
  };

  const handleZipSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedZip) return;

    setIsSubmittingZip(true);
    completionHandledRef.current = null;
    try {
      const res = await apiService.ingestZip(selectedZip);
      toast.success(res.message);
      setSelectedZip(null);
      setIngestionState(res.project_id, true);
      setPollingStatus('queued');
      setLastActiveStatus('queued');
      setFilesProcessed(0);
      setTotalFiles(0);
      setPercentage(0);
      setIngestionError(null);
    } catch (error: any) {
      console.error(error);
      if (error.response?.status === 401 || error.response?.status === 410) {
        toast.error('Session expired or invalid. Creating a new session...');
        await startNewSession();
      } else {
        const errMsg = error.response?.data?.detail || 'ZIP Ingestion failed.';
        toast.error(errMsg);
      }
    } finally {
      setIsSubmittingZip(false);
    }
  };

  const handleQuerySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || !currentProject || isSendingQuery) return;

    const queryText = question.trim();
    setQuestion('');
    setIsSendingQuery(true);

    const tempId = Date.now();
    setChatHistory(prev => [
      ...prev,
      {
        id: tempId,
        question: queryText,
        answer: '',
        sources: [],
        created_at: new Date().toISOString()
      }
    ]);

    try {
      const res = await apiService.queryProject({
        project_id: currentProject.project_id,
        question: queryText
      });

      setChatHistory(prev =>
        prev.map(chat =>
          chat.id === tempId
            ? { ...chat, answer: res.answer, sources: res.sources }
            : chat
        )
      );
    } catch (error: any) {
      console.error('Failed to query codebase:', error);
      const errMsg = error.response?.data?.detail || 'Failed to generate answer. Please try again.';
      toast.error(errMsg);

      setChatHistory(prev => prev.filter(chat => chat.id !== tempId));
    } finally {
      setIsSendingQuery(false);
    }
  };

  const triggerQuickQuestion = (text: string) => {
    if (!currentProject || isSendingQuery) return;
    setQuestion(text);
    setTimeout(() => {
      const submitButton = document.getElementById('chat-submit-btn');
      submitButton?.click();
    }, 50);
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const renderProgressBar = () => {
    const totalBlocks = 20;
    const currentPct = percentage;
    const pctFrac = Math.min(Math.max(currentPct / 100, 0), 1);
    const filledBlocks = Math.round(pctFrac * totalBlocks);
    const emptyBlocks = totalBlocks - filledBlocks;
    const bar = '[' + '='.repeat(filledBlocks) + '.'.repeat(emptyBlocks) + ']';
    return (
      <div className="font-mono text-xs text-[#6b6b6b] mt-2">
        <span className="text-[#f5c542] font-bold">{bar}</span>
        <span className="ml-2 font-bold text-[#d4af37]">{currentPct.toFixed(0)}%</span>
      </div>
    );
  };

  return (
    <div className="flex h-[calc(100vh-64px)] w-full bg-[#0a0a0a] overflow-hidden text-[#6b6b6b] font-mono">
      
      {/* Sidebar Explorer */}
      <aside className="w-80 border-r border-[#2b2b2b] bg-[#0a0a0a] flex flex-col h-full shrink-0">
        
        {/* Top panel */}
        <div className="p-4 border-b border-[#2b2b2b] flex items-center justify-between bg-[#181818]/20">
          <div className="flex items-center gap-2">
            <FolderOpen className="h-4 w-4 text-[#d4af37]" />
            <span className="font-bold text-[#ffffff] text-xs uppercase tracking-wider">// WORKSPACE</span>
          </div>
          <button
            onClick={startNewSession}
            title="Reset active session"
            className="text-[#6b6b6b] hover:text-[#d4af37] p-1 border border-transparent hover:border-[#2b2b2b] bg-transparent hover:bg-[#181818] transition-all cursor-pointer"
          >
            <LogOut className="h-3.5 w-3.5" />
          </button>
        </div>

        {/* Project List Selector */}
        <div className="p-4 border-b border-[#2b2b2b]">
          <label className="block text-[9px] font-bold text-[#6b6b6b]/60 tracking-widest mb-3">SELECT_CODESPACE</label>
          {sessionError ? (
            <div className="text-xs text-red-500/80 py-2 border border-red-500/20 bg-red-500/5 p-3 rounded font-mono">
              <span className="font-bold text-red-500 block mb-1">SESSION_ERROR</span>
              <p className="leading-relaxed">{sessionError}</p>
            </div>
          ) : isLoadingProjects ? (
            <div className="flex items-center gap-2 text-xs text-[#6b6b6b]/60 py-2">
              <Loader2 className="h-3 w-3 animate-spin text-[#6b6b6b]/40" />
              <span>FETCHING CODESPACES...</span>
            </div>
          ) : projects.length === 0 ? (
            <div className="text-xs text-[#6b6b6b]/50 italic py-2">NO CODESPACES FOUND.</div>
          ) : (
            <div className="space-y-1">
              {projects.map((proj) => {
                const isActive = currentProject?.project_id === proj.project_id;
                return (
                  <div
                    key={proj.project_id}
                    className={`group flex items-center justify-between p-2.5 border transition-all ${
                      isActive
                        ? 'bg-[#181818]/60 border-[#d4af37] text-[#ffffff]'
                        : 'border-[#2b2b2b] bg-[#181818]/15 hover:border-[#2b2b2b]/80 text-[#6b6b6b]/75 hover:text-[#ffffff]'
                    }`}
                  >
                    <button
                      onClick={() => selectProject(proj)}
                      className="flex-1 text-left text-xs truncate mr-2 cursor-pointer focus:outline-none"
                    >
                      <div className="font-bold truncate">» {proj.project_name}</div>
                      <div className="text-[9px] text-[#6b6b6b]/55 mt-1">
                        FILES: {proj.file_count} | STATUS: {proj.status.toUpperCase()}
                      </div>
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteProject(proj.project_id);
                      }}
                      className="opacity-0 group-hover:opacity-100 text-[#6b6b6b]/70 hover:text-red-400 p-0.5 border border-transparent hover:border-[#2b2b2b] bg-transparent hover:bg-[#181818] transition-all cursor-pointer focus:opacity-100 focus:outline-none"
                      title="Delete codespace"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Flat File Tree Explorer */}
        <div className="flex-1 overflow-y-auto flex flex-col p-4 bg-[#0a0a0a]">
          <span className="text-[9px] font-bold text-[#6b6b6b]/60 tracking-widest mb-3">WORKSPACE_MAP</span>
          
          {isLoadingFiles ? (
            <div className="flex items-center gap-2 text-xs text-[#6b6b6b]/60 py-4 justify-center">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-[#6b6b6b]/40" />
              <span>MAP_WALKING...</span>
            </div>
          ) : !currentProject ? (
            <div className="text-[10px] text-[#6b6b6b]/50 italic text-center py-8">
              Select or ingest repository.
            </div>
          ) : fileTree.length === 0 ? (
            <div className="text-[10px] text-[#6b6b6b]/50 italic text-center py-8">
              Tree empty.
            </div>
          ) : (
            <div className="space-y-0.5 max-h-full">
              {fileTree.map((file, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between text-[10px] py-1 px-2 hover:bg-[#181818]/30 border border-transparent hover:border-[#2b2b2b] group"
                >
                  <div className="flex items-center gap-1.5 truncate min-w-0 mr-1">
                    <span className="text-[#6b6b6b]/40 select-none">»</span>
                    <span className="text-[#6b6b6b]/80 font-mono truncate" title={file.file_path}>
                      {file.file_path}
                    </span>
                  </div>
                  <span className="text-[9px] text-[#6b6b6b]/50 shrink-0 select-none">
                    {formatBytes(file.size_bytes)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

      </aside>

      {/* Main Workspace Frame */}
      <main className="flex-1 flex flex-col h-full bg-[#0a0a0a]/20 relative">
        
        {/* If no project is selected and no ingestion is running, show onboarding forms */}
        {!currentProject && !isIngesting ? (
          <div className="flex-1 flex flex-col items-center justify-center p-8 max-w-2xl mx-auto overflow-y-auto w-full">
            
            {/* Terminal Title */}
            <div className="flex items-center gap-2 text-[10px] text-[#d4af37] font-bold uppercase tracking-wider mb-8">
              <Terminal className="h-4.5 w-4.5" />
              <span>[ SESSION_LOAD: CODESPACE_IMPORT ]</span>
            </div>

            <div className="w-full space-y-4">
              
              {/* Option A: GitHub Ingestion Form */}
              <div className="border border-[#2b2b2b] bg-[#181818]/10 p-5">
                <div className="flex items-center justify-between text-[9px] text-[#6b6b6b]/50 font-bold tracking-widest mb-4">
                  <span>METHOD_01: REMOTE_REPOSITORY</span>
                  <span>[ HTTPS_ONLY ]</span>
                </div>
                <form onSubmit={handleGithubSubmit} className="space-y-3">
                  <div className="flex gap-2">
                    <input
                      type="url"
                      required
                      value={githubUrl}
                      onChange={(e) => setGithubUrl(e.target.value)}
                      className="flex-1 bg-[#0a0a0a] border border-[#2b2b2b] px-3.5 py-2 text-[#ffffff] text-xs focus:outline-none focus:border-[#f5c542] transition-colors placeholder:text-zinc-700 font-mono"
                      placeholder="https://github.com/username/repository"
                    />
                    <Button type="submit" size="sm" isLoading={isSubmittingGithub}>
                      <span>CLONE_INDEX</span>
                    </Button>
                  </div>
                  <p className="text-[10px] text-[#6b6b6b]/50 leading-normal">
                    * Performed shallow clone at depth=1. Binary extensions and non-code formats will be excluded from index matrices.
                  </p>
                </form>
              </div>

              {/* Option B: ZIP Ingestion Form */}
              <div className="border border-[#2b2b2b] bg-[#181818]/10 p-5">
                <div className="flex items-center justify-between text-[9px] text-[#6b6b6b]/50 font-bold tracking-widest mb-4">
                  <span>METHOD_02: COMPRESSED_ARCHIVE</span>
                  <span>[ ZIP_ONLY ]</span>
                </div>
                <form onSubmit={handleZipSubmit} className="space-y-4">
                  <div className="border border-dashed border-[#2b2b2b] p-6 text-center hover:border-[#d4af37]/45 transition-colors cursor-pointer relative bg-[#181818]/15">
                    <input
                      type="file"
                      accept=".zip"
                      required
                      onChange={(e) => {
                        const files = e.target.files;
                        if (files && files[0]) setSelectedZip(files[0]);
                      }}
                      className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                    />
                    <UploadCloud className="h-6 w-6 text-[#6b6b6b]/60 mx-auto mb-2" />
                    {selectedZip ? (
                      <span className="text-xs text-[#f5c542] font-mono font-bold block truncate max-w-xs mx-auto">
                        » {selectedZip.name} ({(selectedZip.size / (1024 * 1024)).toFixed(2)} MB)
                      </span>
                    ) : (
                      <>
                        <span className="text-xs text-[#ffffff] font-bold block">CHOOSE_LOCAL_ZIP</span>
                        <span className="text-[9px] text-[#6b6b6b]/60 mt-1 block">Drag and drop file here</span>
                      </>
                    )}
                  </div>
                  <div className="flex justify-end">
                    <Button type="submit" size="sm" disabled={!selectedZip} isLoading={isSubmittingZip}>
                      <span>UPLOAD_INDEX</span>
                    </Button>
                  </div>
                </form>
              </div>

            </div>
          </div>
        ) : isIngesting ? (
          
          /* Ingest Status Progress and Checklist Polling display */
          <div className="flex-1 flex flex-col items-center justify-center p-8 max-w-md mx-auto w-full">
            <div className="text-[10px] text-[#d4af37] font-bold uppercase tracking-wider mb-6 flex items-center gap-2">
              <Activity className="h-4.5 w-4.5 animate-pulse" />
              <span>[ PIPELINE_RUNNING: INGEST_MAP ]</span>
            </div>

            <div className="w-full bg-[#181818]/25 border border-[#2b2b2b] p-5 space-y-4">
              <div className="flex items-center justify-between text-xs font-bold text-[#ffffff]">
                <span>INDEX_COMPILATION</span>
                <span className="font-mono text-[#6b6b6b]">
                  {totalFiles > 0 ? `${filesProcessed} / ${totalFiles} F` : 'WAITING_FILE_COUNT...'}
                </span>
              </div>
              
              {/* ASCII Progress Bar */}
              {renderProgressBar()}

              {/* Steps checklists */}
              {/* Completed checks use #4ade80 (Green) success states */}
              <div className="pt-3 border-t border-[#2b2b2b] space-y-2.5 text-[10px] text-[#6b6b6b]/65 font-mono">
                {(() => {
                  const stepsOrder = ['queued', 'cloning', 'parsing', 'generating embeddings', 'saving', 'completed'];
                  let normalizedStatus = lastActiveStatus.toLowerCase().replace(/_/g, ' ').trim();
                  if (normalizedStatus === 'processing') normalizedStatus = 'parsing';
                  const activeIndex = Math.max(0, stepsOrder.indexOf(normalizedStatus));
                  
                  return [
                    { key: 'queued', label: '1. QUEUED' },
                    { key: 'cloning', label: '2. CLONING' },
                    { key: 'parsing', label: '3. PARSING' },
                    { key: 'generating embeddings', label: '4. GENERATING EMBEDDINGS' },
                    { key: 'saving', label: '5. SAVING' },
                    { key: 'completed', label: '6. COMPLETED' }
                  ].map((step, idx) => {
                    let symbol = '[ ]';
                    let colorClass = 'text-[#6b6b6b]/35';
                    let textClass = 'text-[#6b6b6b]/60';
                    
                    if (pollingStatus === 'failed') {
                      if (idx < activeIndex) {
                        symbol = '[x]';
                        colorClass = 'text-[#4ade80]';
                        textClass = 'text-[#6b6b6b]/50';
                      } else if (idx === activeIndex) {
                        symbol = '[!]';
                        colorClass = 'text-red-500 font-bold';
                        textClass = 'text-red-500 font-bold';
                      }
                    } else {
                      if (idx < activeIndex || (idx === activeIndex && step.key === 'completed')) {
                        symbol = '[x]';
                        colorClass = 'text-[#4ade80]';
                        textClass = 'text-[#6b6b6b]/50';
                      } else if (idx === activeIndex) {
                        symbol = '[>]';
                        colorClass = 'text-[#f5c542] animate-pulse';
                        textClass = 'text-[#ffffff] font-bold';
                      }
                    }
                    
                    return (
                      <div key={step.key} className="flex items-center gap-2">
                        <span className={colorClass}>{symbol}</span>
                        <span className={textClass}>{step.label}</span>
                      </div>
                    );
                  });
                })()}
              </div>

              {/* Error message display if failed */}
              {pollingStatus === 'failed' && (
                <div className="mt-4 pt-3 border-t border-[#2b2b2b] text-[10px] text-red-500 font-mono">
                  <div className="font-bold uppercase tracking-wider mb-1 text-red-400">// ERROR_DETAILS</div>
                  <p className="text-zinc-400 leading-normal mb-3">{ingestionError || 'An unknown error occurred during indexing.'}</p>
                  <Button 
                    onClick={() => setIngestionState(null, false)} 
                    variant="outline" 
                    size="sm"
                    className="w-full border-red-500/30 text-red-400 hover:text-red-300 hover:bg-red-950/20 py-1"
                  >
                    <span>CLOSE_RETURN</span>
                  </Button>
                </div>
              )}
            </div>
          </div>
        ) : (
          
          /* Active chat workspace window */
          <div className="flex-1 flex flex-col h-full relative">
            
            {/* Header controls */}
            <header className="px-6 py-3.5 border-b border-[#2b2b2b] flex items-center justify-between bg-[#0a0a0a]/85 backdrop-blur">
              <div className="min-w-0">
                <h2 className="font-bold text-[#ffffff] text-xs uppercase tracking-wide truncate">
                  // codespace: {currentProject?.project_name}
                </h2>
                <div className="text-[9px] text-[#6b6b6b]/50 font-mono tracking-tight mt-1 flex items-center gap-2">
                  <span>ID: {currentProject?.project_id}</span>
                  <span>|</span>
                  <span>FILES: {currentProject?.file_count}</span>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <a
                  href={apiService.getExportPdfUrl(currentProject?.project_id || '')}
                  download={`GitSense_${(currentProject?.project_name || 'project').replace(/\s+/g, '_').replace(/[^a-zA-Z0-9\-_]/g, '')}_${new Date().toISOString().split('T')[0]}.pdf`}
                  target="_blank"
                  rel="noreferrer"
                  className="focus:outline-none"
                >
                  <Button size="sm" variant="outline">
                    <Download className="h-3.5 w-3.5" />
                    <span>EXPORT_PDF</span>
                  </Button>
                </a>
              </div>
            </header>

            {/* Q&A chat lists scroll viewport */}
            <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
              
              {chatHistory.length === 0 ? (
                /* Empty state query suggestions */
                <div className="h-full flex flex-col items-center justify-center max-w-md mx-auto text-center font-mono">
                  <Terminal className="h-6 w-6 text-zinc-800 mb-3" />
                  <h3 className="font-bold text-[#ffffff] text-xs uppercase tracking-wider">codespace query ready</h3>
                  <p className="text-[10px] text-[#6b6b6b]/60 leading-normal mt-2 mb-6">
                    Enter your natural language codebase query below or select a preset instruction:
                  </p>
                  
                  <div className="w-full space-y-1.5 text-left text-xs">
                    <button
                      onClick={() => triggerQuickQuestion('Summarize this repository and explain the codebase layout.')}
                      className="w-full p-2.5 border border-[#2b2b2b] bg-[#181818]/15 hover:border-[#d4af37]/45 text-left text-[11px] text-[#6b6b6b] hover:text-[#ffffff] transition-all cursor-pointer flex items-center justify-between group focus:outline-none"
                    >
                      <span>» run summary_pipeline</span>
                      <ArrowRight className="h-3 w-3 text-zinc-700 group-hover:translate-x-0.5 transition-transform" />
                    </button>
                    
                    <button
                      onClick={() => triggerQuickQuestion('Explain how connection retries are implemented.')}
                      className="w-full p-2.5 border border-[#2b2b2b] bg-[#181818]/15 hover:border-[#d4af37]/45 text-left text-[11px] text-[#6b6b6b] hover:text-[#ffffff] transition-all cursor-pointer flex items-center justify-between group focus:outline-none"
                    >
                      <span>» locate retry_logic</span>
                      <ArrowRight className="h-3 w-3 text-zinc-700 group-hover:translate-x-0.5 transition-transform" />
                    </button>
                  </div>
                </div>
              ) : (
                /* Chat turns list */
                <div className="space-y-6 max-w-4xl mx-auto">
                  {chatHistory.map((chat) => (
                    <div key={chat.id} className="space-y-4">
                      
                      {/* User message block */}
                      <div className="flex justify-end">
                        <div className="max-w-[80%] bg-[#181818] border border-[#2b2b2b] px-4 py-2.5 text-[#e5e5e5] text-xs">
                          <span className="text-[#6b6b6b]/50 mr-1.5 select-none font-bold">$ cat query.txt</span>
                          <span className="font-mono leading-relaxed">{chat.question}</span>
                        </div>
                      </div>

                      {/* AI Response message block */}
                      <div className="flex justify-start">
                        <div className="max-w-[95%] bg-[#181818]/30 border border-[#2b2b2b] px-5 py-4 w-full">
                          
                          {/* Answer text container */}
                          {chat.answer === '' ? (
                            /* Customized Terminal typing loader - uses Bright Gold #F5C542 loader */
                            <div className="space-y-1 text-xs text-[#6b6b6b]/60 font-mono">
                              <div className="flex items-center gap-2">
                                <Loader2 className="h-3 w-3 animate-spin text-[#f5c542]" />
                                <span className="font-bold text-[#ffffff]">SEARCHING INDEX MATRICES...</span>
                              </div>
                              <div className="text-[10px] text-[#6b6b6b]/40 ml-5 font-mono">
                                » Query vector calculated. Merging pgvector similarity with FTS rankings.
                              </div>
                            </div>
                          ) : (
                            <MarkdownRenderer content={chat.answer} />
                          )}

                          {/* Sources citation list rendering */}
                          {chat.sources && chat.sources.length > 0 && (
                            <div className="mt-4 pt-3 border-t border-[#2b2b2b] font-mono">
                              <span className="text-[9px] font-bold text-[#6b6b6b]/50 tracking-wider block mb-2">SOURCE_REFS</span>
                              <div className="flex flex-wrap gap-1">
                                {chat.sources.map((source, index) => (
                                  <button
                                    key={index}
                                    onClick={() => setSelectedCitation(source)}
                                    className="inline-flex items-center gap-1 px-2 py-0.5 border border-[#2b2b2b] hover:border-[#d4af37] bg-transparent hover:bg-[#181818] transition-all text-[10px] text-[#6b6b6b] hover:text-[#d4af37] font-mono cursor-pointer focus:outline-none"
                                  >
                                    <span>[src: {source.file_path.split('/').pop()}:L{source.start_line}-L{source.end_line}]</span>
                                  </button>
                                ))}
                              </div>
                            </div>
                          )}

                        </div>
                      </div>

                    </div>
                  ))}

                  {/* Typing placeholder during pending requests */}
                  {isSendingQuery && chatHistory[chatHistory.length - 1]?.answer !== '' && (
                    <div className="flex justify-start">
                      <div className="max-w-[95%] bg-[#181818]/30 border border-[#2b2b2b] px-5 py-4 w-full">
                        <div className="flex items-center gap-2 text-xs text-[#6b6b6b]/60 font-mono">
                          <Loader2 className="h-3.5 w-3.5 animate-spin text-[#f5c542]" />
                          <span>PIPELINE_RESOLVING_STAGE...</span>
                        </div>
                      </div>
                    </div>
                  )}

                </div>
              )}

              <div ref={chatBottomRef} />
            </div>

            {/* Chat bottom input bar container */}
            <div className="p-4 border-t border-[#2b2b2b] bg-[#0a0a0a]/60">
              <form onSubmit={handleQuerySubmit} className="max-w-4xl mx-auto relative flex items-center">
                <span className="absolute left-4.5 text-[#6b6b6b]/50 select-none text-xs">$</span>
                <input
                  type="text"
                  required
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  disabled={isSendingQuery}
                  placeholder="Ask database query..."
                  className="w-full bg-[#0a0a0a] border border-[#2b2b2b] pl-10 pr-12 py-3 text-[#ffffff] text-xs focus:outline-none focus:border-[#f5c542] transition-colors disabled:opacity-50 font-mono"
                />
                <Button
                  id="chat-submit-btn"
                  type="submit"
                  disabled={!question.trim() || isSendingQuery}
                  className="absolute right-1.5 h-7.5 w-7.5 bg-[#d4af37] hover:bg-[#f5c542] hover:border-[#f5c542] text-[#0a0a0a] flex items-center justify-center p-0 cursor-pointer border-transparent shadow shadow-[#d4af37]/10"
                >
                  <Send className="h-3.5 w-3.5" />
                </Button>
              </form>
              <p className="text-[8px] text-[#6b6b6b]/45 text-center mt-2 font-mono uppercase tracking-wider">
                engine: hybrid query compilation (RRF rank threshold top_5)
              </p>
            </div>

          </div>
        )}

      </main>

      {/* Code citation detail Modal overlay */}
      <Modal
        isOpen={selectedCitation !== null}
        onClose={() => setSelectedCitation(null)}
        title={selectedCitation ? `REF_VIEW: ${selectedCitation.file_path}` : ''}
        className="max-w-3xl"
      >
        {selectedCitation && (
          <div className="space-y-4">
            <div className="flex items-center justify-between text-[10px] text-[#6b6b6b]/70 font-mono bg-[#181818]/30 p-2 border border-[#2b2b2b]">
              <span>Lines: {selectedCitation.start_line} - {selectedCitation.end_line}</span>
              <span>Type: {selectedCitation.file_path.split('.').pop() || 'src'}</span>
            </div>
            <div className="border border-[#2b2b2b] bg-[#0a0a0a] overflow-hidden max-w-full">
              <div className="overflow-x-auto p-4 max-w-full">
                <pre className="font-mono text-xs leading-relaxed text-[#ffffff] whitespace-pre">
                  {selectedCitation.snippet}
                </pre>
              </div>
            </div>
            <div className="flex justify-end mt-4">
              <Button onClick={() => setSelectedCitation(null)} size="sm" variant="secondary">
                Close Viewer
              </Button>
            </div>
          </div>
        )}
      </Modal>

    </div>
  );
}
