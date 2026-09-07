#!/usr/bin/env python3
"""Read-only checks for the citizen-deputy revision of Session 2.

Checks document structure, clues, timing, provisional encounter arithmetic,
continuity boundaries, and local links. This is not a playtest or proof of
published setting accuracy. Never opens Steam or changes character data.
"""
from pathlib import Path
from urllib.parse import unquote
import re

ROOT = Path(__file__).resolve().parents[1]
SESSION = ROOT / "Campaign/Act 2/Session 2.md"


def validate():
    text = SESSION.read_text()
    failures = []

    def check(condition, message):
        if not condition:
            failures.append(message)

    def player_facing(section):
        # Dialogue and descriptive read-aloud both count, including blockquotes
        # nested under response options. Exclude bold Director metadata.
        return "\n".join(line for line in section.splitlines()
                         if re.match(r"^\s*>\s*\*(?!\*)", line))

    slots = re.findall(r"^\| \*\*(\d+):(\d+)–(\d+):(\d+)\*\* \|", text, re.M)
    times = [(int(h) * 60 + int(m), int(h2) * 60 + int(m2))
             for h, m, h2, m2 in slots]
    check([end - start for start, end in times] == [15, 15, 15, 20, 20, 50, 5, 10],
          "Expected 150-minute schedule, 50-minute fight, 10-minute buffer")
    check(bool(times) and times[0][0] == 0 and times[-1][1] == 150, "Runtime must be 150")
    check(all(a[1] == b[0] for a, b in zip(times, times[1:])), "Schedule gap or overlap")
    check(len(re.findall(r"^## Scene \d", text, re.M)) == 7, "Seven scenes")
    for phrase in ["**One planned combat**", "**zero montage tests**", "**No respite.**",
                   "Do not set them to old import values", "No Steam import"]:
        check(phrase in text, f"Missing session boundary: {phrase}")

    opening = text.split("## Scene 1 —")[1].split("## Scene 2 —")[0]
    check(opening.index("### Breakfast first") < opening.index("### Once they have privacy"),
          "Invitation must precede private meeting")
    check("after their reply reaches him" in opening, "Indirect contact must allow a reply")
    check("does not already know about the factory" in opening, "Corbin knowledge boundary")
    recruitment = opening.split("### Why Corbin suggests deputy work")[1].split("### Vesk's last request")[0]
    office = text.split("## Scene 2 —")[1].split("## Scene 3 —")[0]
    recruitment_spoken = player_facing(recruitment)
    for phrase in ["Prince died three years ago", "no heir", "picking fights",
                   "following up thefts", "approve more each year", "stopped when he died",
                   "can't just add another patrol", "why we're taking on civilian help"]:
        check(phrase in recruitment_spoken, f"Recruitment dialogue missing causal link: {phrase}")
    check("as part of this private conversation" in recruitment and
          "If they ask why the shortage has lasted" not in recruitment,
          "Core unrest/recruitment explanation belongs in Corbin's private meeting")
    check("not another assignment or combat" in office and "fifteen minutes" in office,
          "Office confirmation must fit reduced pacing without an extra encounter")
    check("The Prince died three years ago" not in office and
          "not a second explanation" in office,
          "Do not duplicate Corbin's background speech at the office")
    check("not to take more statements" in recruitment_spoken and
          "too busy to finish" in recruitment_spoken,
          "Corbin must distinguish suppression from understaffing aloud")
    for phrase in ["six days before the hearing", "seven days ago", "nine days ago"]:
        check(phrase in text.lower(), f"Missing clue chronology: {phrase}")

    # The Director should not have to invent dialogue to communicate core facts.
    # These checks accept both NPC speech and observable descriptive read-aloud.
    street = text.split("## Scene 4 —")[1].split("## Scene 5 —")[0]
    collection = text.split("## Scene 5 —")[1].split("## Scene 6 —")[0]
    aftermath = text.split("## Scene 7 —")[1].split("## After play —")[0]
    for section, phrases, label in [
        (opening, ["Six days before the hearing", "public repairs", "Jobs marked finished",
                   "kept coming back", "receipt for her request"], "Vesk's request"),
        (office, ["read the open complaints", "public work records", "isn't a warrant",
                  "sealed files", "for each of you", "Clear copies are fine",
                  "No further witness interviews", "two copies"], "Office terms and obstruction"),
        (street, ["took the old pump away", "kept the copies", "Commissioner Ottaviano Bellafonte",
                  "still haven't been paid", "payment reference", "His office address is at the bottom"],
         "Residents' evidence and office lead"),
        (collection, ["Where do you start?", "Copper Beech Walk", "rear doors",
                      "brass handle", "stop the Marshal", "Civic Loomworks and Festooning",
                      "Replacement pump installed and tested", "same repair fund",
                      "office address", "Damage reported this morning"], "Collection discoveries"),
        (aftermath, ["permission's been withdrawn", "sign a receipt", "earned the reward",
                     "They dismissed me", "Investigation closed", "No public notice"], "Aftermath"),
    ]:
        delivered = player_facing(section)
        for phrase in phrases:
            check(phrase in delivered, f"Missing player-facing {label}: {phrase}")

    soul = (ROOT / "Campaign/Soul.md").read_text()
    guidance = (ROOT / "AGENTS.md").read_text()
    check("Player-facing information belongs in dialogue or read-aloud" in soul and
          "Keep GM notes brief and operational" in soul and "Campaign/Soul.md" in guidance,
          "Repo guidance must preserve the dialogue-or-read-aloud writing rule")

    handout = text.split("### Player handout —")[1].split("### Director's solution")[0]
    notices = re.findall(r"^\| ([1-5]) \| (.+?) \| (.+?) \| (.+?) \|$", handout, re.M)
    check([row[0] for row in notices] == list("12345"), "Exactly five player notices")
    check("**" not in "\n".join("|".join(row) for row in notices),
          "Do not highlight the answer on the player handout")
    for word in ["Dury", "Bellafonte", "factory", "corruption"]:
        check(word.lower() not in handout.lower(), f"Handout gives away answer: {word}")
    check("### Director's solution — assignment 3" in text, "One declared solution")
    matrix = text.split("### Director's solution")[1].split("**No deduction roll.**")[0]
    clue_rows = re.findall(r"^\| ([1-5]) \| (.+?) \| (.+?) \| (.+?) \|$", matrix, re.M)
    check(len(clue_rows) == 5, "Five clue comparisons")
    candidates = [number for number, repair, repeated, timing in clue_rows
                  if repair.startswith("Yes") and repeated.startswith("Yes")
                  and timing.startswith("Yes")]
    check(candidates == ["3"], f"Deduction not uniquely supported: {candidates}")
    # Independent date check: all values are days before the new session.
    request_days_ago, pump_complete, earliest_repeat = 7, 12, 9
    drain_complete, drain_complaint = 4, 0
    check(pump_complete > earliest_repeat > request_days_ago,
          "Pump repeat must predate Vesk's inquiry and postdate completion")
    check(drain_complete < request_days_ago and drain_complaint < request_days_ago,
          "Drain job cannot underlie the earlier request")
    interludes = text.split("### Four wrong-job interludes")[1].split("## Scene 4")[0]
    wrong = re.findall(r"^- \*\*([1-5]),", interludes, re.M)
    check(wrong == ["1", "2", "4", "5"], f"Wrong-job branches incomplete: {wrong}")
    check("No combat or montage" in interludes, "Detours must not add encounters")
    check("not an investigation Victory" in interludes, "Wrong jobs must not advance mystery")

    for phrase in ["Gold Buttons", "signed work letters", "not a newly discovered canonical rank",
                   "not a canonically established elected MP", "single poorest",
                   "No further witness interviews", "without a roll",
                   "No invented vote", "two copies", "no contractor guard post or checkpoint"]:
        check(phrase.lower() in text.lower(), f"Missing lore/agency boundary: {phrase}")
    spoken = player_facing(text)
    for term in ["dury", "merovanni", "callout", "remittance", "copying costs",
                 "countersigning", "orphaned causality", "caldris", "cover story complete"]:
        check(term not in spoken.lower(), f"Spoken jargon/knowledge leak: {term}")
    for phrase in ["already active before the heroes arrive", "combat is required",
                   "no master activation lever", "not a completed noncombat route",
                   "Do not override a successful blockade", "at the end of round 5",
                   "two main actions at its winding crank", "end of round 2",
                   "No fugitive leaves the map", "No hidden reinforcements"]:
        check(phrase.lower() in text.lower(), f"Missing encounter rule: {phrase}")

    # The house hunt has multiple independent routes and a meaningful follow-up,
    # rather than automatically giving an address, guest list and room together.
    hunt = collection.split("### The collection —")[0]
    for heading in ["### The open question", "### Follow someone", "### Work the delivery route",
                    "### Use the office access", "### Make a social approach",
                    "### Turn discoveries into an advantage"]:
        check(heading in hunt, f"Missing open investigation route: {heading}")
    for phrase in ["not four compulsory stations", "not the meeting or an entry plan",
                   "two consequential tests", "keep any discovered address",
                   "not whether the session has one"]:
        check(phrase in hunt, f"House-hunt scope or fail-forward rule missing: {phrase}")
    for obsolete in ["His public appointment list names", "The house address is public; find",
                     "Honor a convincing surrender", "A disabled lever cannot activate",
                     "pre-combat sabotage route earns the same"]:
        check(obsolete not in text, f"Superseded handout/bypass route remains: {obsolete}")

    # All four controls have actual distant positions and fixed group mappings.
    controls = re.findall(
        r"^\| (Northwest|Northeast|Southwest|Southeast) control — ([^|]+?) \| ([A-T])(\d+) \| (.+?) \|$",
        text, re.M)
    check(len(controls) == 4, "Exactly four mapped corner controls")
    expected = [("Northwest", "red tuning forks", "B", "2"),
                ("Northeast", "blue swords", "S", "2"),
                ("Southwest", "green paws", "B", "15"),
                ("Southeast", "yellow bells", "S", "15")]
    check([row[:4] for row in controls] == expected, "Corner positions/colors changed")
    points = [(ord(col) - ord('A'), int(row)) for _, _, col, row, _ in controls]
    check(all(max(abs(x - xx), abs(y - yy)) >= 13
              for i, (x, y) in enumerate(points) for xx, yy in points[i + 1:]),
          "Controls must be far apart, not clustered")
    mechanism = text.split("**Corner stop mechanisms")[1].split("**The Marshal's drive:**")[0]
    for phrase in ["maneuver, no test", "until the end of that group's next scheduled activation",
                   "one later, unpaused activation", "The red group's Marshal takes its full turn",
                   "including ones granted by the Marshal", "never affects the Marshal",
                   "Minion pools remain separate", "cannot extend the same pause",
                   "destroying a paused or recovering control does not extend or repeat"]:
        check(phrase.lower() in mechanism.lower(), f"Incomplete corner-control rule: {phrase}")
    check("all non-leader members" in text and "including its armor or lions" in text,
          "Controls must pause whole non-leader groups, not only minions")

    # Reference cycle: pause exactly one activation, then require one working
    # activation. A late-round press follows the same cycle into the next round.
    def press(state):
        return ("paused", True) if state == "ready" else (state, False)

    def activate(state):
        if state == "paused":
            return "recovering", False
        return "ready", True

    for next_round in (1, 2):
        state, accepted = press("ready")
        check(accepted and not press(state)[1], "Repeated press must not extend a pause")
        state, nonleaders_act = activate(state)
        check(not nonleaders_act and not press(state)[1],
              f"Expected skipped activation and cooldown in round {next_round}")
        state, nonleaders_act = activate(state)
        check(nonleaders_act and press(state)[1],
              f"Expected working activation before reuse in round {next_round + 1}")

    rows = re.findall(r"^\| (\d+)–(\d+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \|$",
                      text, re.M)
    check(len(rows) == 4, "Expected four budget scaling rows")
    for values in rows:
        low, high, marshal, armor, attendants, lions, ev, count = map(int, values)
        check(attendants % 4 == 0, f"Minion purchase not a multiple of four: {values}")
        calculated = marshal * 30 + armor * 8 + attendants // 4 * 3 + lions * 10
        check(ev == calculated, f"EV arithmetic: {values}")
        check(count == marshal + armor + attendants + lions, f"Creature count: {values}")
        check(count <= 32 and attendants >= count / 2, f"Crowding limit: {values}")
        check(30 >= ev / 3, f"Leader too small a budget share: {values}")
        for victories in range(low, high + 1):
            es = 40 + 10 * (victories // 2)
            check(ev == es + 20 and es + 10 < ev <= es + 30, f"Not Hard: {values}")
            check(ev - 10 == es + 10, "Depleted-party row must be labeled Standard")
        groups = [33, 11 + (10 if lions == 4 else 0),
                  13 + (10 if lions >= 3 else 0), 3 + (10 if lions >= 2 else 0)]
        check(sum(groups) == ev, f"Four-group allocation: {values}")
        paused_counts = [4, 5 + int(lions == 4),
                         5 + int(lions >= 3), 4 + int(lions >= 2)]
        check(sum(paused_counts) == count - 1,
              f"Control groups must cover every non-leader exactly once: {values}")
    blocks = re.findall(r"^#### (.+?) — level (\d+) (.+?), EV (\d+)", text, re.M)
    check(len(blocks) == 4 and all(int(b[1]) <= 5 for b in blocks),
          "Exactly four level-capped hostile blocks")
    check([int(b[3]) for b in blocks] == [30, 8, 10, 3], "Block EV/table mismatch")
    check("provisional EVs" in text and "not a combat playtest" in text, "Homebrew caveat")
    for phrase in ["another main action", "four × 8", "**Grab:**", "**Escape Grab:**",
                   "No separate hidden faction Malice list", "Outside combat",
                   "shared squad roll", "before** they scout"]:
        check(phrase.lower() in text.lower(), f"Incomplete inline mechanics: {phrase}")
    check("gives participating minions a free strike" not in text,
          "Minion critical must grant another main action")

    for phrase in ["3 Victories and +1 Wealth per hero", "1 investigation Victory",
                   "**2 Victories**", "Cancellation of future work does not cancel an earned claim",
                   "case is officially closed", "Unexplained disappearance",
                   "No public notice was issued", "No automatic healing"]:
        # Equivalent explicit resource warning is accepted.
        if phrase == "No automatic healing":
            check("no XP conversion or automatic healing" in text, "No recovery reset")
        elif phrase == "case is officially closed":
            check("Investigation closed" in text, "Case closure")
        else:
            check(phrase.lower() in text.lower(), f"Missing outcome/reward: {phrase}")
    check("voluntary disappearance" not in text.lower(), "Do not imply Vesk left voluntarily")
    check("Do not run the Draw Steel synchronization script" in text, "No app writes")

    broken = []
    for path in (ROOT / "Campaign").rglob("*.md"):
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", path.read_text()):
            target = target.strip().strip("<>")
            if "://" in target or target.startswith(("#", "mailto:")):
                continue
            filepart = unquote(target.split("#", 1)[0])
            if filepart and not (path.parent / filepart).exists():
                broken.append(f"{path.relative_to(ROOT)} -> {target}")
    check(not broken, "Broken local links: " + "; ".join(broken))
    author = (ROOT / "Campaign/Worldbuilding/The Author and the Unwritten.md").read_text()
    check("Bellafonte → Rudiger Fenwick → Civic Loomworks" in author, "Author reference stale")
    check("Belmonte has ordinary weapons" not in author, "Auction reference still active")
    capital = (ROOT / "Campaign/Worldbuilding/Capital - The City and Its Corruption.md").read_text()
    for phrase in ["Matt Colville's own answer", "**Secondary reference**",
                   "not a verified elected MP", "not independently transcribed",
                   "not organizations established by the cited Capital passage"]:
        check(phrase in capital, f"Missing source qualification: {phrase}")
    narrative = (ROOT / "Campaign/Narrative.md").read_text()
    check("Kell did not name him in played Session 1" in narrative, "S1 knowledge boundary")
    check("# Prepared, not played" in narrative and "**3 maximum**" in narrative,
          "Narrative history/reward distinction")
    check((ROOT / "Drafts/Superseded/Price of Protection - Auction Draft.md").is_file(),
          "Previous auction draft not preserved")
    if failures:
        for failure in failures:
            print("FAIL:", failure)
        return 1
    print("SESSION_2_RUNTIME_OK: 150 minutes, 50-minute fight, 10-minute buffer")
    print("ASSIGNMENTS_OK: five notices, unique supported lead, four short wrong-job branches")
    print("CONSTRUCT_BUDGETS_OK: EV 60/70/80/90, four hostile profiles, four groups, level cap 5")
    print("HOUSE_HUNT_OK: four open approaches, earned entry advantages, fail-forward outcomes")
    print("CORNER_CONTROLS_OK: four distant positions, full groups, leader excluded, recovery cycle")
    print("OBJECTIVES_OK: required combat, blockable escape, five-round clock; no bypass award")
    print("CONTINUITY_OK: bounded lore, unrevealed Dury, quiet closure, prepared rewards")
    print("PLAYER_FACING_TEXT_OK: core explanations in dialogue/read-aloud; repo rule present")
    print("LOCAL_LINKS_OK; NO_STEAM_ACCESS")
    print("NOT A PLAYTEST: custom EVs and at-table timing still require Director judgment")
    return 0


if __name__ == "__main__":
    raise SystemExit(validate())
