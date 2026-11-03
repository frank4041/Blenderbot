"""Placeholder lesson world: an island town, a sea, a sun, and a crate yard."""
import bpy
import bmesh
import math
import random
from mathutils import Vector, Matrix

CRATE_YELLOW = (1.0, 0.68, 0.08, 1)
CRATE_DONE = (0.3, 0.92, 0.45, 1)
PAD = (0.12, 0.55, 0.3, 1)
PAD_DONE = (0.25, 0.95, 0.5, 1)

CRATE = 1.6
REST_Z = 0.06 + CRATE / 2

PADS = {
    'pad_01': (11.0, 4.0),
    'pad_02': (13.5, 4.0),
    'pad_03': (16.0, 4.0),
    'pad_04': (18.5, 4.0),
    'pad_05': (21.0, 4.0),
}

# crate: (start xy, start yaw deg, start scale, pad)
CRATES = {
    'crate_01': ((9.5, -3.0), 0.0, 1.0, 'pad_01'),
    'crate_02': ((13.5, -4.0), 0.0, 1.0, 'pad_02'),
    'crate_03': ((16.0, 4.0), 35.0, 1.0, 'pad_03'),
    'crate_04': ((18.5, 4.0), 0.0, 0.45, 'pad_04'),
    'crate_lost': ((27.0, 15.5), 0.0, 1.0, 'pad_05'),
}
CRATE_ORDER = ['crate_01', 'crate_02', 'crate_03', 'crate_04', 'crate_lost']

# Workshop buildings: (x, y, sx, sy, height)
BUILDINGS = [
    (-14.5, 12.0, 4.5, 3.0, 5.0),   # Blenderbot hides behind this one
    (26.0, 11.5, 4.5, 3.0, 6.0),    # crate_lost hides behind this one
    (-11.0, -8.0, 3.0, 3.0, 3.0),
    (-19.0, -1.0, 4.0, 5.0, 7.0),
    (-7.0, 21.0, 5.0, 4.0, 4.0),
    (5.0, 19.0, 4.0, 4.0, 8.0),
    (15.0, 22.0, 6.0, 4.0, 5.0),
    (-25.0, 9.0, 3.0, 3.0, 4.0),
    (31.0, -5.0, 4.0, 4.0, 5.0),
    (-27.0, 20.0, 4.0, 3.0, 9.0),
    (34.0, 18.0, 3.5, 3.5, 7.0),
]
PASTELS = [
    (0.62, 0.68, 0.8, 1), (0.85, 0.62, 0.66, 1), (0.6, 0.8, 0.78, 1),
    (0.9, 0.78, 0.58, 1), (0.72, 0.66, 0.86, 1), (0.78, 0.8, 0.84, 1),
]


def _link(ob, coll, color, selectable=False, label=None):
    coll.objects.link(ob)
    ob.color = color
    ob.hide_select = not selectable
    ob["bb_lesson"] = 1
    if label:
        ob["bb_label"] = label
    return ob


def _mesh(name, bm, smooth=False):
    old = bpy.data.objects.get(name)
    if old is not None:
        data = old.data
        bpy.data.objects.remove(old, do_unlink=True)
        if data is not None and data.users == 0:
            bpy.data.meshes.remove(data)
    me = bpy.data.meshes.new(name)
    me["bb_lesson"] = 1
    bm.to_mesh(me)
    bm.free()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return bpy.data.objects.new(name, me)


def _box(name, coll, size, loc, color, bevel=0.0, selectable=False, label=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Diagonal((size[0], size[1], size[2], 1)))
    ob = _mesh(name, bm)
    ob.location = loc
    if bevel:
        md = ob.modifiers.new("Bevel", 'BEVEL')
        md.width = bevel
        md.segments = 2
        md.limit_method = 'ANGLE'
    return _link(ob, coll, color, selectable, label)


def _disk(name, coll, radius, z, depth, color, segments=64):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=radius, radius2=radius,
                          depth=depth, matrix=Matrix.Translation((0, 0, z - depth / 2)))
    ob = _mesh(name, bm)
    return _link(ob, coll, color)


