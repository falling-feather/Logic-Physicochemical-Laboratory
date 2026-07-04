import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ContentPageRecord, ContentPageVersion
from app.schemas.content import ContentPage


ENERGY_CONSERVATION_PAGE = ContentPage(
    slug="physics/energy-conservation",
    galaxy="englab",
    subject="physics",
    title="机械能守恒",
    layout="experiment-page",
    status="published",
    version="2026.07-v6.5-schema.1",
    summary="以物理能量守恒实验为后端内容协议第一试点，保留现有实验交互并由后端提供页面结构。",
    sections=[
        {
            "type": "hero",
            "title": "机械能守恒",
            "summary": "观察动能、势能和耗散之间的转换，理解机械能守恒的适用条件。",
        },
        {
            "type": "learning-task",
            "title": "观察任务",
            "summary": "打开耗散后，比较机械能和能量总量的变化趋势。",
            "props": {
                "tier": "核心",
                "scope": "基础主线",
                "concepts": ["动能", "势能", "非保守力做功", "能量守恒"],
            },
        },
        {
            "type": "experiment",
            "title": "交互实验",
            "experimentId": "energy-conservation",
            "props": {
                "moduleSelectorId": "energy-conservation",
                "scriptPath": "pages/physics/energy-conservation.js",
                "defaultFriction": 0.1,
                "fallbackHash": "#physics/energy-conservation",
            },
        },
        {
            "type": "assessment",
            "title": "章节小测",
            "questionSetId": "energy-conservation",
            "summary": "沿用现有工科试验室题库，后续迁入数据库题组。",
        },
        {
            "type": "source-list",
            "title": "参考资料",
            "summary": "首批 schema 保留来源引用，后续进入内容审核与来源索引模型。",
        },
    ],
    courseUnit={
        "courseId": "englab-physics-foundation",
        "unitId": "physics-energy-conservation",
        "order": 10,
        "title": "机械能守恒",
    },
    sources=[
        {
            "label": "OpenStax College Physics 2e · Conservation of Energy",
            "url": "https://openstax.org/books/college-physics-2e/pages/7-introduction-to-work-energy-and-energy-resources",
        }
    ],
)


_SEED_PAGES = {
    ENERGY_CONSERVATION_PAGE.slug: ENERGY_CONSERVATION_PAGE,
}


def ensure_seed_pages(db: Session) -> None:
    for page in _SEED_PAGES.values():
        page_payload = page.model_dump(mode="json")
        schema_hash = _schema_hash(page_payload)
        existing = db.scalar(select(ContentPageRecord).where(ContentPageRecord.slug == page.slug))
        if existing is None:
            db.add(
                ContentPageRecord(
                    slug=page.slug,
                    status=page.status,
                    version=page.version,
                    schema_json=page_payload,
                    schema_hash=schema_hash,
                )
            )
        elif existing.version != page.version and not _has_published_versions(db, page.slug):
            existing.status = page.status
            existing.version = page.version
            existing.schema_json = page_payload
            existing.schema_hash = schema_hash
        elif existing.schema_hash is None:
            existing.schema_hash = schema_hash
    db.commit()


def get_page_schema(db: Session, slug: str) -> ContentPage | None:
    record = db.scalar(
        select(ContentPageRecord).where(
            ContentPageRecord.slug == slug.strip("/"),
            ContentPageRecord.status == "published",
        )
    )
    if record is None:
        return None
    return ContentPage.model_validate(record.schema_json)


def list_page_summaries(db: Session) -> list[dict]:
    records = db.scalars(
        select(ContentPageRecord).where(ContentPageRecord.status == "published").order_by(ContentPageRecord.slug)
    ).all()
    return [
        {
            "slug": page.slug,
            "title": page.schema_json.get("title", page.slug),
            "galaxy": page.schema_json.get("galaxy", ""),
            "subject": page.schema_json.get("subject", ""),
            "layout": page.schema_json.get("layout", ""),
            "status": page.status,
            "version": page.version,
        }
        for page in records
    ]


def _has_published_versions(db: Session, slug: str) -> bool:
    version_id = db.scalar(select(ContentPageVersion.id).where(ContentPageVersion.slug == slug).limit(1))
    return version_id is not None


def _schema_hash(payload: dict) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
