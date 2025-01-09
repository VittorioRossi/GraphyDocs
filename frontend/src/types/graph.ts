export type NodeType = 
    | 'Project' | 'File' | 'Config' | 'Module' | 'Class'
    | 'Method' | 'Function' | 'Variable' | 'Constant'
    | 'Namespace' | 'Interface' | 'Enum' | 'Package'
    | 'Event' | 'Operator';
    
export type EdgeType = 'CONTAINS' | 'REFERENCES' | 'INHERITS_FROM' | 'IMPLEMENTS' | 'PART_OF' | 'DEPENDS_ON';


export interface Node {
    id: string;
    uri: string;
    name: string;
    kind: NodeType;
    project_id: string;
    job_id: string;
    location_file: string;
    location_start_line: number;
    location_end_line: number;
}

export interface Edge {
    source: string;
    target: string;
    type: EdgeType;
}

export interface Graph {
    nodes: Node[];
    edges: Edge[];
}

export interface GraphStats {
    totalNodes: number;
    totalEdges: number;
    nodeTypes: Record<NodeType, number>;
    edgeTypes: Record<EdgeType, number>;
}