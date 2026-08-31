from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any, Iterable

from app.boardsesh import CatalogClimb, SnapshotEntry
from app.mapping import MappingContext


class ConversionError(ValueError):
    """Raised when BoardSesh catalog data cannot be converted."""


ROLE_TO_CRUX = {42: "start", 43: "hand", 44: "finish"}
ROLE_PRIORITY = {"hand": 1, "start": 2, "finish": 3}
FRAME_PATTERN = re.compile(r"p(\d+)r(\d+)")

GRADE_LABELS = {
    13: ("5+", "5a", "V1"),
    14: ("5B", "5b", "V1"),
    15: ("5C", "5c", "V2"),
    16: ("6A", "6a", "V3"),
    17: ("6A+", "6a+", "V3"),
    18: ("6B", "6b", "V4"),
    19: ("6B+", "6b+", "V4"),
    20: ("6C", "6c", "V5"),
    21: ("6C+", "6c+", "V5"),
    22: ("7A", "7a", "V6"),
    23: ("7A+", "7a+", "V7"),
    24: ("7B", "7b", "V8"),
    25: ("7B+", "7b+", "V8"),
    26: ("7C", "7c", "V9"),
    27: ("7C+", "7c+", "V10"),
    28: ("8A", "8a", "V11"),
    29: ("8A+", "8a+", "V12"),
    30: ("8B", "8b", "V13"),
    31: ("8B+", "8b+", "V14"),
    32: ("8C", "8c", "V15"),
    33: ("8C+", "8c+", "V16"),
}
GRADE_SYSTEM_INDEX = {"boardsesh": 0, "font": 1, "v_scale": 2}
FOOT_RULES = {
    "feet_follow_hands",
    "any_feet",
    "campus",
    "feet_follow_hands_open_kicker",
    "only_marked_feet",
}


@dataclass(frozen=True)
class ConversionOptions:
    grade_system: str = "font"
    foot_rules: str = "feet_follow_hands"

    def validate(self) -> None:
        if self.grade_system not in GRADE_SYSTEM_INDEX:
            raise ConversionError("Unknown grade system")
        if self.foot_rules not in FOOT_RULES:
            raise ConversionError("Unknown CRUX foot rule")


def parse_frames(frames: str) -> list[tuple[int, str]]:
    placements: list[tuple[int, str]] = []
    cursor = 0
    for match in FRAME_PATTERN.finditer(frames):
        if match.start() != cursor:
            raise ConversionError(f"Malformed MoonBoard frames at offset {cursor}")
        role_code = int(match.group(2))
        role = ROLE_TO_CRUX.get(role_code)
        if role is None:
            raise ConversionError(f"Unsupported MoonBoard role code {role_code}")
        placements.append((int(match.group(1)), role))
        cursor = match.end()
    if not placements or cursor != len(frames):
        raise ConversionError("Malformed or empty MoonBoard frames")
    return placements


def grade_label(difficulty: float | None, grade_system: str) -> str | None:
    if difficulty is None or not float(difficulty).is_integer():
        return None
    labels = GRADE_LABELS.get(int(difficulty))
    return labels[GRADE_SYSTEM_INDEX[grade_system]] if labels else None


def _crux_holds(
    placements: Iterable[tuple[int, str]],
    mapping: MappingContext,
) -> tuple[list[dict[str, str]], list[int], int]:
    holds_by_id: dict[str, str] = {}
    missing: list[int] = []
    collisions = 0
    for moonboard_hold_id, role in placements:
        crux_ids = mapping.hold_id_to_crux.get(moonboard_hold_id)
        if not crux_ids:
            missing.append(moonboard_hold_id)
            continue
        for crux_id in crux_ids:
            existing = holds_by_id.get(crux_id)
            if existing and existing != role:
                collisions += 1
                if ROLE_PRIORITY[existing] >= ROLE_PRIORITY[role]:
                    continue
            holds_by_id[crux_id] = role
    return (
        [
            {"id": hold_id, "hold_type": role}
            for hold_id, role in holds_by_id.items()
        ],
        sorted(set(missing)),
        collisions,
    )


def convert_catalog(
    climbs: Iterable[CatalogClimb],
    mapping: MappingContext,
    snapshot: SnapshotEntry,
    manifest_url: str,
    options: ConversionOptions,
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    options.validate()
    if snapshot.layout_id != mapping.layout_id:
        raise ConversionError(
            "BoardSesh snapshot layout does not match the selected mapping"
        )

    generated_at = generated_at or datetime.now(timezone.utc)
    converted: list[dict[str, Any]] = []
    skipped_missing_mapping = 0
    skipped_invalid_frames = 0
    missing_grade_count = 0
    role_collision_count = 0
    skipped_examples: list[dict[str, Any]] = []
    input_count = 0

    for climb in climbs:
        input_count += 1
        try:
            placements = parse_frames(climb.frames)
        except ConversionError as exc:
            skipped_invalid_frames += 1
            if len(skipped_examples) < 20:
                skipped_examples.append(
                    {"uuid": climb.uuid, "name": climb.name, "reason": str(exc)}
                )
            continue

        holds, missing_hold_ids, collisions = _crux_holds(placements, mapping)
        role_collision_count += collisions
        if missing_hold_ids:
            skipped_missing_mapping += 1
            if len(skipped_examples) < 20:
                skipped_examples.append(
                    {
                        "uuid": climb.uuid,
                        "name": climb.name,
                        "reason": "missing_crux_hold_mapping",
                        "moonboard_hold_ids": missing_hold_ids,
                    }
                )
            continue

        grade = grade_label(climb.display_difficulty, options.grade_system)
        if grade is None:
            missing_grade_count += 1
        converted.append(
            {
                "external_id": f"boardsesh:{climb.uuid}:{climb.angle}",
                "name": climb.name,
                "description": climb.description or None,
                "grade": grade,
                "angle": str(climb.angle),
                "color": None,
                "foot_rules": options.foot_rules,
                "setter_name": climb.setter_username,
                "holds": holds,
                "source": {
                    "provider": "BoardSesh",
                    "climb_uuid": climb.uuid,
                    "layout_id": mapping.layout_id,
                    "angle": climb.angle,
                    "display_difficulty": climb.display_difficulty,
                    "is_benchmark": climb.benchmark_difficulty is not None,
                    "ascensionist_count": climb.ascensionist_count,
                    "quality_average": climb.quality_average,
                },
            }
        )

    return {
        "format": "crux-climb-import",
        "version": 1,
        "generated_at": generated_at.astimezone(timezone.utc).isoformat(),
        "source": {
            "provider": "BoardSesh",
            "manifest_url": manifest_url,
            "snapshot_url": snapshot.url,
            "snapshot_built_at": snapshot.built_at,
            "board_type": "moonboard",
            "layout_id": mapping.layout_id,
            "setup": mapping.setup,
        },
        "target": {
            "provider": "CRUX",
            "wall_id": mapping.wall_id,
            "mapping_id": mapping.mapping_id,
            "mapping_name": mapping.mapping_name,
        },
        "options": {
            "grade_system": options.grade_system,
            "foot_rules": options.foot_rules,
            "incomplete_climbs": "skip",
        },
        "summary": {
            "input_climbs": input_count,
            "included_climbs": len(converted),
            "skipped_missing_mapping": skipped_missing_mapping,
            "skipped_invalid_frames": skipped_invalid_frames,
            "climbs_without_grade": missing_grade_count,
            "crux_role_collisions": role_collision_count,
            "skipped_examples": skipped_examples,
        },
        "climbs": converted,
    }
