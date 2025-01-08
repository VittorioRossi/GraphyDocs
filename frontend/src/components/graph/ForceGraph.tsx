import React, { useCallback, useMemo, useState } from 'react';
import { ForceGraph2D } from 'react-force-graph';

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

interface GraphNode {
  id: string;
  name: string;
  type: NodeType;
  color: string;
  data: NodeData;
  x?: number;
  y?: number;
  connections?: number;
}

interface GraphLink {
  id: string;
  source: string | GraphNode;
  target: string | GraphNode;
  type: string;
}

interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

interface ForceGraph {
  graphData: GraphData;
  onNodeClick?: (node: GraphNode) => void;
}

const EnhancedForceGraph: React.FC<ForceGraph> = ({ graphData, onNodeClick }) => {
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);
  const [hoveredLink, setHoveredLink] = useState<GraphLink | null>(null);

  const handleNodeClick = useCallback((node: GraphNode) => {
    onNodeClick?.(node);
  }, [onNodeClick]);

  const isDark = false;
  const backgroundColor = isDark ? '#1a1a1a' : '#ffffff';
  const textColor = isDark ? '#ffffff' : '#000000';
  const linkColor = isDark ? '#404040' : '#d1d5db';
  const highlightColor = isDark ? '#60a5fa' : '#3b82f6';

  const processedGraphData = useMemo(() => {
    // Create adjacency list
    const adjacencyList = new Map<string, Set<string>>();
    graphData.links.forEach(link => {
      const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
      const targetId = typeof link.target === 'string' ? link.target : link.target.id;
      
      if (!adjacencyList.has(sourceId)) adjacencyList.set(sourceId, new Set());
      if (!adjacencyList.has(targetId)) adjacencyList.set(targetId, new Set());
      
      adjacencyList.get(sourceId)!.add(targetId);
      adjacencyList.get(targetId)!.add(sourceId);
    });

    // Count all reachable nodes using BFS
    const connectionCount = new Map<string, number>();
    const getAllConnections = (startId: string) => {
      const visited = new Set<string>();
      const queue = [startId];
      visited.add(startId);
      
      while (queue.length > 0) {
        const currentId = queue.shift()!;
        const neighbors = adjacencyList.get(currentId) || new Set();
        
        for (const neighborId of neighbors) {
          if (!visited.has(neighborId)) {
            visited.add(neighborId);
            queue.push(neighborId);
          }
        }
      }
      return visited.size - 1; // Exclude self
    };

    // Calculate total connections for each node
    graphData.nodes.forEach(node => {
      connectionCount.set(node.id, getAllConnections(node.id));
    });

    // Add connection count to nodes
    const nodesWithConnections = graphData.nodes.map(node => ({
      ...node,
      connections: connectionCount.get(node.id) || 0
    }));

    const nodesById = new Map(nodesWithConnections.map(node => [node.id, node]));
    
    const validLinks = graphData.links.filter(link => {
      return nodesById.has(typeof link.source === 'string' ? link.source : link.source.id) && 
             nodesById.has(typeof link.target === 'string' ? link.target : link.target.id);
    }).map(link => ({
      ...link,
      source: nodesById.get(typeof link.source === 'string' ? link.source : link.source.id),
      target: nodesById.get(typeof link.target === 'string' ? link.target : link.target.id)
    }));

    return { nodes: nodesWithConnections, links: validLinks };
  }, [graphData]);

  const getNodeSize = useCallback((node: GraphNode) => {
    if (node.type === 'Project') return 15;
    if (node.type === 'File') return 10;
    return 5;
  }, []);

  const getNodeLabel = useCallback((node: GraphNode) => {
    if (node.type === 'Variable') {
      return '';
    }
    return node.name;
  }, []);

  const drawNode = useCallback((node: GraphNode, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const label = getNodeLabel(node);
    const fontSize = 12/globalScale;
    const isHovered = hoveredNode?.id === node.id;
    const nodeSize = getNodeSize(node);
    
    // Node circle
    ctx.beginPath();
    ctx.arc(node.x!, node.y!, nodeSize, 0, 2 * Math.PI);
    ctx.fillStyle = isHovered ? highlightColor : node.color;
    ctx.fill();
    ctx.strokeStyle = isDark ? '#ffffff33' : '#00000033';
    ctx.stroke();

    if (label) {
      // Label background
      ctx.font = `${fontSize}px Inter`;
      const textWidth = ctx.measureText(label).width;
      const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.4);
      
      ctx.fillStyle = isDark ? '#000000cc' : '#ffffffcc';
      ctx.fillRect(
        node.x! - bckgDimensions[0] / 2,
        node.y! - bckgDimensions[1] / 2,
        bckgDimensions[0],
        bckgDimensions[1]
      );
      
      // Label text
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = isHovered ? highlightColor : textColor;
      ctx.fillText(label, node.x!, node.y!);

      // Type indicator
      const typeLabel = `(${node.type})`;
      ctx.fillStyle = isDark ? '#ffffff66' : '#00000066';
      ctx.fillText(typeLabel, node.x!, node.y! + fontSize);
    }
  }, [hoveredNode, isDark, highlightColor, textColor, getNodeLabel, getNodeSize]);

  return (
    <ForceGraph2D
      graphData={processedGraphData}
      nodeLabel={(node: any) => `${node.name}\n${node.type}`}
      nodeRelSize={6}
      linkLabel={(link: any) => link.type}
      linkColor={() => hoveredLink ? highlightColor : linkColor}
      linkWidth={(link: any) => hoveredLink?.id === link.id ? 2 : 1}
      linkDirectionalArrowLength={6}
      linkDirectionalArrowRelPos={1}
      linkCurvature={0.2}
      linkDirectionalParticles={2}
      linkDirectionalParticleWidth={2}
      linkDirectionalParticleSpeed={0.01}
      nodeCanvasObject={drawNode}
      nodeCanvasObjectMode={() => "after"}
      onNodeClick={handleNodeClick}
      onNodeHover={setHoveredNode}
      onLinkHover={setHoveredLink}
      backgroundColor={backgroundColor}
      width={window.innerWidth}
      height={window.innerHeight}
      d3AlphaDecay={0.01}
      d3VelocityDecay={0.2}
      cooldownTicks={100}
      linkDistance={120}
      d3Force="link"
      enableNodeDrag={true}
      enableZoomPanInteraction={true}
      minZoom={0.5}
      maxZoom={4}
      warmupTicks={50}
    />
  );
};

export default EnhancedForceGraph;