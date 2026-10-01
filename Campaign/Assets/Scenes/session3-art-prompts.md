# Session 3 artwork provenance

Generated with the built-in image-generation tool, not the fallback CLI.
All six selected assets are saved in the repository and copied into the app's
asset cache by `tools/integrate_session3.py`. These are scene and portrait
illustrations; tactical geometry comes from the calibrated yard and native
terrain, not from the office image.

## Office — `Campaign/Assets/Scenes/bellafonte-office.png`

Final prompt:

> Use case: illustration-story. Asset type: virtual tabletop negotiation scene illustration, wide landscape. Create an elegant but practical upstairs office above a private collection in a fantasy Renaissance canal city. Eye-level view from the visitors' side of a polished dark wooden desk. Four comfortable visitor chairs around a broad desk, a high-backed velvet chair behind it, brass inkstand, blank parchment, porcelain water pitcher and cups, warm lamps, tall shuttered windows with evening light, orderly shelves and a tasteful framed landscape. Dignified privilege now feels fragile, but no damaged furniture, chains, prison bars, torture equipment, NPCs or other people. Rich painterly tabletop adventure illustration, crisp beautiful architectural details, inviting amber wood and muted blue upholstery. No writing, labels, UI, watermark or modern objects.

## Portrait prompt set

Each final prompt is the following prefix, the corresponding subject below,
and the following suffix, joined with spaces. `transparent_background=false`
was used for every asset, including the office.

Prefix:

> Use case: illustration-story. Asset type: square virtual tabletop character portrait.

Suffix:

> Painterly fantasy adventure illustration, clear face and shoulders centered within generous margin for circular token crop, warm neutral simple background, no text, logos, frame, watermark or other figures.

`Campaign/Assets/Tokens/irena-vale.png`:

> Irena Vale, a stern professional human woman retrieval captain in her forties, short dark hair, practical blue-wax contractor uniform coat over brigandine, weighted baton at her shoulder, competent rather than villainous, Renaissance canal city.

`Campaign/Assets/Tokens/cleanup-enforcer.png`:

> A burly professional human dockside enforcer wearing practical quilted armor and a muted blue sash, holding a long boarding hook, nets slung over shoulder, Renaissance canal city, paid guard not a cultist.

`Campaign/Assets/Tokens/loomworks-yardhand.png`:

> A wiry human canal freight yardhand wearing worn linen work clothes and a faded blue neckcloth, carrying a hooked hauling pole and a small smoke pot, Renaissance canal city, ordinary hired professional not a cultist.

`Campaign/Assets/Tokens/bellafonte.png`:

> Ottaviano Bellafonte, a vain frightened middle-aged human repairs commissioner and wealthy collector, slightly stout, elaborately embroidered dark velvet coat with a small tear at the collar, neatly dressed, worried face, Renaissance canal city, no injuries or blood.

`Campaign/Assets/Tokens/fenwick.png`:

> Rudiger Fenwick, a well-dressed human contractor broker, middle-aged, lean face, carefully groomed moustache, dark tailored coat and gloves, holding a dispatch satchel with a blue wax seal, wary calculating expression, Renaissance canal city, no weapons.
