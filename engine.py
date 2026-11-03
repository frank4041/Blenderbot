"""Lesson engine: runs steps, watches the view/selection/input, drives the bot and the overlay."""
import bpy
import math
import time
import traceback
from mathutils import Vector, Euler

from . import bot, world, keys, overlay

LESSON_SCENE = "Blenderbot Lesson"
ROOT_COLL = "Blenderbot Lesson"
TICK = 1.0 / 30.0
TYPE_CPS = 55.0
STUCK_AFTER = 25.0


def now():
    return time.perf_counter()


class Runtime:
    def __init__(self):
        self.reset()

    def reset(self):
        self.active = False
        self.session = 0 if not hasattr(self, "session") else self.session
        self.lesson = None
        self.index = 0
        self.task_index = 0
        self.task_progress = 0.0
        self.step_done = False
        self.line = ""
        self.line_t0 = 0.0
        self.reaction = None
        self.reaction_t0 = 0.0
        self.reaction_until = 0.0
        self.reveal_all = False
        self.learned = []
        self.mem = {}
        self.acc = {'orbit': 0.0, 'pan': 0.0, 'zoom': 0.0}
        self.view = None
        self.prev_view = None
        self.start_view = None
        self.glide = None
        self.last_progress_t = 0.0
        self.hint_shown = False
        self.prev_scene = None
        self.saved_space = None
        self.main_area_ptr = 0
        self.buttons = {}
        self.hover = None
        self.eat_release = False
        self.react_once = set()
        self.react_cool = {}
        self.t = now()
        self.dt = TICK
        self.crate_phase = 0
        self.seen_active = None

    # ---- helpers used by lesson checks
    def step(self):
        return self.lesson.steps[self.index]

    def obj(self, name):
        return bpy.data.objects.get(name)

    def view_layer(self):
        sc = bpy.data.scenes.get(LESSON_SCENE)
        return sc.view_layers[0] if sc else None

    def active_object(self):
        vl = self.view_layer()
        return vl.objects.active if vl else None

    def is_selected(self, ob):
        vl = self.view_layer()
        try:
            return ob is not None and vl is not None and ob.select_get(view_layer=vl)
        except Exception:
            return False

    def view_fwd(self):
        if not self.view:
            return Vector((0, 1, 0))
        return self.view['rot'] @ Vector((0, 0, -1))

    def screen_ndc(self, co):
        v = main_view()
        if v is None:
            return None
        p = v['rv3d'].perspective_matrix @ Vector((co.x, co.y, co.z, 1.0))
        if p.w <= 1e-6:
            return None
        return Vector((p.x / p.w, p.y / p.w))


rt = Runtime()
_draw_handle = None


# ======================================================================= view
def main_view():
    wm = bpy.context.window_manager
    best = None
    for win in wm.windows:
        if win.scene is None or win.scene.name != LESSON_SCENE:
            continue
        for area in win.screen.areas:
            if area.type != 'VIEW_3D':
                continue
            if best is None or area.width * area.height > best[1].width * best[1].height:
                best = (win, area)
    if best is None:
        return None
    win, area = best
    region = next((r for r in area.regions if r.type == 'WINDOW'), None)
    space = area.spaces.active
    if region is None or space.region_3d is None:
        return None
    rt.main_area_ptr = area.as_pointer()
    return dict(window=win, area=area, region=region, space=space, rv3d=space.region_3d)


def _view_state(v):
    rv = v['rv3d']
    return dict(rot=rv.view_rotation.copy(), loc=rv.view_location.copy(), dist=rv.view_distance)


def view_to(target, yaw, pitch, dist, dur=1.2):
    v = main_view()
    if v is None:
        return
    rot = Euler((math.radians(pitch), 0.0, math.radians(yaw)), 'XYZ').to_quaternion()
    rv = v['rv3d']
    if rv.view_perspective != 'PERSP':
        rv.view_perspective = 'PERSP'
    a = _view_state(v)
    if a['rot'].dot(rot) < 0:
        rot.negate()
    rt.glide = dict(t0=now(), dur=max(dur, 1e-3), a=a,
                    b=dict(rot=rot, loc=Vector(target), dist=dist))
    if dur <= 0:
        _update_glide(v, force_end=True)


