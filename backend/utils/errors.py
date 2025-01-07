class AnalysisError(Exception):
    """Base exception for analysis errors"""
    pass

class ProjectNotFoundError(Exception):
    """Raised when a project is not found"""
    pass

class JobNotFoundError(Exception):
    """Raised when a job is not found"""
    pass

class InvalidAnalyzerError(AnalysisError):
    """Raised when analyzer type is invalid"""
    pass

class JobNotFoundError(Exception):
    """Raised when a job is not found"""
    pass

class GitCloneError(Exception):
    """Custom exception for git clone errors"""
    pass
