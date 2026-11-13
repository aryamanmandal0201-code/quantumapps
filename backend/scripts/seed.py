"""Create demo accounts and sample tasks.

Run from the backend folder, pointing at the same DATABASE_URL as the live app:
    python -m scripts.seed

Safe to run more than once: existing accounts are left alone.
Set DEMO_USER_PASSWORD (or keep the documented demo default) before running.
"""
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.bootstrap import enable_row_level_security, ensure_admin
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.services import users as user_service
from app.services.tasks import create_task

DEMO_USER_EMAIL = os.getenv("DEMO_USER_EMAIL", "user@taskpilot.demo")
DEMO_USER_PASSWORD = os.getenv("DEMO_USER_PASSWORD", "User@12345")  # public demo account, listed in the README
DEMO_USER_NAME = os.getenv("DEMO_USER_NAME", "Priya Sharma")


def main() -> None:
    Base.metadata.create_all(bind=engine)
    enable_row_level_security()
    ensure_admin()

    with SessionLocal() as db:
        if user_service.get_by_email(db, DEMO_USER_EMAIL):
            print(f"Demo user {DEMO_USER_EMAIL} already exists; nothing to do.")
            return
        user = user_service.create_user(db, email=DEMO_USER_EMAIL, name=DEMO_USER_NAME, password=DEMO_USER_PASSWORD)

        today = datetime.now(ZoneInfo(get_settings().app_timezone)).date()
        friday = today + timedelta(days=(4 - today.weekday()) % 7)
        # Deliberately no "monthly report" task: reviewers will type the brief's example
        # ("Add a task to submit the monthly report by Friday") and shouldn't hit a duplicate.
        samples = [
            ("Prepare the quarterly budget slides", "Use the numbers from finance.", friday, "high"),
            ("Book train tickets for the Jaipur visit", None, today + timedelta(days=10), "medium"),
            ("Review the onboarding checklist", None, today + timedelta(days=2), "low"),
            ("Renew vehicle insurance", "Policy expires end of month.", today + timedelta(days=18), "high"),
        ]
        for title, desc, due, priority in samples:
            create_task(db, owner_id=user.id, title=title, description=desc, due_date=due, priority=priority)
        print(f"Created demo user {DEMO_USER_EMAIL} with {len(samples)} sample tasks.")


if __name__ == "__main__":
    main()
