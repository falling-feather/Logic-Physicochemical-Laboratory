from fastapi import HTTPException


def require_trimmed_text(value: str, detail: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise HTTPException(status_code=422, detail=detail)
    return stripped
