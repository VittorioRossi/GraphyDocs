from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from .database import Base
from .project import Project

class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey('projects.id'), nullable=False)
    status = Column(String, nullable=False, default='pending')  # pending, running, completed, error
    progress = Column(Integer, default=0)  # Progress percentage (0-100)
    message = Column(String)  # Current operation description
    error = Column(String)  # Error message if failed
    last_checkpoint = Column(JSON)  # Last analysis checkpoint
    sequence = Column(Integer, default=0)  # For tracking batch sequence
    active_connections = Column(Integer, default=0)  # Number of active WebSocket connections
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationship to Project
    project = relationship("Project", back_populates="jobs")