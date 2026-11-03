"""Placeholder Blenderbot: built from primitives, animated procedurally.

Swap-in contract for the real character (see README):
  BB_Bot_Root    empty the engine moves/turns (walks, hops, faces)
  BB_Bot_Body    main mesh; everything named BB_Bot_* counts as "the bot" when selected
  BB_Bot_Anchor  empty above the head the speech bubble hangs from
  custom property  BB_Bot_Root["bb_expression"]  (string) / ["bb_expression_id"] (int)
                   so a real rig can drive its face with drivers
"""
import bpy
import bmesh
import math
import random
from mathutils import Vector, Matrix

P = "BB_Bot_"
ROOT, BODY, HEAD, FACE = P + "Root", P + "Body", P + "Head", P + "Face"
EYE_L, EYE_R = P + "EyeL", P + "EyeR"
ARM_L, ARM_R = P + "ArmL", P + "ArmR"
LEG_L, LEG_R = P + "LegL", P + "LegR"
ANTENNA, ANCHOR = P + "Antenna", P + "Anchor"

ORANGE = (0.95, 0.42, 0.05, 1)
WHITE = (0.88, 0.9, 0.93, 1)
DARK = (0.04, 0.05, 0.07, 1)
LIMB = (0.17, 0.18, 0.21, 1)
CYAN = (0.35, 0.95, 1.0, 1)

EYE_BASE = Vector((0.75, 0.35, 1.25))

# name: (eyeL scale mult, eyeR scale mult, eye z offset, head tilt)
EXPRESSIONS = {
    'idle':      ((1, 1, 1),       (1, 1, 1),       0.0,  0.0),
    'happy':     ((1.15, 1, 0.35), (1.15, 1, 0.35), 0.035, 0.0),
    'surprised': ((1.3, 1, 1.3),   (1.3, 1, 1.3),   0.02, 0.0),
    'confused':  ((1, 1, 0.45),    (1, 1, 1.15),    0.0,  0.2),
    'thinking':  ((1, 1, 0.75),    (1, 1, 0.75),    0.07, -0.12),
}
EXPR_IDS = {k: i for i, k in enumerate(EXPRESSIONS)}

HOP_DUR = 0.5
SPIN_DUR = 1.1

S = {}


def reset_state():
    S.clear()
    S.update(
        pos=Vector((0, 0, 0)), yaw=0.0, yaw_target=0.0,
        walk=None, wave=0.0, hop=0.0, hop_h=0.55, hops=0, spin=0.0,
        expr='idle', expr_until=0.0, base_expr='idle',
        blink=0.0, next_blink=2.0, t=0.0, phase=0.0, swing=0.0,
        tilt=0.0,
    )


reset_state()


# ------------------------------------------------------------------ building
def _bm_box(sx, sy, sz, matrix=None):
    bm = bmesh.new()
    m = Matrix.Diagonal((sx, sy, sz, 1))
    if matrix is not None:
        m = matrix @ m
    bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    return bm


def _remove_obj(name):
    old = bpy.data.objects.get(name)
    if old is not None:
        data = old.data
        bpy.data.objects.remove(old, do_unlink=True)
        if data is not None and data.users == 0 and isinstance(data, bpy.types.Mesh):
            bpy.data.meshes.remove(data)


def _obj(name, bm, coll, color, parent=None, loc=(0, 0, 0), smooth=False, bevel=0.0, segs=3):
    _remove_obj(name)
    me = bpy.data.meshes.new(name)
    me["bb_lesson"] = 1
    bm.to_mesh(me)
    bm.free()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.color = color
    if parent is not None:
        ob.parent = parent
    ob.location = loc
    if bevel > 0:
        md = ob.modifiers.new("Bevel", 'BEVEL')
        md.width = bevel
        md.segments = segs
        md.limit_method = 'ANGLE'
        md.harden_normals = True
        for p in me.polygons:
            p.use_smooth = True
    ob["bb_lesson"] = 1
    ob["bb_label"] = "me"
    return ob


def _empty(name, coll, parent=None, loc=(0, 0, 0)):
    old = bpy.data.objects.get(name)
    if old is not None:
        bpy.data.objects.remove(old, do_unlink=True)
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_size = 0.2
    coll.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    ob.location = loc
    ob.hide_select = True
    ob["bb_lesson"] = 1
    return ob


