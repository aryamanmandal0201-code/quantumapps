from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_admin
from ..models import Task, User
from ..schemas import AdminTaskOut, AdminUserOut, RoleUpdate, Status, UserOut
from ..services import tasks as task_service
from ..services import users as user_service

# require_admin runs for every route in this router: normal users get 403 even if they call the API directly.
router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/users", response_model=list[AdminUserOut])
def list_users(db: Session = Depends(get_db)) -> list[AdminUserOut]:
    return [
        AdminUserOut(**UserOut.model_validate(user).model_dump(), open_tasks=open_, done_tasks=done)
        for user, open_, done in user_service.list_users_with_task_counts(db)
    ]


@router.patch("/users/{user_id}/role", response_model=UserOut)
def change_role(
    user_id: int, data: RoleUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> User:
    try:
        return user_service.change_role(db, actor=admin, user_id=user_id, role=data.role)
    except user_service.CannotChangeOwnRole:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You can't change your own role.")
    except user_service.UserNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")


@router.get("/tasks", response_model=list[AdminTaskOut])
def list_all_tasks(
    user_id: int | None = None, status_filter: Status | None = None, db: Session = Depends(get_db)
) -> list[Task]:
    return task_service.list_tasks(db, owner_id=user_id, status=status_filter)
