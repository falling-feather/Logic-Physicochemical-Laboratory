from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.content import ContentPage
from app.services.content_catalog import get_page_schema, list_page_summaries


router = APIRouter()


@router.get("/pages", response_model=list[dict])
def list_content_pages(db: Session = Depends(get_db)) -> list[dict]:
    return list_page_summaries(db)


@router.get("/pages/{slug:path}", response_model=ContentPage)
def read_content_page(slug: str, db: Session = Depends(get_db)) -> ContentPage:
    page = get_page_schema(db, slug)
    if page is None:
        raise HTTPException(status_code=404, detail="Content page not found")
    return page
