#!/usr/bin/env python3
"""Compare or sync this repository with the local Draw Steel campaign.

The Draw Steel app must be open for --apply. Writes go through its local game
server so the running client and its SQLite persistence stay in agreement.
The default mode is a read-only comparison.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import shutil
import sqlite3
import struct
import subprocess
import time
import urllib.request
import uuid
from pathlib import Path

from websockets.sync.client import connect


REPO = Path(__file__).resolve().parents[1]
APP_DATA = Path.home() / "Library/Application Support/MCDM/Codex"
DEFAULT_GAME_ID = "3365ac8c-e59c-48ff-9ec1-6a5c334e121d"
DEFAULT_USER_ID = "steam-76561198023938855"
PLAYERS_PARTY_ID = "0339ff3e-f288-4a85-a02c-a458c091684f"
BLACK_IRON_PACT_ID = "36ea91ca-77c7-4ab8-b289-b5e50dbd7117"
PREGENS_PARTY_ID = "7870ffcb-c942-4db9-a831-bf0210aa11ea"
OLD_TAVERN_MAP_ID = "8791a882-221a-4b58-ac1c-bc9a248a1095"
STARTER_TAVERN_MAP_ID = "8e9d2508-af25-4e96-b407-46ac7ca3fc85"
STARTER_MAP_FOLDER_ID = "b4ac0140-c986-47e9-82c4-827d51e63789"
SYNC_NAMESPACE = uuid.UUID("40ea35b7-bbcf-4d3a-a68a-29a6d98fe645")
LEGACY_MAP_IDS = {OLD_TAVERN_MAP_ID, STARTER_TAVERN_MAP_ID}

HEROES = {
    "Demona": {
        "id": "b8edfa57-0947-4dfb-b3b9-6c03c7e615de",
        "art": "Campaign/Assets/Tokens/demona.png",
        "summary": "Level 3 Devil Disciple of the Chronokinetic Null",
        "level3Choice": {
            "guid": "b3be4364-09e5-4a28-92d6-50255e276339",
            "id": "31f2fcd4-c3cb-4321-94d5-0119ebcd7fd4",
            "name": "Molecular Rearrangement Field",
        },
    },
    "Dorian Ashveil": {
        "id": "f67884c1-3a6b-4296-8d88-a7274367c177",
        "art": "Campaign/Assets/Tokens/dorian-ashveil.png",
        "summary": "Level 3 Devil-Kind Revenant Vanguard Tactician",
        "level3Choice": {
            "guid": "792e9072-01a7-4cac-9232-51ecb1de35b3",
            "id": "15c723ff-7725-4959-b570-458ff8c9ec96",
            "name": "Hit 'Em Hard!",
        },
    },
    "Keth": {
        "id": "0779cf60-c9bd-49de-b769-bf5aacdc832d",
        "art": "Campaign/Assets/Tokens/keth.png",
        "summary": "Level 3 Hakaan Berserker Fury",
        "level3Choice": {
            "guid": "4991e3cd-7c22-43de-8d9d-f4a8428bb8aa",
            "id": "a5d094b6-cfc8-4630-9cb7-54183b2b9580",
            "name": "You Are Already Dead",
        },
    },
    "M.A.C: Multifunctional Android Companion": {
        "id": "0a9de43e-3e2e-43a6-8d11-7fdb483148fa",
        "art": "Campaign/Assets/Tokens/mac.png",
        "source": "DS_Chars/M.A.C_ Multifunctional Android Companion 2.ds-hero",
        "summary": "Level 3 Memonek Duelist Troubadour",
        "level3Choice": {
            "guid": "cc1dced4-4996-4d2d-8a2a-4e275e8214b2",
            "id": "c58c14b2-6c81-4dfe-8511-6f525259e488",
            "name": "We Meet at Last",
        },
    },
}

TARGET_LEVEL = 3
TARGET_XP = 4
TARGET_VICTORIES = 4

CAPITAL_ART = REPO / "Campaign/Assets/Maps/capital-placeholder.png"
CAPITAL_MAP_ID = str(uuid.uuid5(SYNC_NAMESPACE, "map:capital-placeholder"))
CAPITAL_FLOOR_ID = str(uuid.uuid5(SYNC_NAMESPACE, "map:capital-placeholder:floor"))
CAPITAL_LAYER_ID = str(uuid.uuid5(SYNC_NAMESPACE, "map:capital-placeholder:layer"))
CAPITAL_OBJECT_ID = str(uuid.uuid5(SYNC_NAMESPACE, "map:capital-placeholder:object"))
CAPITAL_OBJECT_ASSET_ID = str(
    uuid.uuid5(SYNC_NAMESPACE, "map:capital-placeholder:object-asset")
)
TOKEN_LIBRARY_ID = str(uuid.uuid5(SYNC_NAMESPACE, "image-library:campaign-tokens"))
MAP_LIBRARY_ID = str(uuid.uuid5(SYNC_NAMESPACE, "image-library:campaign-maps"))


def stable_id(label: str) -> str:
    return str(uuid.uuid5(SYNC_NAMESPACE, label))


def forge_steel_level(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    level = data.get("class", {}).get("level")
    if not isinstance(level, int) or not 1 <= level <= 10:
        raise ValueError(f"invalid Forge Steel class level in {path}: {level!r}")
    return level


def read_json_row(db: sqlite3.Connection, name: str) -> dict | None:
    row = db.execute("SELECT value FROM stores WHERE name = ?", (name,)).fetchone()
    if row is None:
        return None
    value = bytes(row[0])
    if value.startswith(b"\0"):
        value = value[1:]
    return json.loads(value)


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"not a PNG: {path}")
    return struct.unpack(">II", data[16:24])


def asset_for(path: Path, image_type: int, keyword: str) -> tuple[str, dict, Path]:
    raw = path.read_bytes()
    image_id = base64.b64encode(hashlib.md5(raw).digest()).decode("ascii")
    asset_id = stable_id(f"image:{path.relative_to(REPO).as_posix()}")
    width, height = png_dimensions(path)
    metadata = {
        "ctime": 1785480000000,
        "height": height,
        "hidden": False,
        "imageId": image_id,
        "imageType": image_type,
        "keywords": {"0": keyword, "_luaTable": False},
        "mtime": 1785480000000,
        "ord": 0,
        "tint": {"a": 1, "b": 1, "g": 1, "r": 1},
        "width": width,
    }
    cache_name = hashlib.md5(image_id.encode("utf-8")).hexdigest().upper()
    cache_path = APP_DATA / "cache" / f"image-{cache_name}.png"
    return asset_id, metadata, cache_path


def map_settings() -> dict:
    return {
        "globalLighting": {"r": 1, "g": 1, "b": 1, "a": 1},
        "insideLighting": {"r": 1, "g": 1, "b": 1, "a": 1},
        "gridColor": {"r": 1, "g": 1, "b": 1, "a": 0.18},
        "luaSettings": {},
        "_patchDescription": "",
        "_patchSettings": {},
        "_unpatchSettings": {},
    }


def empty_floor(parent: str | None, description: str, layer: str | None) -> dict:
    return {
        "parentFloor": parent,
        "description": description,
        "layerDescription": layer,
        "floorHeightInTiles": 10,
        "editor": {},
        "shadowCasting": None,
        "renderOrder": None,
        "shareLighting": None,
        "shareVision": None,
        "roof": False,
        "canopy": False,
        "visionMultiplier": 1,
        "roofVisionExclusion": 1,
        "roofVisionExclusionFade": 0.1,
        "roofMinimumOpacity": 0,
        "roofShowWhenInside": False,
        "tokens": {},
        "objects": {},
        "objectDestruction": {},
        "infoBubbles": {},
        "markupZones": {},
        "map": {
            "biome": None,
            "background": None,
            "dimMin": {"0": -12, "1": -8},
            "dimMax": {"0": 12, "1": 8},
            "numEdit": 1,
            "groundRaster": {
                "updateid": None,
                "field": {"terrainManifest": [], "rasterUnits": {}},
            },
            "terrainLayers": {},
            "effectsLayers": {},
            "logical": {
                "blockLocs": [],
                "walls": [],
                "wallAssetIds": [],
                "stairwaysUp": [],
                "stairwaysDown": [],
                "wallClimbableTiles": [],
            },
        },
        "mapSettings": map_settings(),
        "vision": {
            "useLineOfSight": False,
            "sharedVision": True,
            "playerLimitVision": False,
            "playerVisionDistance": 16,
            "playerLimitFieldOfView": False,
            "playerFieldOfView": 120,
            "playerFogOfWar": False,
        },
    }


def capital_map_records(capital_asset_id: str, image_id: str) -> tuple[dict, dict, dict]:
    # This is deliberately a presentation-only placeholder, not a calibrated
    # tactical map. A locked Core sprite is more robust than ObjectComponentMap
    # here and displays the generated city art edge-to-edge without inventing a
    # grid calibration.
    component = {
        "@class": "ObjectComponentCore",
        "_lastScale": 1.5625,
        "_lastRotation": 0,
        "locked": True,
        "keywords": [],
        "rotation": 0,
        "scale": 1.5625,
        "pivot_x": 0.5,
        "pivot_y": 0.5,
        "sublayer": "Objects",
        "sprite_invisible_to_players": False,
        "height": 0.01,
        "hasShadow": False,
        "disabled": False,
        "properties": None,
    }
    object_asset = {
        "previewType": None,
        "components": {"CORE": component},
        "children": {},
        "keywords": None,
        "imageId": image_id,
        "tint": {"r": 1, "g": 1, "b": 1, "a": 1},
        "width": 0,
        "height": 0,
        "description": "Capital Campaign Placeholder",
        "parentFolder": None,
        "artist": "OpenAI ImageGen",
        "ord": 0,
        "ctime": 1785480000000,
        "mtime": 1785480000000,
        "hidden": False,
    }
    map_object = {
        "assetid": CAPITAL_OBJECT_ASSET_ID,
        "asset": object_asset,
        "parentObj": None,
        "pos": {"x": 0, "y": 0},
        "zorder": 1,
        "createTime": 178548000,
        "components": {"CORE": component},
        "wires": {},
    }
    layer = empty_floor(CAPITAL_FLOOR_ID, "Capital", "Map Layer")
    layer["objects"][CAPITAL_OBJECT_ID] = map_object
    floor = empty_floor(None, "Capital", None)
    details = {"floors": {CAPITAL_LAYER_ID: layer, CAPITAL_FLOOR_ID: floor}}
    manifest = {
        "description": "Capital — Campaign Placeholder",
        "syncVersion": 4,
        "parentFolder": "",
        "ord": 1,
        "loadingScreenImage": capital_asset_id,
        "defaultFloorId": CAPITAL_FLOOR_ID,
        "dimMin": {"0": -12, "1": -8},
        "dimMax": {"0": 12, "1": 8},
        "groundLevel": 0,
        "floors": {"0": CAPITAL_LAYER_ID, "1": CAPITAL_FLOOR_ID},
        "mapSettings": map_settings(),
        "teleporters": {},
    }
    surface = {
        "updateid": "",
        "valid": True,
        "heights": {},
        "rasters": {},
        "effects": {},
        "modifications": {},
    }
    return manifest, details, surface


def document_folder_id(relative: Path) -> str:
    return stable_id(f"document-folder:{relative.as_posix()}")


def document_folder_record(relative: Path, ordinal: int) -> tuple[str, dict]:
    folder_id = document_folder_id(relative)
    parent = relative.parent
    parent_folder = "private" if parent == Path(".") else document_folder_id(parent)
    record = {
        "description": relative.name,
        "parentFolder": parent_folder,
        "hidden": False,
        "ord": ordinal,
        "syncSource": f"Campaign/{relative.as_posix()}/",
    }
    return folder_id, record


def document_record(path: Path, ordinal: int) -> tuple[str, dict]:
    relative = path.relative_to(REPO / "Campaign")
    doc_id = stable_id(f"document:{relative.as_posix()}")
    content = path.read_text(encoding="utf-8")
    title = relative.stem.lstrip("_") or relative.stem
    parent = relative.parent
    parent_folder = (
        "private" if parent == Path(".") else document_folder_id(parent)
    )
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    record = {
        "__typeName": "MarkdownDocument",
        "id": doc_id,
        "description": title,
        "parentFolder": parent_folder,
        "content": content,
        "updateid": stable_id(f"document-update:{relative.as_posix()}:{digest}"),
        "annotations": {"_luaTable": False},
        "docType": "note",
        "hidden": False,
        "hiddenFromPlayers": True,
        "ord": ordinal,
        "syncSource": f"Campaign/{relative.as_posix()}",
        "syncSha256": digest,
        "_luaTable": True,
    }
    return doc_id, record


def party_override(party_id: str, name: str) -> dict:
    return {
        "__typeName": "Party",
        "id": party_id,
        "name": name,
        "hidden": True,
        "_luaTable": True,
    }


def find_server_port() -> int:
    result = subprocess.run(
        ["pgrep", "-f", "local-game-server-mac-arm64"],
        check=True,
        capture_output=True,
        text=True,
    )
    for pid in reversed(result.stdout.split()):
        lsof = subprocess.run(
            ["lsof", "-nP", "-a", "-p", pid, "-iTCP", "-sTCP:LISTEN"],
            check=False,
            capture_output=True,
            text=True,
        )
        match = re.search(r"127\.0\.0\.1:(\d+)\s+\(LISTEN\)", lsof.stdout)
        if match:
            return int(match.group(1))
    raise RuntimeError("Draw Steel local game server is not listening")


def get_root_snapshot(port: int, game_id: str, user_id: str) -> dict:
    url = f"ws://127.0.0.1:{port}/game/{game_id}"
    with connect(url, open_timeout=5, close_timeout=5) as ws:
        ws.recv()
        ws.send(json.dumps({"type": "auth", "userId": user_id}))
        ws.recv()
        message = json.loads(ws.recv())
        if message.get("type") != "put" or message.get("path") != "/":
            raise RuntimeError(f"unexpected Draw Steel snapshot: {message.get('type')}")
        return message["data"]


def apply_ops(port: int, game_id: str, user_id: str, ops: list[dict]) -> None:
    url = f"ws://127.0.0.1:{port}/game/{game_id}"
    req_id = f"repo-sync-{int(time.time() * 1000)}"
    with connect(url, open_timeout=5, close_timeout=5) as ws:
        ws.recv()
        ws.send(json.dumps({"type": "auth", "userId": user_id}))
        ws.recv()
        ws.recv()
        ws.send(json.dumps({"type": "batch", "reqId": req_id, "ops": ops}))
        while True:
            response = json.loads(ws.recv())
            if response.get("reqId") == req_id:
                if response.get("ok") is False:
                    raise RuntimeError(f"Draw Steel rejected sync: {response}")
                return


def firebase_patch(game_id: str, patch: dict) -> None:
    url = (
        "https://mcdm-385cf-default-rtdb.firebaseio.com/"
        f"games/{game_id}/characterIndex/characters.json"
    )
    request = urllib.request.Request(
        url,
        data=json.dumps(patch, separators=(",", ":")).encode("utf-8"),
        method="PATCH",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        if response.status != 200:
            raise RuntimeError(f"Firebase character index returned {response.status}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="apply the reported changes")
    parser.add_argument("--game-id", default=DEFAULT_GAME_ID)
    parser.add_argument("--user-id", default=DEFAULT_USER_ID)
    args = parser.parse_args()

    db_path = APP_DATA / "local-games" / args.game_id / "game.db"
    if not db_path.exists():
        raise SystemExit(f"campaign database not found: {db_path}")

    port = find_server_port()
    current = get_root_snapshot(port, args.game_id, args.user_id)
    ops: list[dict] = []
    descriptions: list[str] = []
    remote_patch: dict = {}
    cache_copies: list[tuple[Path, Path]] = []

    images: dict[str, dict] = {}
    token_library: dict[str, dict] = {}
    for name, spec in HEROES.items():
        art_path = REPO / spec["art"]
        asset_id, metadata, cache_path = asset_for(
            art_path, 3, name.lower().replace(" ", "-")
        )
        images[asset_id] = metadata
        token_library[asset_id] = {"assetid": asset_id}
        cache_copies.append((art_path, cache_path))

        token = current.get("characters", {}).get(spec["id"])
        if token is None:
            raise SystemExit(f"missing managed Player character: {name} ({spec['id']})")
        desired = json.loads(json.dumps(token))
        desired.setdefault("appearance", {})["portraitId"] = asset_id
        desired["appearance"]["offtokenPortraitId"] = asset_id
        desired["ownerId"] = "PARTY"
        desired["partyid"] = PLAYERS_PARTY_ID
        properties = desired.get("properties", {})
        classes = properties.get("classes", {})
        primary_class = classes.get("1")
        if primary_class is None:
            raise SystemExit(f"missing primary Draw Steel class for {name}")
        primary_class["level"] = TARGET_LEVEL
        properties["xp"] = TARGET_XP
        properties["victories"] = TARGET_VICTORIES
        choice = spec["level3Choice"]
        properties.setdefault("levelChoices", {"_luaTable": True})[
            choice["guid"]
        ] = {"1": choice["id"], "_luaTable": False}
        source = spec.get("source")
        if source is not None:
            level = forge_steel_level(REPO / source)
            if level != TARGET_LEVEL:
                raise SystemExit(
                    f"Forge Steel level for {name} is {level}; expected {TARGET_LEVEL}"
                )
        if desired != token:
            ops.append(
                {
                    "type": "put",
                    "store": "game",
                    "path": f"/characters/{spec['id']}",
                    "data": desired,
                }
            )
            descriptions.append(f"UPDATE Player record: {name}")
        remote_patch[spec["id"]] = {
            "name": name,
            "owner": "PARTY",
            "party": PLAYERS_PARTY_ID,
            "portrait": asset_id,
            "portraitAsset": metadata,
            "summaryDescription": spec["summary"],
        }

    capital_asset_id, capital_metadata, capital_cache = asset_for(
        CAPITAL_ART, 0, "capital-campaign-placeholder"
    )
    images[capital_asset_id] = capital_metadata
    cache_copies.append((CAPITAL_ART, capital_cache))
    map_library = {capital_asset_id: {"assetid": capital_asset_id}}

    for asset_id, metadata in images.items():
        if current.get("assets", {}).get("images", {}).get(asset_id) != metadata:
            ops.append(
                {
                    "type": "put",
                    "store": "game",
                    "path": f"/assets/images/{asset_id}",
                    "data": metadata,
                }
            )
            descriptions.append(f"UPSERT image asset: {asset_id}")

    libraries = {
        TOKEN_LIBRARY_ID: {
            "name": "Uncle HT Campaign Tokens",
            "imageType": 3,
            "gmonly": False,
            "hidden": False,
            "table": token_library,
        },
        MAP_LIBRARY_ID: {
            "name": "Uncle HT Campaign Maps",
            "imageType": 0,
            "gmonly": False,
            "hidden": False,
            "table": map_library,
        },
    }
    for library_id, library in libraries.items():
        if current.get("assets", {}).get("imageLibraries", {}).get(library_id) != library:
            ops.append(
                {
                    "type": "put",
                    "store": "game",
                    "path": f"/assets/imageLibraries/{library_id}",
                    "data": library,
                }
            )
            descriptions.append(f"UPSERT image library: {library['name']}")

    party_table = (
        current.get("assets", {})
        .get("objectTables", {})
        .get("parties", {})
        .get("table", {})
    )
    for party_id, name in (
        (BLACK_IRON_PACT_ID, "Black Iron Pact"),
        (PREGENS_PARTY_ID, "Delian Tomb Pregens"),
    ):
        override = party_override(party_id, name)
        if party_table.get(party_id) != override:
            ops.append(
                {
                    "type": "put",
                    "store": "game",
                    "path": f"/assets/objectTables/parties/table/{party_id}",
                    "data": override,
                }
            )
            descriptions.append(f"HIDE legacy party list: {name}")

    for character_id, token in current.get("characters", {}).items():
        on_legacy_map = token.get("locInfo", {}).get("map") in LEGACY_MAP_IDS
        is_pregen = token.get("partyid") == PREGENS_PARTY_ID
        if on_legacy_map or is_pregen:
            ops.append(
                {
                    "type": "delete",
                    "store": "game",
                    "path": f"/characters/{character_id}",
                }
            )
            label = token.get("appearance", {}).get("characterName") or character_id
            descriptions.append(f"DELETE legacy entity: {label}")
            if is_pregen:
                remote_patch[character_id] = None

    for legacy_map_id in sorted(LEGACY_MAP_IDS):
        old_manifest = current.get("mapManifests", {}).get(legacy_map_id)
        if old_manifest is not None:
            ops.append(
                {
                    "type": "delete",
                    "store": "game",
                    "path": f"/mapManifests/{legacy_map_id}",
                }
            )
            ops.append(
                {
                    "type": "put",
                    "store": f"mapdetails:{legacy_map_id}",
                    "path": "/",
                    "data": {},
                }
            )
            ops.append(
                {
                    "type": "put",
                    "store": f"maps:{legacy_map_id}",
                    "path": "/",
                    "data": {},
                }
            )
            descriptions.append(
                f"DELETE map: {old_manifest.get('description', legacy_map_id)}"
            )
    if STARTER_MAP_FOLDER_ID in current.get("mapFolders", {}):
        ops.append(
            {
                "type": "delete",
                "store": "game",
                "path": f"/mapFolders/{STARTER_MAP_FOLDER_ID}",
            }
        )
        descriptions.append("DELETE empty starter map folder: Delian Tomb - Part 1")

    manifest, details, surface = capital_map_records(
        capital_asset_id, capital_metadata["imageId"]
    )
    if current.get("mapManifests", {}).get(CAPITAL_MAP_ID) != manifest:
        ops.extend(
            [
                {
                    "type": "put",
                    "store": "game",
                    "path": f"/mapManifests/{CAPITAL_MAP_ID}",
                    "data": manifest,
                },
                {
                    "type": "put",
                    "store": f"mapdetails:{CAPITAL_MAP_ID}",
                    "path": "/",
                    "data": details,
                },
                {
                    "type": "put",
                    "store": f"maps:{CAPITAL_MAP_ID}",
                    "path": "/",
                    "data": surface,
                },
            ]
        )
        descriptions.append("UPSERT map: Capital — Campaign Placeholder")

    document_table = (
        current.get("assets", {})
        .get("objectTables", {})
        .get("documents", {})
        .get("table", {})
    )
    markdown_paths = sorted(
        path
        for path in (REPO / "Campaign").rglob("*.md")
        if "Assets" not in path.parts
    )
    relative_folder_set: set[Path] = set()
    for path in markdown_paths:
        parent = path.relative_to(REPO / "Campaign").parent
        while parent != Path("."):
            relative_folder_set.add(parent)
            parent = parent.parent
    relative_folders = sorted(
        relative_folder_set, key=lambda path: path.as_posix().casefold()
    )
    managed_folder_ids = set()
    desired_folders: dict[str, dict] = {}
    for ordinal, relative in enumerate(relative_folders, 1):
        folder_id, record = document_folder_record(relative, ordinal)
        managed_folder_ids.add(folder_id)
        desired_folders[folder_id] = record
        if current.get("assets", {}).get("documentFolders", {}).get(folder_id) != record:
            ops.append(
                {
                    "type": "put",
                    "store": "game",
                    "path": f"/assets/documentFolders/{folder_id}",
                    "data": record,
                }
            )
            descriptions.append(f"UPSERT Journal folder: {relative.as_posix()}")

    managed_doc_ids = set()
    desired_documents: dict[str, dict] = {}
    for ordinal, path in enumerate(markdown_paths, 1):
        doc_id, record = document_record(path, ordinal)
        managed_doc_ids.add(doc_id)
        desired_documents[doc_id] = record
        if document_table.get(doc_id) != record:
            ops.append(
                {
                    "type": "put",
                    "store": "game",
                    "path": f"/assets/objectTables/documents/table/{doc_id}",
                    "data": record,
                }
            )
            descriptions.append(
                f"IMPORT Markdown: {path.relative_to(REPO).as_posix()}"
            )
    for doc_id, record in document_table.items():
        if record.get("syncSource", "").startswith("Campaign/") and doc_id not in managed_doc_ids:
            ops.append(
                {
                    "type": "delete",
                    "store": "game",
                    "path": f"/assets/objectTables/documents/table/{doc_id}",
                }
            )
            descriptions.append(f"DELETE stale managed document: {record['syncSource']}")

    for folder_id, record in current.get("assets", {}).get("documentFolders", {}).items():
        if (
            record.get("syncSource", "").startswith("Campaign/")
            and folder_id not in managed_folder_ids
        ):
            ops.append(
                {
                    "type": "delete",
                    "store": "game",
                    "path": f"/assets/documentFolders/{folder_id}",
                }
            )
            descriptions.append(
                f"DELETE stale managed Journal folder: {record['syncSource']}"
            )

    missing_cache = [(source, target) for source, target in cache_copies if not target.exists()]
    for _, target in missing_cache:
        descriptions.append(f"COPY image cache: {target.name}")

    print(f"Draw Steel campaign: {args.game_id}")
    print(f"Repository Markdown documents: {len(markdown_paths)}")
    print(f"Managed Player portraits: {len(HEROES)}")
    print(f"Planned changes: {len(descriptions)}")
    for description in descriptions:
        print(f"  {description}")

    if not args.apply:
        print("Dry run only; pass --apply to synchronize.")
        return

    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup_path = db_path.with_name(f"game.db.before-repo-sync-{stamp}.backup")
    with sqlite3.connect(db_path) as source, sqlite3.connect(backup_path) as backup:
        source.backup(backup)

    for source, target in cache_copies:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    if ops:
        apply_ops(port, args.game_id, args.user_id, ops)
    firebase_patch(args.game_id, remote_patch)
    time.sleep(1.0)

    with sqlite3.connect(db_path) as db:
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise RuntimeError(f"SQLite integrity check failed: {integrity}")

    after = get_root_snapshot(port, args.game_id, args.user_id)
    remaining_legacy = [
        token
        for token in after.get("characters", {}).values()
        if token.get("partyid") == PREGENS_PARTY_ID
        or token.get("locInfo", {}).get("map") in LEGACY_MAP_IDS
    ]
    docs_after = (
        after.get("assets", {})
        .get("objectTables", {})
        .get("documents", {})
        .get("table", {})
    )
    folders_after = after.get("assets", {}).get("documentFolders", {})
    checks = {
        "four managed Players present": all(
            spec["id"] in after.get("characters", {}) for spec in HEROES.values()
        ),
        "source-backed Player levels synchronized": all(
            after.get("characters", {})
            .get(spec["id"], {})
            .get("properties", {})
            .get("classes", {})
            .get("1", {})
            .get("level")
            == forge_steel_level(REPO / spec["source"])
            for spec in HEROES.values()
            if spec.get("source") is not None
        ),
        "all Players share campaign progression": all(
            token.get("properties", {}).get("classes", {}).get("1", {}).get("level")
            == TARGET_LEVEL
            and token.get("properties", {}).get("xp") == TARGET_XP
            and token.get("properties", {}).get("victories") == TARGET_VICTORIES
            for token in (
                after.get("characters", {}).get(spec["id"], {})
                for spec in HEROES.values()
            )
        ),
        "all level 3 choices selected": all(
            after.get("characters", {})
            .get(spec["id"], {})
            .get("properties", {})
            .get("levelChoices", {})
            .get(spec["level3Choice"]["guid"], {})
            .get("1")
            == spec["level3Choice"]["id"]
            for spec in HEROES.values()
        ),
        "legacy entities removed": not remaining_legacy,
        "starter tavern maps removed": not (
            LEGACY_MAP_IDS & set(after.get("mapManifests", {}))
        ),
        "Capital placeholder map present": CAPITAL_MAP_ID in after.get("mapManifests", {}),
        "all Markdown documents imported": all(
            docs_after.get(doc_id) == record
            for doc_id, record in desired_documents.items()
        ),
        "Journal folders mirror repository": all(
            folders_after.get(folder_id) == record
            for folder_id, record in desired_folders.items()
        ),
        "SQLite integrity": integrity == "ok",
    }
    failed = [name for name, ok in checks.items() if not ok]
    for name, ok in checks.items():
        print(f"{'PASS' if ok else 'FAIL'} {name}")
    if failed:
        raise RuntimeError(f"post-sync verification failed: {', '.join(failed)}")
    print(f"APPLIED {len(ops)} Draw Steel data operations")
    print(f"BACKUP {backup_path}")


if __name__ == "__main__":
    main()
