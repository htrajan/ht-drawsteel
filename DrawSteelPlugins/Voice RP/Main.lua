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
