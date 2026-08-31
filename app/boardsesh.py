from dataclasses import dataclass
import asyncio
import gzip
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Any
from uuid import uuid4

import httpx


class BoardSeshError(RuntimeError):
    """Raised when the public BoardSesh dataset cannot be consumed safely."""


@dataclass(frozen=True)
class SnapshotEntry:
    layout_id: int
    url: str
    built_at: str
    content_encoding: str
    bytes: int | None


@dataclass(frozen=True)
class CatalogClimb:
    uuid: str
    name: str
    description: str
    setter_username: str | None
    frames: str
    angle: int
    display_difficulty: float | None
    benchmark_difficulty: float | None
    ascensionist_count: int
    quality_average: float | None
    characteristics: tuple[str, ...]


def resolve_snapshot_entry(manifest: Any, layout_id: int) -> SnapshotEntry:
    if not isinstance(manifest, dict) or not isinstance(manifest.get("entries"), list):
        raise BoardSeshError("BoardSesh manifest has an unexpected shape")
    raw = next(
        (
            entry
            for entry in manifest["entries"]
            if entry.get("boardType") == "moonboard"
            and entry.get("layoutId") == layout_id
        ),
        None,
    )
    if raw is None:
        raise BoardSeshError(
            f"BoardSesh manifest contains no MoonBoard layout {layout_id}"
        )
    try:
        return SnapshotEntry(
            layout_id=layout_id,
            url=str(raw["url"]),
            built_at=str(raw["builtAt"]),
            content_encoding=str(raw.get("contentEncoding") or "identity"),
            bytes=int(raw["bytes"]) if raw.get("bytes") is not None else None,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise BoardSeshError("BoardSesh manifest entry is incomplete") from exc


def _safe_built_at(value: str) -> str:
    safe = re.sub(r"[^0-9A-Za-z_.-]+", "-", value).strip("-")
    return safe[:80] or "unknown"


def _sqlite_uri(path: Path) -> str:
    return f"{path.resolve().as_uri()}?mode=ro"


def validate_snapshot(path: Path) -> None:
    try:
        connection = sqlite3.connect(_sqlite_uri(path), uri=True)
        try:
            result = connection.execute("PRAGMA quick_check").fetchone()
            if not result or result[0] != "ok":
                raise BoardSeshError("BoardSesh SQLite quick_check failed")
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            if not {"board_climbs", "board_climb_stats"}.issubset(tables):
                raise BoardSeshError(
                    "BoardSesh snapshot is missing required catalog tables"
                )
            climb_columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(board_climbs)")
            }
            if "characteristics" not in climb_columns:
                raise BoardSeshError(
                    "BoardSesh snapshot is missing board_climbs.characteristics"
                )
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise BoardSeshError(f"Invalid BoardSesh SQLite snapshot: {exc}") from exc