def _update_glide(v, force_end=False):
    g = rt.glide
    u = 1.0 if force_end else min(1.0, (now() - g['t0']) / g['dur'])
    e = u * u * (3 - 2 * u)
    a, b = g['a'], g['b']
    rv = v['rv3d']
    rv.view_rotation = a['rot'].slerp(b['rot'], e)
    rv.view_location = a['loc'].lerp(b['loc'], e)
    rv.view_distance = a['dist'] + (b['dist'] - a['dist']) * e
    if u >= 1.0:
        rt.glide = None
        rt.prev_view = None
        rt.start_view = _view_state(v)


def _track(v):
    cur = _view_state(v)
    p = rt.prev_view
    if p is not None:
        ang = p['rot'].rotation_difference(cur['rot']).angle
        if ang > math.pi:
            ang = 2 * math.pi - ang
        dd = cur['dist'] - p['dist']
        rt.acc['orbit'] += ang
        rt.acc['zoom'] += abs(dd)
        if abs(dd) < 1e-4 and ang < 1e-4:
            rt.acc['pan'] += (cur['loc'] - p['loc']).length / max(cur['dist'], 0.1)
    if rt.start_view is None:
        rt.start_view = cur
    rt.prev_view = cur
    rt.view = cur


def reset_acc():
    rt.acc = {'orbit': 0.0, 'pan': 0.0, 'zoom': 0.0}
    rt.start_view = rt.view


# ======================================================================= talk
def say(text, expr='idle'):
    rt.line = keys.fmt(text)
    rt.line_t0 = now()
    rt.reaction = None
    rt.reveal_all = False
    bot.set_expression(expr, None, now())


def react(text, expr='surprised', dur=5.0):
    text = keys.fmt(text)
    rt.reaction = text
    rt.reaction_t0 = now()
    rt.reaction_until = now() + dur + len(text) / TYPE_CPS
    rt.reveal_all = False
    bot.set_expression(expr, dur + len(text) / TYPE_CPS, now())


def react_once(key, text, expr='surprised', dur=5.0):
    if key in rt.react_once:
        return
    rt.react_once.add(key)
    react(text, expr, dur)


def react_cool(key, text, expr='surprised', cooldown=20.0, dur=5.0):
    t = rt.react_cool.get(key, -1e9)
    if now() - t < cooldown:
        return
    rt.react_cool[key] = now()
    react(text, expr, dur)


def current_text():
    """(text, t0) for the bubble; reactions temporarily override the main line."""
    if rt.reaction:
        if now() < rt.reaction_until:
            return rt.reaction, rt.reaction_t0
        rt.reaction = None
        rt.line_t0 = 0.0      # main line comes back fully typed
    return rt.line, rt.line_t0


def hint():
    st = rt.step()
    if st.hint:
        react(st.hint, 'thinking', dur=12.0)
    rt.hint_shown = True


def learn(entry):
    if entry not in rt.learned:
        rt.learned.append(entry)


# ======================================================================= steps
def enter_step(i):
    rt.index = i
    st = rt.step()
    rt.task_index = 0
    rt.task_progress = 0.0
    rt.step_done = not st.tasks
    rt.mem = {}
    rt.hint_shown = False
    rt.last_progress_t = now()
    rt.reaction = None
    rt.react_once = {k for k in rt.react_once if k.startswith("maya")}
    reset_acc()
    if st.setup:
        try:
            st.setup(rt)
        except Exception:
            traceback.print_exc()
    ob = rt.active_object()
    rt.seen_active = ob.name if (ob is not None and rt.is_selected(ob)) else None
    say(st.say, st.expr)
    redraw()


def complete_step():
    st = rt.step()
    rt.step_done = True
    for entry in st.teach:
        learn(entry)
    if st.success:
        say(st.success, 'happy')
    bot.hop()


def next_step():
    if not rt.active:
        return
    if not rt.step_done:
        return
    if rt.index >= len(rt.lesson.steps) - 1:
        stop(restore=True)
        return
    enter_step(rt.index + 1)