def build(world_coll, crate_coll):
    rnd = random.Random(7)
    # sea, island, stage
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=900)
    sea = _mesh("sea", bm)
    sea.location = (0, 0, -0.4)
    _link(sea, world_coll, (0.08, 0.32, 0.55, 1), label="the sea")
    _disk("island", world_coll, 90, 0.0, 1.0, (0.3, 0.34, 0.42, 1), 96)
    _disk("stage_rim", world_coll, 5.3, 0.05, 0.05, (0.95, 0.45, 0.08, 1))
    _disk("stage", world_coll, 5.0, 0.08, 0.08, (0.42, 0.46, 0.55, 1))

    # yard floor
    _box("yard", world_coll, (18, 14, 0.04), (15.5, 1.0, 0.02), (0.24, 0.28, 0.34, 1))

    # hometown on the horizon (-Y), with a big sun behind it
    i = 0
    for gx in range(-32, 33, 6):
        for gy in (-52, -60, -68):
            if rnd.random() < 0.25:
                continue
            h = rnd.uniform(4, 20) * (1.3 if abs(gx) < 12 else 1.0)
            col = PASTELS[rnd.randrange(len(PASTELS))]
            _box(f"town_{i:02d}", world_coll, (rnd.uniform(3, 5), rnd.uniform(3, 5), h),
                 (gx + rnd.uniform(-1, 1), gy + rnd.uniform(-1, 1), h / 2), col, bevel=0.15)
            i += 1
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=16)
    sun = _mesh("sun", bm, smooth=True)
    sun.location = (0, -190, 34)
    _link(sun, world_coll, (1.0, 0.72, 0.32, 1), label="the sun")

    for j, (x, y, sx, sy, h) in enumerate(BUILDINGS):
        col = PASTELS[j % len(PASTELS)]
        _box(f"workshop_{j:02d}", world_coll, (sx, sy, h), (x, y, h / 2), col, bevel=0.2)

    for name, (x, y) in PADS.items():
        _box(name, world_coll, (2.2, 2.2, 0.06), (x, y, 0.03), PAD)

    for name in CRATE_ORDER:
        make_crate(name, crate_coll)


def make_crate(name, coll):
    ob = _box(name, coll, (CRATE, CRATE, CRATE), (0, 0, REST_Z), CRATE_YELLOW,
              bevel=0.12, selectable=True, label=name)
    return ob


def missing_crates():
    return [n for n in CRATE_ORDER if bpy.data.objects.get(n) is None]


def layout(solved_count):
    """Put the first `solved_count` crates on their pads; the rest at their start spots."""
    for i, name in enumerate(CRATE_ORDER):
        ob = bpy.data.objects.get(name)
        if ob is None:
            continue
        (sx, sy), yaw, sc, pad = CRATES[name]
        if i < solved_count:
            solve(name, hop=False)
        else:
            ob.location = (sx, sy, 0.06 + CRATE * sc / 2)
            ob.rotation_euler = (0, 0, math.radians(yaw))
            ob.scale = (sc, sc, sc)
            ob.color = CRATE_YELLOW
            p = bpy.data.objects.get(pad)
            if p:
                p.color = PAD


def solve(name, hop=True):
    ob = bpy.data.objects.get(name)
    if ob is None:
        return
    pad = CRATES[name][3]
    px, py = PADS[pad]
    ob.location = (px, py, REST_Z)
    ob.rotation_euler = (0, 0, 0)
    ob.scale = (1, 1, 1)
    ob.color = CRATE_DONE
    p = bpy.data.objects.get(pad)
    if p:
        p.color = PAD_DONE


def on_pad(name):
    ob = bpy.data.objects.get(name)
    if ob is None:
        return False
    px, py = PADS[CRATES[name][3]]
    loc = ob.matrix_world.translation
    d = math.hypot(loc.x - px, loc.y - py)
    return d < 0.8 and 0.1 < loc.z < 2.4


def axis_aligned(name, tol_deg=8.0):
    ob = bpy.data.objects.get(name)
    if ob is None:
        return False
    m = ob.matrix_world.to_3x3().normalized()
    c = math.cos(math.radians(tol_deg))
    for i in range(3):
        col = m.col[i]
        if max(abs(col.x), abs(col.y), abs(col.z)) < c:
            return False
    return True
