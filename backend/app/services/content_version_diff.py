import re
from typing import Any

from app.schemas.admin import (
    AdminContentPageVersionDiffItem,
    AdminContentPageVersionSemanticDiff,
    AdminContentPageVersionSemanticFieldChange,
    AdminContentPageVersionSemanticSectionChange,
    AdminContentPageVersionSemanticSourceChange,
)


_DIFF_MISSING = object()
_CONTENT_METADATA_FIELDS = ("slug", "galaxy", "subject", "title", "layout", "status", "version", "summary")
_CONTENT_SECTION_FIELDS = ("sectionId", "type", "title", "summary", "experimentId", "questionSetId")
_CONTENT_COURSE_UNIT_FIELDS = ("courseId", "unitId", "order", "title")
_CONTENT_SOURCE_FIELDS = ("sourceId", "label", "url")
_CONTENT_DIFF_SENSITIVE_FIELD_TOKENS = (
    "authorization",
    "apikey",
    "api_key",
    "accesskey",
    "access_key",
    "credential",
    "crossorigin",
    "integrity",
    "password",
    "privatekey",
    "private_key",
    "sandbox",
    "script",
    "secret",
    "token",
)


def build_content_schema_diff(before: Any, after: Any, path: str = "$") -> list[AdminContentPageVersionDiffItem]:
    if isinstance(before, dict) and isinstance(after, dict):
        changes: list[AdminContentPageVersionDiffItem] = []
        for key in sorted(set(before) | set(after)):
            before_value = before.get(key, _DIFF_MISSING)
            after_value = after.get(key, _DIFF_MISSING)
            changes.extend(build_content_schema_diff(before_value, after_value, f"{path}.{key}"))
        return changes

    if isinstance(before, list) and isinstance(after, list):
        changes = []
        for index in range(max(len(before), len(after))):
            before_value = before[index] if index < len(before) else _DIFF_MISSING
            after_value = after[index] if index < len(after) else _DIFF_MISSING
            changes.extend(build_content_schema_diff(before_value, after_value, f"{path}[{index}]"))
        return changes

    if before != after:
        return [
            AdminContentPageVersionDiffItem(
                path=path,
                before=_diff_value(before, path),
                after=_diff_value(after, path),
            )
        ]
    return []


def build_content_schema_semantic_diff(before: Any, after: Any) -> AdminContentPageVersionSemanticDiff:
    before_schema = before if isinstance(before, dict) else {}
    after_schema = after if isinstance(after, dict) else {}
    metadata_changes = _semantic_field_changes(before_schema, after_schema, _CONTENT_METADATA_FIELDS)
    course_unit_changes = _semantic_course_unit_changes(
        before_schema.get("courseUnit"),
        after_schema.get("courseUnit"),
    )
    section_changes = _semantic_section_changes(
        before_schema.get("sections"),
        after_schema.get("sections"),
    )
    source_changes = _semantic_source_changes(
        before_schema.get("sources"),
        after_schema.get("sources"),
    )
    summary = {
        "metadata": len(metadata_changes),
        "course_unit": len(course_unit_changes),
        "sections_added": _semantic_action_count(section_changes, "added"),
        "sections_removed": _semantic_action_count(section_changes, "removed"),
        "sections_modified": _semantic_action_count(section_changes, "modified"),
        "sections_moved": sum(1 for change in section_changes if change.moved),
        "sources_added": _semantic_action_count(source_changes, "added"),
        "sources_removed": _semantic_action_count(source_changes, "removed"),
        "sources_modified": _semantic_action_count(source_changes, "modified"),
        "sources_moved": sum(1 for change in source_changes if change.moved),
    }
    summary["semantic_changes"] = (
        len(metadata_changes)
        + len(course_unit_changes)
        + len(section_changes)
        + len(source_changes)
    )
    return AdminContentPageVersionSemanticDiff(
        metadata_changes=metadata_changes,
        course_unit_changes=course_unit_changes,
        section_changes=section_changes,
        source_changes=source_changes,
        summary=summary,
    )


