from fastapi import APIRouter, Depends

from app.api.deps.auth import get_current_user
from app.models import User
from app.schemas.auth import UserPublic


router = APIRouter()


@router.get("/me", response_model=UserPublic)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user
