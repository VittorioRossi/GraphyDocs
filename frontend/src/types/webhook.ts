import { Graph, Node, Edge } from './graph';
import { RequestStatus, AnalysisProgress } from './analysis';

export interface BatchData {
    nodes: Node[];
    edges: Edge[];
    analysis_stats: AnalysisProgress;
    sequence: number;
}

export interface WSMessageBase {
    type: string;
    data: Record<string, unknown>;
}

export interface StartAnalysisResponse extends WSMessageBase {
    type: 'start_analysis_response';
    data: {
        job_id: string;
        status: RequestStatus;
        analysis_stats: AnalysisProgress;
        graph_data?: Graph;
    };
}

export interface BatchUpdateMessage {
    type: 'batch_update';
    data: BatchData;
}

export interface StatusUpdateMessage {
    type: 'status_update';
    data: {
        status: RequestStatus;
        analysis_stats: AnalysisProgress;
    };
}

export interface ErrorMessage {
    type: 'error';
    data: {
        message: string;
        error_type: string;
    };
}

export interface AnalysisCompleteMessage {
    type: 'analysis_complete';
    data: {
        job_id: string;
    };
}

export interface SubscribeMessage {
    type: 'subscribe_response';
    data: {
        job_id: string;
    };
}

export type WebSocketMessage =
    | StartAnalysisResponse
    | BatchUpdateMessage
    | StatusUpdateMessage
    | ErrorMessage
    | AnalysisCompleteMessage
    | SubscribeMessage;