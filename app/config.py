from dataclasses import dataclass
import os
from pathlib import Path


DEFAULT_MANIFEST_URL = (
    "https://boardsesh-board-snapshots.t3.tigrisfiles.io/"
    "board-snapshots/v1-gzip/manifest.json"
)

MOONBOARD_LAYOUTS = {
    1: "MoonBoard 2010",
    2: "MoonBoard 2016",
    3: "MoonBoard 2024",
    4: "MoonBoard Masters 2017",
    5: "MoonBoard Masters 2019",
    6: "Mini MoonBoard 2020",
    7: "Mini MoonBoard 2025",
}


@dataclass(frozen=True)
class Settings:
    manifest_url: str
    cache_dir: Path
    download_limit_bytes: int
    request_timeout_seconds: float

    @classmethod
    def from_environment(cls) -> "Settings":
        download_limit_mb = int(os.getenv("DOWNLOAD_LIMIT_MB", "300"))
        request_timeout = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "60"))
        if download_limit_mb < 1:
            raise ValueError("DOWNLOAD_LIMIT_MB must be positive")
        if request_timeout <= 0:
            raise ValueError("REQUEST_TIMEOUT_SECONDS must be positive")
        return cls(
            manifest_url=os.getenv("BOARDSESH_MANIFEST_URL", DEFAULT_MANIFEST_URL),
            cache_dir=Path(os.getenv("CACHE_DIR", "/data/cache")),
            download_limit_bytes=download_limit_mb * 1024 * 1024,
            request_timeout_seconds=request_timeout,
        )
