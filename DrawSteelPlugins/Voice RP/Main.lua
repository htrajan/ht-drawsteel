-- Draw Steel Code Mod: Voice RP.
-- Register this file through Compendium > Code Mods before linking a git folder.
-- The browser records speech; the local bridge writes the hero and NPC lines
-- to the current game's chat. This panel is just the in-app launch point.

local mod = dmhub.GetModLoading()

DockablePanel.Register{
    name = "Voice RP",
    icon = "phosphor/microphone-light.png",
    minHeight = 120,
    dmonly = true,
    content = function()
        return gui.Panel{
            width = "100%",
            height = "auto",
            flow = "vertical",
            children = {
                gui.Label{
                    text = "Speak as a hero to the active NPC",
                    width = "100%",
                    height = "auto",
                    fontSize = 16,
                },
                gui.Label{
                    text = "Choose a hero and record in the local voice panel. Both lines appear in Draw Steel chat.",
                    width = "100%",
                    height = "auto",
                    textWrap = true,
                },
                gui.Button{
                    text = "Open Voice RP",
                    width = 180,
                    height = 32,
                    click = function()
                        dmhub.OpenURL("http://127.0.0.1:8765/")
                    end,
                },
            },
        }
    end,
}

-- Campaign companion. Registered in the existing mod, not an empty extra mod.
-- The import tool installs native documents, maps, bestiary and encounter data.
Session3 = rawget(_G,"Session3") or {}
local S3 = Session3
S3.ids = {
    script = "59b11f49-ccaf-5c69-b873-e4fd26f5ff58",
    negotiation = "54f774d8-e0cd-5d92-8f32-ba83cadf8c1c",
    office = "01b0f643-4dcd-5c02-9747-9cdf4713133e",
    yard = "98912355-f847-5850-974a-7a4e089118b9",
    yardFloor = "23622c4d-e077-5c96-aaf2-3f3bad5d4258",
    state = "004189c9-fc34-53c0-90ca-911655b2dbde",
    group = "62f438b2-3c9c-5dbe-b290-2db6d0c42bf5",
    smoke = "3a078c8c-44bd-5e17-a230-02e0aab672f0",
    fenwick = "57f2d0a0-ed32-4143-bf7e-1df12ce39663",
    vale = "299145b4-5fd0-5df8-836a-302ffe964406",
}
S3.scenes = {
    {"1. Bellafonte — 0:00–0:20", "4c8cc9b1-a3ec-5df4-aea7-921244832607"},
    {"2. Hanae and Melvin — 0:20–0:30", "2ab02683-5eb2-5717-ab71-30ce0be20e10"},
    {"3. Cipher and preparation — 0:30–1:15", "e8a8556b-4098-502c-8512-89adc47c9736"},
    {"4. Exchange — 1:15–1:25", "871c84f3-927f-586c-b459-5244e26ec2c5"},
    {"5. Retrieval — 1:25–2:00", "a39d7d62-c6b1-5523-803f-daf7f20447ce"},
    {"6. Evidence and cistern — 2:00–2:15", "fa9da36d-36b6-51f9-a0a2-b57f392e110c"},
}
S3.handouts = {
    {"Bellafonte's book / engram", "bc405cb4-a582-5011-ab41-ca78f6debca8"},
    {"Encrypted letter", "6ecb4990-fa07-5e1f-bfc9-589faf6958e9"},
    {"Compose a reply", "c9e2efb9-1a42-533e-be34-79e5a4ee2111"},
    {"Satchel dispatches", "7680c219-18e9-59e4-9de9-b69a76e16ddb"},
}

function S3.Notice(text)
    S3.message = text
    print("SESSION3:: " .. text)
end

function S3.State()
    local doc = dmhub.GetTable("documents")[S3.ids.state]
    return doc and DeepCopy(doc:try_get("session3State", {})) or {}
end

function S3.Save(state)
    local doc = DeepCopy(dmhub.GetTable("documents")[S3.ids.state])
    if doc == nil then S3.Notice("Session 3 state document is not installed."); return end
    doc.session3State = state
    dmhub.SetAndUploadTableItem("documents", doc)
end

function S3.Doc(id)
    local doc = dmhub.GetTable("documents")[id]
    if doc then doc:ShowDocument() else S3.Notice("Document missing: " .. id) end
end