def _semantic_section_changes(before: Any, after: Any) -> list[AdminContentPageVersionSemanticSectionChange]:
    before_entries = _semantic_indexed_entries(before, _section_identity)
    after_entries = _semantic_indexed_entries(after, _section_identity)
    changes: list[AdminContentPageVersionSemanticSectionChange] = []
    for key in sorted(set(before_entries) | set(after_entries)):
        before_entry = before_entries.get(key)
        after_entry = after_entries.get(key)
        before_item = before_entry["item"] if before_entry is not None else None
        after_item = after_entry["item"] if after_entry is not None else None
        if before_entry is None:
            changes.append(
                AdminContentPageVersionSemanticSectionChange(
                    action="added",
                    key=key,
                    index_after=after_entry["index"] if after_entry is not None else None,
                    section_id_after=_semantic_stable_id(after_item, "sectionId"),
                    type_after=_semantic_text(after_item, "type"),
                    title_after=_semantic_text(after_item, "title"),
                )
            )
            continue
        if after_entry is None:
            changes.append(
                AdminContentPageVersionSemanticSectionChange(
                    action="removed",
                    key=key,
                    index_before=before_entry["index"],
                    section_id_before=_semantic_stable_id(before_item, "sectionId"),
                    type_before=_semantic_text(before_item, "type"),
                    title_before=_semantic_text(before_item, "title"),
                )
            )
            continue

        field_changes = _semantic_field_changes(before_item, after_item, _CONTENT_SECTION_FIELDS)
        prop_changes = _semantic_map_changes(
            _semantic_mapping(before_item.get("props") if isinstance(before_item, dict) else None),
            _semantic_mapping(after_item.get("props") if isinstance(after_item, dict) else None),
            prefix="props.",
        )
        moved = before_entry["index"] != after_entry["index"]
        if field_changes or prop_changes or moved:
            changes.append(
                AdminContentPageVersionSemanticSectionChange(
                    action="modified" if field_changes or prop_changes else "moved",
                    key=key,
                    index_before=before_entry["index"],
                    index_after=after_entry["index"],
                    section_id_before=_semantic_stable_id(before_item, "sectionId"),
                    section_id_after=_semantic_stable_id(after_item, "sectionId"),
                    type_before=_semantic_text(before_item, "type"),
                    type_after=_semantic_text(after_item, "type"),
                    title_before=_semantic_text(before_item, "title"),
                    title_after=_semantic_text(after_item, "title"),
                    moved=moved,
                    field_changes=field_changes,
                    prop_changes=prop_changes,
                )
            )
    return changes


def _semantic_source_changes(before: Any, after: Any) -> list[AdminContentPageVersionSemanticSourceChange]:
    before_entries = _semantic_indexed_entries(before, _source_identity)
    after_entries = _semantic_indexed_entries(after, _source_identity)
    changes: list[AdminContentPageVersionSemanticSourceChange] = []
    for key in sorted(set(before_entries) | set(after_entries)):
        before_entry = before_entries.get(key)
        after_entry = after_entries.get(key)
        before_item = before_entry["item"] if before_entry is not None else None
        after_item = after_entry["item"] if after_entry is not None else None
        if before_entry is None:
            changes.append(
                AdminContentPageVersionSemanticSourceChange(
                    action="added",
                    key=key,
                    index_after=after_entry["index"] if after_entry is not None else None,
                    source_id_after=_semantic_stable_id(after_item, "sourceId"),
                    label_after=_semantic_text(after_item, "label"),
                    url_after=_semantic_text(after_item, "url"),
                )
            )
            continue
        if after_entry is None:
            changes.append(
                AdminContentPageVersionSemanticSourceChange(
                    action="removed",
                    key=key,
                    index_before=before_entry["index"],
                    source_id_before=_semantic_stable_id(before_item, "sourceId"),
                    label_before=_semantic_text(before_item, "label"),
                    url_before=_semantic_text(before_item, "url"),
                )
            )
            continue

        field_changes = _semantic_field_changes(before_item, after_item, _CONTENT_SOURCE_FIELDS)
        moved = before_entry["index"] != after_entry["index"]
        if field_changes or moved:
            changes.append(
                AdminContentPageVersionSemanticSourceChange(
                    action="modified" if field_changes else "moved",
                    key=key,
                    index_before=before_entry["index"],
                    index_after=after_entry["index"],
                    source_id_before=_semantic_stable_id(before_item, "sourceId"),
                    source_id_after=_semantic_stable_id(after_item, "sourceId"),
                    label_before=_semantic_text(before_item, "label"),
                    label_after=_semantic_text(after_item, "label"),
                    url_before=_semantic_text(before_item, "url"),
                    url_after=_semantic_text(after_item, "url"),
                    moved=moved,
                    field_changes=field_changes,
                )
            )
    return changes


def _semantic_course_unit_changes(before: Any, after: Any) -> list[AdminContentPageVersionSemanticFieldChange]:
    before_map = _semantic_mapping(before)
    after_map = _semantic_mapping(after)
    return _semantic_field_changes(before_map, after_map, _CONTENT_COURSE_UNIT_FIELDS)


def _semantic_field_changes(
    before: Any,
    after: Any,
    fields: tuple[str, ...],
) -> list[AdminContentPageVersionSemanticFieldChange]:
    before_map = _semantic_mapping(before)
    after_map = _semantic_mapping(after)
    changes: list[AdminContentPageVersionSemanticFieldChange] = []
    for field in fields:
        before_value = before_map.get(field)
        after_value = after_map.get(field)
        if before_value != after_value:
            changes.append(
                AdminContentPageVersionSemanticFieldChange(
                    field=field,
                    before=_diff_value(before_value, field),
                    after=_diff_value(after_value, field),
                )
            )
    return changes


