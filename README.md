# boardsesh-crux-converter

A Dockerized web app that combines the public MoonBoard catalog from the
[BoardSesh snapshots](https://github.com/boardsesh/boardsesh/blob/main/docs/board-snapshots-dataset.md)
with a persistent mapping from
[CRUX WLED Bridge](https://github.com/Spikeystrike/crux-wled-bridge)
and generates a versioned CRUX import file.

> Status: first importable interchange-format draft. The app does not write
> directly to CRUX yet. The `crux-climb-import/v2` format is defined by this
> project and represents the publicly documented CRUX climb fields.

## What the converter does

- always resolves the current BoardSesh manifest entry for the selected MoonBoard;
- supports Standard, Masters, and Mini through the mapping's BoardSesh layout ID;
- reads multiple stored mappings directly from CRUX WLED Bridge;
- alternatively accepts exported mapping JSON files;
- optionally filters climbs by wall angle;
- converts start, hand, and finish holds to CRUX hold types;
- derives the CRUX foot rule for each climb from `board_climbs.characteristics`;
- preserves setter, grade, angle, benchmark status, and community statistics;
- skips climbs with incomplete hold mappings and records them in
  `summary.skipped_examples`;
- skips `method_footless_kickboard` because CRUX has no exact equivalent
  without a separate kicker-hold mapping;
- caches the validated SQLite snapshot in a Docker volume.

Mappings remain strictly bound to their CRUX wall:
`<wall_id> + <moonboard_hold_id> -> <crux_hold_id(s)>`.
There is no global hold fallback.

## Start with Docker Compose

```sh
git clone https://github.com/Spikeystrike/boardsesh-crux-converter.git
cd boardsesh-crux-converter
docker compose up --build
```

Then open:

```text
http://localhost:8080
```

If CRUX WLED Bridge runs on the same Docker host, the app can reach it at
`http://host.docker.internal:<PORT>`. If the bridge runs in a different
Compose project, both services can instead join the same external Docker
network.

The app is intended for a trusted local network. It accepts a bridge URL and
should not be exposed publicly without access control in front of it.

## Usage

1. Enter the bridge URL and CRUX wall ID, then load the stored mappings.
2. Select the required mapping. Board, setup, and BoardSesh layout ID are taken
   from the persistent mapping.
3. Optionally select a wall angle and grade scale. The foot rule is derived
   automatically from the BoardSesh characteristics.
4. Click **Create CRUX import file**.

English is the default interface language. Use the flag in the top-right corner
to switch to German or back to English. The selection is stored in the browser.

Instead of connecting to the bridge, you can open a JSON file. The following
formats are supported:

- the list response `{"mappings": [...]}`;
- a list of serialized mappings;
- a single serialized mapping;
- the bridge save response `{"mapping": {...}}`.

Example list response containing two selectable mappings:

```json
{
  "mappings": [
    {
      "id": "moonboard-mini-left",
      "wallid": 216943,
      "name": "Mini 2020 left",
      "board_type": "mini",
      "setup": "mini_2020",
      "mapping": {
        "boardsesh_layout_id": 6,
        "matches": [
          {
            "moonboard_hold_id": 1,
            "crux_hold_ids": ["8ba97f45a6656519"]
          },
          {
            "moonboard_hold_id": 2,
            "crux_hold_ids": ["8ba97f45a6656520"]
          }
        ]
      }
    },
    {
      "id": "moonboard-standard-2016",
      "wallid": 216943,
      "name": "Standard 2016",
      "board_type": "standard",
      "setup": "standard_2016",
      "mapping": {
        "boardsesh_layout_id": 2,
        "matches": [
          {
            "moonboard_hold_id": 1,
            "crux_hold_ids": ["8ba97f45a6656601"]
          },
          {
            "moonboard_hold_id": 2,
            "crux_hold_ids": [
              "8ba97f45a6656602",
              "8ba97f45a6656603"
            ]
          }
        ]
      }
    }
  ]
}
```

The `id` identifies the selectable mapping, `wallid` identifies the target
CRUX wall, and `boardsesh_layout_id` selects the BoardSesh snapshot.
Each `matches` entry maps one MoonBoard hold ID to one or more CRUX hold IDs.
Real exports normally contain a match for every mapped MoonBoard position; the
example is shortened to two positions per mapping.

## Environment variables

| Variable | Default | Description |
| --- | --- | --- |
| `PORT` | `8080` | Published Compose port |
| `BOARDSESH_MANIFEST_URL` | Official v1-gzip manifest | BoardSesh data source |
| `CACHE_DIR` | `/data/cache` | Snapshot cache inside the container |
| `DOWNLOAD_LIMIT_MB` | `300` | Maximum download and decoded database size |
| `REQUEST_TIMEOUT_SECONDS` | `60` | HTTP timeout |

BoardSesh publishes the SQLite catalogs nightly and requires consumers to
resolve each snapshot URL through the stable manifest. The converter follows
that model, runs `PRAGMA quick_check`, and downloads a given snapshot only
once.

## Foot rules

BoardSesh stores the MoonBoard method in `board_climbs.characteristics`.
The converter maps it as follows:

| BoardSesh characteristic | Meaning | CRUX `foot_rules` |
| --- | --- | --- |
| No method characteristic | Feet follow hands, kicker open | `feet_follow_hands_open_kicker` |
| `method_no_kickboard` | Feet follow hands, kicker unavailable | `feet_follow_hands` |
| `method_footless` | No feet and no kicker | `campus` |
| `method_footless_kickboard` | Only the kicker may be used for feet | Skipped with a diagnostic |

The generic BoardSesh characteristics `no_kickboard` and `campus` are also
mapped to `feet_follow_hands` and `campus`, respectively.
`only_marked_feet` would represent `method_footless_kickboard` only if every
kicker hold were additionally marked as a CRUX foot hold. The current
persistent mapping does not identify kicker holds separately, so the converter
does not create a silently incorrect mapping.

## Import format v2

The complete schema is available at
[`schema/crux-import-v2.schema.json`](schema/crux-import-v2.schema.json).
The previous v1 schema remains available for files that have already been
generated.

Abbreviated example:

```json
{
  "format": "crux-climb-import",
  "version": 2,
  "target": {
    "provider": "CRUX",
    "wall_id": 216943,
    "mapping_id": "mapping-uuid",
    "mapping_name": "Mini 2020 left"
  },
  "summary": {
    "input_climbs": 1234,
    "included_climbs": 1170,
    "skipped_missing_mapping": 64,
    "skipped_unsupported_foot_rule": 3,
    "foot_rule_counts": {
      "feet_follow_hands_open_kicker": 1150,
      "feet_follow_hands": 18,
      "campus": 2
    }
  },
  "climbs": [
    {
      "external_id": "boardsesh:climb-uuid:40",
      "name": "Example",
      "grade": "6b",
      "angle": "40",
      "foot_rules": "feet_follow_hands_open_kicker",
      "holds": [
        {"id": "8ba97f45a6656519", "hold_type": "start"}
      ]
    }
  ]
}
```

The actual file also contains provenance, options, community statistics, and
diagnostics. CRUX hold IDs remain strings so hexadecimal IDs found in real wall
data are preserved without loss.

BoardSesh role codes are mapped as follows:

| BoardSesh | Meaning | CRUX `hold_type` |
| --- | --- | --- |
| `42` | Start | `start` |
| `43` | Hand | `hand` |
| `44` | Finish | `finish` |

The public
[CRUX API Reference](https://docs.cruxapp.ca/api-documentation/api-reference)
currently documents no bulk-import endpoint. This first version therefore
generates an explicitly versioned file. A future CRUX importer can implement
the JSON Schema without rebuilding the BoardSesh side.

## Development and tests

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
python -m unittest discover -s tests -p 'test_*.py'
docker build -t boardsesh-crux-converter .
```

The tests cover mapping variants, wall-specific bridge requests, snapshot
filters, frame roles, grade conversion, diagnostics, API routes, and the JSON
Schema. GitHub Actions runs the tests and Docker build on every push.

## Data and trademarks

Climb data comes from the public BoardSesh dataset and contains user-generated
content. Setter names are retained in the export for attribution. MoonBoard and
CRUX are trademarks of their respective owners. This project is not affiliated
with or endorsed by them.