function S3.BeginNegotiation(hostPanel)
    assert(not NegotiationRun.Live(), "A negotiation is already live; present it instead")
    local doc=dmhub.GetTable("documents")[S3.ids.negotiation]
    assert(doc, "Bellafonte negotiation is missing")
    if not doc:try_get("hiddenFromPlayers",false) then
        doc.hiddenFromPlayers=true; doc:Upload()
    end
    local live=LiveNegotiation.FromDocument(doc)
    -- The office is a presentation map. Keep the campaign's four heroes at
    -- their existing positions, but include them at the conversation table.
    live.roster={}
    for _,id in ipairs({"b8edfa57-0947-4dfb-b3b9-6c03c7e615de",
        "f67884c1-3a6b-4296-8d88-a7274367c177",
        "0779cf60-c9bd-49de-b769-bf5aacdc832d",
        "0a9de43e-3e2e-43a6-8d11-7fdb483148fa"}) do
        local hero=dmhub.GetCharacterById(id)
        assert(hero and hero.properties:IsHero(), "A Session 3 hero is missing")
        live.roster[#live.roster+1]={charid=id,name=hero.name}
    end
    NegotiationRun.Log(live,"","","The negotiation with "..live.npcName.." begins.","system")
    GameHud.PresentDialogToUsers(hostPanel,"negotiation",{docid=doc.id},live)
end

function S3.Map(id)
    for _, map in ipairs(game.maps) do
        if map.id == id then game.ChangeMap(map); return end
    end
    S3.Notice("Map missing: " .. id)
end

function S3.Square(square)
    return core.Loc{x=string.byte(square, 1)-65-9, y=7-tonumber(square:sub(2)), floorIndex=game.currentFloorIndex}
end

function S3.Zone(id, name, keyword, locs, height, visible)
    game.currentFloor:SetMarkupZone(id, {
        name=name, keyword=keyword, keywordName=name, locs=locs,
        altitude=0, height=height or 1, playerVisible=visible ~= false,
        pattern={color="#8796b4", angle=45}, ord=0,
    })
end

local function rectangle(a, b)
    local p, q = S3.Square(a), S3.Square(b)
    return {p.x,p.y+1,q.x+1,p.y+1,q.x+1,q.y,p.x,q.y}
end

local function tiles(a, b)
    local p, q = S3.Square(a), S3.Square(b)
    local result = {}
    for x=p.x,q.x do for y=q.y,p.y do result[#result+1]={x=x,y=y} end end
    return result
end

function S3.PrepareTerrain()
    if game.currentMapId ~= S3.ids.yard then S3.Notice("Open the lift yard first."); return end
    local state=S3.State()
    if state.terrain then S3.Notice("Native terrain is already installed; it has not been reset."); return end
    local floor=game.currentFloor
    if not floor.supportsSolidOperations then S3.Notice("This engine does not support solid markup."); return end
    floor:ExecutePolygonOperation{points={rectangle("A1","R14")}, tileid="-MGAVDxkFE-ZzzNYBV0D", floor=true}
    -- Top-down art stays unchanged; native solids supply elevation, cover and pathing.
    floor:ExecutePolygonOperation{points={rectangle("F3","N5")}, tileid="-MGAVDxkFE-ZzzNYBV0D", wallid="eae7f3fe-d278-455c-853a-ac43f948c743", wallheight=2, solid=true, walls=true, floor=true}
    for _,pair in ipairs({{"C3","E3"},{"C8","E8"},{"O6","Q6"}}) do
        floor:ExecutePolygonOperation{points={rectangle(pair[1],pair[2])}, tileid="-MGAVDxkFE-ZzzNYBV0D", wallid="eae7f3fe-d278-455c-853a-ac43f948c743", wallheight=1, solid=true, walls=true, floor=true}
    end
    state.terrain=true; state.bridge=false; state.crane="gantry"
    S3.Save(state)
    S3.Notice("Floor, two-square-high gantry, scenery and canal rules are ready. Climb the marked stairs normally.")
end

function S3.Bridge()
    if game.currentMapId ~= S3.ids.yard then S3.Notice("Open the lift yard first."); return end
    local state=S3.State()
    state.bridge=not state.bridge
    game.currentFloor:ExecutePolygonOperation{
        points={rectangle("L9","N11")}, tileid="-MGAVDxkFE-ZzzNYBV0D",
        wallid="eae7f3fe-d278-455c-853a-ac43f948c743", wallheight=2,
        solid=true, walls=true, floor=true, erase=not state.bridge, eraseInvisibleOnly=true,
    }
    S3.Save(state)
    S3.Notice(state.bridge and "Bridge raised. Maneuver at K9; place bridge occupants on their chosen side without damage." or "Bridge lowered. Maneuver at K9; passage restored.")
end

function S3.Crane()
    local state=S3.State()
    state.crane = state.crane=="quay" and "gantry" or "quay"
    S3.Save(state)
    S3.Zone("session3-platform", "Cargo platform: "..state.crane, "", tiles(state.crane=="quay" and "J9" or "J4", state.crane=="quay" and "K10" or "K5"), 1)
    S3.Notice("Platform destination: "..state.crane..". Maneuver at F8; move platform occupants at the end of the acting turn.")
end

function S3.Tip(a,b)
    if game.currentMapId ~= S3.ids.yard then S3.Notice("Open the lift yard first."); return end
    game.currentFloor:ExecutePolygonOperation{points={rectangle(a,b)}, tileid="-MGAVDxkFE-ZzzNYBV0D", wallid="eae7f3fe-d278-455c-853a-ac43f948c743", erase=true, eraseInvisibleOnly=true, solid=true, walls=true, floor=false}
    local difficult=dmhub.GetTable("environmentalKeywords")
    local keyword=""
    for id,k in pairs(difficult) do if k.name=="Difficult Terrain" then keyword=id; break end end
    S3.Zone("session3-tipped-"..a, "Tipped scenery", keyword, tiles(a,b),1)
    S3.Notice("Scenery tipped. Main action; apply 4 damage and push 1 minus Stability to creatures in the line. The line is difficult terrain and provides cover.")
end

function S3.Smoke(caster, targets, size, ending)
    local target=targets[1]
    local center=target and (target.loc or target.token and target.token.loc)
    if not center then S3.Notice("Choose a smoke destination."); return end
    local state=S3.State(); state.clouds=state.clouds or {}
    local squad=caster.properties:MinionSquad()
    local owner=size==2 and squad or caster.charid
    if size==2 then
        state.usedPots=state.usedPots or {}
        if state.usedPots[owner] then S3.Notice("This squad has used its smoke pot this encounter."); return end
        state.usedPots[owner]=true
    end
    local id="session3-smoke-"..owner
    local locs={}
    for x=0,size-1 do for y=0,size-1 do locs[#locs+1]={x=center.x+x,y=center.y+y} end end
    local q=dmhub.initiativeQueue
    state.clouds[id]={owner=caster.charid, squad=squad, ending=ending, round=q and q.round or 0, turn=q and q.turn or 0, locs=locs}
    S3.Zone(id,"Blue-wax smoke",S3.ids.smoke,locs,size)
    S3.Save(state)
    S3.Notice("Smoke placed. One bane for a strike crossing more than one smoke square; no additional concealment. The panel removes it on the specified next turn.")
end

function S3.Invoke(ability, caster, actor, name, distance, symbols)
    local standard=MCDMUtils.GetStandardAbility(name)
    if not standard then S3.Notice("Native standard ability missing: "..name); return end
    local clone=standard:MakeTemporaryClone()
    clone.actionResourceId="none"; clone.resourceCost="none"; clone.disableSquadCoordination=true
    if distance then
        MCDMUtils.DeepReplace(clone,"<<distance>>",tostring(distance))
        MCDMUtils.DeepReplace(clone,"<<range>>",tostring(distance))
        clone.range=distance
    end
    clone.invoker=caster.properties
    return ActivatedAbilityInvokeAbilityBehavior.ExecuteInvoke(caster,clone,actor,"prompt",symbols or {},{})
end

function S3.MoveCrew(ability, caster, targets, symbols)
    for _,target in ipairs(targets) do
        if target.token then S3.Invoke(ability,caster,target.token,"Move",target.token.properties:CurrentMovementSpeed(),symbols) end
    end
    S3.Notice("Crew movement resolved. Select one moved ally and use its native free strike, if desired; no other ally gets a strike.")
end

function S3.ShiftAlly(ability, caster, targets, symbols)
    for _,target in ipairs(targets) do
        if target.token then S3.Invoke(ability,caster,target.token,"Shift",3,symbols) end
    end
end

function S3.HookGrab(ability, caster, targets, symbols)
    local cast=symbols and symbols.cast
    for _,target in ipairs(targets) do
        local tok=target.token
        local tier=cast and (cast:try_get("tokenToTier",{})[tok and tok.charid] or cast.tier) or 0
        if tok and tier==3 and tok.properties:AttributeForPotencyResistance("mgt")<3 and caster:Distance(tok)<=1 then
            for id,cond in pairs(dmhub.GetTable(CharacterCondition.tableName)) do
                if string.lower(cond.name)=="grabbed" then
                    tok:ModifyProperties{description="Boarding Hook grab",execute=function()
                        tok.properties:InflictCondition(id,{duration="eoe",casterInfo={tokenid=caster.charid},cast=cast})
                    end}
                    break
                end
            end
        end
    end
end

function S3.Reaction(caster, name, symbols)
    local target=S3.reactionTargets and S3.reactionTargets[caster.charid]
    if not target or not target.valid then S3.Notice("The triggering ally is no longer available."); return end
    if name=="Change Places" then
        if caster:Distance(target)<=1 then caster:SwapPositions(target) end
    elseif name=="Bodyguard" then
        S3.Invoke(nil,caster,caster,"Shift",2,symbols)
        if caster:Distance(target)<=1 then
            caster:ModifyProperties{description="Bodyguard: 4 unpreventable damage",execute=function() caster.properties:TakeDamage(4,"Bodyguard") end}
        else
            S3.Notice("Bodyguard was declined or ended nonadjacent. Do not apply the damage-reduction modifier.")
        end
    end
end

function S3.EscapeStep(caster, step)
    local state=S3.State()
    local square=step=="mooring" and "R11" or "M11"
    if caster.loc:DistanceInTiles(S3.Square(square))>1 then S3.Notice("Fenwick must be adjacent to "..square.."."); return end
    if state.keyTaken or state.jammed or state.mechanismBroken then S3.Notice("The key or mooring mechanism prevents this action."); return end
    if step=="gangplank" and not state.mooring then S3.Notice("Fenwick must release the mooring in an earlier main action."); return end
    local q=dmhub.initiativeQueue
    if step=="gangplank" and state.mooringTurn==(q and q.turn or 0) then S3.Notice("The gangplank requires a later main action."); return end
    state[step]=true
    if step=="mooring" then state.mooringTurn=q and q.turn or 0
    else state.boardAfterTurn=q and q.turn or 0 end
    S3.Save(state)
    S3.Notice(step=="mooring" and "Mooring released. Fenwick still needs a later main action at M11." or "Gangplank lowered. Move Fenwick aboard; he must remain there until the next Blue activation ends, no earlier than round 3.")
end

function S3.TakeEvidence(caster)
    local state=S3.State()
    if not state.ledgerCarrier and caster.loc:DistanceInTiles(S3.Square(state.ledgerSquare or "I8"))<=1 then
        state.ledgerCarrier=caster.charid; S3.Save(state); S3.Notice("The unattended ledger is now carried by "..creature.GetTokenDescription(caster)..".")
    else S3.Notice("Select evidence custody in the panel. A conscious unwilling carrier must be grabbed or made unconscious first.") end
end

function S3.Tick()
    if not dmhub.isDM or game.currentMapId~=S3.ids.yard then return end
    local q=dmhub.initiativeQueue
    if not q then return end
    local state=S3.State(); local changed=false
    local current=q.currentTurn
    local active=current and InitiativeQueue.GetTokensForInitiativeId(current,dmhub.allTokens) or {}
    local activeIds={}; for _,t in ipairs(active) do activeIds[t.charid]=true end
    for id,c in pairs(state.clouds or {}) do
        local seen=activeIds[c.owner] and q.turn>c.turn
        if c.ending=="start" and seen or c.ending=="end" and c.nextTurn and q.turn>c.nextTurn then
            game.currentFloor:RemoveMarkupZone(id); state.clouds[id]=nil; changed=true
        elseif c.ending=="end" and seen and not c.nextTurn then c.nextTurn=q.turn; changed=true end
    end
    if q.round>=4 then S3.Notice("Round 4: finish this round, then hirelings surrender or withdraw. No reinforcements.") end
    if changed then S3.Save(state) end
end

-- Keep native reaction prompts and roll modifiers; add only campaign-specific
-- eligibility. Other monsters and character sheets use untouched core behavior.
if not S3.hooksInstalled then
    S3.hooksInstalled=true
    GameSystem.RegisterGoblinScriptField{
        target=creature, name="Session3 Evidence Carrier", type="boolean",
        desc="Carries the Session 3 ledger or satchel.",
        calculate=function(c)
            local t=dmhub.LookupToken(c); local s=S3.State()
            return t and (s.ledgerCarrier==t.charid or s.satchelCarrier==t.charid) or false
        end,
    }
    local baseFill=monster.FillMonsterActivatedAbilities
    monster.FillMonsterActivatedAbilities=function(self,options,result)
        if self:try_get("groupid")==S3.ids.group then
            if self:try_get("role")~="Noncombatant" and not options.excludeGlobal then self:FillFreeStrikes(options,result) end
            return
        end
        return baseFill(self,options,result)
    end
    local basePrepare=ActivatedAbility.PrepareTargets
    ActivatedAbility.PrepareTargets=function(self,caster,symbols,targets)
        local result=basePrepare(self,caster,symbols,targets)
        if caster.properties:try_get("groupid")==S3.ids.group and caster.properties.minion then
            for _,target in ipairs(result) do target.numAttackers=math.min(3,target.numAttackers or 1) end
        end
        return result
    end
    local baseTrigger=CharacterModifier.TypeInfo.powertabletrigger.applyTriggerToPowerRoll
    CharacterModifier.TypeInfo.powertabletrigger.applyTriggerToPowerRoll=function(self,token,caster,target,ability,roll,options)
        if self:try_get("session3Reaction") then
            if self.name=="Bodyguard" and target.charid~=S3.ids.fenwick and token:Distance(target)>1 then return false end
            if self.name=="Change Places" and token:Distance(target)>1 then return false end
            S3.reactionTargets=S3.reactionTargets or {}; S3.reactionTargets[token.charid]=target
        end
        return baseTrigger(self,token,caster,target,ability,roll,options)
    end
end

DockablePanel.Register{
    name="Session 3", icon="phosphor/book-open-light.png", dmonly=true, minHeight=400,
    content=function()
        local children={gui.Label{text="THE LAST RECEIPT · Director",fontSize=20,width="100%",height="auto"}}
        local function button(label,action)
            children[#children+1]=gui.Button{text=label,width="100%",height=30,click=action}
        end
        button("Full session script",function() S3.Doc(S3.ids.script) end)
        button("Pin script to left rail",function() IconRailDocAdd(S3.ids.script,"left") end)
        for _,entry in ipairs(S3.scenes) do local e=entry; button(e[1],function() S3.Doc(e[2]) end) end
        button("Bellafonte's office",function() S3.Map(S3.ids.office) end)
        button("Negotiation preparation",function() S3.Doc(S3.ids.negotiation) end)
        button("Begin Bellafonte negotiation",function(element) S3.BeginNegotiation(element) end)
        button("Open lift yard",function() S3.Map(S3.ids.yard) end)
        button("Install native yard terrain once",S3.PrepareTerrain)
        children[#children+1]=gui.Label{text="Player-safe handouts — review before sharing",height="auto",width="100%"}
        for _,entry in ipairs(S3.handouts) do
            local e=entry
            children[#children+1]=gui.Panel{width="100%",height=30,flow="horizontal",
                gui.Button{text=e[1],width="75%",height=28,click=function() S3.Doc(e[2]) end},
                gui.Button{text="Share",width="25%",height=28,click=function(element) GameHud.PresentDialogToUsers(element,"document",{docid=e[2]}) end},
            }
        end
        button("Winch: raise / lower bridge",S3.Bridge)
        button("Crane: change platform destination",S3.Crane)
        button("Tip west castle scenery C3–E3",function() S3.Tip("C3","E3") end)
        button("Tip dragon scenery C8–E8",function() S3.Tip("C8","E8") end)
        button("Tip sun scenery O6–Q6",function() S3.Tip("O6","Q6") end)
        button("Undo Fenwick's mooring release",function() local s=S3.State();s.mooring=false;S3.Save(s);S3.Notice("Mooring resecured; spend the acting hero's main action.") end)
        button("Key taken / returned",function() local s=S3.State();s.keyTaken=not s.keyTaken;S3.Save(s);S3.Notice(s.keyTaken and "Key secured. Fenwick cannot release the mooring." or "Key returned to Fenwick.") end)
        button("Mechanism jammed / cleared",function() local s=S3.State();s.jammed=not s.jammed;S3.Save(s);S3.Notice(s.jammed and "Mechanism jammed; spend a maneuver and suitable held object." or "Mechanism cleared.") end)
        button("Ledger → selected token / ground",function()
            local s=S3.State(); local t=dmhub.selectedTokens[1]
            s.ledgerCarrier=t and t.charid or nil
            if t then S3.Notice("Ledger custody: "..creature.GetTokenDescription(t)) else S3.Notice("Ledger unattended. Verify its map square.") end
            S3.Save(s)
        end)
        button("Satchel → selected token / ground",function()
            local s=S3.State(); local t=dmhub.selectedTokens[1]; s.satchelCarrier=t and t.charid or "ground";S3.Save(s)
            S3.Notice(t and "Satchel custody: "..creature.GetTokenDescription(t) or "Satchel unattended.")
        end)
        children[#children+1]=gui.Label{
            text="135 minutes of play + 15-minute buffer. Do not begin combat or award Victories during setup. Bespoke story rulings remain with the Director.",
            width="100%",height="auto",textWrap=true,fontSize=13,
        }
        children[#children+1]=gui.Label{
            width="100%",height="auto",textWrap=true,fontSize=14,
            thinkTime=0.5, think=function(element)
                S3.Tick(); element.text=S3.message or "Ready. No Session 3 outcomes have been recorded."
            end,
        }
        return gui.Panel{width="100%",height="100%",flow="vertical",vscroll=true,children=children}
    end,
}

dmhub.RegisterEventHandler("EnterGame",function()
    if mod.unloaded or not dmhub.isDM then return end
    dmhub.Schedule(1,function()
        if mod.unloaded or not dmhub.GetTable("documents")[S3.ids.script] then return end
        IconRailDocAdd(S3.ids.script,"left")
        local panel=PanelDocument.Get("Session 3")
        if panel then panel:PresentPanel{width=440,height=820} end
        local state=S3.State()
        if not state.officePresented then
            state.officePresented=true;S3.Save(state)
            S3.Map(S3.ids.office)
        end
        S3.Notice("Session 3 companion loaded. Script pinned; office, negotiation, handouts and combat controls available.")
    end)
end)

-- Typed, local-only script tools. Commands never evaluate supplied Lua and
-- never patch a running game's SQLite store. Native APIs own all mutations.
DrawSteelScriptTools = rawget(_G,"DrawSteelScriptTools") or {}
local ST=DrawSteelScriptTools
ST.handlers={}
ST.writes={}
local function tool(name,write,fn) ST.handlers[name]=fn; ST.writes[name]=write end
local function required(args,key)
    assert(type(args[key])=="string" and #args[key]>0,"Missing string argument: "..key)
    return args[key]
end
local function documentFor(args)
    local doc=dmhub.GetTable("documents")[required(args,"id")]
    assert(doc,"Document does not exist")
    return doc
end
local function tokenFor(args)
    local token=dmhub.GetTokenById(required(args,"id"))
    assert(token and token.valid,"Token is not deployed on the current map")
    return token
end
local function tokenInfo(token)
    local p=token.properties
    local abilities={}
    for _,a in ipairs(p:GetActivatedAbilities{}) do
        abilities[#abilities+1]={name=a.name,guid=a.guid,range=a.range,
            action=a.actionResourceId,description=a.description,behaviors=a.behaviors,
            cost=a:try_get("resourceNumber",0),resource=a:try_get("resourceCost")}
    end
    return {id=token.charid,name=token.name,loc={x=token.loc.x,y=token.loc.y,floor=token.loc.floor,altitude=token.loc.altitude},
        properties=p,abilities=abilities,playerControlled=token.playerControlled}
end
tool("ping",false,function() return {game_id=dmhub.gameid,director=dmhub.isDM,version=dmhub.version,protocol=1} end)
tool("list_maps",false,function()
    local result={}
    for _,m in ipairs(game.maps) do result[#result+1]={id=m.id,name=m.description,defaultFloor=m.defaultFloorId} end
    return {current=game.currentMapId,maps=result}
end)
tool("list_documents",false,function()
    local result={}
    for id,d in pairs(dmhub.GetTable("documents")) do
        if not d:try_get("hidden",false) then result[#result+1]={id=id,name=d.description,type=d.typeName,private=d:try_get("hiddenFromPlayers",false),folder=d.parentFolder} end
    end
    return result
end)
tool("read_document",false,function(args) return documentFor(args) end)
tool("list_tokens",false,function()
    local result={}
    for _,t in ipairs(dmhub.allTokens) do result[#result+1]={id=t.charid,name=t.name,x=t.loc.x,y=t.loc.y,minion=t.properties.minion,squad=t.properties:MinionSquad(),group=InitiativeQueue.GetInitiativeId(t)} end
    return {map=game.currentMapId,tokens=result}
end)
tool("inspect_token",false,function(args) return tokenInfo(tokenFor(args)) end)
tool("session3_status",false,function()
    local documents=dmhub.GetTable("documents")
    local profiles={}
    for id,entry in pairs(assets.monsters) do
        local p=entry.info and entry.info.properties
        if p and p:try_get("groupid")==S3.ids.group then
            profiles[#profiles+1]={id=id,name=p.monster_type,level=p.cr,ev=p.ev,
                stamina=p.max_hitpoints,speed=p.walkingSpeed,stability=p.stability,
                abilities=p.innateActivatedAbilities,features=p.characterFeatures}
        end
    end
    return {game_id=dmhub.gameid,current_map=game.currentMapId,script=documents[S3.ids.script],
        negotiation=documents[S3.ids.negotiation],state=S3.State(),profiles=profiles,
        session_panel=PanelDocument.Get("Session 3")~=nil,live_negotiation=NegotiationRun.Live()}
end)
tool("open_document",true,function(args) documentFor(args):ShowDocument();return {opened=args.id} end)
tool("pin_document",true,function(args) documentFor(args);IconRailDocAdd(args.id,"left");return {pinned=args.id} end)
tool("open_panel",true,function(args)
    local p=PanelDocument.Get(required(args,"name"));assert(p,"Unknown native panel")
    p:PresentPanel();return {opened=args.name}
end)
tool("select_tokens",true,function(args)
    assert(type(args.ids)=="table" and #args.ids<=20,"Supply at most 20 token IDs")
    local result={};for _,id in ipairs(args.ids) do result[#result+1]=tokenFor{id=id} end
    dmhub.selectedTokens=result;return {selected=#result}
end)
tool("switch_map",true,function(args)
    local id=required(args,"id");local found=false
    for _,m in ipairs(game.maps) do if m.id==id then game.ChangeMap(m);found=true;break end end
    assert(found,"Unknown map")
    local deadline=dmhub.Time()+10
    while game.currentMapId~=id and dmhub.Time()<deadline do coroutine.yield(0.1) end
    assert(game.currentMapId==id,"Map transition did not finish")
    return {map=id}
end)
tool("begin_negotiation",true,function(args)
    local doc=documentFor(args);assert(doc.typeName=="NegotiationDocument","Not a negotiation document")
    assert(not NegotiationRun.Live(),"A negotiation is already live; present it rather than resetting it")
    if doc.id==S3.ids.negotiation then S3.BeginNegotiation(GameHud.instance.documentsPanel)
    else NegotiationRun.Begin(doc,GameHud.instance.documentsPanel) end
    return {begun=doc.id,interest=doc.startInterest,patience=doc.startPatience}
end)
tool("hide_negotiation",true,function() NegotiationRun.Hide();return {hidden=true} end)
tool("present_negotiation",true,function() assert(NegotiationRun.Live(),"No live negotiation");NegotiationRun.Present(GameHud.instance.documentsPanel);return {presented=true} end)
tool("prepare_yard",true,function()
    assert(game.currentMapId==S3.ids.yard,"Switch to the yard first")
    S3.PrepareTerrain();assert(S3.State().terrain,"Terrain installation failed")
    return {terrain=true,floor=game.currentFloorId}
end)
tool("show_office",true,function() S3.Map(S3.ids.office);return {office=S3.ids.office} end)
tool("bridge",true,function() S3.Bridge();return {raised=S3.State().bridge} end)
tool("crane",true,function() S3.Crane();return {destination=S3.State().crane} end)
tool("cast_ability",true,function(args)
    local caster=tokenFor{id=required(args,"caster")}
    local name=required(args,"ability");local ability
    for _,a in ipairs(caster.properties:GetActivatedAbilities{}) do if a.name==name then ability=a;break end end
    assert(ability,"Ability not found on this creature")
    assert(ability:CanAfford(caster),"Creature cannot afford this ability")
    local queue=dmhub.initiativeQueue
    if queue and not queue.hidden then
        assert(InitiativeQueue.GetInitiativeId(caster)==queue:CurrentInitiativeId(),"Creature is not in the active initiative group")
    end
    local range=ability:GetRange(caster.properties)
    local filter=string.lower(ability:try_get("targetFilter","") or "")
    assert(filter=="" or filter=="enemy" or filter=="not enemy","This custom target filter is not supported by scripted casting")
    local targets={}
    for _,id in ipairs(args.targets or {}) do
        local target=tokenFor{id=id}
        assert(caster:Distance(target)<=range,"Target is out of range")
        if filter=="enemy" then assert(not caster:IsFriend(target),"Target is not an enemy") end
        if filter=="not enemy" then assert(caster:IsFriend(target),"Target is not an ally") end
        targets[#targets+1]={token=target}
    end
    for _,loc in ipairs(args.locations or {}) do
        assert(type(loc.x)=="number" and type(loc.y)=="number","Invalid target location")
        local destination=core.Loc{x=loc.x,y=loc.y,floorIndex=game.currentFloorIndex}
        assert(caster.loc:DistanceInTiles(destination)<=range,"Location is out of range")
        targets[#targets+1]={loc=destination}
    end
    assert(#targets>0 or ability.targetType=="self","Specify targets")
    assert(#targets<=ability:GetNumTargets(caster,{}),"Too many targets")
    local result=ActivatedAbilityInvokeAbilityBehavior.ExecuteInvoke(caster,ability:MakeTemporaryClone(),caster,"args",{}, {targetArgs=targets})
    return {ability=name,native_result=result or false}
end)

function ST.Poll()
    if mod.unloaded then return end
    if not ST.nextHeartbeat or dmhub.Time()>=ST.nextHeartbeat then
        ST.nextHeartbeat=dmhub.Time()+5
        dmhub.WriteTextFile("script-tools","heartbeat.json",dmhub.ToJson{
            protocol=1,game_id=dmhub.gameid,director=dmhub.isDM,time_ms=dmhub.serverTimeMilliseconds,
        })
    end
    if ST.busy or not dmhub.gameid or dmhub.gameid=="" then return end
    for _,path in ipairs(dmhub.GetTextFilePaths("script-tools/requests") or {}) do
        local req=dmhub.ParseJsonFile(path)
        local id=req and req.id
        if id and id:match("^[0-9a-f%-]+$") and #id==36 then
            local results=dmhub.GetTextFilePaths("script-tools/results") or {}
            local cancels=dmhub.GetTextFilePaths("script-tools/cancelled") or {}
            local already=false
            for _,p in ipairs(results) do if p:find(id,1,true) then already=true end end
            for _,p in ipairs(cancels) do if p:find(id,1,true) then already=true end end
            if not already and req.game_id==dmhub.gameid then
                ST.busy=true
                dmhub.WriteTextFile("script-tools/results",id..".json",dmhub.ToJson{id=id,status="running"})
                dmhub.Coroutine(function()
                    local ok,result=pcall(function()
                        assert(req.protocol==1,"Unsupported protocol")
                        assert(dmhub.isDM,"Director mode is required")
                        assert(type(req.expires_ms)=="number" and req.expires_ms>=dmhub.serverTimeMilliseconds,"Request expired")
                        local fn=ST.handlers[req.command];assert(fn,"Unsupported native tool")
                        assert(not ST.writes[req.command] or req.allow_write==true,"Mutation was not explicitly authorized")
                        return fn(req.args or {})
                    end)
                    local response={id=id,status=ok and "ok" or "error"}
                    if ok then response.result=result else response.error=tostring(result) end
                    local encodedOK,encoded=pcall(dmhub.ToJson,response)
                    if not encodedOK then encoded=dmhub.ToJson{id=id,status="error",error="Native result serialization failed"} end
                    dmhub.WriteTextFile("script-tools/results",id..".json",encoded)
                    ST.busy=false
                end)
                break
            end
        end
    end
end

dmhub.Coroutine(function()
    while not mod.unloaded do
        local ok,err=pcall(ST.Poll)
        if not ok then print("SCRIPTTOOLS:: "..tostring(err)) end
        coroutine.yield(0.5)
    end
end)
