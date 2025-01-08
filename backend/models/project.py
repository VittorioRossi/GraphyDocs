import uuid

from sqlalchemy import Column, DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    path = Column(String, nullable=False)
    source_type = Column(Enum("git", "zip", name="source_types"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    # Relationship
    jobs = relationship("Job", back_populates="project", lazy="dynamic")
