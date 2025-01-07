# Code-Agnostic Knowledge Graph Structure

## Nodes

1. **CodeNode**
   - Abstract base node type for all code-related entities
   - Properties:
     - name: String
     - fullQualifiedName: String
     - kind: Enum (Module, Class, Function, Variable, etc.)
     - location: {file: String, startLine: Int, endLine: Int}

2. **Module**
   - Represents a code file or module
   - Inherits from CodeNode

3. **Namespace**
   - Represents a namespace or package
   - Inherits from CodeNode

4. **Class**
   - Represents a class or struct
   - Inherits from CodeNode
   - Additional properties:
     - isAbstract: Boolean

5. **Function**
   - Represents a function, method, or procedure
   - Inherits from CodeNode
   - Additional properties:
     - returnType: String
     - isStatic: Boolean

6. **Variable**
   - Represents a variable, field, or property
   - Inherits from CodeNode
   - Additional properties:
     - type: String
     - isConstant: Boolean

7. **Enum**
   - Represents an enumeration
   - Inherits from CodeNode

8. **Interface**
   - Represents an interface or protocol
   - Inherits from CodeNode

9. **Annotation**
   - Represents an annotation or decorator
   - Inherits from CodeNode

10. **Parameter**
    - Represents a function parameter
    - Inherits from CodeNode
    - Additional properties:
      - type: String

## Relationships

1. **CONTAINS**
   - Represents hierarchical structure
   - Example: Module CONTAINS Class, Class CONTAINS Function

2. **INHERITS_FROM**
   - Represents inheritance or implementation
   - Example: Class INHERITS_FROM Interface

3. **CALLS**
   - Represents function invocations
   - Example: Function CALLS Function

4. **REFERENCES**
   - Represents usage of a variable or type
   - Example: Function REFERENCES Variable

5. **RETURNS**
   - Links a function to its return type
   - Example: Function RETURNS Class

6. **HAS_PARAMETER**
   - Links a function to its parameters
   - Example: Function HAS_PARAMETER Parameter

7. **ANNOTATED_BY**
   - Links an entity to its annotations
   - Example: Function ANNOTATED_BY Annotation

8. **IMPORTS**
   - Represents module/namespace imports
   - Example: Module IMPORTS Module

9. **IMPLEMENTS**
   - Represents interface implementation
   - Example: Class IMPLEMENTS Interface

10. **OVERRIDES**
    - Represents method overriding
    - Example: Function OVERRIDES Function

11. **HAS_TYPE**
    - Links variables to their types
    - Example: Variable HAS_TYPE Class

12. **THROWS**
    - Represents exceptions a function may throw
    - Example: Function THROWS Class

## Metadata Nodes

1. **Project**
   - Represents the entire project
   - Properties:
     - name: String
     - version: String
     - language: String

2. **Dependency**
   - Represents external dependencies
   - Properties:
     - name: String
     - version: String

## Additional Relationships

1. **PART_OF**
   - Links CodeEntities to the Project
   - Example: Module PART_OF Project

2. **DEPENDS_ON**
   - Links the Project to its Dependencies
   - Example: Project DEPENDS_ON Dependency

## Usage Guidelines

1. Start with the Project node as the root of your graph.
2. Create Module nodes for each file in the project.
3. As you analyze each module, create appropriate CodeNode nodes and establish relationships.
4. Use the CONTAINS relationship to build the hierarchical structure of the code.
5. Use other relationships to represent the semantic connections between entities.
6. Attach Dependency nodes to represent external libraries or frameworks used in the project.

This structure provides a flexible foundation that can accommodate various programming paradigms and languages. It captures both the structural and semantic aspects of code, allowing for rich querying and analysis of the resulting knowledge graph.