def _semantic_map_changes(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    prefix: str = "",
) -> list[AdminContentPageVersionSemanticFieldChange]:
    changes: list[AdminContentPageVersionSemanticFieldChange] = []
    for field in sorted(set(before) | set(after)):
        before_value = before.get(field)
        after_value = after.get(field)
        if before_value != after_value:
            changes.append(
                AdminContentPageVersionSemanticFieldChange(
                    field=f"{prefix}{field}",
                    before=_diff_value(before_value, f"{prefix}{field}"),
                    after=_diff_value(after_value, f"{prefix}{field}"),
                )
            )
    return changes


def _semantic_indexed_entries(values: Any, identity_fn) -> dict[str, dict[str, Any]]:
    if not isinstance(values, list):
        return {}
    occurrences: dict[str, int] = {}
    entries: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(values):
        identity = identity_fn(item, index)
        occurrences[identity] = occurrences.get(identity, 0) + 1
        key = identity if occurrences[identity] == 1 else f"{identity}#{occurrences[identity]}"
        entries[key] = {"item": item, "index": index}
    return entries


def _section_identity(item: Any, index: int) -> str:
    if not isinstance(item, dict):
        return f"section:index:{index}"
    props = _semantic_mapping(item.get("props"))
    explicit_id = item.get("sectionId") or item.get("id") or props.get("sectionId") or props.get("id")
    if explicit_id:
        return f"section:id:{_identity_token(explicit_id)}"
    if item.get("experimentId"):
        return f"section:experiment:{_identity_token(item['experimentId'])}"
    if item.get("questionSetId"):
        return f"section:question-set:{_identity_token(item['questionSetId'])}"
    section_type = item.get("type")
    title = item.get("title")
    if section_type and title:
        return f"section:{_identity_token(section_type)}:{_identity_token(title)}"
    if section_type:
        return f"section:type:{_identity_token(section_type)}"
    return f"section:index:{index}"


def _source_identity(item: Any, index: int) -> str:
    if not isinstance(item, dict):
        return f"source:index:{index}"
    if item.get("sourceId"):
        return f"source:id:{_identity_token(item['sourceId'])}"
    if item.get("label"):
        return f"source:label:{_identity_token(item['label'])}"
    if item.get("url"):
        return f"source:url:{_identity_token(item['url'])}"
    return f"source:index:{index}"


def _identity_token(value: Any) -> str:
    return str(value).strip().lower()


def _semantic_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _semantic_text(value: Any, field: str) -> str | None:
    if not isinstance(value, dict):
        return None
    field_value = value.get(field)
    return str(field_value) if field_value is not None else None


def _semantic_stable_id(value: Any, field: str) -> str | None:
    return _semantic_text(value, field)


def _semantic_action_count(changes: list[Any], action: str) -> int:
    return sum(1 for change in changes if change.action == action)


def _diff_value(value: Any, path: str = "$") -> Any:
    if value is _DIFF_MISSING:
        return None
    return _sanitize_diff_value(value, path)


def _sanitize_diff_value(value: Any, path: str) -> Any:
    if value is None:
        return None
    if _is_sensitive_diff_path(path):
        return _redacted_diff_value(value)
    if isinstance(value, dict):
        return {key: _sanitize_diff_value(item, f"{path}.{key}") for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_diff_value(item, f"{path}[{index}]") for index, item in enumerate(value)]
    return value


def _is_sensitive_diff_path(path: str) -> bool:
    return any(_is_sensitive_diff_segment(segment) for segment in _diff_path_segments(path))


def _diff_path_segments(path: str) -> list[str]:
    return [
        segment
        for segment in path.replace("[", ".").replace("]", "").replace("$", "").split(".")
        if segment and not segment.isdigit()
    ]


def _is_sensitive_diff_segment(segment: str) -> bool:
    normalized = segment.replace("_", "").replace("-", "").lower()
    words = _diff_segment_words(segment)
    if normalized in {"authorization", "cookie", "credential", "credentials", "crossorigin", "integrity", "password"}:
        return True
    if normalized == "sandbox" or normalized.endswith("sandbox"):
        return True
    if normalized.startswith("script") or "script" in words:
        return True
    return any(
        token.replace("_", "") in normalized
        for token in _CONTENT_DIFF_SENSITIVE_FIELD_TOKENS
        if token not in {"script", "sandbox", "integrity", "crossorigin"}
    )


def _diff_segment_words(segment: str) -> set[str]:
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", segment.replace("_", " ").replace("-", " "))
    return {word.lower() for word in spaced.split() if word}


def _redacted_diff_value(value: Any) -> dict[str, Any]:
    preview: dict[str, Any] = {
        "redacted": True,
        "reason": "content_diff_sensitive_field",
        "value_type": type(value).__name__,
    }
    if isinstance(value, (str, bytes, list, dict, tuple, set)):
        preview["length"] = len(value)
    return preview
