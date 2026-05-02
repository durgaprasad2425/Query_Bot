from enum import Enum
from pydantic import BaseModel, Field


class AllowedFileTypes(str, Enum):
    """Enumeration of accepted file types for document upload."""
    PDF = "pdf"
    TXT = "txt"


class DocumentChunking(BaseModel):
    """Represents a text segment parsed from a document, ready for embedding."""
    chunk_id: str
    document_id: str
    content: str
    metadata: dict = Field(default_factory=dict)


class ConfidenceLevels(str, Enum):
    """Self-evaluated confidence level returned by the validation agent."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNVERIFIED = "unverified"