def skip_step():
    if not rt.active:
        return
    st = rt.step()
    for entry in st.teach:
        learn(entry)
    if rt.index >= len(rt.lesson.steps) - 1:
        stop(restore=True)
        return
    enter_step(rt.index + 1)


def restart_step():
    if rt.active:
        enter_step(rt.index)


def _check_tasks():
    st = rt.step()
    if rt.step_done or not st.tasks or rt.glide is not None:
        return
    task = st.tasks[rt.task_index]
    try:
        p = task.check(rt)
    except Exception:
        traceback.print_exc()
        p = 0.0
    if p is True:
        p = 1.0
    elif p is False or p is None:
        p = 0.0
    p = max(0.0, min(1.0, float(p)))
    if abs(p - rt.task_progress) > 0.02 or p >= 1.0:
        rt.last_progress_t = now()
    rt.task_progress = p
    if p >= 1.0:
        rt.task_index += 1
        rt.task_progress = 0.0
        reset_acc()
        rt.mem.clear()
        if rt.task_index >= len(st.tasks):
            complete_step()
        else:
            nt = st.tasks[rt.task_index]
            if nt.say:
                say(nt.say, nt.expr or 'happy')
            bot.hop(0.35)


def _watch_selection():
    st = rt.step()
    if rt.step_done or not st.tasks:
        return
    want = st.tasks[rt.task_index].want
    if not want:
        return
    ob = rt.active_object()
    name = ob.name if (ob is not None and rt.is_selected(ob)) else None
    if name == rt.seen_active:
        return                      # only react to a *new* pick, not leftovers from the last step
    rt.seen_active = name
    if ob is None or name is None or not ob.get("bb_lesson"):
        return
    ok = bot.is_bot(ob) if want == 'bot' else ob.name == want
    if ok:
        return
    label = "me" if bot.is_bot(ob) else ob.get("bb_label", ob.name)
    if want == 'bot':
        react_once("sel:" + ob.name, f"That's {label}! I'm the orange one.", 'confused')
    elif label == "me":
        react_once("sel:bot", f"Hey, that's me! We need **{want}**.", 'happy')
    else:
        react_once("sel:" + ob.name, f"That's {label}. Look for **{want}**.", 'confused')


def _ensure_actors():
    if not bot.exists():
        coll = bpy.data.collections.get("Blenderbot Bot")
        if coll is None:
            return
        bot.build(coll)
        react("Hey! Don't delete me, I'm your tour guide!", 'surprised')
    missing = world.missing_crates()
    if missing:
        coll = bpy.data.collections.get("Blenderbot Crates")
        if coll is None:
            return
        for n in missing:
            world.make_crate(n, coll)
        world.layout(rt.crate_phase)
        react("Hey, I still need that crate!", 'surprised')


# ======================================================================= tick
def redraw():
    try:
        for win in bpy.context.window_manager.windows:
            for area in win.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
    except Exception:
        pass


def tick():
    if not rt.active:
        return None
    try:
        _tick()
    except Exception:
        traceback.print_exc()
    return TICK if rt.active else None


def _tick():
    if bpy.data.scenes.get(LESSON_SCENE) is None:
        stop(restore=False)
        return
    t = now()
    rt.dt = min(0.1, t - rt.t)
    rt.t = t
    v = main_view()
    if v is None:
        return            # user switched to another scene; lesson pauses
    _ensure_actors()
    bot.update(rt.dt, t)
    if rt.glide is not None:
        _update_glide(v)
        rt.view = _view_state(v)
    else:
        _track(v)
    _watch_selection()
    _check_tasks()
    st = rt.step()
    if (not rt.step_done and st.tasks and not rt.hint_shown
            and t - rt.last_progress_t > STUCK_AFTER):
        hint()
    redraw()


# ======================================================================= input
def _inside(region, x, y):
    return region.x <= x < region.x + region.width and region.y <= y < region.y + region.height