class SnapshotService:
    def __init__(
        self,
        manifest_url: str,
        cache_dir: Path,
        download_limit_bytes: int,
        timeout_seconds: float,
    ):
        self.manifest_url = manifest_url
        self.cache_dir = cache_dir
        self.download_limit_bytes = download_limit_bytes
        self.timeout_seconds = timeout_seconds
        self._download_lock = asyncio.Lock()

    async def load_manifest(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                follow_redirects=True,
            ) as client:
                response = await client.get(self.manifest_url)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
            raise BoardSeshError(
                f"Could not load the BoardSesh manifest: {exc}"
            ) from exc
        if not isinstance(payload, dict):
            raise BoardSeshError("BoardSesh manifest must be a JSON object")
        return payload

    async def get_snapshot(self, layout_id: int) -> tuple[Path, SnapshotEntry]:
        entry = resolve_snapshot_entry(await self.load_manifest(), layout_id)
        if entry.bytes is not None and entry.bytes > self.download_limit_bytes:
            raise BoardSeshError("BoardSesh snapshot exceeds DOWNLOAD_LIMIT_MB")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        destination = self.cache_dir / (
            f"moonboard-{layout_id}-{_safe_built_at(entry.built_at)}.db"
        )
        if destination.exists():
            validate_snapshot(destination)
            return destination, entry

        async with self._download_lock:
            if destination.exists():
                validate_snapshot(destination)
                return destination, entry
            await self._download(entry, destination)
        return destination, entry

    async def _download(self, entry: SnapshotEntry, destination: Path) -> None:
        raw_path = destination.with_name(
            f".{destination.name}.{uuid4().hex}.download"
        )
        decoded_path = destination.with_name(
            f".{destination.name}.{uuid4().hex}.decoded"
        )
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                follow_redirects=True,
            ) as client:
                async with client.stream("GET", entry.url) as response:
                    response.raise_for_status()
                    total = 0
                    with raw_path.open("wb") as output:
                        async for chunk in response.aiter_raw():
                            total += len(chunk)
                            if total > self.download_limit_bytes:
                                raise BoardSeshError(
                                    "BoardSesh snapshot exceeds DOWNLOAD_LIMIT_MB"
                                )
                            output.write(chunk)

            with raw_path.open("rb") as source:
                is_gzip = source.read(2) == b"\x1f\x8b"

            if is_gzip:
                decoded_total = 0
                with gzip.open(raw_path, "rb") as source, decoded_path.open(
                    "wb"
                ) as output:
                    while chunk := source.read(1024 * 1024):
                        decoded_total += len(chunk)
                        if decoded_total > self.download_limit_bytes:
                            raise BoardSeshError(
                                "Decoded snapshot exceeds DOWNLOAD_LIMIT_MB"
                            )
                        output.write(chunk)
                validate_snapshot(decoded_path)
                os.replace(decoded_path, destination)
            else:
                validate_snapshot(raw_path)
                os.replace(raw_path, destination)
        except httpx.HTTPStatusError as exc:
            raise BoardSeshError(
                f"Snapshot download returned HTTP {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            raise BoardSeshError(f"Snapshot download failed: {exc}") from exc
        finally:
            for path in (raw_path, decoded_path):
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass


def _parse_characteristics(value: Any, climb_uuid: str) -> tuple[str, ...]:
    if value is None or value == "":
        return ()
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except json.JSONDecodeError as exc:
        raise BoardSeshError(
            f"Invalid characteristics JSON for BoardSesh climb {climb_uuid}"
        ) from exc
    if not isinstance(parsed, list) or any(
        not isinstance(item, str) for item in parsed
    ):
        raise BoardSeshError(
            f"Invalid characteristics for BoardSesh climb {climb_uuid}"
        )
    return tuple(parsed)


def read_catalog(
    path: Path,
    layout_id: int,
    angle: int | None = None,
) -> list[CatalogClimb]:
    validate_snapshot(path)
    connection = sqlite3.connect(_sqlite_uri(path), uri=True)
    connection.row_factory = sqlite3.Row
    try:
        parameters: list[Any] = [layout_id]
        angle_filter = ""
        if angle is not None:
            angle_filter = " AND stats.angle = ?"
            parameters.append(angle)
        rows = connection.execute(
            """
            SELECT
                climbs.uuid,
                climbs.name,
                climbs.description,
                climbs.setter_username,
                climbs.frames,
                stats.angle,
                stats.display_difficulty,
                stats.benchmark_difficulty,
                COALESCE(stats.ascensionist_count, 0) AS ascensionist_count,
                stats.quality_average,
                climbs.characteristics
            FROM board_climbs AS climbs
            JOIN board_climb_stats AS stats
              ON stats.board_type = climbs.board_type
             AND stats.climb_uuid = climbs.uuid
            WHERE climbs.board_type = 'moonboard'
              AND climbs.layout_id = ?
              AND COALESCE(climbs.is_listed, 0) = 1
              AND COALESCE(climbs.is_draft, 0) = 0
              AND COALESCE(climbs.frames, '') != ''
            """
            + angle_filter
            + " ORDER BY LOWER(climbs.name), climbs.uuid, stats.angle",
            parameters,
        ).fetchall()
        return [
            CatalogClimb(
                uuid=str(row["uuid"]),
                name=str(row["name"] or "Unnamed MoonBoard climb"),
                description=str(row["description"] or ""),
                setter_username=(
                    str(row["setter_username"])
                    if row["setter_username"] is not None
                    else None
                ),
                frames=str(row["frames"]),
                angle=int(row["angle"]),
                display_difficulty=(
                    float(row["display_difficulty"])
                    if row["display_difficulty"] is not None
                    else None
                ),
                benchmark_difficulty=(
                    float(row["benchmark_difficulty"])
                    if row["benchmark_difficulty"] is not None
                    else None
                ),
                ascensionist_count=int(row["ascensionist_count"]),
                quality_average=(
                    float(row["quality_average"])
                    if row["quality_average"] is not None
                    else None
                ),
                characteristics=_parse_characteristics(
                    row["characteristics"], str(row["uuid"])
                ),
            )
            for row in rows
        ]
    except sqlite3.Error as exc:
        raise BoardSeshError(f"Could not query BoardSesh snapshot: {exc}") from exc
    finally:
        connection.close()
