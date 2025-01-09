import React, { useCallback, useRef, useEffect, useMemo } from 'react';
import { ForceGraph2D } from 'react-force-graph';
import { Node, Edge, Graph } from '@/types/graph';
import { NODE_COLORS } from '@/constants/colors';

interface GraphVisualizationProps {
  graphData: Graph;
  onNodeClick?: (node: Node) => void;
}

interface ForceGraphData {
  nodes: Node[];
  links: Edge[];
}

const GraphVisualization: React.FC<GraphVisualizationProps> = ({ 
  graphData, 
  onNodeClick 
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<any>(null);
  const [dimensions, setDimensions] = React.useState({ width: 0, height: 0 });

  // Transform graph data to match ForceGraph2D format
  const transformedData = useMemo<ForceGraphData>(() => ({
    nodes: graphData.nodes,
    links: graphData.edges.map(edge => ({
      ...edge,
    }))
  }), [graphData]);

  const updateDimensions = useCallback(() => {
    if (containerRef.current) {
      const { offsetWidth, offsetHeight } = containerRef.current;
      setDimensions({ width: offsetWidth, height: offsetHeight });
    }
  }, []);

  // Initial zoom out effect based on graph size
  useEffect(() => {
    if (graphRef.current) {
      const distance = Math.sqrt(transformedData.nodes.length) * 200;
      graphRef.current.zoom(0.7);
      graphRef.current.centerAt(0, 0, 1000);
    }
  }, [transformedData.nodes.length]);

  useEffect(() => {
    const resizeObserver = new ResizeObserver(updateDimensions);
    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }
    return () => resizeObserver.disconnect();
  }, [updateDimensions]);

  const getNodeColor = useCallback(
    (node: Node) => NODE_COLORS[node.kind] || NODE_COLORS.default,
    []
  );

  const drawNode = useCallback((node: Node, ctx: CanvasRenderingContext2D, globalScale: number) => {
    // Calculate node size based on type and scale
    const baseNodeSize = node.kind === 'Project' ? 8 : 
                        node.kind === 'File' ? 6 : 3;
    const nodeSize = baseNodeSize * (1 + (globalScale > 1.5 ? (globalScale - 1.5) * 0.5 : 0));
    const color = getNodeColor(node);

    // Draw node with shadow effect
    ctx.shadowColor = 'rgba(0, 0, 0, 0.2)';
    ctx.shadowBlur = 5;
    ctx.beginPath();
    ctx.arc(node.x!, node.y!, nodeSize, 0, 2 * Math.PI);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.strokeStyle = '#ffffff44';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Draw label when zoomed in enough
    if (globalScale > 1.5) {
      const shortLabel = node.name.length > 6 ? 
        node.name.substring(0, 5) + '...' : 
        node.name;
        
      // Adaptive font size based on node size and scale
      const fontSize = Math.min(nodeSize * 0.8, 12/globalScale);
      
      ctx.font = `${fontSize}px Inter`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      
      // Fade in text based on zoom level
      const opacity = Math.min((globalScale - 1.5) / 0.5, 1);
      ctx.fillStyle = `rgba(255, 255, 255, ${opacity})`;
      ctx.fillText(shortLabel, node.x!, node.y!);
    }
  }, [getNodeColor]);

  return (
    <div ref={containerRef} className="w-full h-full">
      <ForceGraph2D
        graphData={transformedData}
        ref={graphRef}
        width={dimensions.width}
        height={dimensions.height}
        nodeLabel={node => `${node.name}\n${node.kind}`}
        nodeCanvasObject={drawNode}
        nodeCanvasObjectMode={() => "after"}
        onNodeClick={onNodeClick}
        linkDirectionalArrowLength={8}
        linkDirectionalArrowRelPos={1}
        linkCurvature={0.25}
        linkDirectionalParticles={3}
        linkDirectionalParticleWidth={2.5}
        linkDirectionalParticleSpeed={0.008}
        d3AlphaDecay={0.008}
        d3VelocityDecay={0.15}
        cooldownTicks={120}
        enableNodeDrag={true}
        minZoom={0.4}
        maxZoom={5}
        backgroundColor="#00000000"
      />
    </div>
  );
};

export default GraphVisualization;