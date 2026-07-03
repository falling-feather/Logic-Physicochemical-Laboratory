from fastapi import APIRouter, HTTPException

from app.schemas.content import ContentPage
from app.services.content_catalog import get_page_schema


router = APIRouter()


@router.get("/page/{slug:path}", response_model=ContentPage)
def render_page(slug: str) -> ContentPage:
    page = get_page_schema(slug)
    if page is None:
        raise HTTPException(status_code=404, detail="Renderable page not found")
    return page

