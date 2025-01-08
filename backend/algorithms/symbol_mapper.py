from typing import Dict, Optional
from lsp.lsp_symbols import SymbolKind
from graph.models import (
    EntityKind,
    Location,
    CodeNode,
    Class,
    Function,
    Variable,
    Parameter,
    Enum,
)
import uuid


class SymbolMapper:
    KIND_MAPPING = {
        SymbolKind.File: EntityKind.MODULE,
        SymbolKind.Module: EntityKind.MODULE,
        SymbolKind.Namespace: EntityKind.NAMESPACE,
        SymbolKind.Package: EntityKind.MODULE,
        SymbolKind.Class: EntityKind.CLASS,
        SymbolKind.Method: EntityKind.METHOD,
        SymbolKind.Property: EntityKind.VARIABLE,
        SymbolKind.Field: EntityKind.VARIABLE,
        SymbolKind.Constructor: EntityKind.FUNCTION,
        SymbolKind.Enum: EntityKind.ENUM,
        SymbolKind.Interface: EntityKind.INTERFACE,
        SymbolKind.Function: EntityKind.FUNCTION,
        SymbolKind.Variable: EntityKind.VARIABLE,
        SymbolKind.Constant: EntityKind.VARIABLE,
        SymbolKind.String: EntityKind.VARIABLE,
        SymbolKind.Number: EntityKind.VARIABLE,
        SymbolKind.Boolean: EntityKind.VARIABLE,
        SymbolKind.Array: EntityKind.VARIABLE,
        SymbolKind.Object: EntityKind.VARIABLE,
        SymbolKind.Key: EntityKind.VARIABLE,
        SymbolKind.Null: EntityKind.VARIABLE,
        SymbolKind.EnumMember: EntityKind.ENUM,
        SymbolKind.Struct: EntityKind.CLASS,
        SymbolKind.Event: EntityKind.VARIABLE,
        SymbolKind.Operator: EntityKind.FUNCTION,
        SymbolKind.TypeParameter: EntityKind.PARAMETER,
    }

    @classmethod
    def get_entity_kind(cls, symbol_kind: int) -> Optional[EntityKind]:
        return cls.KIND_MAPPING.get(SymbolKind(symbol_kind), EntityKind.OTHER)

    @classmethod
    def map_symbol_details(cls, symbol: Dict, project_id: str) -> Optional[CodeNode]:
        kind = cls.get_entity_kind(symbol["kind"])
        if not kind:
            return None

        location = Location(
            file=symbol["location"]["uri"].replace("file://", ""),
            start_line=symbol["location"]["range"]["start"]["line"],
            end_line=symbol["location"]["range"]["end"]["line"],
        )

        base_attrs = {
            "id": str(uuid.uuid4()),  # Convert UUID to string
            "uri": symbol["location"]["uri"],
            "name": symbol["name"],
            "fully_qualified_name": symbol.get("detail", symbol["name"]),
            "kind": kind,
            "location": location,
            "project_id": project_id,
        }

        if kind == EntityKind.CLASS:
            return Class(**base_attrs, is_abstract=False)
        elif kind == EntityKind.FUNCTION:
            return Function(
                **base_attrs,
                return_type=symbol.get("detail", "").split(" -> ")[-1],
                is_static=False,
            )
        elif kind == EntityKind.VARIABLE:
            return Variable(
                **base_attrs,
                type=symbol.get("detail", "Any"),
                is_constant=symbol["kind"] == SymbolKind.Constant,
            )
        elif kind == EntityKind.PARAMETER:
            return Parameter(**base_attrs, type=symbol.get("detail", "Any"))
        elif kind == EntityKind.ENUM:
            return Enum(**base_attrs, values=[])
        else:
            return CodeNode(**base_attrs)
