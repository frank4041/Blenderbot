"""Lesson 1: The Basics. Camera, selecting, framing, G/R/S, the Outliner."""
import math
from mathutils import Vector

from .. import engine as E
from .. import bot, world
from ..lesson import Lesson, Step, Task

YARD_BOT = (7.6, 2.4)
HIDE_SPOT = (-15.5, 15.5)


# ------------------------------------------------------------------ setup helpers
def crates(rt, n):
    rt.crate_phase = n
    world.layout(n)


def yard_view(dur=1.4):
    E.view_to((15.2, 1.5, 0.5), 0, 56, 20, dur)


def at_yard(rt, n, dur=1.2):
    crates(rt, n)
    bot.teleport(YARD_BOT, 30)
    yard_view(dur)


def select_only(rt, ob):
    vl = rt.view_layer()
    if vl is None or ob is None:
        return
    for o in vl.objects:
        if o.select_get(view_layer=vl):
            o.select_set(False, view_layer=vl)
    ob.select_set(True, view_layer=vl)
    vl.objects.active = ob


# ------------------------------------------------------------------ checks
def chk_orbit(rt):
    return rt.acc['orbit'] / math.radians(100)


def chk_behind(rt):
    f = rt.view_fwd()
    fh = Vector((f.x, f.y))
    if fh.length < 0.2:
        return 0.3
    fh.normalize()
    bf = bot.forward()
    d = fh.dot(Vector((bf.x, bf.y)))
    return 1.0 if d > 0.82 else max(0.0, (d + 1) / 1.82) * 0.95


def chk_zoom_out(rt):
    if not rt.view or not rt.start_view:
        return 0.0
    start = rt.start_view['dist']
    target = rt.mem.setdefault('zoom_target', max(38.0, start * 2.5))
    return (rt.view['dist'] - start) / (target - start)


def chk_pan(rt):
    return rt.acc['pan'] / 0.35


def chk_centered(rt):
    c = rt.mem.get('centered', 0.0)
    if bot.is_walking():
        rt.mem['centered'] = 0.0
        return 0.0
    ndc = rt.screen_ndc(bot.body_world())
    if ndc is not None and abs(ndc.x) < 0.22 and abs(ndc.y) < 0.32:
        c += rt.dt
    else:
        c = max(0.0, c - rt.dt * 2)
    rt.mem['centered'] = c
    return c / 0.7


def chk_select_bot(rt):
    ob = rt.active_object()
    return bot.is_bot(ob) and rt.is_selected(ob)


def chk_frame_bot(rt):
    if not rt.view:
        return False
    return (rt.view['loc'] - bot.body_world()).length < 1.8 and rt.view['dist'] < 20


def sel(name):
    def _c(rt):
        ob = rt.obj(name)
        return ob is not None and rt.active_object() == ob and rt.is_selected(ob)
    return _c


def frame_obj(name):
    def _c(rt):
        ob = rt.obj(name)
        if ob is None or not rt.view:
            return False
        return (rt.view['loc'] - ob.matrix_world.translation).length < 1.8 and rt.view['dist'] < 25
    return _c


def on_pad(name):
    def _c(rt):
        if world.on_pad(name):
            world.solve(name)
            return True
        return False
    return _c


def rotated_into_place(name):
    def _c(rt):
        ob = rt.obj(name)
        if ob is None:
            return False
        sc = ob.scale
        if max(abs(sc.x - 1), abs(sc.y - 1), abs(sc.z - 1)) > 0.06:
            E.react_once("rot_but_scaled", "Whoa, that's scaling! To rotate, press **{rotate}**.", 'surprised')
        if world.on_pad(name) and world.axis_aligned(name):
            world.solve(name)
            return True
        return False
    return _c


def scaled_into_place(name):
    def _c(rt):
        ob = rt.obj(name)
        if ob is None:
            return False
        if not world.axis_aligned(name, 4.0):
            E.react_once("scale_but_rotated", "Careful! In Blender **{rotate}** is rotate. "
                         "(In Maya, R scales!) Scale is **{scale}**.", 'surprised')
        sc = ob.scale
        mn, mx = min(sc), max(sc)
        if world.on_pad(name) and 0.82 <= mn and mx <= 1.22 and mx / max(mn, 1e-4) < 1.2:
            world.solve(name)
            return True
        return False
    return _c


# ------------------------------------------------------------------ setups
def s_hello(rt):
    bot.teleport((0, 0), 0)
    crates(rt, 0)
    E.view_to((0, 0, 1.35), 0, 84, 7.5, dur=2.4)
    bot.wave(3.2)


def s_town(rt):
    bot.hop()