def build(coll):
    """Create the placeholder bot at the current state position."""
    root = _empty(ROOT, coll)
    root.hide_select = True

    body = _obj(BODY, _bm_box(0.8, 0.55, 0.72), coll, ORANGE, root, (0, 0, 0.98), bevel=0.14)

    head = _obj(HEAD, _bm_box(1.0, 0.78, 0.68), coll, WHITE, body, (0, 0, 0.78), bevel=0.2)
    _obj(FACE, _bm_box(0.8, 0.05, 0.48), coll, DARK, head, (0, -0.375, 0.0), bevel=0.1)

    for name, x in ((EYE_L, 0.17), (EYE_R, -0.17)):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=0.1)
        e = _obj(name, bm, coll, CYAN, head, (x, -0.41, 0.02), smooth=True)
        e.scale = EYE_BASE

    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.025, radius2=0.025, depth=0.24,
                          matrix=Matrix.Translation((0, 0, 0.12)))
    bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.075,
                              matrix=Matrix.Translation((0, 0, 0.27)))
    _obj(ANTENNA, bm, coll, ORANGE, head, (0, 0, 0.34), smooth=True)

    for name, x in ((ARM_L, 0.5), (ARM_R, -0.5)):
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.08, radius2=0.08, depth=0.55,
                              matrix=Matrix.Translation((0, 0, -0.275)))
        bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.13,
                                  matrix=Matrix.Translation((0, 0, -0.62)))
        _obj(name, bm, coll, LIMB, body, (x, 0, 0.28), smooth=True)

    for name, x in ((LEG_L, 0.2), (LEG_R, -0.2)):
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.11, radius2=0.11, depth=0.55,
                              matrix=Matrix.Translation((0, 0, -0.275)))
        bmesh.ops.create_cube(bm, size=1.0,
                              matrix=Matrix.Translation((0, -0.07, -0.58)) @ Matrix.Diagonal((0.26, 0.4, 0.12, 1)))
        _obj(name, bm, coll, LIMB, root, (x, 0, 0.62), smooth=False)

    _empty(ANCHOR, coll, head, (0.4, 0, 0.5))
    root["bb_expression"] = S['expr']
    root["bb_expression_id"] = EXPR_IDS.get(S['expr'], 0)
    _apply(0.0)
    return root


def exists():
    return bpy.data.objects.get(ROOT) is not None and bpy.data.objects.get(BODY) is not None


def is_bot(ob):
    return ob is not None and ob.name.startswith(P)


def body_world():
    b = bpy.data.objects.get(BODY)
    if b is None:
        return S['pos'] + Vector((0, 0, 1.0))
    return b.matrix_world.translation.copy()


def anchor_world():
    a = bpy.data.objects.get(ANCHOR)
    if a is None:
        return S['pos'] + Vector((0.4, 0, 2.6))
    return a.matrix_world.translation.copy()


def forward():
    y = S['yaw']
    return Vector((math.sin(y), -math.cos(y), 0))


# ------------------------------------------------------------------ actions
def teleport(pos, yaw_deg=None):
    S['pos'] = Vector((pos[0], pos[1], 0))
    S['walk'] = None
    if yaw_deg is not None:
        S['yaw'] = S['yaw_target'] = math.radians(yaw_deg)
    body = bpy.data.objects.get(BODY)
    if body is not None:
        body.location = (0, 0, 0.98)
        body.rotation_euler = (0, 0, 0)
        body.scale = (1, 1, 1)


def walk_to(pos, speed=1.8, yaw_deg=None, delay=0.0):
    S['walk'] = dict(to=Vector((pos[0], pos[1], 0)), speed=speed,
                     yaw=None if yaw_deg is None else math.radians(yaw_deg), delay=delay)


def is_walking():
    return S['walk'] is not None


def wave(dur=2.2):
    S['wave'] = dur


def hop(height=0.55, times=1):
    S['hop'] = HOP_DUR
    S['hop_h'] = height
    S['hops'] = times - 1


def celebrate():
    hop(0.7, 2)
    S['spin'] = SPIN_DUR


def set_expression(name, hold=None, now=0.0):
    """hold=None makes it the resting expression; hold=seconds makes it temporary."""
    if name not in EXPRESSIONS:
        name = 'idle'
    if hold is None:
        S['base_expr'] = name
        S['expr'] = name
        S['expr_until'] = 0.0
    else:
        S['expr'] = name
        S['expr_until'] = now + hold


