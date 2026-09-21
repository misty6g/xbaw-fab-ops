"""Tool health board."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import ToolOut
from app.services.queries import tool_board

router = APIRouter()


@router.get("/tools", response_model=list[ToolOut])
def get_tools(
    hours: int = Query(default=24, ge=1, le=24 * 30),
    db: Session = Depends(get_db),
) -> list[ToolOut]:
    return tool_board(db, hours)
