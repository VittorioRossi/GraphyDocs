import React, { useCallback, useMemo } from 'react';
import { ForceGraph2D } from 'react-force-graph';

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

interface GraphNode {
  id: string;
  name: string;
  type: NodeType;
  color: string;
  data: NodeData;
  x?: number;
  y?: number;
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

const EnhancedForceGraph: React.FC<ForceGraph> = ({ 
  graphData, 
  onNodeClick 
}) => {

  const processedGraphData = useMemo(() => {
    const nodesById = new Map(graphData.nodes.map(node => [node.id, node]));
    
    const validLinks = graphData.links.filter(link => {
      return nodesById.has(link.source) && nodesById.has(link.target);
    }).map(link => ({
      ...link,
      source: nodesById.get(link.source),
      target: nodesById.get(link.target)
    }));

    console.log('Processing graph data:', {
      originalNodes: graphData.nodes.length,
      originalLinks: graphData.links.length,
      processedNodes: graphData.nodes.length,
      processedLinks: validLinks.length,
      sampleLink: validLinks[0],
      nodesById: nodesById.size
    });

    return { nodes: graphData.nodes, links: validLinks };
}, [graphData]);

  const handleNodeClick = useCallback((node: any) => {
    if (onNodeClick && node) {
      onNodeClick(node as GraphNode);
    }
  }, [onNodeClick]);

  return (
    <ForceGraph2D
      graphData={processedGraphData}
      nodeLabel={node => `${(node as GraphNode).name}\n${(node as GraphNode).type}`}
      nodeColor={node => (node as GraphNode).color}
      nodeRelSize={8}
      linkLabel={link => (link as GraphLink).type}
      linkColor={() => "#666"}
      linkWidth={2}
      linkDirectionalArrowLength={4}
      linkDirectionalArrowRelPos={1}
      linkCurvature={0.2}
      linkDirectionalParticles={1}
      linkDirectionalParticleSpeed={0.01}
      onNodeClick={handleNodeClick}
      backgroundColor="#f9fafb"
      nodeCanvasObjectMode={() => "after"}
      nodeCanvasObject={(node, ctx, globalScale) => {
        const label = (node as GraphNode).name;
        const fontSize = 12/globalScale;
        ctx.font = `${fontSize}px Inter, system-ui, sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        
        // Draw background for better readability
        const textWidth = ctx.measureText(label).width;
        const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.4);
        
        ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
        ctx.fillRect(
          node.x - bckgDimensions[0] / 2,
          node.y - bckgDimensions[1] / 2,
          bckgDimensions[0],
          bckgDimensions[1]
        );
        
        // Draw text
        ctx.fillStyle = 'rgba(0, 0, 0, 0.8)';
        ctx.fillText(label, node.x, node.y);
      }}
      width={window.innerWidth}
      height={window.innerHeight}
      d3AlphaDecay={0.01}
      d3VelocityDecay={0.4}
      cooldownTicks={100}
      onEngineStop={() => console.log('Layout stabilized')}
    />
  );
};

export default EnhancedForceGraph;