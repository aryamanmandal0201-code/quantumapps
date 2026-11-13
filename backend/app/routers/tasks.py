from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Task, User
from ..schemas import Status, TaskIn, TaskOut, TaskUpdate
from ..services import tasks as task_service

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

NOT_FOUND = "Task not found."


def _own_task_or_404(db: Session, user: User, task_id: int) -> Task:
    task = task_service.get_owned_task(db, user.id, task_id)
    if task is None:
        # Same answer whether the task doesn't exist or belongs to someone else, so ids can't be probed.
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return task


@router.get("", response_model=list[TaskOut])
def list_my_tasks(
    status_filter: Status | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Task]:
    return task_service.list_tasks(db, owner_id=user.id, status=status_filter)


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_my_task(data: TaskIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Task:
    return task_service.create_task(db, owner_id=user.id, **data.model_dump())


@router.patch("/{task_id}", response_model=TaskOut)
def update_my_task(
    task_id: int, data: TaskUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Task:
    task = _own_task_or_404(db, user, task_id)
    return task_service.update_task(db, task, data.model_dump(exclude_unset=True))


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_task(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    task_service.delete_task(db, _own_task_or_404(db, user, task_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
