# Blenderbot v0.1 (lesson engine prototype)

An interactive guide that teaches Blender inside Blender, like Maya's Mayabot.

## Install
Blender 4.2+ (tested on 5.1): drag `blenderbot.zip` into Blender, or go to
Edit > Preferences > Get Extensions > the dropdown (top right) > Install from Disk.
Then open the 3D View sidebar (N) > **Blenderbot** tab > **Start**.

The lesson builds its own scene ("Blenderbot Lesson") and changes the viewport look while it runs.
Exit or Finish switches back to your scene, restores your viewport and deletes everything it made.

## What's in the Basics lesson (15 steps)
Welcome > Orbit (then orbit *behind* the bot to see his hometown) > Zoom > Pan (he walks, you follow)
> Select ("catch me if you can") > Frame (Numpad .) > Crates: Move (G), Axis lock (G then Y),
Rotate (R then Z), Scale (S) > Outliner (find crate_lost, frame it, bring it home) > Recap > Bye.

## What makes it better than Mayabot
- **The speech bubble is pinned to the bot.** When he's off-screen, the bubble docks to the screen edge
  with an arrow pointing at him.
- **He reacts** with face changes and short lines when you:
  - pick the wrong object ("That's crate_01! I'm the orange one.")
  - use a Maya habit (Alt+Right-drag, W/E, or R when you meant scale)
  - delete him (he comes back)
  - get stuck for 25 seconds (he gives you a hint)
- **It uses your own keys.** It reads your settings (3-button-mouse emulation) and your keymap, so every
  hint names the keys *you* press.
- **It checks results, not button presses.** Mouse, trackpad, or the navigation gizmo all count.
- **A cheat sheet builds up** in the top left as you learn each key.
- **Beyond the basics is opt-in.** A toggle in the tab shows the extra chapters (not built yet).

## Plugging in your own character
The engine only needs these names. Delete the placeholder in `bot.build()` and load your own instead:

| Name | What it is |
|---|---|
| `BB_Bot_Root` | Empty. The engine moves and turns this (walking, hopping, facing). Your rig goes under it. |
| `BB_Bot_Body` | Main selectable mesh. Anything named `BB_Bot_*` counts as "the bot" when clicked. |
| `BB_Bot_Anchor` | Empty above the head. The speech bubble hangs from here. |
| `BB_Bot_Root["bb_expression"]` | String: idle / happy / surprised / confused / thinking. Also `["bb_expression_id"]` as an int (0-4), so your face rig can follow it with a driver. |

The placeholder animates its arms, legs and eyes in `bot._apply()`. That's the part to swap for your
rig's actions.

## Adding or changing steps
Lessons are plain data in `lessons/basics.py`:
`Step(id, title, say, tasks=[Task(label, check_fn, say=..., want=...)], success, hint, setup, teach)`.
A check function returns True or a 0-1 progress value. Put `{orbit}`, `{grab}` and similar in any text
and it's replaced with the user's real key.

## Files
`engine.py` runs the steps, timer, view tracking and reactions · `overlay.py` draws the bubble, task card
and cheat sheet · `bot.py` is the placeholder bot · `world.py` builds the placeholder island and crates ·
`keys.py` reads the keymap · `ui.py` has the sidebar panel and operators
