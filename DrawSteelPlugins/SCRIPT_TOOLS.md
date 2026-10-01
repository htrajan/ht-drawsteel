# Native Draw Steel script tools

The existing Voice RP code mod now includes a Director-only command receiver.
It uses documented native Lua APIs, not Mac-control, simulated input, browser
automation, or a websocket port. The app's new in-process SQLite server is not
edited while running.

## Transport and safety

`tools/drawsteel_tools.py` writes a UUID-named JSON request into the app's local
`compendium/script-tools/requests` directory. The native Lua receiver polls every half
second, calls the named handler, and writes a JSON response. This works entirely
on this Mac without a model call, network listener, or API key.

Commands are scoped to an exact game ID and require Director mode. Mutations
require the CLI's `--write` flag as well as the receiver's allowlist. There is
no `eval`, arbitrary SQL, file-read, shell, or generic property-patch command.
The receiver writes a durable `running` receipt before execution to prevent
replay after a restart. Expired and cancelled requests do not execute. If a
native operation has already started when the client times out, inspect state
before deciding what to do next; the client never retries it automatically.

The installed Voice RP `Main.lua` must be updated and reloaded once. Thereafter
no panel needs to stay open for script tools to work. The campaign must be open
as Director. A heartbeat in `script-tools/heartbeat.json` reports the loaded
game, Director status, protocol and time. The engine's text-file API is rooted
in `compendium`, so the full heartbeat path is
`~/Library/Application Support/MCDM/Codex/compendium/script-tools/heartbeat.json`.

## Examples

Run from the repository root:

```sh
python3 tools/drawsteel_tools.py ping
python3 tools/drawsteel_tools.py list_maps
python3 tools/drawsteel_tools.py list_documents
python3 tools/drawsteel_tools.py list_tokens
python3 tools/drawsteel_tools.py session3_status

python3 tools/drawsteel_tools.py open_panel --write --args '{"name":"Session 3"}'
python3 tools/drawsteel_tools.py show_office --write
python3 tools/drawsteel_tools.py open_document --write --args '{"id":"59b11f49-ccaf-5c69-b873-e4fd26f5ff58"}'
python3 tools/drawsteel_tools.py begin_negotiation --write --args '{"id":"54f774d8-e0cd-5d92-8f32-ba83cadf8c1c"}'

python3 tools/drawsteel_tools.py switch_map --write --args '{"id":"98912355-f847-5850-974a-7a4e089118b9"}'
python3 tools/drawsteel_tools.py prepare_yard --write
python3 tools/drawsteel_tools.py inspect_token --args '{"id":"299145b4-5fd0-5df8-836a-302ffe964406"}'
```

`read_document` returns document contents and native negotiation fields.
`inspect_token` returns properties, position, native ability descriptions,
behaviors, costs and action types. `session3_status` audits the source script,
negotiation, creature profiles, prop tracker and native panel registration.
Results are JSON, so an evaluation harness can compare them directly with the
session instead of interpreting pixels.

Other commands: `pin_document`, `select_tokens`, `hide_negotiation`,
`present_negotiation`, `bridge`, `crane`, and `cast_ability`.

Python harnesses can call the same interface without spawning a CLI process:

```python
import sys
sys.path.insert(0, "tools")
from drawsteel_tools import call

maps = call("list_maps")
call("open_panel", {"name": "Session 3"}, write=True)
```

The Bellafonte start handler includes all four campaign heroes in the native
negotiation roster even though the furnished office is a presentation map.
Their map positions and resources do not change. An already-live negotiation
cannot be reset by this command; use `present_negotiation` to resume it.

`cast_ability` invokes the app's native ability pipeline. It is not a fully
headless combat simulator: native roll dialogs and choice prompts may still
need a Director response. Do not treat a successful invocation as proof that
every movement, roll, trigger and choice has resolved. For automated combat
playthroughs, extend the typed command surface with explicit native roll and
choice-resolution handlers, rather than adding an unrestricted Lua executor.

## Testing

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tools -p test_drawsteel_tools.py
PYTHONDONTWRITEBYTECODE=1 python3 tools/check_drawsteel_session3.py
```

Transport tests use a mock app. Real `ping`, map/document inspection and native
mutation results are the acceptance checks for a loaded installation.
