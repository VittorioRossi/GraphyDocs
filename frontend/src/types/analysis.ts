export type RequestStatus = 'pending' | 'running' | 'completed' | 'error' | 'stopped' | 'connected' | 'disconnected' | 'closing';

export type AnalysisProgress = {
    status: 'pending' | 'running' | 'completed' | 'error';
    progress: number;
    processed_files: number;
    currentFile?: string;
    error?: string;
  };
  
  