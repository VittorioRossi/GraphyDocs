export interface AnalysisStatus {
    status: string;
    progress: number;
    currentFile?: string;
    processedFiles: number;
    totalFiles: number;
    error?: string;
}

export interface GraphStats {
    totalNodes: number;
    totalEdges: number;
    nodeTypes: Record<string, number>;
    edgeTypes: Record<string, number>;
}
