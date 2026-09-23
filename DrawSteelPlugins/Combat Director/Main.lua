-- Draw Steel Code Mod: Combat Director.
-- Requires the Monster AI Code Mod. The model selects from moves that Monster
-- AI has scored as legal for the selected enemy. Execution scores the chosen
-- move again and uses Monster AI's own cast/trigger pipeline.

local mod = dmhub.GetModLoading()
local endpoint = "http://127.0.0.1:8765/api/suggest"

local function findAbilityByName(abilities, name)
    for _,ability in ipairs(abilities) do
        if ability.name == name then return ability end
    end
    return nil
end

local function currentActor()
    if not dmhub.isDM or MonsterAI == nil then
        return nil, "Director access and Monster AI are required."
    end
    if MonsterAI.IsAIRunning() then
        return nil, "Stop automatic Monster AI before using this panel."
    end
    local selected = dmhub.selectedTokens or {}
    if #selected ~= 1 then
        return nil, "Select one enemy token."
    end
    local token = selected[1]
    if not token.valid or token.playerControlled or token.properties == nil
        or not token.properties:has_key("monster_type") then
        return nil, "Select one live non-player monster."
    end
    local queue = dmhub.initiativeQueue
    if queue == nil or queue.hidden then
        return nil, "Start combat first."
    end
    local initiativeid = InitiativeQueue.GetInitiativeId(token)
    if initiativeid == nil or initiativeid ~= queue:CurrentInitiativeId() then
        return nil, "Select a monster in the active initiative group."
    end
    if not MonsterAI.TokenIsLiveCombatant(token) then
        return nil, "This monster can no longer act."
    end
    return token, nil
end

