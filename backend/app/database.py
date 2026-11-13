from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings


def _normalize_url(url: str) -> str:
    """Supabase gives 'postgres://' or 'postgresql://' URLs; SQLAlchemy needs the psycopg driver name."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


DATABASE_URL = _normalize_url(get_settings().database_url)
if DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}
else:
    # Supabase's transaction pooler (port 6543) doesn't support prepared statements,
    # so turn off psycopg's automatic ones. Harmless on the session pooler or direct connections.
    _connect_args = {"prepare_threshold": None}

# pool_pre_ping avoids errors when the hosted database closes idle connections.
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: one database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
