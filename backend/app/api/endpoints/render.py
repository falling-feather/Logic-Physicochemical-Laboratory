from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.content import ContentPage
from app.services.content_catalog import get_page_schema


router = APIRouter()


@router.get("/page/{slug:path}", response_model=ContentPage)
def render_page(slug: str, db: Session = Depends(get_db)) -> ContentPage:
    page = get_page_schema(db, slug)
    if page is None:
        raise HTTPException(status_code=404, detail="Renderable page not found")
    return page