# ------------------------------------------------------------------ per-frame
def _lerp_angle(a, b, t):
    d = (b - a + math.pi) % (2 * math.pi) - math.pi
    return a + d * t


def update(dt, now):
    S['t'] += dt
    t = S['t']
    moving = False
    w = S['walk']
    if w is not None:
        if w['delay'] > 0:
            w['delay'] -= dt
        else:
            d = w['to'] - S['pos']
            d.z = 0
            dist = d.length
            step = w['speed'] * dt
            if dist <= step or dist < 1e-4:
                S['pos'] = w['to'].copy()
                if w['yaw'] is not None:
                    S['yaw_target'] = w['yaw']
                S['walk'] = None
            else:
                S['pos'] += d.normalized() * step
                S['yaw_target'] = math.atan2(d.x, -d.y)
                S['phase'] += dt * w['speed'] * 3.4
                moving = True
    S['yaw'] = _lerp_angle(S['yaw'], S['yaw_target'], min(1.0, dt * 9))
    target_swing = math.sin(S['phase']) * 0.6 if moving else 0.0
    S['swing'] += (target_swing - S['swing']) * min(1.0, dt * 14)

    if S['expr_until'] and now > S['expr_until']:
        S['expr'] = S['base_expr']
        S['expr_until'] = 0.0

    if S['blink'] > 0:
        S['blink'] -= dt
    else:
        S['next_blink'] -= dt
        if S['next_blink'] <= 0:
            S['blink'] = 0.13
            S['next_blink'] = random.uniform(2.2, 5.0)

    if S['hop'] > 0:
        S['hop'] -= dt
        if S['hop'] <= 0 and S['hops'] > 0:
            S['hops'] -= 1
            S['hop'] = HOP_DUR
    if S['spin'] > 0:
        S['spin'] -= dt
    if S['wave'] > 0:
        S['wave'] -= dt
    _apply(t, moving)


def _apply(t, moving=False):
    root = bpy.data.objects.get(ROOT)
    if root is None:
        return
    z = 0.0
    if moving:
        z += abs(math.sin(S['phase'])) * 0.07
    else:
        z += 0.035 * math.sin(t * 2.2)
    if S['hop'] > 0:
        u = 1.0 - S['hop'] / HOP_DUR
        z += 4 * S['hop_h'] * u * (1 - u)
    spin = 0.0
    if S['spin'] > 0:
        u = 1.0 - S['spin'] / SPIN_DUR
        spin = (u * u * (3 - 2 * u)) * 2 * math.pi
    root.location = S['pos'] + Vector((0, 0, z))
    root.rotation_euler = (0, 0, S['yaw'] + spin)
    if root.get("bb_expression") != S['expr']:
        root["bb_expression"] = S['expr']
        root["bb_expression_id"] = EXPR_IDS.get(S['expr'], 0)

    sw = S['swing']
    leg_l, leg_r = bpy.data.objects.get(LEG_L), bpy.data.objects.get(LEG_R)
    if leg_l:
        leg_l.rotation_euler = (sw, 0, 0)
    if leg_r:
        leg_r.rotation_euler = (-sw, 0, 0)

    arm_l, arm_r = bpy.data.objects.get(ARM_L), bpy.data.objects.get(ARM_R)
    cheer = S['spin'] > 0
    if arm_l:
        arm_l.rotation_euler = (-sw * 0.8, -2.5 if cheer else -0.12, 0)
    if arm_r:
        if S['wave'] > 0:
            arm_r.rotation_euler = (0, 2.55 + 0.35 * math.sin(t * 11), 0)
        else:
            arm_r.rotation_euler = (sw * 0.8, 2.5 if cheer else 0.12, 0)

    el, er, ez, tilt = EXPRESSIONS.get(S['expr'], EXPRESSIONS['idle'])
    blink = 0.12 if S['blink'] > 0 else 1.0
    for name, mult, x in ((EYE_L, el, 0.17), (EYE_R, er, -0.17)):
        e = bpy.data.objects.get(name)
        if e:
            e.scale = (EYE_BASE.x * mult[0], EYE_BASE.y * mult[1], EYE_BASE.z * mult[2] * blink)
            e.location = (x, -0.41, 0.02 + ez)
    S['tilt'] += (tilt - S['tilt']) * 0.25
    head = bpy.data.objects.get(HEAD)
    if head:
        head.rotation_euler = (0, S['tilt'], 0)
