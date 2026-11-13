import groq
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..agent.agent import AgentError, run_agent
from ..database import get_db
from ..deps import get_current_user, get_llm_client
from ..models import ChatMessage, User
from ..schemas import ChatIn, ChatMessageOut, ChatOut
from ..services import chat as chat_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatOut)
def chat(
    data: ChatIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm: groq.Groq = Depends(get_llm_client),
) -> ChatOut:
    history = chat_service.recent_history_for_model(db, user.id)
    try:
        result = run_agent(db, user, data.message, history, client=llm)
    except AgentError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))
    chat_service.save_exchange(db, user.id, data.message, result["reply"], result["tool_calls"])
    return ChatOut(**result)


@router.get("/history", response_model=list[ChatMessageOut])
def history(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ChatMessage]:
    return chat_service.list_messages(db, user.id)


@router.delete("/history", status_code=status.HTTP_204_NO_CONTENT)
def clear_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    chat_service.clear_history(db, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
