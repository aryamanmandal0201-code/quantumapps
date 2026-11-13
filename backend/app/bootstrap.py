import logging

from .config import get_settings
from .database import Base, SessionLocal, engine
from .services import users as user_service

log = logging.getLogger("taskpilot")


def enable_row_level_security() -> None:
    """Supabase exposes every table in the public schema through its REST API (PostgREST).
    Turning on RLS with no policies blocks that API completely. This backend connects as the
    table owner, which bypasses RLS, so the app itself is unaffected. Idempotent."""
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        for table in Base.metadata.tables:
            conn.exec_driver_sql(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def ensure_admin() -> None:
    """Create the first admin from ADMIN_EMAIL / ADMIN_PASSWORD if it doesn't exist yet.

    This is the only way an admin is created besides promotion by another admin
    (public sign-up can't, and Render's free plan has no shell, so this runs on startup).
    """
    settings = get_settings()
    if not (settings.admin_email and settings.admin_password):
        log.warning("ADMIN_EMAIL / ADMIN_PASSWORD not set; no admin account was created.")
        return
    with SessionLocal() as db:
        if user_service.get_by_email(db, settings.admin_email):
            return
        user_service.create_user(
            db, email=settings.admin_email, name=settings.admin_name, password=settings.admin_password, role="admin"
        )
        log.info("Created admin account %s", settings.admin_email)
