import React, { useCallback, useEffect, useState, useRef } from 'react';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import useWebSocket, { ReadyState } from 'react-use-websocket';
import { useParams, useNavigate } from 'react-router-dom';


import ForceGraph from './graph/ForceGraph';
import NodeDetailsCard from './graph/NodeDetail';
import AnalysisPanel from './graph/AnalysisPanel';
import { AnalysisStatus, GraphStats } from './graph/AnalysisPanel';

interface NodeData {
  location?: string;
  documentation?: string;
  qualifiedName?: string;
  path?: string;
  [key: string]: any;
}


type NodeType = 
  | 'Project' | 'File' | 'Config' | 'Module' | 'Class'
  | 'Method' | 'Function' | 'Variable' | 'Constant'
  | 'Namespace' | 'Interface' | 'Enum' | 'Package'
  | 'Event' | 'Operator';
  
type EdgeType = 'CONTAINS' | 'REFERENCES' | 'INHERITS_FROM' | 'IMPLEMENTS' | 'PART_OF' | 'DEPENDS_ON';

interface GraphNode {
  id: string;
  name: string;
  type: NodeType;
  color: string;
  data: NodeData;
}

interface GraphLink {
  id: string;
  source: string;
  target: string;
  type: EdgeType;
}

interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}


interface WSMessage {
  type: string;
  data: {
    job_id?: string;
    status?: string;
    progress?: number;
    error?: string;
    message?: string;
    error_type?: string;
    nodes?: any[];
    edges?: any[];
    sequence?: number;
    graph_data?: GraphData;
    checkpoint?: any;
    current_file?: string;
    processed_files?: number;
    total_files?: number;
  };
}

const NODE_COLORS: Record<string, string> = {
  'Project': '#4a5568', 'File': '#3182ce', 'Config': '#d69e2e',
  'Module': '#805ad5', 'Class': '#e53e3e', 'Method': '#38a169',
  'Function': '#2b6cb0', 'Variable': '#dd6b20', 'Constant': '#805ad5',
  'Namespace': '#718096', 'Interface': '#6b46c1', 'Enum': '#975a16',
  'Package': '#2c5282', 'Event': '#c53030', 'Operator': '#4c51bf',
  'default': '#a0aec0'
};

function transformNode(node: any): GraphNode {
  return {
    id: node.id,
    name: node.name || 'Unnamed',
    type: node.kind as NodeType,
    color: NODE_COLORS[node.kind] || NODE_COLORS.default,
    data: {
      ...node,
      location: node.location,
      documentation: node.documentation,
      qualifiedName: node.qualified_name,
      path: node.path
    }
  };
}

function transformEdge(edge: any): GraphLink {
  return {
    id: edge.id || `${edge.source}-${edge.target}-${edge.type}`,
    source: edge.source,
    target: edge.target,
    type: edge.type as EdgeType
  };
}

function transformGraphData(data: any): GraphData {
  return {
    nodes: data.nodes?.map(transformNode) || [],
    links: data.edges?.map(transformEdge) || []
  };
}



