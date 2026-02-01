"""
Database connection and session management
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
import config

# Create engine
engine = create_engine(
    config.DATABASE_URL,
    connect_args={"check_same_thread": False},  # Needed for SQLite
    echo=False  # Set to True for SQL query logging
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """
    Initialize the database by creating all tables
    """
    from .models import Base
    Base.metadata.create_all(bind=engine)
    print("Database initialized successfully!")

@contextmanager
def get_session() -> Session:
    """
    Context manager for database sessions
    Automatically handles commit/rollback and closing

    Usage:
        with get_session() as session:
            # Your database operations here
            session.add(obj)
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()
