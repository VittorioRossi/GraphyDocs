import { WebSocketMessage, StartAnalysisResponse, BatchUpdateMessage, StatusUpdateMessage, ErrorMessage, AnalysisCompleteMessage } from '@/types/webhook';
import { Graph, Node, Edge } from '@/types/graph';
import { AnalysisProgress } from '@/types/analysis';


interface WebSocketHandlerCallbacks {
  onStartAnalysis: (jobId: string, analysisProgress: AnalysisProgress, graphData?: Graph) => void;
  onBatchUpdate: (nodes: Node[], edges: Edge[], ) => void;
  onProgressUpdate: (updates: Partial<AnalysisProgress>) => void;
  onError: (message: string, errorType: string) => void;
  onComplete: (jobId: string) => void;
}
export class WebSocketMessageHandler {
  private callbacks: WebSocketHandlerCallbacks;

  constructor(callbacks: WebSocketHandlerCallbacks) {
    this.callbacks = callbacks;
  }

  handleMessage = (message: WebSocketMessage) => {
    console.log('Message:', message);
    switch (message.type) {
      case 'start_analysis_response':
        this.handleStartAnalysis(message);
        break;
      case 'batch_update':
        this.handleBatchUpdate(message);
        break;
      case 'status_update':
        this.handleStatusUpdate(message);
        break;
      case 'subscribe_response':
        this.handleSubscribed(message);
        break;
      case 'error':
        this.handleError(message);
        break;
      case 'analysis_complete':
        this.handleComplete(message);
        break;
      default:
        console.warn('Unknown message type:', message.type);
    }
  };

  private handleStartAnalysis = (message: StartAnalysisResponse) => {
    const { job_id, analysis_stats, graph_data } = message.data;
    const progress: AnalysisProgress = {
      status: message.data.status,
      progress: Math.round((analysis_stats.processed_files / analysis_stats.processed_files) * 100),
      processed_files: analysis_stats.processed_files,
      processed_files: analysis_stats.processed_files,
      currentFile: analysis_stats.error || undefined
    };
    this.callbacks.onStartAnalysis(job_id, progress, graph_data);
  };

  private handleBatchUpdate = (message: BatchUpdateMessage) => {
    const { nodes, edges, analysis_stats } = message.data;
    const progress: Partial<AnalysisProgress> = {
      status: 'running',
      processed_files: analysis_stats.processed_files,
      total_files: analysis_stats.total_files,
      currentFile: analysis_stats.error,
      progress: Math.round((analysis_stats.processed_files / analysis_stats.total_files) * 100)
    };
    this.callbacks.onBatchUpdate(nodes || [], edges || []);
    this.callbacks.onProgressUpdate(progress);
  };
  
  private handleStatusUpdate = (message: StatusUpdateMessage) => {
    console.log('Status update:', message);
  };

  private handleError = (message: ErrorMessage) => {
    const { message: errorMessage, error_type } = message.data;
    this.callbacks.onError(errorMessage, error_type);
  };

  private handleComplete = (message: AnalysisCompleteMessage) => {
    const { job_id } = message.data;
    this.callbacks.onComplete(job_id);
  };

  private handleSubscribed = (message: WebSocketMessage) => {
    console.log('Subscribed:', message);
  }
}