def s_orbit(rt):
    bot.teleport((0, 0), 0)
    E.view_to((0, 0, 1.35), 0, 84, 7.5, dur=0.8)


def s_zoom(rt):
    bot.teleport((0, 0), 0)


def s_pan(rt):
    bot.teleport((0, 0), 0)
    E.view_to((0, 0, 1.2), -20, 76, 11, dur=1.2)
    bot.walk_to((9, -1), speed=1.7, yaw_deg=0, delay=1.6)


def s_find(rt):
    if bot.S['pos'].length < 0.1:
        bot.teleport((9, -1), 0)
    bot.walk_to(HIDE_SPOT, speed=7.5, yaw_deg=0, delay=0.6)
    bot.hop()


def s_frame(rt):
    bot.teleport(HIDE_SPOT, 0)
    if not chk_select_bot(rt):
        select_only(rt, rt.obj(bot.BODY))
    E.view_to((-4, 6, 1), 40, 58, 44, dur=1.2)


def s_crates(rt):
    at_yard(rt, 0, 1.6)
    bot.hop()


def s_grab(rt):
    at_yard(rt, 0)


def s_axis(rt):
    at_yard(rt, 1)


def s_rotate(rt):
    at_yard(rt, 2)


def s_scale(rt):
    at_yard(rt, 3)


def s_outliner(rt):
    at_yard(rt, 4)


def s_recap(rt):
    crates(rt, 5)
    bot.teleport(YARD_BOT, 0)
    E.view_to((YARD_BOT[0], YARD_BOT[1], 1.4), -10, 82, 8.5, dur=1.6)
    bot.celebrate()


def s_bye(rt):
    bot.wave(3.0)


