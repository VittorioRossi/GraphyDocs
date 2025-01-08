from .interface import GraphMapper

from fastapi import HTTPException

from .package_analyzer import PackageAnalyzer

ANALYZER_TYPES = {
    "package": PackageAnalyzer,
}


def get_analyzer_by_type(analyzer_type: str) -> GraphMapper:
    """
    Factory function to create the appropriate analyzer based on type
    """
    analyzer_class = ANALYZER_TYPES.get(analyzer_type.lower())
    if not analyzer_class:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported analyzer type: {analyzer_type}. Supported types: {', '.join(ANALYZER_TYPES.keys())}",
        )
    return analyzer_class()
