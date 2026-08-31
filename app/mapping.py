from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx


class MappingError(ValueError):
    """Raised when a CRUX WLED Bridge mapping cannot be used."""


@dataclass(frozen=True)
class MappingContext:
    mapping_id: str
    mapping_name: str
    wall_id: int
    board_type: str
    setup: str
    layout_id: int
    hold_id_to_crux: dict[int, tuple[str, ...]]


def mapping_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        records = payload
    elif not isinstance(payload, dict):
        raise MappingError("Mapping JSON must be an object or array")
    elif isinstance(payload.get("mappings"), list):
        records = payload["mappings"]
    elif isinstance(payload.get("mapping"), dict) and "wallid" in payload["mapping"]:
        records = [payload["mapping"]]
    elif "wallid" in payload and isinstance(payload.get("mapping"), dict):
        records = [payload]
    else:
        raise MappingError("No serialized MoonBoard mapping was found in the JSON")

    if not all(isinstance(record, dict) for record in records):
        raise MappingError("Every mapping entry must be an object")
    return records


def mapping_summaries(payload: Any) -> list[dict[str, Any]]:
    summaries = []
    for record in mapping_records(payload):
        settings = record.get("mapping") or {}
        summaries.append(
            {
                "id": str(record.get("id") or ""),
                "name": str(record.get("name") or "Unnamed mapping"),
                "wallid": record.get("wallid"),
                "board_type": record.get("board_type"),
                "setup": record.get("setup"),
                "boardsesh_layout_id": settings.get("boardsesh_layout_id"),
            }
        )
    return summaries


def select_mapping(payload: Any, mapping_id: str | None = None) -> MappingContext:
    records = mapping_records(payload)
    if mapping_id:
        record = next(
            (item for item in records if str(item.get("id")) == mapping_id),
            None,
        )
        if record is None:
            raise MappingError("The selected mapping was not found")
    elif len(records) == 1:
        record = records[0]
    else:
        raise MappingError("Select one mapping from the uploaded mapping list")

    settings = record.get("mapping")
    if not isinstance(settings, dict):
        raise MappingError("The mapping entry has no mapping data")
    try:
        wall_id = int(record["wallid"])
        layout_id = int(settings["boardsesh_layout_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise MappingError(
            "The mapping must contain wallid and boardsesh_layout_id"
        ) from exc

    matches = settings.get("matches")
    if not isinstance(matches, list) or not matches:
        raise MappingError("The mapping contains no matched MoonBoard positions")

    hold_id_to_crux: dict[int, tuple[str, ...]] = {}
    for match in matches:
        if not isinstance(match, dict):
            continue
        try:
            moonboard_hold_id = int(match["moonboard_hold_id"])
        except (KeyError, TypeError, ValueError):
            continue
        raw_ids = match.get("crux_hold_ids", [])
        if not isinstance(raw_ids, list):
            raw_ids = [raw_ids]
        crux_ids = tuple(
            sorted(
                {
                    str(crux_id).strip()
                    for crux_id in raw_ids
                    if str(crux_id).strip()
                }
            )
        )
        if crux_ids:
            hold_id_to_crux[moonboard_hold_id] = crux_ids

    if not hold_id_to_crux:
        raise MappingError("The mapping contains no CRUX hold IDs")

    return MappingContext(
        mapping_id=str(record.get("id") or ""),
        mapping_name=str(record.get("name") or "Unnamed mapping"),
        wall_id=wall_id,
        board_type=str(record.get("board_type") or ""),
        setup=str(record.get("setup") or ""),
        layout_id=layout_id,
        hold_id_to_crux=hold_id_to_crux,
    )


def validate_bridge_url(url: str) -> str:
    normalized = url.strip().rstrip("/")
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise MappingError("Bridge URL must be an http:// or https:// URL")
    if parsed.username or parsed.password:
        raise MappingError("Put credentials in a reverse proxy, not in the URL")
    return normalized


async def fetch_bridge_mapping_payload(
    bridge_url: str,
    wall_id: int,
    *,
    timeout_seconds: float,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    base_url = validate_bridge_url(bridge_url)
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            timeout=timeout_seconds,
            follow_redirects=True,
        )
    try:
        response = await client.get(
            f"{base_url}/virtualmapping/mappings",
            params={"wallid": wall_id},
        )
        response.raise_for_status()
        payload = response.json()
        mapping_records(payload)
        return payload
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:300]
        raise MappingError(
            f"Bridge returned HTTP {exc.response.status_code}: {detail}"
        ) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise MappingError(f"Could not load mappings from the bridge: {exc}") from exc
    finally:
        if owns_client:
            await client.aclose()
