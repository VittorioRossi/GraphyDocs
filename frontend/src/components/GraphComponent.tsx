import React, { useCallback, useEffect, useState, useRef, useMemo } from 'react';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';
import useWebSocket, { ReadyState } from 'react-use-websocket';
import { useParams, useNavigate } from 'react-router-dom';
import { Node, Edge, NodeType, EdgeType, Graph, GraphStats } from '@/types/graph';
import { WebSocketMessage } from '@/types/webhook';
import { AnalysisProgress, RequestStatus } from '@/types/analysis';
import { Button } from '@/components/ui/button';

import AnalysisPanel from './graph/AnalysisPanelComponent';
import WebSocketMessageHandler from '@/services/websocket';
import GraphVizComponent from '@/components/graph/GraphVizComponent';
import NodeDetailsCard from '@/components/graph/NodeDetailsComponent';

const WS_URL = 'ws://localhost:8000/api/v1/ws';

const GraphComponent: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const reconnectAttemptRef = useRef(0);

  // State management
  const [jobId, setJobId] = useState<string | null>(null);
  const [graphData, setGraphData] = useState<Graph>({ nodes: [], edges: [] });
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [graphStats, setGraphStats] = useState<GraphStats>({
    totalNodes: 0,
    totalEdges: 0,
    nodeTypes: {},
    edgeTypes: {}
  });

  const [, setRequestStatus] = useState<RequestStatus>('pending');
  const [analysisProgress, setAnalysisProgress] = useState<AnalysisProgress>({
    status: 'pending',
    progress: 0,
    processed_files: 0,
  });

  // WebSocket setup
  const { sendJsonMessage, lastJsonMessage, readyState, getWebSocket } = useWebSocket(WS_URL, {
    share: false,
    shouldReconnect: () => true,
    retryOnError: true,
    reconnectInterval: (attemptNumber) => Math.min(1000 * Math.pow(2, attemptNumber), 30000),
    onOpen: () => {
      console.log('WebSocket connected');
      reconnectAttemptRef.current = 0;
      setError(null);
      setRequestStatus('connected');
      
      // Resubscribe to the job if it exists
      if (jobId) {
        sendJsonMessage({
          type: 'subscribe',
          data: { job_id: jobId }
        });
      }
    },
    onClose: () => {
      console.log('WebSocket disconnected');
      setRequestStatus('disconnected');
    },
    onError: (event) => {
      console.error('WebSocket error:', event);
      setError('Connection error occurred');
    }
  });

  // Update graph statistics
  const updateGraphStats = useCallback((nodes: Node[], edges: Edge[]) => {
    const nodeTypes = nodes.reduce<Record<NodeType, number>>(
      (acc, node) => ({...acc, [node.kind]: (acc[node.kind] || 0) + 1}), 
      {} as Record<NodeType, number>
    );

    const edgeTypes = edges.reduce<Record<EdgeType, number>>(
      (acc, edge) => ({...acc, [edge.type]: (acc[edge.type] || 0) + 1}), 
      {} as Record<EdgeType, number>
    );

    setGraphStats({ 
      totalNodes: nodes.length, 
      totalEdges: edges.length, 
      nodeTypes, 
      edgeTypes 
    });
  }, []);

  // WebSocket message handler
  const wsHandler = useMemo(() => new WebSocketMessageHandler({
    onStartAnalysis: (newJobId, progress, initialGraphData) => {
      console.log('Analysis started:', { newJobId, progress });
      setJobId(newJobId);
      setAnalysisProgress(progress);
      
      if (initialGraphData) {
        setGraphData(initialGraphData);
        updateGraphStats(initialGraphData.nodes, initialGraphData.edges);
      }

      // Subscribe to job updates immediately
      if (newJobId) {
        console.log('Subscribing to job:', newJobId);
        sendJsonMessage({
          type: 'subscribe',
          data: { job_id: newJobId }
        });
      }
    },
    onProgressUpdate: (updates) => {
      console.log('Progress update:', updates);
      setAnalysisProgress(prev => ({
        ...prev,
        ...updates
      }));
    },
    onBatchUpdate: (nodes, edges) => {
      console.log('Batch update received:', { nodes, edges });
      setGraphData(prev => {
        const newNodes = [...prev.nodes, ...nodes];
        const newEdges = [...prev.edges, ...edges];
        updateGraphStats(newNodes, newEdges);
        return { nodes: newNodes, edges: newEdges };
      });
    },
    onError: (message, errorType) => {
      console.error('Analysis error:', { message, errorType });
      setError(message);
      setRequestStatus('error');
      setAnalysisProgress(prev => ({
        ...prev,
        status: 'error'
      }));

      if (errorType === 'ProjectNotFoundError') {
        setTimeout(() => navigate('/'), 3000);
      }
    },
    onComplete: () => {
      console.log('Analysis completed');
      setAnalysisProgress(prev => ({
        ...prev,
        status: 'completed',
        progress: 100
      }));
    }
  }), [navigate, sendJsonMessage, updateGraphStats]);

  // Effect to handle WebSocket connection status
  useEffect(() => {
    switch (readyState) {
      case ReadyState.CONNECTING:
        setRequestStatus('pending');
        break;
      case ReadyState.OPEN:
        setRequestStatus('connected');
        break;
      case ReadyState.CLOSING:
      case ReadyState.CLOSED:
        setRequestStatus('disconnected');
        reconnectAttemptRef.current += 1;
        break;
    }
  }, [readyState]);

  // Effect to start analysis when connected
  useEffect(() => {
    if (readyState === ReadyState.OPEN && projectId && !jobId) {
      console.log('Starting analysis for project:', projectId);
      sendJsonMessage({
        type: 'start_analysis',
        data: { 
          project_id: projectId,
          analyzer_type: 'package'
        }
      });
    }
  }, [readyState, projectId, sendJsonMessage, jobId]);

  // Effect to resubscribe to the job when WebSocket reconnects
  useEffect(() => {
    if (readyState === ReadyState.OPEN && jobId) {
      console.log('Resubscribing to job:', jobId);
      sendJsonMessage({
        type: 'subscribe',
        data: { job_id: jobId }
      });
    }
  }, [readyState, jobId, sendJsonMessage]);

  // Effect to process WebSocket messages
  useEffect(() => {
    if (lastJsonMessage) {
      try {
        console.log('Received WebSocket message:', lastJsonMessage);
        wsHandler.handleMessage(lastJsonMessage as WebSocketMessage);
      } catch (error) {
        console.error('Error processing WebSocket message:', error);
        setError('Error processing server message');
      }
    }
  }, [lastJsonMessage, wsHandler]);

  // Cleanup effect
  useEffect(() => {
    return () => {
      const ws = getWebSocket();
      if (ws) {
        console.log('Closing WebSocket connection');
        ws.close();
      }
    };
  }, [getWebSocket]);

  // Node selection handler
  const handleNodeClick = useCallback((node: Node) => {
    setSelectedNode(node);
  }, []);

  return (
    <div className="relative h-screen w-full">
      <Button
        variant="outline"
        className="absolute top-4 left-4 z-50"
        onClick={() => navigate(-1)}
      >
        Back
      </Button>

      <AnalysisPanel 
        status={analysisProgress}
        stats={graphStats} 
      />

      {selectedNode && (
        <NodeDetailsCard 
          node={selectedNode} 
          onClose={() => setSelectedNode(null)} 
        />
      )}

      {error && (
        <Alert variant="destructive" className="absolute bottom-4 right-4 w-96 z-10 bg-red-500 text-white">
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <GraphVizComponent
        graphData={graphData}
        onNodeClick={handleNodeClick}
      />
    </div>
  );
};

export default GraphComponent;