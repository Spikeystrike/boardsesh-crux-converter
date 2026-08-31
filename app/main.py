import asyncio
import json
from pathlib import Path
import re
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.requests import Request

from app.boardsesh import BoardSeshError, SnapshotService, read_catalog
from app.config import MOONBOARD_LAYOUTS, Settings
from app.converter import ConversionError, ConversionOptions, convert_catalog
from app.mapping import (
    MappingError,
    fetch_bridge_mapping_payload,
    mapping_summaries,
    select_mapping,
)


APP_DIR = Path(__file__).resolve().parent
PROJECT_DIR = APP_DIR.parent
settings = Settings.from_environment()
snapshot_service = SnapshotService(
    settings.manifest_url,
    settings.cache_dir,
    settings.download_limit_bytes,
    settings.request_timeout_seconds,
)

app = FastAPI(
    title="BoardSesh to CRUX Converter",
    version="0.1.0",
)
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")


class BridgeMappingsRequest(BaseModel):
    bridge_url: str = Field(min_length=1)
    wall_id: int = Field(gt=0)


class ConvertRequest(BaseModel):
    bridge_url: str | None = None
    wall_id: int | None = Field(default=None, gt=0)
    mapping_id: str | None = None
    mapping_payload: Any | None = None
    angle: int | None = Field(default=None, ge=0, le=90)
    grade_system: Literal["font", "v_scale", "boardsesh"] = "font"
    foot_rules: Literal[
        "feet_follow_hands",
        "any_feet",
        "campus",
        "feet_follow_hands_open_kicker",
        "only_marked_feet",
    ] = "feet_follow_hands"


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "layouts": MOONBOARD_LAYOUTS,
            "manifest_url": settings.manifest_url,
        },
    )


@app.get("/healthz")
async def health():
    return {"status": "ok", "version": app.version}


@app.get("/schema/crux-import-v1.schema.json")
async def schema():
    return FileResponse(
        PROJECT_DIR / "schema" / "crux-import-v1.schema.json",
        media_type="application/schema+json",
    )


@app.post("/api/bridge/mappings")
async def bridge_mappings(payload: BridgeMappingsRequest):
    try:
        mappings = await fetch_bridge_mapping_payload(
            payload.bridge_url,
            payload.wall_id,
            timeout_seconds=settings.request_timeout_seconds,
        )
        return {"mappings": mapping_summaries(mappings)}
    except MappingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def _selected_mapping(payload: ConvertRequest):
    if payload.mapping_payload is not None:
        return select_mapping(payload.mapping_payload, payload.mapping_id)
    if not payload.bridge_url or payload.wall_id is None:
        raise MappingError(
            "Provide either mapping JSON or a bridge URL and wall ID"
        )
    bridge_payload = await fetch_bridge_mapping_payload(
        payload.bridge_url,
        payload.wall_id,
        timeout_seconds=settings.request_timeout_seconds,
    )
    return select_mapping(bridge_payload, payload.mapping_id)


def _download_name(mapping_name: str, layout_id: int) -> str:
    safe_name = re.sub(r"[^0-9A-Za-z_.-]+", "-", mapping_name).strip("-")
    return f"crux-moonboard-{safe_name or layout_id}.json"


@app.post("/api/convert")
async def convert(payload: ConvertRequest):
    try:
        mapping = await _selected_mapping(payload)
        snapshot_path, snapshot_entry = await snapshot_service.get_snapshot(
            mapping.layout_id
        )
        climbs = await asyncio.to_thread(
            read_catalog,
            snapshot_path,
            mapping.layout_id,
            payload.angle,
        )
        document = convert_catalog(
            climbs,
            mapping,
            snapshot_entry,
            settings.manifest_url,
            ConversionOptions(
                grade_system=payload.grade_system,
                foot_rules=payload.foot_rules,
            ),
        )
    except MappingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ConversionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except BoardSeshError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    encoded = json.dumps(
        document,
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")
    filename = _download_name(mapping.mapping_name, mapping.layout_id)
    return Response(
        content=encoded,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Included-Climbs": str(document["summary"]["included_climbs"]),
        },
    )
