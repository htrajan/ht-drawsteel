#!/usr/bin/env python3
"""Read-only acceptance check against the running Steam app, without screen input."""
from pathlib import Path

from drawsteel_tools import call, GAME_ID


def main():
    ping=call("ping")
    assert ping["game_id"]==GAME_ID and ping["director"], "Open the campaign as Director"
    state=call("session3_status")
    source=Path(__file__).resolve().parents[1]/"Campaign/Act 2/Session 3.md"
    assert state["script"]["content"]==source.read_text(), "The app script differs from the Markdown source"
    assert state["script"]["hiddenFromPlayers"] and state["session_panel"]
    negotiation=state["negotiation"]
    assert negotiation["hiddenFromPlayers"]
    assert (negotiation["startInterest"],negotiation["startPatience"],negotiation["impression"])==(2,3,3)
    assert negotiation["sceneImage"] and negotiation["portrait"]
    expected={"Irena Vale — Blue-Wax Captain":(4,20,100,5,1),
        "Cleanup Enforcer":(3,10,65,5,2),"Loomworks Yardhand":(2,5,9,6,0),
        "Commissioner Ottaviano Bellafonte":(0,0,20,5,0),"Rudiger Fenwick":(0,0,20,5,0)}
    profiles={p["name"]:(p["level"],p["ev"],p["stamina"],p["speed"],p["stability"]) for p in state["profiles"]}
    assert profiles==expected, f"Native profile mismatch: {profiles}"
    live=state.get("live_negotiation")
    if live and live["docid"]==negotiation["id"]:
        assert len(live["roster"])==4, "Bellafonte's party roster is incomplete"
    print(f"LIVE_SESSION3_OK: app {ping['version']}; exact script, private preparation, office artwork, native panel, five profiles")
    print("Read-only check: no rolls, resources, positions, initiative or outcomes changed.")
    print("This is not a live combat playtest or visual acceptance check.")


if __name__=="__main__":main()
