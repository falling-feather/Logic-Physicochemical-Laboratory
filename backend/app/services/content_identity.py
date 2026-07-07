from __future__ import annotations

from typing import Any

from app.schemas.content import ContentPage


def content_stable_identity_errors(page_schema: ContentPage) -> list[str]:
    errors: list[str] = []
    for index, section in enumerate(page_schema.sections):
        path = f"sections[{index}]"
        if section.sectionId is None:
            errors.append(f"{path}.sectionId is required")
        section_props = section.props if isinstance(section.props, dict) else {}
        for legacy_key in ("sectionId", "id"):
            legacy_value = section_props.get(legacy_key)
            if legacy_value is not None and section.sectionId is not None and str(legacy_value) != section.sectionId:
                errors.append(f"{path}.props.{legacy_key} conflicts with {path}.sectionId")
    for index, source in enumerate(page_schema.sources):
        if source.sourceId is None:
            errors.append(f"sources[{index}].sourceId is required")
    return errors


def content_stable_identity_snapshot(errors: list[str]) -> dict[str, Any]:
    return {
        "status": "valid" if not errors else "invalid",
        "error_count": len(errors),
        "errors": errors,
    }
