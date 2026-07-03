from fastapi import APIRouter, HTTPException

from app.schemas.content import ContentPage
from app.services.content_catalog import get_page_schema, list_page_summaries


router = APIRouter()


@router.get("/pages", response_model=list[dict])
def list_content_pages() -> list[dict]:
    return list_page_summaries()


@router.get("/pages/{slug:path}", response_model=ContentPage)
def read_content_page(slug: str) -> ContentPage:
    page = get_page_schema(slug)
    if page is None:
        raise HTTPException(status_code=404, detail="Content page not found")
    return page

