# boardsesh-crux-converter

Dockerisierte Web-App, die den öffentlichen MoonBoard-Katalog aus den
[BoardSesh-Snapshots](https://github.com/boardsesh/boardsesh/blob/main/docs/board-snapshots-dataset.md)
mit einem persistenten Mapping aus der
[CRUX WLED Bridge](https://github.com/Spikeystrike/crux-wled-bridge)
verknüpft und eine versionierte CRUX-Importdatei erzeugt.

> Status: erster importierbarer Austauschformat-Entwurf. Die App schreibt noch
> nicht direkt in CRUX. Das Format `crux-climb-import/v2` ist in diesem Projekt
> definiert und bildet die öffentlich dokumentierten CRUX-Climb-Felder ab.

## Was der Konverter macht

- lädt immer den aktuellen BoardSesh-Manifest-Eintrag für das gewählte MoonBoard;
- unterstützt Standard, Masters und Mini über die BoardSesh-Layout-ID des Mappings;
- liest mehrere gespeicherte Mappings direkt aus der CRUX WLED Bridge;
- akzeptiert alternativ exportierte Mapping-JSON-Dateien;
- filtert optional nach Wandwinkel;
- konvertiert Start-, Hand- und Finish-Griffe in CRUX-Hold-Typen;
- leitet die CRUX-Fußregel pro Boulder aus `board_climbs.characteristics` ab;
- erhält Setter, Grad, Winkel, Benchmark-Status und Community-Statistiken;
- überspringt Boulder mit fehlenden Hold-Zuordnungen vollständig und dokumentiert
  sie in `summary.skipped_examples`;
- überspringt `method_footless_kickboard`, weil CRUX dafür ohne ein separates
  Kicker-Hold-Mapping keine exakt passende Regel anbietet;
- cached den validierten SQLite-Snapshot in einem Docker-Volume.

Das Mapping bleibt strikt an die CRUX-Wand gebunden:
`<wall_id> + <moonboard_hold_id> -> <crux_hold_id(s)>`.
Es gibt keinen globalen Hold-Fallback.

## Start mit Docker Compose

```sh
git clone https://github.com/Spikeystrike/boardsesh-crux-converter.git
cd boardsesh-crux-converter
docker compose up --build
```

Danach im Browser öffnen:

```text
http://localhost:8080
```

Wenn die CRUX WLED Bridge auf demselben Docker-Host läuft, kann die App sie über
`http://host.docker.internal:<PORT>` erreichen. Läuft die Bridge in einem
anderen Compose-Projekt, können beide Services alternativ in dasselbe externe
Docker-Netz gehängt werden.

Die App ist für ein vertrauenswürdiges lokales Netz gedacht. Sie nimmt eine
Bridge-URL entgegen und sollte ohne vorgeschaltete Zugriffskontrolle nicht
öffentlich ins Internet gestellt werden.

## Bedienung

1. Bridge-URL und CRUX Wall-ID eingeben und die gespeicherten Mappings laden.
2. Das gewünschte Mapping auswählen. Board, Setup und BoardSesh-Layout-ID werden
   aus dem persistenten Mapping übernommen.
3. Optional Winkel und Gradskala wählen. Die Fußregel kommt automatisch aus den
   BoardSesh-Characteristics.
4. **CRUX-Importdatei erzeugen** anklicken.

Statt der Bridge kann eine JSON-Datei geöffnet werden. Unterstützt werden:

- die Listenantwort `{"mappings": [...]}`;
- eine Liste serialisierter Mappings;
- ein einzelnes serialisiertes Mapping;
- die Save-Antwort `{"mapping": {...}}` der Bridge.

## Umgebungsvariablen

| Variable | Standard | Bedeutung |
| --- | --- | --- |
| `PORT` | `8080` | veröffentlichter Compose-Port |
| `BOARDSESH_MANIFEST_URL` | offizieller v1-gzip Manifest | BoardSesh-Datenquelle |
| `CACHE_DIR` | `/data/cache` | Snapshot-Cache im Container |
| `DOWNLOAD_LIMIT_MB` | `300` | Grenze für Download und entpackte DB |
| `REQUEST_TIMEOUT_SECONDS` | `60` | HTTP-Timeout |

BoardSesh veröffentlicht die SQLite-Kataloge laut eigener Dokumentation nachts
und erwartet, dass Verbraucher die jeweilige Snapshot-URL immer neu über den
stabilen Manifest ermitteln. Der Konverter folgt diesem Modell, prüft
`PRAGMA quick_check` und lädt denselben Snapshot nur einmal.

## Fußregeln

BoardSesh beschreibt die MoonBoard-Methode in
`board_climbs.characteristics`. Der Konverter bildet sie so ab:

| BoardSesh-Characteristic | Bedeutung | CRUX `foot_rules` |
| --- | --- | --- |
| kein Methodeneintrag | Feet follow hands, Kicker offen | `feet_follow_hands_open_kicker` |
| `method_no_kickboard` | Feet follow hands, Kicker gesperrt | `feet_follow_hands` |
| `method_footless` | Keine Füße, kein Kicker | `campus` |
| `method_footless_kickboard` | Nur Kicker darf als Fuß genutzt werden | wird mit Diagnose übersprungen |

Die generischen BoardSesh-Characteristics `no_kickboard` und `campus` werden
ebenfalls auf `feet_follow_hands` beziehungsweise `campus` abgebildet.
`only_marked_feet` wäre für `method_footless_kickboard` nur dann korrekt, wenn
alle Kicker-Griffe zusätzlich als CRUX-Fußgriffe markiert würden. Das aktuelle
persistente Mapping unterscheidet Kicker-Griffe noch nicht separat, daher nimmt
der Konverter hier keine stillschweigend falsche Zuordnung vor.

## Importformat v2

Das vollständige Schema liegt unter
[`schema/crux-import-v2.schema.json`](schema/crux-import-v2.schema.json).
Das bisherige v1-Schema bleibt für bereits erzeugte Dateien erhalten.

Gekürztes Beispiel:

```json
{
  "format": "crux-climb-import",
  "version": 2,
  "target": {
    "provider": "CRUX",
    "wall_id": 216943,
    "mapping_id": "mapping-uuid",
    "mapping_name": "Mini 2020 links"
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
      "name": "Beispiel",
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

Die tatsächliche Datei enthält zusätzlich Provenienz, Optionen,
Community-Statistiken und Diagnosen. CRUX-Hold-IDs bleiben Strings, damit auch
die in realen Wall-Daten vorkommenden hexadezimalen IDs verlustfrei erhalten
bleiben.

BoardSesh-Rollencodes werden so abgebildet:

| BoardSesh | Bedeutung | CRUX `hold_type` |
| --- | --- | --- |
| `42` | Start | `start` |
| `43` | Hand | `hand` |
| `44` | Finish | `finish` |

Das öffentliche
[CRUX API Reference](https://docs.cruxapp.ca/api-documentation/api-reference)
dokumentiert derzeit keinen Bulk-Import-Endpunkt. Deshalb erzeugt diese erste
Version eine explizit versionierte Datei; der spätere CRUX-Importer kann sich
gegen das JSON-Schema implementieren, ohne den BoardSesh-Teil neu zu bauen.

## Entwicklung und Tests

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
python -m unittest discover -s tests -p 'test_*.py'
docker build -t boardsesh-crux-converter .
```

Die Tests prüfen Mapping-Varianten, wall-spezifische Bridge-Abfragen,
Snapshot-Filter, Frame-Rollen, Gradabbildung, Fehlerdiagnosen, API-Routen und
das JSON-Schema. GitHub Actions führt Tests und Docker-Build bei jedem Push aus.

## Daten und Marken

Die Kletterdaten stammen aus dem öffentlichen BoardSesh-Datensatz und enthalten
user-generated content. Setter-Namen werden im Export zur Attribution erhalten.
MoonBoard und CRUX sind Marken ihrer jeweiligen Rechteinhaber; dieses Projekt ist
nicht mit ihnen verbunden oder von ihnen unterstützt.