const GraphComponent: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const WS_URL = 'ws://localhost:8000/api/v1/ws';
  const reconnectAttemptRef = useRef(0);
  const processedBatchesRef = useRef(new Set<string>());

  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], links: [] });
  const [status, setStatus] = useState<string>('idle');
  const [progress, setProgress] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [graphStats, setGraphStats] = useState<GraphStats>({
    totalNodes: 0, totalEdges: 0, nodeTypes: {}, edgeTypes: {}
  });
  const [currentFile, setCurrentFile] = useState<string | null>(null);
  const [processedFiles, setProcessedFiles] = useState<number>(0);
  const [totalFiles, setTotalFiles] = useState<number>(0);

  const updateGraphStats = useCallback((nodes: GraphNode[], links: GraphLink[]) => {
    setGraphStats({
      totalNodes: nodes.length,
      totalEdges: links.length,
      nodeTypes: nodes.reduce<Record<string, number>>((acc, node) => ({
        ...acc, [node.type]: (acc[node.type] || 0) + 1
      }), {}),
      edgeTypes: links.reduce<Record<string, number>>((acc, link) => ({
        ...acc, [link.type]: (acc[link.type] || 0) + 1
      }), {})
    });
  }, []);

  const updateGraph = useCallback((nodes: any[], edges: any[], shouldMerge = false) => {
    setGraphData(prev => {
      if (!shouldMerge) {
        const newData = transformGraphData({ nodes, edges });
        updateGraphStats(newData.nodes, newData.links);
        return newData;
      }

      const nodeMap = new Map(prev.nodes.map(node => [node.id, node]));
      const transformedNodes = nodes?.map(transformNode) || [];
      const newNodes = [...prev.nodes];

      transformedNodes.forEach(node => {
        if (!nodeMap.has(node.id)) {
          newNodes.push(node);
          nodeMap.set(node.id, node);
        }
      });

      const newLinks = [...prev.links];
      (edges?.map(transformEdge) || []).forEach(edge => {
        if (nodeMap.has(edge.source) && nodeMap.has(edge.target)) {
          const isDuplicate = newLinks.some(link => 
            link.source === edge.source && 
            link.target === edge.target && 
            link.type === edge.type
          );
          if (!isDuplicate) {
            newLinks.push(edge);
          }
        }
      });

      updateGraphStats(newNodes, newLinks);
      return { nodes: newNodes, links: newLinks };
    });
  }, [updateGraphStats]);

  const { sendJsonMessage, lastJsonMessage, readyState, getWebSocket } = useWebSocket(WS_URL, {
    share: false,
    shouldReconnect: () => true,
    reconnectInterval: (attemptNumber) => Math.min(1000 * Math.pow(2, attemptNumber), 30000),
    onOpen: () => {
      reconnectAttemptRef.current = 0;
      setError(null);
      setStatus('connected');
    },
    onClose: () => setStatus('disconnected'),
    onError: () => setError('WebSocket connection error'),
  });


  const handleMessage = useCallback((message: WSMessage) => {
    if (!message?.type) {
      console.warn('Received invalid message format:', message);
      return;
    }

    const messageKey = message.data?.sequence ? 
      `${message.type}-${message.data.sequence}` : 
      `${message.type}-${JSON.stringify(message.data)}`;

    if (processedBatchesRef.current.has(messageKey)) {
      console.debug('Skipping duplicate message:', messageKey);
      return;
    }

    console.log(`Processing message type: ${message.type}`, message.data);
    
    switch (message.type) {
      case 'start_analysis_response': {
        const { status, job_id, graph_data, progress } = message.data;

        if (status === 'completed') {
          setStatus('completed');
          if (graph_data) {
            updateGraph(graph_data.nodes, graph_data.edges);
          }
        } else if (['running', 'started', 'resumed'].includes(status)) {
          setStatus('running');
          if (progress) setProgress(progress);
          if (graph_data) {
            updateGraph(graph_data.nodes, graph_data.edges, true);
          }
          sendJsonMessage({
            type: 'subscribe',
            data: { job_id, ...(message.data.checkpoint && { checkpoint: message.data.checkpoint }) }
          });
        }
        break;
      }

      case 'batch_update': {
        if (!message.data.sequence) {
          console.warn('Received batch update without sequence number');
          return;
        }

        processedBatchesRef.current.add(messageKey);
        const { nodes, edges } = message.data;
        if (nodes || edges) {
          updateGraph(nodes || [], edges || [], true);
        }
        break;
      }

      case 'status_update': {
        const { status, progress, error, current_file, processed_files, total_files } = message.data;
        if (status) setStatus(status);
        if (progress) setProgress(progress);
        if (error) setError(error);
        if (current_file) setCurrentFile(current_file);
        if (processed_files !== undefined) setProcessedFiles(processed_files);
        if (total_files !== undefined) setTotalFiles(total_files);
        break;
      }

      case 'analysis_complete':
        setStatus('completed');
        break;

      case 'analysis_error':
        setError(message.data.error);
        setStatus('error');
        break;

      case 'error': {
        let errorMessage = message.data.message;
        if (message.data.error_type === 'ProjectNotFoundError') {
          errorMessage = 'Project not found. Please verify the project ID.';
          setTimeout(() => navigate('/'), 3000);
        } else if (message.data.error_type === 'JobNotFoundError') {
          errorMessage = 'Analysis job not found. The job may have expired or been deleted.';
        }
        setError(errorMessage);
        setStatus('error');
        break;
      }
    }
  }, [updateGraph, navigate, sendJsonMessage]);


  useEffect(() => {
    if (readyState === ReadyState.OPEN) {
      sendJsonMessage({
        type: 'start_analysis',
        data: { project_id: projectId, analyzer_type: 'package' }
      });
    }
  }, [readyState, projectId, sendJsonMessage]);

  useEffect(() => {
    if (lastJsonMessage) {
      try {
        handleMessage(lastJsonMessage as WSMessage);
      } catch (error) {
        console.error('Error processing WebSocket message:', error);
      }
    }
  }, [lastJsonMessage, handleMessage]);

  useEffect(() => {
    return () => getWebSocket()?.close();
  }, [getWebSocket]);

  const handleNodeClick = useCallback((node: GraphNode) => {
    if (!node || typeof node !== 'object') {
      console.warn('Invalid node clicked:', node);
      return;
    }
    setSelectedNode(node);
  }, []);


  const analysisStatus: AnalysisStatus = {
    status,
    progress,
    ...(currentFile && { currentFile }),
    processedFiles,
    totalFiles,
    ...(error && { error })
  };  

  

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
        status={analysisStatus} 
        stats={graphStats} 
      />

      {selectedNode && (
        <NodeDetailsCard 
          node={selectedNode} 
          onClose={() => setSelectedNode(null)} 
        />
      )}

      {error && (
        <Alert variant="destructive" className="absolute top-4 left-4 w-96 z-10">
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <ForceGraph
        graphData={graphData}
        onNodeClick={handleNodeClick}
      />
    </div>
  );
};

export default GraphComponent;