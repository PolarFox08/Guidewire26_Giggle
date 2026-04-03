"""
GigShield Database Configuration Module

Initializes SQLAlchemy engine, session factory, and ORM base class.
Configured for Supabase PostgreSQL with connection pooling.

All SQLAlchemy ORM models inherit from DeclarativeBase defined here.
get_db() is the FastAPI dependency for database sessions.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import QueuePool

from app.core.config import settings


# SQLAlchemy Engine Configuration
# ================================
# Supabase PostgreSQL with optimized connection pooling for Railway/free tier deployment
engine = create_engine(
    settings.database_url,
    # Connection Pool Settings (optimized for Supabase)
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=0,
    pool_pre_ping=True,  # Test connection before using (prevents stale connections)
    pool_recycle=3600,   # Recycle connections every hour (Supabase idle timeout)
    # Engine Settings
    echo=settings.debug,  # Log SQL statements in debug mode
    connect_args={
        "connect_timeout": 10,  # Connection timeout in seconds
    },
)


# Session Factory
# ===============
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)
"""
SessionLocal factory for creating database sessions.
Used by get_db() dependency to create per-request sessions.
"""


# Declarative Base for ORM Models
# ================================
DeclarativeBase = declarative_base()
"""
Base class for all SQLAlchemy ORM models.
All models in app/models/ must inherit from this.

Usage in model files:
    from app.core.database import DeclarativeBase
    
    class WorkerProfile(DeclarativeBase):
        __tablename__ = "worker_profiles"
        ...
"""


# Database Dependency for FastAPI
# ================================
def get_db() -> Session:
    """
    FastAPI dependency that yields a database session.
    
    Automatically commits on success, rolls back on exception.
    Closes the session after the request completes.
    
    Usage in endpoints:
        @router.get("/some-endpoint")
        def endpoint(db: Session = Depends(get_db)):
            result = db.query(SomeModel).first()
            return result
    
    Yields:
        Session: SQLAlchemy database session for this request
        
    Ensures:
        - One session per request
        - Automatic cleanup (close) after request
        - Proper rollback on errors
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Event Listeners
# ===============
# Enforce audit_events append-only constraint at ORM layer
@event.listens_for(Session, "before_flush")
def receive_before_flush(session, flush_context, instances):
    """
    Intercept before_flush to prevent UPDATE operations on audit_events.
    
    This enforces that audit_events is append-only at the ORM layer
    (in addition to database-level permission revocation).
    
    The audit_events table must never be modified after creation.
    Only INSERT is permitted. UPDATE and DELETE will raise RuntimeError.
    """
    from app.models.audit import AuditEvent
    
    # Check for any updates to AuditEvent
    for obj in session.dirty:
        if isinstance(obj, AuditEvent):
            raise RuntimeError(
                "audit_events table is append-only. "
                "UPDATE operations are not permitted. "
                "Only INSERT is allowed per IRDAI regulatory requirements."
            )
    
    # Check for any deletes of AuditEvent
    for obj in session.deleted:
        if isinstance(obj, AuditEvent):
            raise RuntimeError(
                "audit_events table is append-only. "
                "DELETE operations are not permitted. "
                "Only INSERT is allowed per IRDAI regulatory requirements."
            )
