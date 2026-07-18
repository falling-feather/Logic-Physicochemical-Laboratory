"""Same-origin local preview surface for the Astra website.

This module deliberately mounts only reviewed public directories.  It is a
development/acceptance entrypoint, not the staging or production service
bundle defined by ``deploy.ps1``.
"""

import os
import re
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from app.main import create_app


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PUBLIC_MOUNTS = (
    ("/pages", "pages"),
    ("/shared", "shared"),
    ("/UI", "UI"),
    ("/codevis", "codevis"),
)
LOCAL_PREVIEW_HEAD = """    <meta name="astra-local-preview" content="same-origin">
    <script>
        globalThis.ASTRA_LOCAL_PREVIEW_SAME_ORIGIN = true;
        try { globalThis.localStorage.removeItem('astra-api-base'); } catch (_) {}
    </script>
"""


def create_local_preview_app(
    project_root: Path | None = None,
    instance_id: str | None = None,
) -> FastAPI:
    root = (project_root or PROJECT_ROOT).resolve()
    preview_instance_id = (
        instance_id
        or os.environ.get("ASTRA_LOCAL_PREVIEW_INSTANCE_ID")
        or "unmanaged-local-preview"
    ).strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", preview_instance_id):
        raise RuntimeError("ASTRA_LOCAL_PREVIEW_INSTANCE_ID is invalid")
    preview_headers = {
        "Cache-Control": "no-cache",
        "X-Astra-Local-Preview": "1",
        "X-Astra-Local-Instance": preview_instance_id,
    }
    index_source = (root / "index.html").read_text(encoding="utf-8")
    if "</head>" not in index_source:
        raise RuntimeError("index.html is missing its closing head element")
    local_index_source = index_source.replace("</head>", f"{LOCAL_PREVIEW_HEAD}</head>", 1)
    application = create_app()

    @application.get("/", include_in_schema=False)
    @application.get("/index.html", include_in_schema=False)
    def local_index(request: Request) -> Response:
        query_items = list(request.query_params.multi_items())
        same_origin_items = [(key, value) for key, value in query_items if key != "apiBase"]
        if len(same_origin_items) != len(query_items):
            target = request.url.path
            if same_origin_items:
                target = f"{target}?{urlencode(same_origin_items)}"
            return RedirectResponse(
                target,
                status_code=307,
                headers=preview_headers,
            )
        return HTMLResponse(
            content=local_index_source,
            headers=preview_headers,
        )

    @application.get("/sw.js", include_in_schema=False)
    def local_service_worker() -> FileResponse:
        return FileResponse(
            root / "sw.js",
            media_type="application/javascript",
            headers={
                "Cache-Control": "no-cache",
                "Service-Worker-Allowed": "/",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @application.get("/LICENSE.md", include_in_schema=False)
    def local_license() -> FileResponse:
        return FileResponse(root / "LICENSE.md", media_type="text/markdown")

    for route, relative_directory in PUBLIC_MOUNTS:
        directory = root / relative_directory
        if not directory.is_dir():
            raise RuntimeError(f"Required public directory is missing: {relative_directory}")
        application.mount(
            route,
            StaticFiles(directory=directory, html=relative_directory == "codevis", follow_symlink=False),
            name=f"local-preview-{relative_directory.lower()}",
        )

    return application


app = create_local_preview_app()
