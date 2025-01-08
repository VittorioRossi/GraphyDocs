from typing import List, Dict
from .graph_manager import CodeGraphManager


class GraphQueries:
    def __init__(self, graph_manager: CodeGraphManager):
        self.gm = graph_manager

    def get_inheritance_hierarchy(self, class_name: str) -> Dict:
        with self.gm.driver.session() as session:
            result = session.run(
                """
                MATCH path = (c:Class {name: $class_name})-[:INHERITS_FROM*]->(parent:Class)
                RETURN nodes(path) as hierarchy
            """,
                {"class_name": class_name},
            )
            return [dict(node) for record in result for node in record["hierarchy"]]

    def get_method_overrides(self, method_name: str) -> List[Dict]:
        with self.gm.driver.session() as session:
            result = session.run(
                """
                MATCH (m:Function {name: $method_name})<-[:OVERRIDES*]-(override:Function)
                RETURN m as base, collect(override) as overrides
            """,
                {"method_name": method_name},
            )
            return [dict(record) for record in result]

    def get_call_graph(self, function_name: str, depth: int = 3) -> List[Dict]:
        with self.gm.driver.session() as session:
            result = session.run(
                """
                MATCH path = (caller:Function)-[:CALLS*1..{depth}]->(f:Function {name: $function_name})
                RETURN nodes(path) as call_chain
            """,
                {"function_name": function_name, "depth": depth},
            )
            return [dict(node) for record in result for node in record["call_chain"]]

    def get_component_dependencies(self, component_name: str) -> List[Dict]:
        with self.gm.driver.session() as session:
            result = session.run(
                """
                MATCH (c:CodeNode {name: $name})-[r:REFERENCES|CALLS|IMPORTS]->(dep)
                RETURN type(r) as relationship, collect(dep) as dependencies
            """,
                {"name": component_name},
            )
            return [dict(record) for record in result]


# Frontend Graph Data Structure
class GraphVisualization:
    def __init__(self, graph_manager: CodeGraphManager):
        self.gm = graph_manager

    def get_graph_data(self, project_name: str) -> Dict:
        with self.gm.driver.session() as session:
            result = session.run(
                """
                MATCH (n:CodeNode)-[:PART_OF]->(p:Project {name: $project_name})
                OPTIONAL MATCH (n)-[r]->(m:CodeNode)-[:PART_OF]->(p)
                RETURN collect(distinct n) as nodes,
                       collect(distinct {from: startNode(r).name, 
                                      to: endNode(r).name, 
                                      type: type(r)}) as relationships
            """,
                {"project_name": project_name},
            )

            graph_data = result.single()
            return {
                "nodes": [self._format_node(node) for node in graph_data["nodes"]],
                "edges": [
                    self._format_edge(rel)
                    for rel in graph_data["relationships"]
                    if rel["from"] and rel["to"]
                ],
            }

    def _format_node(self, node: Dict) -> Dict:
        return {
            "id": node["name"],
            "label": node["name"],
            "type": node["kind"],
            "data": {"fqn": node["fullyQualifiedName"], "location": node["location"]},
        }

    def _format_edge(self, edge: Dict) -> Dict:
        return {"source": edge["from"], "target": edge["to"], "type": edge["type"]}

    def get_subgraph(self, entity_name: str, depth: int = 2) -> Dict:
        with self.gm.driver.session() as session:
            result = session.run(
                """
                MATCH path = (n:CodeNode {name: $name})-[*1..{depth}]-(related:CodeNode)
                RETURN collect(distinct nodes(path)) as nodes,
                       collect(distinct relationships(path)) as rels
            """,
                {"name": entity_name, "depth": depth},
            )

            graph_data = result.single()
            return {
                "nodes": [self._format_node(node) for node in graph_data["nodes"]],
                "edges": [self._format_edge(rel) for rel in graph_data["rels"]],
            }
