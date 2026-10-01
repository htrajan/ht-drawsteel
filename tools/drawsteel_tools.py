#!/usr/bin/env python3
"""Call native Draw Steel Lua tools through a local file mailbox.

No screen automation, websocket server, model call or live SQLite mutation.
Writes require --write. A timed-out request is cancelled, never retried.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from pathlib import Path

APP_DATA=Path.home()/"Library/Application Support/MCDM/Codex"
GAME_ID="3365ac8c-e59c-48ff-9ec1-6a5c334e121d"
READ={"ping","list_maps","list_documents","read_document","list_tokens","inspect_token","session3_status"}
WRITE={"open_document","open_panel","pin_document","select_tokens","switch_map",
       "begin_negotiation","hide_negotiation","present_negotiation","prepare_yard",
       "show_office","bridge","crane","cast_ability"}


def atomic_json(path: Path, value: dict):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value),encoding="utf-8")
    os.replace(temporary,path)


def decode_lua(value):
    """Normalize the engine's JSON table markers without losing type names."""
    if isinstance(value,list):return [decode_lua(v) for v in value]
    if not isinstance(value,dict):return value
    items={k:decode_lua(v) for k,v in value.items() if k!="_luaTable"}
    if value.get("_luaTable") is False and all(k.isdigit() for k in items):
        keys=sorted(items,key=int)
        if keys==[str(i) for i in range(1,len(keys)+1)]:return [items[k] for k in keys]
    return items


def call(command: str, args: dict | None=None, *, write=False, timeout=15,
         game_id=GAME_ID, app_data=APP_DATA):
    if command not in READ|WRITE:raise ValueError("Unsupported command")
    if command in WRITE and not write:raise ValueError(f"{command} requires --write")
    if args is not None and not isinstance(args,dict):raise ValueError("Arguments must be a JSON object")
    if not 0.1<=timeout<=120:raise ValueError("Timeout must be 0.1–120 seconds")
    # Native WriteTextFile/GetTextFilePaths are rooted in compendium, not the
    # application data root. Use the engine's actual sandboxed file location.
    root=Path(app_data)/"compendium/script-tools"
    rid=str(uuid.uuid4());request=root/"requests"/(rid+".json")
    result=root/"results"/(rid+".json");cancel=root/"cancelled"/(rid+".json")
    atomic_json(request,{"protocol":1,"id":rid,"game_id":game_id,"command":command,
        "args":args or {},"allow_write":write,"expires_ms":int((time.time()+timeout)*1000)})
    deadline=time.monotonic()+timeout
    try:
        while time.monotonic()<deadline:
            if result.exists():
                try:response=json.loads(result.read_text())
                except (ValueError,OSError):time.sleep(0.05);continue
                if response.get("id")!=rid:raise RuntimeError("Mismatched response ID")
                if response.get("status") in ("ok","error","cancelled"):
                    if response.get("status")!="ok":raise RuntimeError(response.get("error","Native tool failed"))
                    return decode_lua(response.get("result"))
            time.sleep(0.1)
        atomic_json(cancel,{"id":rid})
        # A begun native operation may still finish. Never resubmit blindly.
        raise TimeoutError(f"No completed app response for {rid}. Request cancelled; if already running, its outcome is unknown. Open the campaign as Director with the updated Voice RP mod loaded.")
    finally:
        if request.exists():request.unlink()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=sorted(READ|WRITE))
    parser.add_argument("--args",default="{}",help="JSON argument object")
    parser.add_argument("--write",action="store_true",help="Explicitly allow the named mutation")
    parser.add_argument("--timeout",type=float,default=15)
    parser.add_argument("--game-id",default=GAME_ID)
    options=parser.parse_args()
    try:
        result=call(options.command,json.loads(options.args),write=options.write,
                    timeout=options.timeout,game_id=options.game_id)
    except (ValueError,RuntimeError,TimeoutError) as exc:parser.exit(1,str(exc)+"\n")
    print(json.dumps(result,indent=2,ensure_ascii=False))


if __name__=="__main__":main()
