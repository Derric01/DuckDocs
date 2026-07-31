"""Repository implementations."""

from app.repositories.memory import DocumentRepository
from app.repositories.sql import SqlDocumentRepository

AnyRepository = DocumentRepository | SqlDocumentRepository

__all__ = ["AnyRepository", "DocumentRepository", "SqlDocumentRepository"]
