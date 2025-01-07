import React, { useCallback, useEffect, useState, useRef } from 'react';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import useWebSocket, { ReadyState } from 'react-use-websocket';
import { useParams, useNavigate } from 'react-router-dom';
import ForceGraph from './ForceGraph';

interface NodeData {
  location?: string;
  documentation?: string;
  qualifiedName?: string;
  path?: string;
  [key: string]: any;
}

type NodeType = 
  | 'Project'
  | 'File'
  | 'Config'
  | 'Module'
  | 'Class'
  | 'Method'
  | 'Function'
  | 'Variable'
  | 'Constant'
  | 'Namespace'
  | 'Interface'
  | 'Enum'
  | 'Package'
  | 'Event'
  | 'Operator';
  
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

interface GraphStats {
  totalNodes: number;
  totalEdges: number;
  nodeTypes: Record<string, number>;
  edgeTypes: Record<string, number>;
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
  'Project': '#4a5568',
  'File': '#3182ce',
  'Config': '#d69e2e',
  'Module': '#805ad5',
  'Class': '#e53e3e',
  'Method': '#38a169',
  'Function': '#2b6cb0',
  'Variable': '#dd6b20',
  'Constant': '#805ad5',
  'Namespace': '#718096',
  'Interface': '#6b46c1',
  'Enum': '#975a16',
  'Package': '#2c5282',
  'Event': '#c53030',
  'Operator': '#4c51bf',
  'default': '#a0aec0'
};
const GraphComponent: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const WS_URL = 'ws://localhost:8000/api/ws';
  const reconnectAttemptRef = useRef(0);
  const processedBatchesRef = useRef(new Set<string>());

  const { sendJsonMessage, lastJsonMessage, readyState, getWebSocket } = useWebSocket(WS_URL, {
    share: false,
    shouldReconnect: (closeEvent) => {
      console.log('WebSocket disconnected, attempting to reconnect...', closeEvent);
      return true;
    },
    reconnectInterval: (attemptNumber) => {
      const delay = Math.min(1000 * Math.pow(2, attemptNumber), 30000);
      console.log(`Reconnect attempt ${attemptNumber, delay}ms`);
      return delay;
    },
    onOpen: () => {
      console.log('WebSocket connected, readyState:', ReadyState[ReadyState.OPEN]);
      reconnectAttemptRef.current = 0;
      setError(null);
    },
    onClose: () => {
      console.log('WebSocket disconnected, readyState:', ReadyState[ReadyState.CLOSED]);
    },
    onError: (event) => {
      console.error('WebSocket error:', event);
      setError('WebSocket connection error');
    },
    onMessage: (event) => {
      console.log('Raw WebSocket message received:', event.data);
    },
  });

  useEffect(() => {
    console.log('Current WebSocket state:', ReadyState[readyState]);
  }, [readyState]);

  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], links: [] });
  const [status, setStatus] = useState<string>('idle');
  const [progress, setProgress] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [graphStats, setGraphStats] = useState<GraphStats>({
    totalNodes: 0,
    totalEdges: 0,
    nodeTypes: {},
    edgeTypes: {}
  });
  const [currentFile, setCurrentFile] = useState<string | null>(null);
  const [processedFiles, setProcessedFiles] = useState<number>(0);
  const [totalFiles, setTotalFiles] = useState<number>(0);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);

  const updateGraphStats = useCallback((nodes: GraphNode[], links: GraphLink[]) => {
    const nodeTypes = nodes.reduce<Record<string, number>>((acc, node) => ({
      ...acc,
      [node.type]: (acc[node.type] || 0) + 1
    }), {});

    const edgeTypes = links.reduce<Record<string, number>>((acc, link) => ({
      ...acc,
      [link.type]: (acc[link.type] || 0) + 1
    }), {});

    setGraphStats({
      totalNodes: nodes.length,
      totalEdges: links.length,
      nodeTypes,
      edgeTypes
    });
  }, []);


  const handleMessage = useCallback((message: WSMessage) => {
    if (!message || !message.type) {
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
      case 'start_analysis_response':
        const { status, job_id, graph_data, progress, checkpoint } = message.data;
        setCurrentJobId(job_id);
  
        switch (status) {
          case 'completed':
            setStatus('completed');
            if (graph_data) {
              setGraphData(graph_data);
            }
            break;
  
          case 'running':
          case 'started':
          case 'resumed':
            setStatus('running');
            if (progress) setProgress(progress);
            sendJsonMessage({
              type: 'subscribe',
              data: { 
                job_id,
                ...(checkpoint && { checkpoint })
              }
            });
            break;
        }
        break;  

      case 'batch_update':
        if (!message.data.sequence) {
          console.warn('Received batch update without sequence number');
          return;
        }

        processedBatchesRef.current.add(messageKey);
        console.log(`Processing batch ${message.data.sequence}:`, message.data);

        if (message.data.nodes || message.data.edges) {
          setGraphData(prev => {
            // Create a map of existing nodes for efficient lookup
            const nodeMap = new Map(prev.nodes.map(node => [node.id, node]));
            const newNodes = [...prev.nodes];

            // Process new nodes
            if (message.data.nodes) {
              message.data.nodes.forEach((node: any) => {
                if (!nodeMap.has(node.id)) {
                  const newNode: GraphNode = {
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
                  newNodes.push(newNode);
                  nodeMap.set(node.id, newNode);
                }
              });
            }

            // Process new edges
            const newLinks = [...prev.links];
            if (message.data.edges) {
              message.data.edges.forEach((edge: any) => {
                if (nodeMap.has(edge.source) && nodeMap.has(edge.target)) {
                  const newLink: GraphLink = {
                    id: edge.id || `${edge.source}-${edge.target}-${edge.type}`,
                    source: edge.source,
                    target: edge.target,
                    type: edge.type as EdgeType
                  };
                  
                  // Check for duplicate edges
                  const isDuplicate = newLinks.some(link => 
                    link.source === newLink.source && 
                    link.target === newLink.target && 
                    link.type === newLink.type
                  );
            
                  if (!isDuplicate) {
                    newLinks.push(newLink);
                  }
                }
              });
            }
            
            console.log('Updated graph data:', { nodes: newNodes, links: newLinks });
            updateGraphStats(newNodes, newLinks);
            return { nodes: newNodes, links: newLinks };
          });
        }
        break;

      case 'status_update':
        console.log('Status update:', message.data);
        if (message.data.status) setStatus(message.data.status);
        if (message.data.progress) setProgress(message.data.progress);
        if (message.data.error) setError(message.data.error);
        if (message.data.current_file) setCurrentFile(message.data.current_file);
        if (message.data.processed_files !== undefined) setProcessedFiles(message.data.processed_files);
        if (message.data.total_files !== undefined) setTotalFiles(message.data.total_files);
        break;

      case 'analysis_complete':
        console.log('Analysis completed for job:', message.data.job_id);
        setStatus('completed');
        break;

      case 'analysis_error':
        console.error('Analysis error:', message.data.error);
        setError(message.data.error);
        setStatus('error');
        break;

      case 'progress':
        console.log(`Progress update: ${message.data.progress}%`);
        setProgress(message.data.progress);
        break;

      case 'error':
        console.error(`WebSocket error: ${message.data.message} (${message.data.error_type})`);
        let errorMessage = message.data.message;
        
        switch(message.data.error_type) {
          case 'ProjectNotFoundError':
            errorMessage = `Project not found. Please verify the project ID.`;
            setTimeout(() => {
              navigate('/');
            }, 3000);
            break;
          case 'JobNotFoundError':
            errorMessage = `Analysis job not found. The job may have expired or been deleted.`;
            break;
          case 'ValueError':
            errorMessage = `Invalid input: ${message.data.message}`;
            break;
          case 'ServerError':
            errorMessage = `Server error occurred. Please try again later.`;
            break;
        }
        
        setError(errorMessage);
        setStatus('error');
        break;


      default:
        console.warn(`Unhandled message type: ${message.type}`, message);
    }
  }, [sendJsonMessage, updateGraphStats, navigate]);

  // Add debug logging for job subscription
  useEffect(() => {
    if (currentJobId) {
      console.log(`Subscribing to updates for job: ${currentJobId}`);
      processedBatchesRef.current.clear();
    }
  }, [currentJobId]);

  useEffect(() => {
    if (readyState === ReadyState.OPEN) {
      sendJsonMessage({
        type: 'start_analysis',
        data: {
          project_id: projectId,
          analyzer_type: 'package'
        }
      });
    }
  }, [readyState, projectId, sendJsonMessage]);
  

  // Add connection status monitoring
  useEffect(() => {
    switch (readyState) {
      case ReadyState.CONNECTING:
        setStatus('connecting');
        break;
      case ReadyState.CLOSED:
        setStatus('disconnected');
        reconnectAttemptRef.current += 1;
        break;
      case ReadyState.CLOSING:
        setStatus('closing');
        break;
    }
  }, [readyState]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      const ws = getWebSocket();
      if (ws) {
        ws.close();
      }
    };
  }, [getWebSocket]);

  useEffect(() => {
      if (lastJsonMessage) {
        try {
          console.log('Raw lastJsonMessage:', lastJsonMessage);
          handleMessage(lastJsonMessage as WSMessage);
        } catch (error) {
          console.error('Error processing WebSocket message:', error);
        }
      }
    }, [lastJsonMessage, handleMessage]);

  const handleNodeClick = useCallback((node: any) => {
    if (!node || typeof node !== 'object') {
        console.warn('Invalid node clicked:', node);
        return;
    }
    setSelectedNode(node as GraphNode);
}, []);
  return (
    <div className="relative h-screen w-full">
      {/* Status Card */}
      <Card className="absolute top-4 right-4 w-96 z-10">
        <CardHeader>
          <CardTitle>Analysis Status</CardTitle>
        </CardHeader>
        <CardContent>
          <Progress value={progress} className="mb-2" />
          <div className="space-y-2 text-sm">
            <p>Status: {status}</p>
            {currentFile && <p>Current File: {currentFile}</p>}
            <p>Processed Files: {processedFiles}/{totalFiles}</p>
            {error && <p className="text-red-500">Error: {error}</p>}
          </div>
        </CardContent>
      </Card>

      {/* Graph Statistics */}
      <Card className="absolute bottom-4 right-4 w-96 z-10">
        <CardHeader>
          <CardTitle>Graph Statistics</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2 text-sm">
            <p>Total Nodes: {graphStats.totalNodes}</p>
            <p>Total Edges: {graphStats.totalEdges}</p>
            <div className="mt-2">
              <p className="font-semibold">Node Types:</p>
              {Object.entries(graphStats.nodeTypes).map(([type, count]) => (
                <p key={type}>{type}: {count}</p>
              ))}
            </div>
            <div className="mt-2">
              <p className="font-semibold">Edge Types:</p>
              {Object.entries(graphStats.edgeTypes).map(([type, count]) => (
                <p key={type}>{type}: {count}</p>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Node Details */}
      {selectedNode && (
        <Card className="absolute top-4 left-4 w-96 z-10">
          <CardHeader>
            <CardTitle>{selectedNode.name}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <p>Type: {selectedNode.type}</p>
              {selectedNode.data && Object.entries(selectedNode.data).map(([key, value]) => (
                <p key={key}>{key}: {String(value)}</p>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Error Display */}
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