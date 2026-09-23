# Draw Steel AI Code Mods

These are **Draw Steel Steam app Code Mods**, not Codex desktop plugins.

- `Voice RP/Main.lua` adds an in-app launcher. The local browser page captures speech, lets the Director select one of the four heroes, and posts both the hero's line and a GPT-6 Luna (max reasoning) NPC reply to Draw Steel chat. When a negotiation is presented, the bridge selects that NPC; during free roleplay, choose the NPC in the page.
- `Combat Director/Main.lua` adds a Director-only combat dock. It asks GPT-6 Sol (high reasoning) to choose from Monster AI's scored legal moves for the selected active enemy. **Execute suggested move** rechecks legality and invokes the chosen move through Monster AI's cast and reaction pipeline. It does not advance initiative automatically.

## Start the local bridge

From the campaign repository:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 DrawSteelPlugins/bridge.py
```

Open `http://127.0.0.1:8765/` for Voice RP. Chromium-based browsers support the page's speech recognition; a typed line also works. The browser may send audio to its speech provider. The bridge itself binds only to `127.0.0.1` and uses the signed-in ChatGPT desktop app's bundled Codex CLI. It requires no API key. The bridge must be running during play.

## Draw Steel installation

Both private Code Mods have been registered in **UNCLE HT'S DS CAMPAIGN** through **Compendium > Code Mods**. The official **Monster AI** module is also installed. The app loads checked-out copies from `~/Library/Application Support/MCDM/Codex/mods/Voice_RP_b01e` and `.../Combat_Director_a388`. This repository is the editable source; after changes, copy each `Main.lua` to its corresponding app-data directory and restart Draw Steel. Direct `gitfolder` loading from this repository was tested but macOS denied the app access to `Documents`.

The Steam installation's original bundle plist is malformed on this machine. A temporary wrapper at `/tmp/DrawSteelCodexWrapper.app` launches the original binary without modifying the Steam installation. If launching through Steam fails, use:

```sh
env SteamAppId=2902740 SteamGameId=2902740 open -a /tmp/DrawSteelCodexWrapper.app
```

The voice flow has completed a typed-transcript end-to-end test: Luna replied and both messages appeared in Draw Steel chat. The test messages were removed afterward. The microphone path has not been tested with live audio. Combat Director loads, and the suggestion endpoint has passed a model test; **auto-execution has not yet been tested in a live encounter**. Try it first in a disposable combat before relying on it during a session.

Fast bridge checks: `python3 -B -m unittest discover -s DrawSteelPlugins -p 'test_*.py'`.

## Scope and safety

- Voice RP is a performance aid. It does not advance negotiation meters, make rolls, or create facts outside the NPC brief and recent chat. Review speech recognition before sending.
- Combat suggestions are constrained to moves scored legal by the installed Monster AI mod. The Director makes the final choice to execute, and the panel checks turn and move legality again. A monster must be selected in its active initiative group. Player-controlled tokens are excluded.
- The bridge stores no conversation history or audio. The current Draw Steel chat and the NPC brief supply context for each reply.

Reference: [official Draw Steel Codex source and modding workflow](https://github.com/VerisimLLC/draw-steel-codex).
