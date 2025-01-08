from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from enum import Enum
from .database import Base

class JobStatus(str, Enum):
    PENDING = 'pending'
    STOPPED = 'stopped'
    RUNNING = 'running'
    COMPLETED = 'completed'
    ERROR = 'error'

def get_enum_values(enum_class):
    return [member.value for member in enum_class]



class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey('projects.id'), nullable=False)
    status = Column(String, nullable=False, default=JobStatus.PENDING.value)
    progress = Column(Integer, default=0)  # Progress percentage (0-100)
    message = Column(String)  # Current operation description
    error = Column(String)  # Error message if failed
    last_checkpoint = Column(JSON)  # Last analysis checkpoint
    sequence = Column(Integer, default=0)  # For tracking batch sequence
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    analyzer_type = Column(String)  # Analyzer type

    # Relationship to Project
    project = relationship("Project", back_populates="jobs")