# ------------------------------------------------------------------ the lesson
STEPS = [
    Step("hello", "Welcome",
         "Hi there! I'm **Blenderbot**. Welcome to Blender, where you can make pretty much "
         "anything you can imagine.",
         setup=s_hello, expr='happy'),
    Step("town", "Welcome",
         "Props, characters, whole worlds. It all starts with knowing how to get around. "
         "Let me show you my town!",
         setup=s_town, expr='happy'),

    Step("orbit", "Orbit",
         "First, let's look around. Hold **{orbit}** and drag to orbit around me.",
         tasks=[
             Task("Orbit the view", chk_orbit, bar=True),
             Task("Orbit behind Blenderbot", chk_behind, bar=True,
                  say="Nice! Now orbit all the way **behind me**. I want to show you something."),
         ],
         success="Beautiful, isn't it? That's my hometown out there.",
         hint="Hold **{orbit}** and move the mouse sideways. On a trackpad, a two-finger drag works too. "
              "You can also drag the colored axis ball in the top-right corner.",
         setup=s_orbit, teach=[("Orbit", "orbit")]),

    Step("zoom", "Zoom",
         "Now zoom out to see the whole island. Roll the **{zoom}** toward you.",
         tasks=[Task("Zoom out", chk_zoom_out, bar=True)],
         success="That's all of it! Zoom works both ways, so you can get as close as you like.",
         hint="Roll the **{zoom}** toward you to zoom out. You can also hold **{zoom_drag}** and drag, "
              "or pinch on a trackpad.",
         setup=s_zoom, teach=[("Zoom", "zoom")]),

    Step("pan", "Pan",
         "Walk with me! Hold **{pan}** and drag to slide the view along. Keep me in the middle.",
         tasks=[
             Task("Pan the view", chk_pan, bar=True),
             Task("Keep Blenderbot in the center", chk_centered, bar=True,
                  say="That's it! Now line me up in the middle of the screen."),
         ],
         success="Thanks for keeping up!",
         hint="Hold **{pan}** and drag the way you want the view to slide.",
         setup=s_pan, teach=[("Pan", "pan")]),

    Step("find", "Select",
         "Catch me if you can! Find me, then **{select}** on me to select me.",
         tasks=[Task("Find and select Blenderbot", chk_select_bot, want='bot')],
         success="Got me! See the outline? That means I'm selected.",
         hint="Follow the arrow on my speech bubble. Orbit, pan and zoom until you can see me, "
              "then **{select}** on me.",
         setup=s_find, expr='happy', teach=[("Select", "select")]),

    Step("frame", "Frame",
         "Lost me again? With the mouse over the viewport, press **{frame}**. It flies the view "
         "straight to whatever's selected.",
         tasks=[Task("Press {frame} to frame Blenderbot", chk_frame_bot)],
         success="Handy, right? Whenever you get lost, select something and frame it.",
         hint="Hover over the 3D view and press **{frame}**. No numpad? Use the **View** menu, "
              "then **Frame Selected**.",
         setup=s_frame, teach=[("Frame selected", "frame")]),

    Step("crates", "Uh oh",
         "Oh no, my crates! I was supposed to sort them onto the green pads. Can you help me?",
         setup=s_crates, expr='confused'),

    Step("grab", "Move",
         "Click **crate_01** to select it. Then press **{grab}**, move the mouse, and click to drop it "
         "on the first green pad.",
         tasks=[
             Task("Select crate_01", sel('crate_01'), want='crate_01'),
             Task("Press {grab} and drop it on the first pad", on_pad('crate_01'),
                  say="Now tap **{grab}**, move it onto the first pad, and click to drop it."),
         ],
         success="Perfect fit! Moving with **{grab}** is something you'll do all the time.",
         hint="Select the crate, tap **{grab}** once (don't hold it), move the mouse, then left-click "
              "to drop. Right-click or **Esc** cancels.",
         setup=s_grab, tags=['transform'], teach=[("Move", "grab")]),

    Step("axis", "Lock an axis",
         "Pro move: select **crate_02**, press **{grab}**, then **Y**. Now it can only slide along "
         "the green Y axis, straight onto its pad.",
         tasks=[
             Task("Select crate_02", sel('crate_02'), want='crate_02'),
             Task("{grab}, then Y, onto the second pad", on_pad('crate_02'),
                  say="Now **{grab}**, then **Y**, and slide it onto the second pad. "
                      "Typing **8** moves it exactly 8 units!"),
         ],
         success="Smooth! **X**, **Y** and **Z** lock any move to that axis.",
         hint="With the crate selected: **{grab}**, then **Y**, move the mouse, click. Or type **8** "
              "and press **Enter** for an exact move.",
         setup=s_axis, tags=['transform'], teach=[("Lock to an axis", "{grab}, then X / Y / Z")]),

    Step("rotate", "Rotate",
         "This one's crooked. Select **crate_03**, press **{rotate}**, then **Z**, and turn it until "
         "it lines up with its pad.",
         tasks=[
             Task("Select crate_03", sel('crate_03'), want='crate_03'),
             Task("{rotate}, then Z, to line it up", rotated_into_place('crate_03'),
                  say="Now **{rotate}**, then **Z**, and turn it straight. Hold **Ctrl** to snap in steps."),
         ],
         success="Lined up!",
         hint="**{rotate}** then **Z** spins it flat on the ground. Hold **Ctrl** while turning to snap "
              "in 5 degree steps.",
         setup=s_rotate, tags=['transform'], teach=[("Rotate", "rotate")]),

    Step("scale", "Scale",
         "This crate shrank in the wash! Select **crate_04**, press **{scale}**, and move the mouse "
         "away to grow it until it fills its pad.",
         tasks=[
             Task("Select crate_04", sel('crate_04'), want='crate_04'),
             Task("{scale} it up to full size", scaled_into_place('crate_04'),
                  say="Now press **{scale}** and move the mouse away from the crate to grow it."),
         ],
         success="Good as new!",
         hint="Press **{scale}**, then move the mouse away from the crate to grow it. Typing **2.2** "
              "then **Enter** makes it exactly the right size.",
         setup=s_scale, tags=['transform'], teach=[("Scale", "scale")]),

    Step("outliner", "Outliner",
         "One crate is missing, and I can't see it anywhere! The **Outliner** (top right) lists "
         "everything in the scene. Find **crate_lost** there and click it.",
         tasks=[
             Task("Click crate_lost in the Outliner", sel('crate_lost'), want='crate_lost'),
             Task("Hover the viewport, press {frame}", frame_obj('crate_lost'),
                  say="Found it! Now hover over the viewport and press **{frame}** to fly to it."),
             Task("Bring it to the last pad", on_pad('crate_lost'),
                  say="There it is, hiding behind that building! Zoom out, then use **{grab}** to "
                      "bring it to the last pad."),
         ],
         success="All sorted! You found it like a pro.",
         hint="In the Outliner, open **Blenderbot Lesson**, then **Blenderbot Crates**. Or type "
              "**lost** in the Outliner's search box.",
         setup=s_outliner, tags=['transform'], teach=[("Find anything", "Outliner, then {frame}")]),

    Step("recap", "You did it",
         "You did it! You can orbit, zoom and pan, select and frame anything, and move, rotate and "
         "scale it. Everything in Blender is built on these.",
         setup=s_recap, expr='happy'),

    Step("bye", "What's next",
         "Want to go further? Switch on **Beyond the basics** in the Blenderbot tab whenever you're "
         "ready. Thanks for hanging out with me!",
         setup=s_bye, expr='happy'),
]

LESSON = Lesson("basics", "The Basics",
                "Move around, select, and move, rotate and scale things. About 10 minutes.",
                STEPS)
