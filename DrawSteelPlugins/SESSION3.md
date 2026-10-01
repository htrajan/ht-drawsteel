# Session 3 in the Steam app

The authoritative text is `Campaign/Act 2/Session 3.md`. The importer copies it
verbatim. It does not advance campaign history, spend hero resources, award
Victories, or start combat.

## Opening the session

Open the existing campaign as Director. **Panels → Session 3** opens the session
companion. The full script is also pinned to the left rail. The companion opens
automatically when the campaign is entered and presents Bellafonte's office on
the first entry after installation.

**Negotiation preparation** opens the native negotiation document. **Begin
Bellafonte negotiation** uses the app's negotiation stage, furnished office
background, Bellafonte portrait, party roster, arguments, power rolls, Interest,
Patience, and hidden motivations/pitfall. Starting values are 2/3, Impression 3.
He gives all core information regardless of Interest; willingness to appear as
bait is the subject of the negotiation. Neither counter gives him bargaining
power or permission to demand concessions.

The furnished office and five portraits were generated with the built-in
image tool. Saved paths and the final prompt set are recorded in
[`session3-art-prompts.md`](../Campaign/Assets/Scenes/session3-art-prompts.md).

## Script and handouts

The exact full script and six scene extracts are Director-only. Each evidence
handout has **review** and **Share** controls. Do not share the full script or
negotiation preparation. The encrypted letter has no solution, the reply sheet
has no sample answer, and the satchel uses only the unexplained L.R.A. initials.

## Combat

The bestiary folder **Session 3 — Loomworks and captives** contains native
profiles for Vale, the enforcers, yardhands, Bellafonte, and Fenwick, with custom
portraits. The calibrated lift yard has Vale, two enforcers, eight yardhands in
two four-minion squads, and Fenwick, grouped into Blue, Gray and White. Four
encounter presets cover 50/60/70/80 EV; select the printed budget after the
respite. Do not deploy a preset on top of the already placed baseline crew.

Damage, potency, conditions, forced movement, Malice costs, extraction shifts,
pooled minion Stamina and reaction modifiers use native app systems. The
campaign companion removes unprinted fallback Malice and noncombatant free
strikes, limits yardhand coordinated attackers to three, creates smoke zones,
and tracks props and mooring steps. Keep the companion open during combat so
its turn monitor expires smoke and reminds you of the round-four stop.

Open the yard and click **Install native yard terrain once** before play.
Invisible native geometry overlays the art: floor, two-square-high gantry,
scenery, and canal water. The winch control changes the bridge's native barrier.
These changes are undoable through the app.

The Director still adjudicates choices and bespoke situations: which side
bridge occupants choose, crane passenger movement, scenery damage/cover, the
smoke-crossing bane, legal Bodyguard destinations, evidence transfers from
unwilling carriers, the controlled-barge helm requirement, surrender and final
departure. The companion supplies the printed rules and live prop controls;
it does not replace these choices with scripted captures or outcomes.

## Reimporting safely

Close Draw Steel first, then run:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/integrate_session3.py --apply
```

The current app has an in-process SQLite server. The tool refuses to write
while its executable is running, creates a complete SQLite backup in the local
game directory, and preserves all hero properties. Reimporting keeps imported
tokens' live damage, conditions, resources and positions. It repairs only
overflowed animation stamps from the earlier playthrough.

The campaign companion lives in the already-installed Voice RP code mod's
`Main.lua`; no additional empty mod is created. Copy the repository version to
that mod's local folder after changes, then reopen the app.

Offline checks:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tools -p test_integrate_session3.py
python3 tools/validate_session3.py
```

Passing these checks confirms import structure and continuity, not an
end-to-end live combat playtest.
