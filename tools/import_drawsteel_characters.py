#!/usr/bin/env python3
"""Import the four DS_Chars heroes into the local Draw Steel campaign database.

The Draw Steel app stores one NUL-prefixed JSON document per character in the
campaign SQLite `stores` table.  This script resolves all rule object IDs from
the installed streamed core module instead of hard-coding version-specific IDs.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import time
import unicodedata
import uuid
from pathlib import Path


APP_DATA = Path.home() / "Library/Application Support/MCDM/Codex"
GAME_ID = "3365ac8c-e59c-48ff-9ec1-6a5c334e121d"
PLAYER_PARTY_ID = "0339ff3e-f288-4a85-a02c-a458c091684f"
HERO_TYPE_ID = "be5f5f52-b2cc-4033-ae16-6a4d25e10c2e"
GAME_DB = APP_DATA / "local-games" / GAME_ID / "game.db"
MODULE_JSON = (
    APP_DATA
    / "cache"
    / "module-streamed-c6304b28-ecf8-4c2e-ad71-1753ef4f817e.json"
)


def normalized(value: str) -> str:
    value = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    return "".join(ch for ch in value if ch.isalnum())


def lua_values(table: dict | None) -> list:
    if not table:
        return []
    return [
        table[key]
        for key in sorted(
            (key for key in table if str(key).isdigit()), key=lambda key: int(key)
        )
    ]


def lua_array(values: list[str]) -> dict:
    result = {str(index): value for index, value in enumerate(values, 1)}
    result["_luaTable"] = False
    return result


class Rules:
    def __init__(self, module_path: Path):
        module = json.loads(module_path.read_text())
        self.tables = module["assets"]["objectTables"]

    def item(self, table: str, name: str) -> dict:
        candidates = [
            item
            for item in self.tables[table]["table"].values()
            if isinstance(item, dict)
            and normalized(item.get("name", "")) == normalized(name)
        ]
        if not candidates:
            raise KeyError(f"{table}: no item named {name!r}")
        visible = [item for item in candidates if not item.get("hidden")]
        return (visible or candidates)[0]

    def item_id(self, table: str, name: str) -> str:
        return self.item(table, name)["id"]

    def features(self, item: dict, level: int | None = None) -> list[dict]:
        if "modifierInfo" in item:
            return lua_values(item["modifierInfo"].get("features"))
        levels = item.get("levels", {})
        keys = ["tutoriallevel-1", "tutoriallevel-2", "tutoriallevel-3", "tutoriallevel-4"]
        if level is not None:
            keys.extend(f"level-{n}" for n in range(1, level + 1))
        result = []
        for key in keys:
            result.extend(lua_values((levels.get(key) or {}).get("features")))
        return result

    def all_nested(self, features: list[dict]) -> list[dict]:
        result = []
        for feature in features:
            result.append(feature)
            result.extend(self.all_nested(lua_values(feature.get("features"))))
        return result

    def choice(self, features: list[dict], name: str) -> dict:
        candidates = [
            feature
            for feature in self.all_nested(features)
            if "Choice" in feature.get("__typeName", "")
            and normalized(feature.get("name", "")) == normalized(name)
        ]
        if len(candidates) != 1:
            raise KeyError(f"choice {name!r}: expected one match, found {len(candidates)}")
        return candidates[0]

    def option_id(self, choice: dict, option_name: str) -> str:
        options = [
            option
            for option in lua_values(choice.get("options"))
            if normalized(option.get("name", "")) == normalized(option_name)
        ]
        if len(options) != 1:
            raise KeyError(
                f"{choice.get('name')}: option {option_name!r}, found {len(options)}"
            )
        return options[0]["guid"]


class HeroBuilder:
    def __init__(self, rules: Rules, spec: dict):
        self.rules = rules
        self.spec = spec
        self.choices: dict[str, list[str] | str] = {}

        self.race = rules.item("races", spec["ancestry"])
        self.career = rules.item("careers", spec["career"])
        self.hero_class = rules.item("classes", spec["class"])
        self.subclass = rules.item("subclasses", spec["subclass"])

    def add(self, choice_guid: str, selected_id: str) -> None:
        current = self.choices.setdefault(choice_guid, [])
        assert isinstance(current, list)
        current.append(selected_id)

    def add_item(self, choice: dict, table: str, item_name: str) -> None:
        self.add(choice["guid"], self.rules.item_id(table, item_name))

    def add_option(self, choice: dict, option_name: str) -> None:
        self.add(choice["guid"], self.rules.option_id(choice, option_name))

    def add_named_items(
        self, features: list[dict], choice_name: str, table: str, names: list[str]
    ) -> None:
        choice = self.rules.choice(features, choice_name)
        for name in names:
            self.add_item(choice, table, name)

    def add_named_options(
        self, features: list[dict], choice_name: str, names: list[str]
    ) -> None:
        choice = self.rules.choice(features, choice_name)
        for name in names:
            self.add_option(choice, name)

    def build_choices(self) -> dict:
        spec = self.spec
        race_features = self.rules.features(self.race)
        class_features = self.rules.features(self.hero_class, spec["level"])
        subclass_features = self.rules.features(self.subclass, spec["level"])
        career_features = self.rules.features(self.career)

        # Ancestry feature options and skills.
        if spec.get("ancestry_options"):
            feature_choice = next(
                f
                for f in race_features
                if f.get("__typeName") == "CharacterFeatureChoice"
            )
            for name in spec["ancestry_options"]:
                self.add_option(feature_choice, name)
        if spec.get("ancestry_skills"):
            skill_choice = next(
                f
                for f in race_features
                if f.get("__typeName") == "CharacterSkillChoice"
            )
            for name in spec["ancestry_skills"]:
                self.add_item(skill_choice, "Skills", name)

        # Culture language and each aspect's selected skill.
        if spec.get("culture_languages"):
            self.choices["cultureLanguageChoice"] = [
                self.rules.item_id("languages", name)
                for name in spec["culture_languages"]
            ]
        for aspect_kind, aspect in spec["culture"].items():
            aspect_item = self.rules.item("cultureAspects", aspect["name"])
            aspect_features = self.rules.features(aspect_item)
            choice = next(
                f
                for f in aspect_features
                if f.get("__typeName") == "CharacterSkillChoice"
            )
            self.add_item(choice, "Skills", aspect["skill"])

        # Career has a few special option choices plus skills/languages/perks.
        for choice_name, option_names in spec.get("career_options", {}).items():
            self.add_named_options(career_features, choice_name, option_names)
        for choice_name, names in spec.get("career_skills", {}).items():
            self.add_named_items(career_features, choice_name, "Skills", names)
        for choice_name, names in spec.get("career_languages", {}).items():
            self.add_named_items(career_features, choice_name, "languages", names)
        for choice_name, names in spec.get("career_perks", {}).items():
            self.add_named_items(career_features, choice_name, "feats", names)

        # Class, subclass, ability, skill, and perk selections.
        subclass_choice = next(
            f
            for f in class_features
            if f.get("__typeName") == "CharacterSubclassChoice"
        )
        self.add(subclass_choice["guid"], self.subclass["id"])
        for choice_name, option_names in spec.get("class_options", {}).items():
            self.add_named_options(class_features, choice_name, option_names)
        for choice_name, names in spec.get("class_skills", {}).items():
            self.add_named_items(class_features, choice_name, "Skills", names)
        for choice_name, names in spec.get("class_perks", {}).items():
            self.add_named_items(class_features, choice_name, "feats", names)
        for choice_name, option_names in spec.get("subclass_options", {}).items():
            self.add_named_options(subclass_features, choice_name, option_names)
        for choice_name, names in spec.get("subclass_skills", {}).items():
            self.add_named_items(subclass_features, choice_name, "Skills", names)

        result = {"raceid": self.race["id"], "_luaTable": True}
        for guid, selections in self.choices.items():
            assert isinstance(selections, list)
            result[guid] = lua_array(selections)
        return result

    def build_properties(self) -> dict:
        spec = self.spec
        attributes = {
            short: {
                "__typeName": "CharacterAttribute",
                "baseValue": spec["attributes"][short],
                "id": short,
                "_luaTable": True,
            }
            for short in ("mgt", "rea", "agl", "prs", "inu")
        }
        attributes["_luaTable"] = True

        aspects = {
            kind: self.rules.item_id("cultureAspects", value["name"])
            for kind, value in spec["culture"].items()
        }
        aspects["_luaTable"] = True

        properties = {
            "__typeName": "character",
            "attributes": attributes,
            "chartypeid": HERO_TYPE_ID,
            "damage_taken": 0,
            "skillProficiencies": {"_luaTable": False},
            "savingThrowProficiencies": {"_luaTable": False},
            "inventory": {"_luaTable": False},
            "equipment": {"_luaTable": False},
            "innateAttacks": {"_luaTable": False},
            "classes": {
                "1": {
                    "classid": self.hero_class["id"],
                    "level": spec["level"],
                    "_luaTable": True,
                },
                "_luaTable": False,
            },
            "raceid": self.race["id"],
            "backgroundid": self.career["id"],
            "culture": {
                "__typeName": "Culture",
                "aspects": aspects,
                "_luaTable": True,
            },
            "levelChoices": self.build_choices(),
            "characterDescription": {
                "__typeName": "CharacterDescription",
                "_luaTable": True,
            },
            "_luaTable": True,
        }
        if spec.get("kit"):
            properties["kitid"] = self.rules.item_id("kits", spec["kit"])
        if spec.get("kit2"):
            properties["kitid2"] = self.rules.item_id("kits", spec["kit2"])
        if spec.get("complication"):
            properties["complicationid"] = self.rules.item_id(
                "complications", spec["complication"]
            )
        if spec.get("incident"):
            properties["notes"] = {
                "1": {
                    "title": "Inciting Incident",
                    "text": spec["incident"],
                    "_luaTable": True,
                },
                "_luaTable": False,
            }
        return properties

    def build_token(self) -> tuple[str, dict]:
        character_id = str(uuid.uuid4())
        name = self.spec["name"]
        token = {
            "locInfo": {
                "mountedOn": None,
                "mountedOnObject": None,
                "mountedSaddle": 0,
                "floor": None,
                "map": None,
                "summonLoc": {},
                "rotation": 0,
            },
            "appearance": {
                "portraitId": None,
                "offtokenPortraitId": None,
                "portraitFrameId": None,
                "portraitRibbon": None,
                "backgroundId": None,
                "anthem": None,
                "anthemVolume": 1,
                "tokenScaling": 1,
                "tokenZoom": 1,
                "portraitOffset": {"x": 0, "y": 0},
                "frameHueShift": 0,
                "frameSaturation": 1,
                "frameBrightness": 1,
                "characterName": name,
                "characterNamePrivate": False,
                "flip": False,
                "saddlePositions": {},
            },
            "disguise": None,
            "settings": {
                "canRotate": False,
                "useLight": False,
                "lightColor": {"r": 1, "g": 1, "b": 1, "a": 1},
                "lightIntensity": 0.1,
                "lightRadius": 10,
                "lightFalloff": 0.1,
                "lightAngle": 360,
            },
            "mountedBy": {},
            "updateid": character_id,
            "properties": self.build_properties(),
            "tokenType": None,
            "bestiaryId": None,
            "summonerid": None,
            "ownerId": "PARTY",
            "partyid": PLAYER_PARTY_ID,
            "size": -1,
            "createdTimestamp": int(time.time() * 1000),
        }
        return character_id, token


SPECS = [
    {
        "name": "Demona",
        "ancestry": "Devil",
        "ancestry_options": ["Beast Legs", "Prehensile Tail"],
        "ancestry_skills": ["Brag"],
        "class": "Null",
        "subclass": "Disciple of the Chronokinetic",
        "level": 3,
        "attributes": {"mgt": 1, "agl": 2, "rea": 0, "inu": 2, "prs": 0},
        "culture_languages": ["Anjali"],
        "culture": {
            "environment": {"name": "Urban", "skill": "Lie"},
            "organization": {"name": "Bureaucratic", "skill": "Lead"},
            "upbringing": {"name": "Academic", "skill": "Criminal Underworld"},
        },
        "career": "Politician",
        "career_skills": {
            "Politician Interpersonal Skill": ["Read Person", "Sneak"]
        },
        "career_languages": {"Politician Language": ["Axiomatic"]},
        "career_perks": {"Politician Interpersonal Perk": ["Charming Liar"]},
        "class_options": {
            "Signature Abilities": ["Joint Lock", "Magnetic Strike"],
            "3-Discipline Heroic Abilities": ["Relentless Nemesis"],
            "5-Discipline Heroic Abilities": ["Impart Force"],
            "Psionic Augmentation": ["Density Augmentation"],
            "7-Discipline Heroic Abilities": ["Molecular Rearrangement Field"],
        },
        "class_skills": {"Skills": ["Persuade", "Flirt"]},
        "class_perks": {"Perk": ["Gum Up the Works"]},
        "subclass_options": {"2nd-Level Chronokinetic Abilities Choice": ["Blur"]},
        "subclass_skills": {"Chronokinetic Lore Skill": ["Rumors"]},
        "complication": "Chaos Touched",
        "incident": (
            "**Right Side of History:** You used your influence to expose a "
            "government's corruption or prevent a tyrant's rise, and became a hero."
        ),
    },
    {
        "name": "Dorian Ashveil",
        "ancestry": "Revenant",
        "ancestry_options": ["Undead Influence"],
        "class": "Tactician",
        "subclass": "Vanguard",
        "level": 3,
        "attributes": {"mgt": 2, "agl": 0, "rea": 2, "inu": 0, "prs": 1},
        "culture_languages": [],
        "culture": {
            "environment": {"name": "Nomadic", "skill": "Navigate"},
            "organization": {"name": "Bureaucratic", "skill": "Lie"},
            "upbringing": {"name": "Martial", "skill": "Alertness"},
        },
        "career": "Performer",
        "career_options": {"Music or Performance Skill": ["Perform Skill"]},
        "career_skills": {
            "Performer Interpersonal Skills": ["Read Person", "Interrogate"]
        },
        "career_perks": {"Performer Interpersonal Perk": ["Power Player"]},
        "class_options": {
            "3-Focus Heroic Abilities": ["Concussive Strike"],
            "5-Focus Heroic Abilities": ["Hammer and Anvil"],
            "7-Focus Heroic Abilities": ["Hit 'Em Hard!"],
        },
        "class_skills": {"Skills": ["Strategy", "Search"]},
        "class_perks": {"Perk": ["Charming Liar"]},
        "subclass_options": {
            "2nd-Level Vanguard Ability": ["No Dying on My Watch"]
        },
        "subclass_skills": {"Vanguard Interpersonal Skill": ["Intimidate"]},
        "kit": "Shining Armor",
        "kit2": "Warrior Priest",
        "incident": (
            "**Cursed Audience:** During a performance, your audience was overcome "
            "by a curse and disintegrated. You became a hero while seeking answers."
        ),
    },
    {
        "name": "Keth",
        "ancestry": "Hakaan",
        "ancestry_options": ["Forceful", "Great Fortitude"],
        "class": "Fury",
        "subclass": "Berserker",
        "level": 3,
        "attributes": {"mgt": 2, "agl": 2, "rea": 0, "inu": 0, "prs": 1},
        "culture_languages": ["Vhoric"],
        "culture": {
            "environment": {"name": "Rural", "skill": "Monsters"},
            "organization": {"name": "Communal", "skill": "Lift"},
            "upbringing": {"name": "Labor", "skill": "Blacksmithing"},
        },
        "career": "Explorer",
        "career_skills": {
            "Explorer Exploration Skills": ["Endurance", "Climb"]
        },
        "career_languages": {
            "Explorer Languages": ["High Kuric", "Vastariax"]
        },
        "career_perks": {"Explorer Exploration Perk": ["Friend Catapult"]},
        "class_options": {
            "Signature Ability": ["Brutal Slam"],
            "3-Ferocity Heroic Abilities": ["Back!"],
            "5-Ferocity Heroic Abilities": ["Thunder Roar"],
            "7-Ferocity Abilities": ["You Are Already Dead"],
        },
        "class_skills": {"Skills": ["Alertness", "Track"]},
        "class_perks": {"Perk": ["I've Got You"]},
        "subclass_options": {"2nd-Level Berserker Ability": ["Wrecking Ball"]},
        "kit": "Mountain",
        "incident": (
            "**Awakening:** In an uncharted area, you awakened a dark horror. "
            "You became a hero to end what you unleashed and guard other dangers."
        ),
    },
    {
        "name": "M.A.C: Multifunctional Android Companion",
        "ancestry": "Memonek",
        "ancestry_options": ["Unphased", "Useful Emotion", "Keeper of Order"],
        "class": "Troubadour",
        "subclass": "Duelist",
        "level": 2,
        "attributes": {"mgt": 1, "agl": 2, "rea": -1, "inu": 1, "prs": 2},
        "culture_languages": ["Axiomatic"],
        "culture": {
            "environment": {"name": "Nomadic", "skill": "Persuade"},
            "organization": {"name": "Communal", "skill": "Blacksmithing"},
            "upbringing": {"name": "Academic", "skill": "Rumors"},
        },
        "career": "Performer",
        "career_options": {"Music or Performance Skill": ["Perform Skill"]},
        "career_skills": {"Performer Interpersonal Skills": ["Flirt", "Brag"]},
        "career_perks": {"Performer Interpersonal Perk": ["Pardon My Friend"]},
        "class_options": {
            "Signature Ability": ["Witty Banter"],
            "3-Drama Heroic Abilities": ["Harsh Critic"],
            "5-Drama Heroic Abilities": ["Dramatic Reversal"],
            "Invocation": ["Allow Me to Introduce Tonight's Players"],
        },
        "class_skills": {
            "Interpersonal Skills": ["Read Person", "Empathize", "Lie"],
            "Intrigue or Lore Skill": ["Search"],
        },
        "class_perks": {"Perk": ["Charming Liar"]},
        "subclass_options": {
            "2nd-level Duelist Ability": ["Classic Chandelier Stunt"]
        },
        "kit": "Swashbuckler",
        "complication": "Grifter",
        "incident": "**Fame and Fortune:** Your talent brought acclaim and opportunity.",
    },
]


def existing_hero_names(connection: sqlite3.Connection) -> dict[str, str]:
    result = {}
    for key, value in connection.execute(
        "SELECT name, value FROM stores WHERE name LIKE 'game::characters/%'"
    ):
        try:
            token = json.loads(bytes(value)[1:])
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        name = token.get("appearance", {}).get("characterName")
        if name:
            result[normalized(name)] = key
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply", action="store_true", help="write records after validating them"
    )
    args = parser.parse_args()

    rules = Rules(MODULE_JSON)
    built = [HeroBuilder(rules, spec).build_token() for spec in SPECS]

    with sqlite3.connect(GAME_DB) as connection:
        existing = existing_hero_names(connection)
        duplicates = [
            spec["name"] for spec in SPECS if normalized(spec["name"]) in existing
        ]
        if duplicates:
            raise SystemExit(f"already present; refusing duplicate import: {duplicates}")

        print(f"Campaign database: {GAME_DB}")
        print(f"Target party: {PLAYER_PARTY_ID}")
        for (character_id, token), spec in zip(built, SPECS):
            properties = token["properties"]
            choice_count = sum(
                1
                for key in properties["levelChoices"]
                if key not in {"raceid", "_luaTable"}
            )
            print(
                f"VALID {spec['name']}: level {spec['level']} "
                f"{spec['ancestry']} {spec['class']} ({choice_count} choice groups)"
            )

        if not args.apply:
            print("Dry run only; pass --apply to write the four records.")
            return

        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup = GAME_DB.with_name(f"game.db.before-character-import-{stamp}.backup")
        backup_connection = sqlite3.connect(backup)
        connection.backup(backup_connection)
        backup_connection.close()

        connection.execute("BEGIN IMMEDIATE")
        for character_id, token in built:
            key = f"game::characters/{character_id}"
            encoded = b"\x00" + json.dumps(
                token, separators=(",", ":"), ensure_ascii=False
            ).encode("utf-8")
            connection.execute(
                "INSERT INTO stores(name, value) VALUES (?, ?)", (key, encoded)
            )
        connection.commit()

        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity check failed: {integrity}")

        now_present = existing_hero_names(connection)
        missing = [
            spec["name"]
            for spec in SPECS
            if normalized(spec["name"]) not in now_present
        ]
        if missing:
            raise RuntimeError(f"post-write verification missing: {missing}")

        print(f"APPLIED 4 character records")
        print(f"BACKUP {backup}")
        print("INTEGRITY ok")


if __name__ == "__main__":
    main()
