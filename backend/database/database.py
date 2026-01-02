"""
Database connection and session management
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from contextlib import contextmanager
import os
from dotenv import load_dotenv
from database.models import Base

# Load environment variables
load_dotenv()

# Database URL from environment variable
# Format: postgresql://username:password@localhost:5432/database_name
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://qr_user:strongpassword@localhost:5432/met_museum'
)

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    pool_size=10,  # Number of connections to keep open
    max_overflow=20,  # Max additional connections when pool is full
    pool_pre_ping=True,  # Verify connections before using them
    echo=False,  # Set to True to see SQL queries (useful for debugging)
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Thread-safe session
ScopedSession = scoped_session(SessionLocal)


def get_db():
    """
    Dependency function to get database session
    Use this with FastAPI dependency injection or in your scripts

    Example:
        db = next(get_db())
        try:
            # do database operations
            db.commit()
        except:
            db.rollback()
            raise
        finally:
            db.close()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session():
    """
    Context manager for database sessions
    Automatically handles commit/rollback and closing

    Example:
        with get_db_session() as db:
            artwork = Artwork(title="Mona Lisa")
            db.add(artwork)
            # automatically commits when exiting the context
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


def init_db():
    """
    Initialize the database
    Creates all tables if they don't exist

    WARNING: This will NOT modify existing tables
    Use Alembic migrations for schema changes on existing databases
    """

    Base.metadata.create_all(bind=engine)
    print("✓ Database tables created successfully!")


def drop_all_tables():
    """
    Drop all tables - USE WITH CAUTION!
    This will delete all data in the database
    """

    response = input("⚠️  WARNING: This will delete ALL data. Type 'yes' to confirm: ")
    if response.lower() == 'yes':
        Base.metadata.drop_all(bind=engine)
        print("✓ All tables dropped")
    else:
        print("Operation cancelled")


if __name__ == "__main__":
    # Test database connection
    print("Testing database connection...")
    try:
        with engine.connect() as conn:
            print("✓ Successfully connected to database!")
            print(f"Database URL: {DATABASE_URL.split('@')[1]}")  # Hide credentials
    except Exception as e:
        print(f"✗ Failed to connect to database: {e}")
        print("\nMake sure PostgreSQL is running and your DATABASE_URL is correct.")