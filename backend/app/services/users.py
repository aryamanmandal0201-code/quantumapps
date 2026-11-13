"""User accounts: creation, login checks and roles.

No HTTP here. Routers translate these exceptions into status codes.
"""
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Role, Task, User
from ..security import hash_password, verify_password


class EmailTaken(Exception):
    """An account with this email already exists."""


class UserNotFound(Exception):
    """No user with that id."""


class CannotChangeOwnRole(Exception):
    """Admins can't demote (or re-promote) themselves, so there is always at least one admin."""


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == normalize_email(email)))


def create_user(db: Session, email: str, name: str, password: str, role: Role = "user") -> User:
    """Public sign-up never passes `role`, so it is always 'user'. Only the admin bootstrap passes 'admin'."""
    if get_by_email(db, email):
        raise EmailTaken(email)
    user = User(email=normalize_email(email), name=name.strip(), hashed_password=hash_password(password), role=role)
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:  # two sign-ups with the same email at the same moment
        db.rollback()
        raise EmailTaken(email) from exc
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = get_by_email(db, email)
    if user is None or not verify_password(password, user.hashed_password):
        return None
    return user


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at)))


def list_users_with_task_counts(db: Session) -> list[tuple[User, int, int]]:
    """Every user with (open task count, done task count), in one query."""
    open_count = func.coalesce(func.sum(case((Task.status == "todo", 1), else_=0)), 0)
    done_count = func.coalesce(func.sum(case((Task.status == "done", 1), else_=0)), 0)
    rows = db.execute(
        select(User, open_count, done_count)
        .outerjoin(Task, Task.owner_id == User.id)
        .group_by(User.id)
        .order_by(User.created_at)
    ).all()
    return [(user, int(open_), int(done)) for user, open_, done in rows]


def change_role(db: Session, actor: User, user_id: int, role: Role) -> User:
    if user_id == actor.id:
        raise CannotChangeOwnRole()
    user = db.get(User, user_id)
    if user is None:
        raise UserNotFound(user_id)
    user.role = role
    db.commit()
    db.refresh(user)
    return user
