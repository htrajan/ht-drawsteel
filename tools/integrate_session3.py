#!/usr/bin/env python3
"""Prepare Session 3 in the Steam app without changing hero resources.

The current engine uses an in-process SQLite server. Apply only while Draw
Steel is closed, take a SQLite backup, and let the app load the result normally.
Default is a read-only validation/preview. Reapplying preserves live tokens.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path

import sync_drawsteel_campaign as sync
import session3_cipher as cipher

REPO = sync.REPO
APP_DATA = sync.APP_DATA
SESSION = REPO / "Campaign/Act 2/Session 3.md"
SID = sync.stable_id
FOLDER = SID("session3:documents")
BESTIARY_FOLDER = SID("session3:bestiary")
NEGOTIATION = SID("session3:bellafonte-negotiation")
OFFICE_MAP = SID("session3:office-map")
OFFICE_FLOOR = SID("session3:office-floor")
OFFICE_LAYER = SID("session3:office-layer")
BELLAFONTE = "4078bff7-7679-4119-ab06-89c48e1daab7"
FENWICK = "57f2d0a0-ed32-4143-bf7e-1df12ce39663"
MAIN = "d19658a2-4d7b-4504-af9e-1a5410fb17fd"
MANEUVER = "a513b9a6-f311-4b0f-88b8-4e9c7bf92d0b"
TRIGGER = "b9bc06dd-80f1-4f33-bc55-25c114e3300c"
MALICE = "101bab52-7f7c-4bab-92c2-9f8e0cfb7ec8"
GROUP = SID("session3:loomworks-group")
SMOKE = SID("session3:smoke-keyword")
WATER = SID("session3:canal-keyword")


def arr(values):
    return {**{str(i): v for i, v in enumerate(values, 1)}, "_luaTable": False}


def typed(type_name, **kwargs):
    return {"__typeName": type_name, **kwargs, "_luaTable": True}


def command(rule, applyto="targets"):
    return typed("ActivatedAbilityDrawSteelCommandBehavior", rule=rule, applyto=applyto)


def script(code):
    return typed("ActivatedAbilityScriptBehavior", name="Session3", code=code)


def ability(name, description, *, action=MAIN, range=1, bonus=None, tiers=None,
            signature=False, keywords=(), target="target", count="1", cost=0,
            behaviors=(), limit=None, target_filter="", trigger=False):
    effects = list(behaviors)
    if tiers:
        effects.insert(0, typed("ActivatedAbilityPowerRollBehavior",
                               roll=f"2d10 + {bonus}", tiers=arr(tiers)))
    result = typed("ActivatedAbility", name=name, description=description,
                   guid=SID("session3:ability:" + name), iconid="ui-icons/skills/1.png",
                   actionResourceId=action, abilityType="none", range=range,
                   numTargets=count, repeatTargets=False, targetType=target,
                   targetFilter=target_filter, objectTarget=True,
                   keywords={**{k: True for k in keywords}, "_luaTable": True},
                   categorization="Signature Ability" if signature else "Malice" if cost else "Ability",
                   behaviors=arr(effects), modifiers=arr([]), strain=arr([]),
                   display={"brightness": 1, "bgcolor": "#ffffffff", "hueshift": 0,
                            "saturation": 1, "_luaTable": True},
                   effectImplemented=True, implementation=4)
    if cost:
        result.update(resourceCost=MALICE, resourceNumber=cost)
    if limit:
        result["usageLimitOptions"] = {"resourceRefreshType": limit, "charges": "1",
                                       "resourceid": SID("session3:usage:" + name), "_luaTable": True}
    if trigger:
        result["trigger"] = "strike"
    return result


def feature(name, description, modifiers=()):
    return typed("CharacterFeature", name=name, description=description, source="Session 3",
                 guid=SID("session3:trait:" + name), modifiers=arr(list(modifiers)),
                 implementation=4 if modifiers else 0)


def reaction(name, description, distance, **modifications):
    # The powertable trigger pays the triggered action. Its nested movement
    # behavior must not charge a second triggered action.
    before=ability(name,description,target="self",action="none",
                   behaviors=[script(f"Session3.Reaction(casterToken, '{name}', symbols)")])
    before["__typeName"]="TriggeredAbility"
    power=typed("CharacterModifier",name=name,behavior="power",guid=SID("session3:reaction-power:"+name),
                rollType="ability_power_roll",modtype="none",activationCondition=False,
                source="Trigger",hasTriggerBefore=True,triggerBefore=before,
                keywords={"Strike":True,"_luaTable":True},**modifications)
    return feature(name,description,[typed("CharacterModifier",name=name,description=description,
        behavior="powertabletrigger",guid=SID("session3:reaction:"+name),
        powerRollModifier=power,range=str(distance),targetType="ally",trigger="strike",
        type="trigger",rules=description,session3Reaction=True)])


def traits_from_script(text, heading, end):
    return text.split(heading, 1)[1].split(end, 1)[0].strip()


def monsters(text):
    """Native rolls/commands implement damage, potency, slides, pulls and conditions.

    Bespoke actions call the companion Lua controller, which uses native movement,
    zones, resource payments and reaction prompts rather than chat-only macros.
    """
    vale = [
        ability("Weighted Baton", "", bonus=2, signature=True, keywords=("Melee", "Strike", "Weapon"),
                tiers=["6 damage; slide 1", "10 damage; slide 2",
                       "14 damage; slide 3; A<2 slowed (EoT)"]),
        ability("Extraction Order", "One ally or Fenwick within 10 shifts up to 3 squares. Once per round.",
                action=MANEUVER, range=10, target_filter="not Enemy", limit="round",
                behaviors=[script("Session3.ShiftAlly(ability, casterToken, targets, symbols)")]),
        ability("Change Places", "Trigger: an adjacent ally is targeted by a strike. Swap with them and become the target, only if both destinations are legal. Once per round.",
                action=TRIGGER, range=1, target_filter="not Enemy", limit="round",
                behaviors=[command("swap places with the target", "caster")]),
        ability("Smoke Route", "A 3-cube within 8. Difficult terrain; strikes crossing more than one smoke square take a bane. Lasts until the start of Vale's next turn. Only one cloud at a time.",
                action=MANEUVER, range=8, cost=2, target="emptyspace",
                behaviors=[script("Session3.Smoke(casterToken, targets, 3, 'start')")]),
        ability("Move the Crew", "Up to three allies within 10 each move up to their speed, provoking free strikes normally. One may make a free strike after moving.",
                range=10, count="3", cost=4, target_filter="not Enemy",
                behaviors=[script("Session3.MoveCrew(ability, casterToken, targets, symbols)")]),
    ]
    enforcer = [
        ability("Boarding Hook", "At tier 3, if the target ends adjacent after the pull, they are grabbed.",
                range=2, bonus=2, signature=True, keywords=("Melee", "Strike", "Weapon"),
                tiers=["6 damage; pull 1", "10 damage; M<2 pull 2", "14 damage; M<3 pull 3"],
                behaviors=[script("Session3.HookGrab(ability, casterToken, targets, symbols)")]),
        ability("Bodyguard", "Triggered action, once per round: Fenwick or an adjacent ally is hit by a strike. Shift up to 2 to an unoccupied space adjacent to them, reduce that strike's damage by 4, and take 4 unpreventable damage. No legal destination means no trigger.",
                action=TRIGGER, range=3, target_filter="not Enemy", limit="round",
                behaviors=[script("Session3.Bodyguard(ability, casterToken, targets, symbols)")]),
        ability("Weighted Net", "", range=5, bonus=1, cost=3, keywords=("Ranged", "Weapon"),
                tiers=["4 damage", "6 damage; A<2 slowed (EoT)", "8 damage; A<3 slowed (EoT) and prone"]),
    ]
    yardhand = [
        ability("Hook, Net and Haul", "Shared squad roll. Each additional participating minion on the same target adds 3 damage; maximum three attackers.",
                range=2, bonus=1, signature=True, keywords=("Melee", "Strike", "Weapon"),
                tiers=["3 damage", "4 damage; pull 1", "5 damage; pull 2"]),
        ability("Smoke Pot", "Once per squad per encounter. Place a 2-cube within 5; difficult terrain and a bane for strikes crossing more than one smoke square. Ends at the end of this squad's next turn.",
                action=MANEUVER, range=5, target="emptyspace",
                behaviors=[script("Session3.Smoke(casterToken, targets, 2, 'end')")]),
        ability("Quick Hands", "Pick up an adjacent unattended ledger or satchel as a maneuver. Cannot take an object from a conscious unwilling creature.",
                action=MANEUVER, behaviors=[script("Session3.TakeEvidence(casterToken, targets)")]),
    ]
    common = feature("Paid Extraction", "Paid professionals, not cultists. Surrender when Vale falls and Fenwick is secured, or when extraction is impossible. At the end of round 4 surrender or withdraw; never add reinforcements.")
    definitions = {
        "irena-vale": ("Irena Vale — Blue-Wax Captain", 4, "Elite Controller", 20, 100, 5, 1, 5, [1, 2, 2, 2, 2], vale, [common]),
        "cleanup-enforcer": ("Cleanup Enforcer", 3, "Platoon Defender", 10, 65, 5, 2, 5, [2, 1, 0, 1, 0], enforcer,
            [common, feature("Hold the Route", "Melee free strikes deal 2 additional damage to a creature carrying the ledger or satchel. Other strikes are unaffected.", [typed("CharacterModifier", behavior="power", name="Hold the Route", guid=SID("session3:hold-route"), rollType="ability_power_roll", modtype="none", filterAbility="Ability.Free Strike", activationCondition='Target has "Evidence Carrier"', damageModifier="2", keywords={"Melee": True, "_luaTable": True})])]),
        "loomworks-yardhand": ("Loomworks Yardhand", 2, "Minion Harrier", 5, 9, 6, 0, 3, [1, 1, -1, 0, 0], yardhand, [common]),
        "bellafonte": ("Commissioner Ottaviano Bellafonte", 0, "Noncombatant", 0, 20, 5, 0, 0, [0, 0, 2, 1, 2], [], []),
        "fenwick": ("Rudiger Fenwick", 0, "Noncombatant", 0, 20, 5, 0, 0, [0, 1, 2, 1, 2], [
            ability("Release Mooring", "Main action adjacent to R11. Use Fenwick's key to release the mooring before lowering the gangplank.", target="self", behaviors=[script("Session3.EscapeStep(casterToken, 'mooring')")]),
            ability("Lower Gangplank", "Later main action adjacent to M11, after releasing the mooring. Then move aboard. Departure requires remaining aboard through the next Blue activation and cannot happen before round 3.", target="self", behaviors=[script("Session3.EscapeStep(casterToken, 'gangplank')")]),
        ], [feature("Noncombatant Fugitive", "No attacks or free strikes. Satchel starts carried. Key cannot be delegated. Officers catch him at the west street boundary. Actual movement, grabs and blockers govern escape.")]),
    }
    result = {}
    for key, (name, level, role, ev, hp, speed, stability, fs, stats, actions, feats) in definitions.items():
        if key=="irena-vale":
            description=actions[2]["description"]
            feats.append(reaction("Change Places",description,1,changeTarget=True,
                changeTargetRange="distance",changeTargetDistance=1,changeTargetFilter="Target = Triggerer",
                changeTargetEffect="all"))
            actions=[a for a in actions if a["name"]!="Change Places"]
        if key=="cleanup-enforcer":
            description=actions[1]["description"]
            feats.append(reaction("Bodyguard",description,3,damageReduction="4"))
            actions=[a for a in actions if a["name"]!="Bodyguard"]
            feats[1]["modifiers"]["1"]["activationCondition"]="Target.Session3 Evidence Carrier"
        result[key] = typed("monster", monster_type=name, monster_category="Monster", groupid=GROUP,
            cr=level, role=role, ev=ev, max_hitpoints=hp, damage_taken=0, walkingSpeed=speed,
            creatureSize="1M", stability=stability, opportunityAttack=fs,
            attributes={**{k: typed("CharacterAttribute", id=k, baseValue=v) for k, v in zip(["mgt", "agl", "rea", "inu", "prs"], stats)}, "_luaTable": True},
            minion=key=="loomworks-yardhand", withCaptain="-", keywords={"Humanoid": True, "_luaTable": True},
            innateActivatedAbilities=arr(actions), characterFeatures=arr(feats),
            resources=arr([]), equipment=arr([]), skillRatings=arr([]), savingThrowRatings=arr([]),
            innateAttacks=arr([]), levelChoices=arr([]), titles=arr([]), skillProficiencies=arr([]),
            notes=arr([{"title": "Complete Session 3 rules", "text": text[text.index("### Interactive terrain"):text.index("### Player-facing feedback")], "_luaTable": True}]))
    return result


def document(label, title, content, ordinal=0):
    return typed("MarkdownDocument", id=SID("session3:document:"+label), description=title,
                 parentFolder=FOLDER, content=content, updateid=hashlib.sha256(content.encode()).hexdigest(),
                 annotations=arr([]), docType="note", hidden=False, hiddenFromPlayers=True, ord=ordinal)


def read_store(db, key, default=None):
    row = db.execute("SELECT value FROM stores WHERE name=?", (key,)).fetchone()
    if not row:
        return copy.deepcopy(default)
    value = row[0] if isinstance(row[0], bytes) else row[0].encode()
    return json.loads(gzip.decompress(value[1:]) if value[0]==1 else value[1:])


def write_store(db, key, value):
    db.execute("INSERT OR REPLACE INTO stores(name,value) VALUES(?,?)",
               (key, b"\0"+json.dumps(value, separators=(",", ":")).encode()))


def loc(square, height=0):
    col=ord(square[0])-65
    row=int(square[1:])
    return [col-9,7-row,height]


def token(properties, portrait, name, square, grouping=None):
    result = {"appearance": {"portraitId": portrait, "offtokenPortraitId": portrait,
        "portraitFrameId": sync.PLAYER_TOKEN_FRAME_ID, "tokenScaling": 1, "tokenZoom": 1,
        "portraitOffset": {"x": 0, "y": 0}, "characterName": name, "characterNamePrivate": False,
        "frameHueShift": 0.57, "frameSaturation": 1, "frameBrightness": 1},
        "locInfo": {"map": sync.LIFT_YARD_MAP_ID, "floor": sync.LIFT_YARD_FLOOR_ID,
                    "loc": loc(square), "pos": {"x": 0, "y": 0}, "updateid": 1, "rotation": 0},
        "properties": copy.deepcopy(properties), "ownerId": None, "partyid": None,
        "size": 2, "settings": {"canRotate": False, "useLight": False},
        "updateid": SID("session3:token-update:"+name), "createdTimestamp": int(time.time()*1000)}
    result["properties"]["session3PlacementVersion"]=2
    if grouping:
        result["properties"]["initiativeGrouping"] = grouping
    return result


def prepare(db):
    text = SESSION.read_text()
    tables = read_store(db, "game::assets/objectTables", {})
    docs = tables.setdefault("documents", {}).setdefault("table", {})
    source_id, source_doc = sync.document_record(SESSION, 0)
    source_doc["parentFolder"] = FOLDER
    docs[source_id] = source_doc
    for i, section in enumerate(text.split("\n## Scene ")[1:]):
        title, _, body = section.partition("\n")
        docs[SID("session3:document:scene"+str(i+1))] = document("scene"+str(i+1), "Scene "+title, "## Scene "+section.split("\n## ",1)[0], i+1)
    ledger = text.split("> **O. Bellafonte — private receipts**",1)[1].split("\n\n“The last receipt”",1)[0]
    ledger = "# O. Bellafonte — private receipts\n"+"\n".join(line[2:] if line.startswith("> ") else "" if line==">" else line for line in ledger.splitlines())
    handouts = {
        "ledger": ("Evidence — Bellafonte's book and coded labels", ledger),
        "cipher": ("Evidence — Fenwick's encrypted letter", "# Fenwick's letter\n\n"+cipher.handout(text,"### Player handout — Fenwick's encrypted reply")),
        "reply": ("Handout — reconstruct the engram and write back", "# Your answer to Fenwick\n\n"+cipher.handout(text,"### Work out the engram")+"\n\nRecord more written/ordinary letter pairs as you find them.\n\nWrite the message you want Fenwick to receive, then encrypt it using the pairs you recovered.\n\nPlaintext:\n\nEncrypted message:\n"),
        "dispatch": ("Evidence — blue-wax satchel", "# Civic Loomworks and Festooning — dispatch abstracts\n\n| Dispatch | Charge | Routing |\n| --- | --- | --- |\n| CLF 18-441 | Dog-leg pump removal and reassignment | L.R.A. / 44-C |\n| CLF 18-447 | Foxes fountain stone and fitting | L.R.A. / 44-C |\n| CLF 18-452 | Factory oil and treated thread | L.R.A. / 44-C |\n\nScheduled transfer: One sealed Bureau of Accounts file. North records annex. Second bell after opening. Receiving name supplied separately."),
    }
    for i, (key,(title,content)) in enumerate(handouts.items(),20):
        docs[SID("session3:document:"+key)] = document(key,title,content,i)
    state_id=SID("session3:state")
    if state_id not in docs:
        docs[state_id]=document("state","Session 3 — live prop tracker","Director-only. Tracks props and map changes, not played session outcomes.",30)
        docs[state_id]["id"]=state_id
        docs[state_id]["session3State"]={"satchelCarrier":FENWICK,"_luaTable":True}
    portraits = {}
    images = read_store(db,"game::assets/images",{})
    copies = []
    for key in ["irena-vale", "cleanup-enforcer", "loomworks-yardhand", "bellafonte", "fenwick"]:
        source=REPO/f"Campaign/Assets/Tokens/{key}.png"
        asset,metadata,cache=sync.asset_for(source,1,"session3-"+key)
        metadata["keywords"]=["session3-"+key]
        images[asset]=metadata; portraits[key]=asset; copies.append((source,cache))
    office_asset,metadata,cache=sync.asset_for(REPO/"Campaign/Assets/Scenes/bellafonte-office.png",0,"bellafonte-office")
    metadata["keywords"]=["bellafonte-office"]
    images[office_asset]=metadata; copies.append((REPO/"Campaign/Assets/Scenes/bellafonte-office.png",cache))
    docs[NEGOTIATION] = typed("NegotiationDocument", id=NEGOTIATION, description="Bellafonte — willing help, not a confession gate", parentFolder=FOLDER,
        npcName="Commissioner Ottaviano Bellafonte", npcDesc="Frightened repairs commissioner, caught with false approvals.",
        portrait=portraits["bellafonte"], sceneImage=office_asset, attitude="suspicious", startInterest=2, startPatience=3, impression=3,
        opening="I can tell you who brought me the reports. Please let me sit down first.",
        stakes="Will Bellafonte appear as bait? He gives every core fact regardless of Interest. He cannot demand concessions. Obvious injury makes him unavailable.",
        traits=arr([{"id":SID("session3:motivation:"+name), "kind":kind, "name":name, "line":line, "_luaTable":True} for name,kind,line in [
            ("Protection","motivation","Fenwick has bought officers and clerks. Please keep him away from wherever Petrovic holds me."),
            ("Power","motivation","My testimony is important. I would appreciate being addressed as Commissioner."),
            ("Greed","motivation","A private room, clean clothes and decent food would help. I know I cannot insist on them."),
            ("Justice","pitfall","I know the residents suffered. Reminding me will not make me brave enough to face Fenwick.")]]),
        offers=arr([{"terms":"He gives the complete confession, book location, emergency phrase and old coded labels. "+("He will appear under guard if uninjured." if i>=3 else "He will write the note but will not face Fenwick."),"_luaTable":True} for i in range(6)]),
        summaries=arr([]), hidden=False, hiddenFromPlayers=True, docType="negotiation", ord=8)
    tables.setdefault("MonsterGroup",{}).setdefault("table",{})[GROUP]=typed("MonsterGroup",id=GROUP,name="Civic Loomworks retrieval crew",attacks=arr([]),traits=arr([]),maliceAbilities=arr([]),inherits={GROUP:True,"_luaTable":True},bandScope="band",description="Only printed Malice abilities. Paid professionals, not Unwritten cultists.")
    # Listing the group itself in inherits suppresses no defaults; the companion
    # Lua filter excludes unprinted fallback Malice for these five profiles.
    tables.setdefault("environmentalKeywords",{}).setdefault("table",{}).update({
        SMOKE:typed("EnvironmentalKeyword",id=SMOKE,name="Blue-wax smoke",description="Difficult terrain. Strikes crossing more than one square of this cloud take one bane.",difficultTerrain=True,defaultPlayerVisible=True,display={"bgcolor":"#94a3b8","_luaTable":True},modifiers=arr([])),
        WATER:typed("EnvironmentalKeyword",id=WATER,name="Canal water",description="Swimming is difficult terrain; quay ladders cost 2 movement per vertical square, bare quay 3.",water=True,difficultTerrain=True,defaultPlayerVisible=True,display={"bgcolor":"#3373d9","_luaTable":True},modifiers=arr([]))})
    folders=read_store(db,"game::assets/documentFolders",{})
    folders[FOLDER]={"description":"Session 3 — The Last Receipt", "parentFolder":"private", "ord":0,"hidden":False}
    bestiary=read_store(db,"game::assets/monsters",{})
    props=monsters(text)
    records={}; gblue=SID("session3:initiative:blue");ggray=SID("session3:initiative:gray");gwhite=SID("session3:initiative:white")
    for key,p in props.items():
        bid=SID("session3:monster:"+key)
        prototype=token(p,portraits[key],p["monster_type"],"I8")
        prototype["locInfo"]["map"]=None;prototype["bestiaryId"]=bid
        bestiary[bid]={"info":prototype,"description":p["monster_type"],"parentFolder":BESTIARY_FOLDER,"hidden":False,"ord":len(records),"ctime":int(time.time()*1000),"mtime":int(time.time()*1000)}
        records[key]=bid
    encounters=tables.setdefault("encounters",{}).setdefault("table",{})
    for ev,count in [(50,2),(60,3),(70,4),(80,5)]:
        eid=SID("session3:encounter:"+str(ev))
        encounters[eid]=typed("Encounter",id=eid,name=f"Session 3 — Blue-Wax Retrieval ({ev} EV)",groups=arr([
            {"monsters":{records["irena-vale"]:1,records["loomworks-yardhand"]:4,"_luaTable":True},"_luaTable":True},
            {"monsters":{records["cleanup-enforcer"]:(count+1)//2,"_luaTable":True},"_luaTable":True},
            {"monsters":{records["cleanup-enforcer"]:count//2,records["loomworks-yardhand"]:4,"_luaTable":True},"_luaTable":True}]),hidden=False)
    chars={}
    specs=[(SID("session3:token:vale"),"irena-vale","Irena Vale","L8",gblue),
           (SID("session3:token:enforcer1"),"cleanup-enforcer","Cleanup Enforcer 1","F7",ggray),
           (SID("session3:token:enforcer2"),"cleanup-enforcer","Cleanup Enforcer 2","N9",gwhite),
           (FENWICK,"fenwick","Rudiger Fenwick","K8",gblue)]
    for squad,squares,group in [("Blue",["C5","D5","C6","D6"],gblue),("White",["O8","P8","O9","P9"],gwhite)]:
        for i,square in enumerate(squares,1):specs.append((SID(f"session3:token:yardhand:{squad}:{i}"),"loomworks-yardhand",f"{squad} Yardhand {i}",square,group))
    for cid,key,name,square,group in specs:
        t=token(props[key],portraits[key],name,square,group);t["bestiaryId"]=records[key]
        if key=="loomworks-yardhand":t["properties"]["minionSquad"]=name.split()[0]+" Loomworks Squad"
        existing=read_store(db,"game::characters/"+cid)
        if existing and existing.get("bestiaryId")==records[key]:
            # Preserve played damage, resources, conditions, position and squad.
            for field in ["damage_taken","resources","inflictedConditions","ongoingEffects","minionSquad"]:
                if field in existing.get("properties",{}):t["properties"][field]=existing["properties"][field]
            if existing["properties"].get("session3PlacementVersion")==2:
                t["locInfo"]=existing.get("locInfo",t["locInfo"])
        chars[cid]=t
    bell=token(props["bellafonte"],portraits["bellafonte"],"Commissioner Bellafonte","I8")
    bell["locInfo"]={"map":OFFICE_MAP,"floor":OFFICE_FLOOR,"loc":[0,0,0],"updateid":1,"pos":{"x":0,"y":0}}
    bell["bestiaryId"]=records["bellafonte"]
    previous=read_store(db,"game::characters/"+BELLAFONTE)
    if previous and previous.get("bestiaryId")==records["bellafonte"]:
        bell["locInfo"]=previous["locInfo"]
        for field in ["damage_taken","resources","inflictedConditions","ongoingEffects"]:
            if field in previous.get("properties",{}):bell["properties"][field]=previous["properties"][field]
    chars[BELLAFONTE]=bell
    for imported in chars.values():
        position=imported.get("locInfo",{}).get("loc")
        if isinstance(position,dict):
            imported["locInfo"]["loc"]=[position.get(str(i),0) for i in range(3)]
    # Presentation map + the same image on the native negotiation stage.
    floor=sync.empty_floor(None,"Bellafonte's upstairs office",None)
    layer=sync.empty_floor(OFFICE_FLOOR,"Bellafonte's upstairs office","Scenery")
    manifest,details,surface=sync.capital_map_records(office_asset,metadata["imageId"])
    office_object=next(iter(details["floors"][sync.CAPITAL_LAYER_ID]["objects"].values()))
    office_object["components"]["CORE"]["scale"]=1.5625
    office_object["asset"]["components"]["CORE"]["scale"]=1.5625
    layer["objects"][SID("session3:office-object")]=office_object
    for f in [floor,layer]:f["mapSettings"]=sync.map_settings(grid_alpha=0)
    manifest.update(description="Session 3 — Bellafonte's Office",ord=0,defaultFloorId=OFFICE_FLOOR,
                    floors=[OFFICE_LAYER,OFFICE_FLOOR],dimMin=[-12,-8],dimMax=[12,8])
    writes={"game::assets/objectTables":tables,"game::assets/documentFolders":folders,
            "game::assets/images":images,"game::assets/monsters":bestiary,
            "game::assets/monsterFolders":{**read_store(db,"game::assets/monsterFolders",{}),BESTIARY_FOLDER:{"description":"Session 3 — Loomworks and captives","parentFolder":"","ord":0,"hidden":False}},
            "game::mapManifests/"+OFFICE_MAP:manifest,
            "mapdetails:"+OFFICE_MAP+"::root":{"floors":{OFFICE_FLOOR:floor,OFFICE_LAYER:layer}},
            "maps:"+OFFICE_MAP+"::root":surface}
    writes.update({"game::characters/"+cid:t for cid,t in chars.items()})
    yard=read_store(db,"mapdetails:"+sync.LIFT_YARD_MAP_ID+"::root")
    if not yard:raise ValueError("The calibrated lift-yard map is missing; do not invent a replacement.")
    wf=yard["floors"][sync.LIFT_YARD_FLOOR_ID]
    canal=[{"x":col-9,"y":7-row} for col in range(12) for row in range(12,15)]
    wf.setdefault("markupZones",{})[SID("session3:canal-zone")]=dict(name="Canal water",keyword=WATER,keywordName="Canal water",locs=arr(canal),altitude=0,height=1,playerVisible=False,pattern={"color":"#3373d9","angle":0},ord=0)
    writes["mapdetails:"+sync.LIFT_YARD_MAP_ID+"::root"]=yard
    # Repair overflowed animation stamps produced by the old playthrough, not
    # stats or resources. This is why Dorian and Bellafonte could disappear.
    for hero in sync.HEROES.values():
        cid=hero["id"];old=read_store(db,"game::characters/"+cid)
        if old:
            info=old.get("locInfo",{})
            changed=False
            if info.get("updateid",0)>2147483647:
                info["updateid"]=1;changed=True
            if isinstance(info.get("loc"),dict):
                info["loc"]=[info["loc"].get(str(i),0) for i in range(3)];changed=True
            if changed:writes["game::characters/"+cid]=old
    return writes,copies,records


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--game-id",default=sync.DEFAULT_GAME_ID)
    args=parser.parse_args()
    dbpath=APP_DATA/"local-games"/args.game_id/"game.db"
    if args.apply:
        procs=subprocess.run(["ps","-ax","-o","comm="],capture_output=True,text=True,check=True)
        if any(line.strip().endswith("/Contents/MacOS/Codex") for line in procs.stdout.splitlines()):
            raise SystemExit("Close Draw Steel before --apply; its server is now in-process.")
    with sqlite3.connect(dbpath) as db:
        writes,copies,records=prepare(db)
        print(json.dumps({"stores":len(writes),"portraits":len(records),"encounters":[50,60,70,80],"negotiation":NEGOTIATION,"runSheet":sync.document_record(SESSION,0)[0],"office":OFFICE_MAP,"heroResources":"unchanged"},indent=2))
        if not args.apply:return
        backup=dbpath.with_name(f"game.before-session3-{time.strftime('%Y%m%d-%H%M%S')}.db")
        with sqlite3.connect(backup) as dest:db.backup(dest)
        before={cid:read_store(db,"game::characters/"+cid)["properties"] for cid in [x["id"] for x in sync.HEROES.values()]}
        for source,dest in copies:shutil.copy2(source,dest)
        for key,value in writes.items():write_store(db,key,value)
        for cid,properties in before.items():assert read_store(db,"game::characters/"+cid)["properties"]==properties,"Hero changed!"
        db.commit()
        print("SESSION3_IMPORTED; BACKUP="+str(backup))


if __name__=="__main__":main()