local function buildCandidates(token)
    local ai = MonsterAI.new{}
    ai:SetupCombatants(token, dmhub.initiativeQueue)
    ai.paths = ai:CalculateRemainingMovementPaths(token)
    local candidates = {}
    local public = {}

    if token.properties.minion then
        ai.squadMembers = {}
        local squadid = token.properties:MinionSquad()
        local initiativeid = InitiativeQueue.GetInitiativeId(token)
        for _,member in ipairs(InitiativeQueue.GetTokensForInitiativeId(initiativeid) or {}) do
            if MonsterAI.TokenIsLiveCombatant(member) and member.properties.minion
                and member.properties:MinionSquad() == squadid then
                ai.squadMembers[#ai.squadMembers+1] = {token = member}
            end
        end
        ai.squad = {}
        for _,ability in ipairs(ai.abilities) do
            if ability.categorization == "Signature Ability" and ability:CanAfford(token) then
                local loc, score = ai:FindBestMoveToUseStrike(token, ability)
                if loc ~= nil and type(score) == "number" and score > 0 then
                local candidate = { id = "minion-signature", ability = ability }
                candidates[candidate.id] = candidate
                public[#public+1] = { id = candidate.id, ability = ability.name,
                    plan = "Coordinated minion signature strike", score = score }
                break
                end
            end
        end
    else
        for id,move in pairs(ai.moves) do
            if ai.MoveMatchesMonster(token, move) then
                local abilities = {}
                local legal = true
                for _,name in ipairs(move.abilities or {}) do
                    local ability = findAbilityByName(ai.abilities, name)
                    if ability == nil or not ability:CanAfford(token) then
                        legal = false
                        break
                    end
                    abilities[#abilities+1] = ability
                end
                if legal then
                    local ok, score = pcall(move.score, move, ai, token,
                        abilities[1], abilities[2], abilities[3])
                    if ok and type(score) == "table" and type(score.score) == "number"
                        and score.score > 0 then
                        local names = {}
                        for _,ability in ipairs(abilities) do
                            names[#names+1] = ability.name
                        end
                        candidates[id] = { id = id, move = move, score = score,
                            abilities = abilities }
                        public[#public+1] = { id = id, ability = table.concat(names, ", "),
                            plan = ai.ScoringPlanLogName(score), score = score.score }
                    end
                end
            end
        end
    end
    table.sort(public, function(a, b) return a.id < b.id end)
    return ai, candidates, public
end

DockablePanel.Register{
    name = "Combat Director",
    icon = "phosphor/sparkle-light.png",
    minHeight = 160,
    dmonly = true,
    content = function()
        local pending = nil
        local status = gui.Label{
            text = "Select the active enemy, then ask for a suggestion.",
            width = "100%", height = "auto", textWrap = true,
        }
        local reason = gui.Label{
            text = "", width = "100%", height = "auto", textWrap = true,
        }
        local executeButton

        local function setStatus(value)
            if mod.unloaded then return end
            status.text = value
        end

        executeButton = gui.Button{
            text = "Execute suggested move",
            width = 210, height = 32, enabled = false,
            click = function()
                local token, err = currentActor()
                if token == nil then setStatus(err); return end
                if pending == nil or pending.tokenid ~= token.charid
                    or pending.initiativeid ~= dmhub.initiativeQueue:CurrentInitiativeId() then
                    setStatus("The turn changed. Ask for a new suggestion.")
                    executeButton.enabled = false
                    return
                end
                local ai, candidates, public = buildCandidates(token)
                local candidate = candidates[pending.moveid]
                if candidate == nil then
                    setStatus("That move is no longer legal. Ask again.")
                    executeButton.enabled = false
                    return
                end
                local currentPlan = nil
                for _,item in ipairs(public) do
                    if item.id == pending.moveid then currentPlan = item.plan end
                end
                if currentPlan ~= pending.plan then
                    setStatus("The tactical plan changed. Ask for a new suggestion.")
                    executeButton.enabled = false
                    return
                end
                executeButton.enabled = false
                pending = nil
                setStatus("Executing " .. candidate.id .. "...")
                DockablePanel.StartProcess{
                    panel = "Combat Director",
                    id = "combat-director-execute",
                    coroutine = function(process)
                        if process.stopRequested or mod.unloaded then return end
                        local executed = false
                        local ok, failure
                        if candidate.id == "minion-signature" then
                            local controls = {}
                            local controlOk, controlFailure = pcall(function()
                                for _,member in ipairs(ai.squadMembers) do
                                    controls[#controls+1] = {
                                        token = member.token,
                                        info = ai:BeginTokenControl(member.token),
                                    }
                                end
                            end)
                            if controlOk then
                                ok, failure = ai:RunYieldingFunction(function()
                                    executed = ai:ExecuteSquadStrike(candidate.ability)
                                end)
                            else
                                ok, failure = false, controlFailure
                            end
                            for i=#controls,1,-1 do
                                local item = controls[i]
                                local endOk, endFailure = pcall(function()
                                    ai:EndTokenControl(item.token, item.info)
                                end)
                                if not endOk then ok, failure = false, endFailure end
                            end
                        else
                            ok, failure = ai:RunWithTokenControl(token, function()
                                executed = candidate.move.execute(candidate.move, ai, token,
                                    candidate.score, candidate.abilities[1],
                                    candidate.abilities[2], candidate.abilities[3])
                            end)
                        end
                        if ok and executed ~= false and ai:try_get("_tmp_moveFailure") == nil then
                            setStatus("Move executed. Resolve any player reactions in the app.")
                        else
                            setStatus("Execution stopped: " .. tostring(failure
                                or ai:try_get("_tmp_moveFailure") or "move returned false"))
                        end
                    end,
                }
            end,
        }

        local suggestButton = gui.Button{
            text = "Suggest action (Sol high)",
            width = 210, height = 32,
            click = function()
                local token, err = currentActor()
                if token == nil then setStatus(err); return end
                local ai, candidates, public = buildCandidates(token)
                if #public == 0 then
                    setStatus("No scored legal Monster AI move for this actor.")
                    return
                end
                pending = nil
                executeButton.enabled = false
                setStatus("Asking Sol high to choose among " .. tostring(#public) .. " legal moves...")
                local initiativeid = dmhub.initiativeQueue:CurrentInitiativeId()
                net.Post{
                    url = endpoint,
                    timeout = 240,
                    data = {
                        actor = token.name,
                        scene = "Active round " .. tostring(dmhub.initiativeQueue.round)
                            .. ". Current monster: " .. token.name
                            .. ". Choose a move that fits its tactics and protects its goal.",
                        candidates = public,
                    },
                    success = function(response)
                        if mod.unloaded then return end
                        if response.error then
                            setStatus(response.error)
                        elseif candidates[response.move_id] ~= nil then
                            local chosenPlan = nil
                            for _,item in ipairs(public) do
                                if item.id == response.move_id then chosenPlan = item.plan end
                            end
                            pending = { tokenid = token.charid, initiativeid = initiativeid,
                                moveid = response.move_id, plan = chosenPlan }
                            reason.text = tostring(response.reason or "")
                                .. " Risk: " .. tostring(response.risk or "")
                            setStatus("Suggested: " .. response.move_id)
                            executeButton.enabled = true
                        else
                            setStatus("The model returned a move outside the legal list.")
                        end
                    end,
                    error = function(message)
                        if not mod.unloaded then setStatus("Bridge: " .. tostring(message)) end
                    end,
                }
            end,
        }

        return gui.Panel{
            width = "100%", height = "auto", flow = "vertical",
            children = {status, reason, suggestButton, executeButton},
        }
    end,
}