def _hit(x, y):
    for name, (x0, y0, x1, y1) in rt.buttons.items():
        if name != 'bubble' and x0 <= x <= x1 and y0 <= y <= y1:
            return name
    b = rt.buttons.get('bubble')
    if b and b[0] <= x <= b[2] and b[1] <= y <= b[3]:
        return 'bubble'
    return None


def click(name):
    if name == 'next':
        if rt.step_done:
            next_step()
    elif name == 'skip':
        skip_step()
    elif name == 'restart':
        restart_step()
    elif name == 'hint':
        hint()
    elif name == 'exit':
        stop(restore=True)
    elif name == 'bubble':
        rt.reveal_all = True
    redraw()


def handle_event(ev):
    """Called by the modal watcher. Returns True to consume the event."""
    if not rt.active:
        return False
    v = main_view()
    if v is None:
        return False
    x, y = ev.mouse_x, ev.mouse_y
    if ev.type == 'MOUSEMOVE':
        h = _hit(x, y) if _inside(v['region'], x, y) else None
        if h == 'bubble':
            h = None
        if h != rt.hover:
            rt.hover = h
            redraw()
        return False
    if ev.type == 'LEFTMOUSE':
        if ev.value == 'PRESS' and _inside(v['region'], x, y):
            h = _hit(x, y)
            if h:
                rt.eat_release = True
                click(h)
                return True
        elif ev.value == 'RELEASE' and rt.eat_release:
            rt.eat_release = False
            return True
    if ev.value == 'PRESS' and _inside(v['region'], x, y):
        _maya_habits(ev)
    return False


def _maya_habits(ev):
    emulate = bpy.context.preferences.inputs.use_mouse_emulate_3_button
    if ev.alt and not ev.ctrl and not ev.shift:
        if ev.type == 'RIGHTMOUSE':
            react_cool("maya_dolly", "**Alt + Right-drag** is Maya's dolly! In Blender, zoom with the "
                       "**{zoom}** or drag with **{zoom_drag}**.", 'thinking')
            return
        if not emulate and ev.type in {'LEFTMOUSE', 'MIDDLEMOUSE'}:
            react_cool("maya_nav", "That's Maya muscle memory! In Blender, drag with **{orbit}** to orbit "
                       "and **{pan}** to pan.", 'thinking')
            return
    if (not (ev.alt or ev.ctrl or ev.shift) and ev.type in {'W', 'E'}
            and 'transform' in rt.step().tags):
        react_cool("maya_wer", "**W** and **E** are Maya keys! In Blender it's **{grab}** to move, "
                   "**{rotate}** to rotate and **{scale}** to scale.", 'thinking')


# ======================================================================= start/stop
_SPACE_ATTRS = [
    ("shading", "type"), ("shading", "light"), ("shading", "color_type"),
    ("shading", "show_shadows"), ("shading", "shadow_intensity"), ("shading", "show_cavity"),
    ("shading", "background_type"), ("shading", "background_color"),
    ("overlay", "show_floor"), ("overlay", "show_axis_x"), ("overlay", "show_axis_y"),
    ("overlay", "show_cursor"), ("overlay", "show_extras"), ("overlay", "show_relationship_lines"),
    ("overlay", "show_text"), ("overlay", "show_stats"),
    (None, "lens"), (None, "clip_end"),
]


def _save_space(space):
    saved = {}
    for path, attr in _SPACE_ATTRS:
        owner = getattr(space, path) if path else space
        try:
            val = getattr(owner, attr)
            if hasattr(val, "__len__") and not isinstance(val, str):
                val = tuple(val)
            saved[(path, attr)] = val
        except Exception:
            pass
    return saved


def _restore_space(space, saved):
    for (path, attr), val in saved.items():
        owner = getattr(space, path) if path else space
        try:
            setattr(owner, attr, val)
        except Exception:
            pass


def _style_space(space):
    sh, ov = space.shading, space.overlay
    sh.type = 'SOLID'
    sh.light = 'STUDIO'
    sh.color_type = 'OBJECT'
    sh.show_shadows = True
    sh.shadow_intensity = 0.35
    sh.show_cavity = True
    sh.background_type = 'VIEWPORT'
    sh.background_color = (0.55, 0.7, 0.85)
    ov.show_floor = False
    ov.show_axis_x = False
    ov.show_axis_y = False
    ov.show_cursor = False
    ov.show_extras = False
    ov.show_relationship_lines = False
    ov.show_text = False
    ov.show_stats = False
    space.lens = 40
    space.clip_end = 3000


