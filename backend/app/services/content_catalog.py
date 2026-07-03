from app.schemas.content import ContentPage


ENERGY_CONSERVATION_PAGE = ContentPage(
    slug="physics/energy-conservation",
    galaxy="englab",
    subject="physics",
    title="机械能守恒",
    layout="experiment-page",
    status="draft",
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


_PAGES = {
    ENERGY_CONSERVATION_PAGE.slug: ENERGY_CONSERVATION_PAGE,
}


def get_page_schema(slug: str) -> ContentPage | None:
    return _PAGES.get(slug.strip("/"))


def list_page_summaries() -> list[dict]:
    return [
        {
            "slug": page.slug,
            "title": page.title,
            "galaxy": page.galaxy,
            "subject": page.subject,
            "layout": page.layout,
            "status": page.status,
            "version": page.version,
        }
        for page in sorted(_PAGES.values(), key=lambda item: item.slug)
    ]

