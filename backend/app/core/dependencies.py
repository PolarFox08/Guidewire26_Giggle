"""
GigShield FastAPI Dependencies Module

Centralizes all FastAPI dependency injection functions.
Endpoints import from here using: from fastapi import Depends

This module imports core dependencies from app.core and re-exports them
for convenient access throughout the application.
"""

from sqlalchemy.orm import Session
from fastapi import Depends

from app.core.database import get_db as _get_db_session


# Database Session Dependency
# ============================
def get_db() -> Session:
    """
    FastAPI dependency that provides a database session for endpoint handler.
    
    This is the primary dependency used by all endpoints that need database access.
    
    Usage in endpoints:
        from fastapi import APIRouter, Depends
        from sqlalchemy.orm import Session
        from app.core.dependencies import get_db
        
        router = APIRouter()
        
        @router.get("/example")
        def get_example(db: Session = Depends(get_db)):
            result = db.query(SomeModel).first()
            return result
    
    Yields:
        Session: SQLAlchemy database session for this request
    """
    yield from _get_db_session()


__all__ = [
    "get_db",
]
"""
Public API exports for this module.
Only include dependencies that are safe for external use.
"""