def _build_scene():
    old = bpy.data.scenes.get(LESSON_SCENE)
    if old is not None:
        _delete_scene(old)
    sc = bpy.data.scenes.new(LESSON_SCENE)
    sc.display.light_direction = (0.45, -0.35, 0.82)
    sc.display.shadow_shift = 0.05
    root = bpy.data.collections.new(ROOT_COLL)
    sc.collection.children.link(root)
    c_bot = bpy.data.collections.new("Blenderbot Bot")
    c_crates = bpy.data.collections.new("Blenderbot Crates")
    c_world = bpy.data.collections.new("Blenderbot World")
    for c in (c_bot, c_crates, c_world):
        root.children.link(c)
    bot.reset_state()
    world.build(c_world, c_crates)
    bot.build(c_bot)
    return sc


def _delete_scene(sc):
    colls = []
    for name in ("Blenderbot Bot", "Blenderbot Crates", "Blenderbot World", ROOT_COLL):
        c = bpy.data.collections.get(name)
        if c is not None:
            colls.append(c)
    meshes = set()
    for c in colls:
        for ob in list(c.objects):
            if ob.type == 'MESH' and ob.data is not None:
                meshes.add(ob.data.name)
            bpy.data.objects.remove(ob, do_unlink=True)
    for c in colls:
        bpy.data.collections.remove(c)
    for me in list(bpy.data.meshes):
        if me.users == 0 and (me.name in meshes or me.get("bb_lesson")):
            bpy.data.meshes.remove(me)
    if len(bpy.data.scenes) > 1:
        bpy.data.scenes.remove(sc)


def start(context, lesson):
    if rt.active:
        stop(restore=True)
    rt.reset()
    rt.session += 1
    rt.lesson = lesson
    win = context.window or bpy.context.window_manager.windows[0]
    rt.prev_scene = win.scene.name
    sc = _build_scene()
    win.scene = sc
    v = main_view()
    if v is not None:
        rt.saved_space = (v['area'].as_pointer(), _save_space(v['space']))
        _style_space(v['space'])
        rt.glide = None
        view_to((0, 0, 3), -35, 62, 48, dur=0)
    rt.active = True
    _add_draw()
    if not bpy.app.timers.is_registered(tick):
        bpy.app.timers.register(tick, first_interval=TICK)
    enter_step(0)


def stop(restore=True):
    was_active = rt.active
    rt.active = False
    _remove_draw()
    if bpy.app.timers.is_registered(tick):
        bpy.app.timers.unregister(tick)
    if restore and was_active:
        try:
            _restore_all()
        except Exception:
            traceback.print_exc()
    sess = rt.session
    rt.reset()
    rt.session = sess
    redraw()


def _restore_all():
    wm = bpy.context.window_manager
    prev = bpy.data.scenes.get(rt.prev_scene or "") or next(
        (s for s in bpy.data.scenes if s.name != LESSON_SCENE), None)
    if rt.saved_space:
        ptr, saved = rt.saved_space
        for win in wm.windows:
            for area in win.screen.areas:
                if area.as_pointer() == ptr:
                    _restore_space(area.spaces.active, saved)
    if prev is not None:
        for win in wm.windows:
            if win.scene and win.scene.name == LESSON_SCENE:
                win.scene = prev
    sc = bpy.data.scenes.get(LESSON_SCENE)
    if sc is not None and prev is not None:
        _delete_scene(sc)


def _add_draw():
    global _draw_handle
    if _draw_handle is None:
        _draw_handle = bpy.types.SpaceView3D.draw_handler_add(overlay.draw, (), 'WINDOW', 'POST_PIXEL')


def _remove_draw():
    global _draw_handle
    if _draw_handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_draw_handle, 'WINDOW')
        except Exception:
            pass
        _draw_handle = None
