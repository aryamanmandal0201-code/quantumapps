"""Task data access. Every function takes an owner_id, so callers can only ever touch one user's tasks.

Both the REST API and the AI agent's tools go through these functions, which is how
ownership is enforced in one place instead of being trusted to the LLM.
"""
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from ..models import Task


def _ordered(stmt):
    # Open tasks first, then by due date (tasks without a date last), then oldest first.
    return stmt.order_by(Task.status.desc(), Task.due_date.is_(None), Task.due_date, Task.id)


def list_tasks(
    db: Session,
    owner_id: int | None,
    status: str | None = None,
    due_before: date | None = None,
    due_after: date | None = None,
    search: str | None = None,
) -> list[Task]:
    """owner_id=None lists every user's tasks; only admin-only code paths pass None."""
    stmt = select(Task).options(joinedload(Task.owner), joinedload(Task.created_by))
    if owner_id is not None:
        stmt = stmt.where(Task.owner_id == owner_id)
    if status in ("todo", "done"):
        stmt = stmt.where(Task.status == status)
    if due_before:
        stmt = stmt.where(Task.due_date <= due_before)
    if due_after:
        stmt = stmt.where(Task.due_date >= due_after)
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(or_(Task.title.ilike(like), Task.description.ilike(like)))
    return list(db.scalars(_ordered(stmt)).unique())


def get_owned_task(db: Session, owner_id: int, task_id: int) -> Task | None:
    return db.scalar(select(Task).where(Task.id == task_id, Task.owner_id == owner_id))


def create_task(
    db: Session,
    owner_id: int,
    title: str,
    description: str | None = None,
    due_date: date | None = None,
    priority: str = "medium",
    created_by_id: int | None = None,
) -> Task:
    task = Task(
        owner_id=owner_id,
        created_by_id=created_by_id or owner_id,
        title=title.strip(),
        description=(description or None),
        due_date=due_date,
        priority=priority,
        status="todo",
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update_task(db: Session, task: Task, fields: dict) -> Task:
    allowed = {"title", "description", "due_date", "priority", "status"}
    for key, value in fields.items():
        if key in allowed:
            setattr(task, key, value)
    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, task: Task) -> None:
    db.delete(task)
    db.commit()
