from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel

class EntityKind(Enum):
    MODULE = "Module"
    CLASS = "Class" 
    FUNCTION = "Function"
    VARIABLE = "Variable"
    NAMESPACE = "Namespace"
    ENUM = "Enum"
    INTERFACE = "Interface"
    ANNOTATION = "Annotation"
    PARAMETER = "Parameter"
    METHOD = "Method"
    OTHER = "Other"


class RelationType(Enum):
    CONTAINS = "CONTAINS"
    INHERITS_FROM = "INHERITS_FROM"
    CALLS = "CALLS"
    REFERENCES = "REFERENCES"
    ANNOTATED_BY = "ANNOTATED_BY"
    IMPORTS = "IMPORTS"
    IMPLEMENTS = "IMPLEMENTS"
    OVERRIDES = "OVERRIDES"
    HAS_TYPE = "HAS_TYPE"
    PART_OF = "PART_OF"
    DEPENDS_ON = "DEPENDS_ON"

    RETURNS = "RETURNS"
    HAS_PARAMETER = "HAS_PARAMETER"
    THROWS = "THROWS"

class Node(BaseModel):
    """
    Node class represents a node in a graph.

    Attributes:
        id (str): Unique identifier for the node.
        uri (str): Unique identifier for the node.
        name (str): Descriptive name for the node.
    """
    id: str  # Add id attribute
    uri: str
    name: str
    kind: str
    project_id: str
    job_id: str = None

class Edge(BaseModel):
    """
    Edge class represents an edge in a graph.

    Attributes:
        source (str): The source node of the edge.
        target (str): The target node of the edge.
        type (RelationType): The type of relationship between the nodes.
    """
    source: str
    target: str
    type: RelationType

class Location(BaseModel):
    """
    Location model representing a specific location within a file.

    Attributes:
        file (str): The path to the file.
        start_line (int): The starting line number of the location.
        end_line (int): The ending line number of the location.
    """
    file: str
    start_line: int
    end_line: int

class CodeNode(Node):
    """
    Represents a code entity node in the graph.

    Attributes:
        uri (str): Unique identifier for the node.
        name (str): Descriptive name for the node.
        kind (EntityKind): The kind of code entity.
        location (Location): The location of the code entity.
    """
    kind: EntityKind
    location: Location
    fully_qualified_name: str

    def model_dump(self, *args, **kwargs):
        data = super().model_dump(*args, **kwargs)
        if "location" in data:
            loc = data.pop("location")
            data.update({
                "location_file": loc["file"],
                "location_start_line": loc["start_line"],
                "location_end_line": loc["end_line"]
            })
        return data

class FileNode(Node):
    """
    Represents a file node in the graph.

    Attributes:
        uri (str): Unique identifier for the node given by LSP.
        name (str): File name with extension.
        path (str): File path on the filesystem.
    """
    path: str
    name: str


class ConfigFile(FileNode):
    """
    Represents a configuration file in the graph.

    Attributes:
        config_type (Optional[str]): The type of configuration file.
    """
    kind: str = "ConfigFile"
    config_type: Optional[str]

class Project(Node):
    kind: str = "Project"
    name: str
    version: str

class Module(CodeNode):
    pass

class Namespace(CodeNode):
    pass

class Class(CodeNode):
    is_abstract: bool

class Function(CodeNode):
    return_type: str
    is_static: bool

class Variable(CodeNode):
    type: str
    is_constant: bool

class Enum(CodeNode):
    values: List[str]

class Annotation(CodeNode):
    arguments: Dict[str, str]

class Parameter(CodeNode):
    type: str


if __name__ == "__main__":
    node = CodeNode(
        id="1",
        uri="file://path/to/file.py",
        name="function",
        kind=EntityKind.FUNCTION,
        location=Location(
            file="file.py",
            start_line=1,
            end_line=1
        ),
        fully_qualified_name="module.function")
    print(node.model_dump(mode="json"))
    # Should print flattened structure with location_file, location_start_line, location_end_line