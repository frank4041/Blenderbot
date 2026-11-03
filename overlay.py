"""Viewport overlay: speech bubble pinned to the bot, task card, learned-keys cheat sheet."""
import bpy
import blf
import gpu
import math
import time
from gpu_extras.batch import batch_for_shader
from mathutils import Vector

from . import engine as E
from . import bot, keys

FONT = 0
ORANGE = (0.98, 0.55, 0.14, 1.0)
BUBBLE = (0.98, 0.98, 0.97, 0.97)
INK = (0.1, 0.11, 0.13, 1.0)
CARD = (0.1, 0.11, 0.13, 0.93)
CARD_LINE = (1, 1, 1, 0.08)
TXT = (0.92, 0.93, 0.95, 1.0)
DIM = (0.6, 0.63, 0.68, 1.0)
GREEN = (0.32, 0.88, 0.5, 1.0)
GREY = (0.32, 0.34, 0.38, 1.0)

_sh = None


def _shader():
    global _sh
    if _sh is None:
        _sh = gpu.shader.from_builtin('UNIFORM_COLOR')
    return _sh


def _fill(verts, idx, color):
    sh = _shader()
    b = batch_for_shader(sh, 'TRIS', {"pos": verts}, indices=idx)
    sh.bind()
    sh.uniform_float("color", color)
    b.draw(sh)


def rrect(x0, y0, x1, y1, r, color, seg=6):
    r = max(0.0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    pts = []
    for cx, cy, a0 in ((x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180), (x1 - r, y0 + r, 270)):
        for i in range(seg + 1):
            a = math.radians(a0 + 90 * i / seg)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    verts = [((x0 + x1) / 2, (y0 + y1) / 2)] + pts
    n = len(pts)
    idx = [(0, i, i + 1) for i in range(1, n)] + [(0, n, 1)]
    _fill(verts, idx, color)


def circle(x, y, r, color, seg=20):
    verts = [(x, y)] + [(x + r * math.cos(2 * math.pi * i / seg), y + r * math.sin(2 * math.pi * i / seg))
                        for i in range(seg)]
    idx = [(0, i, i % seg + 1) for i in range(1, seg + 1)]
    _fill(verts, idx, color)


def tri(a, b, c, color):
    _fill([a, b, c], [(0, 1, 2)], color)


def text(x, y, s, size, color):
    blf.size(FONT, size)
    blf.color(FONT, *color)
    blf.position(FONT, x, y, 0)
    blf.draw(FONT, s)


def tw(s, size):
    blf.size(FONT, size)
    return blf.dimensions(FONT, s)[0]


# ------------------------------------------------------------ rich text
def tokens(src):
    out, word, acc, sp, i = [], "", False, False, 0
    while i < len(src):
        if src.startswith("**", i):
            if word:
                out.append((word, acc, sp))
                word, sp = "", False
            acc = not acc
            i += 2
            continue
        ch = src[i]
        if ch == " ":
            if word:
                out.append((word, acc, sp))
                word = ""
            sp = True
        else:
            word += ch
        i += 1
    if word:
        out.append((word, acc, sp))
    return out


def layout(toks, maxw, size):
    blf.size(FONT, size)
    spw = blf.dimensions(FONT, " ")[0]
    lines, x, widest = [[]], 0.0, 0.0
    for w, acc, sp in toks:
        ww = blf.dimensions(FONT, w)[0]
        gap = spw if (sp and lines[-1]) else 0.0
        if lines[-1] and x + gap + ww > maxw and sp:
            lines.append([])
            x, gap = 0.0, 0.0
        lines[-1].append((x + gap, w, acc))
        x += gap + ww
        widest = max(widest, x)
    return lines, widest


def draw_rich(lines, x, y_top, size, lh, color, accent, reveal):
    n = reveal
    for li, line in enumerate(lines):
        y = y_top - (li + 1) * lh + (lh - size) * 0.5
        for (ox, w, acc) in line:
            if n <= 0:
                return
            part = w[:n]
            n -= len(w)
            text(x + ox, y, part, size, accent if acc else color)


# ------------------------------------------------------------ main
def _scale():
    p = bpy.context.preferences.system
    try:
        return max(0.75, p.dpi / 72.0)
    except Exception:
        return p.ui_scale


def _pads(area, region):
    left = right = top = 0
    for r in area.regions:
        if r.width <= 1 or r.height <= 1:
            continue
        if r.type == 'TOOLS':
            left = max(left, r.width)
        elif r.type == 'UI':
            right = max(right, r.width)
        elif r.type in {'HEADER', 'TOOL_HEADER'}:
            if r.y >= region.y + region.height - r.height - 2 and r.y < region.y + region.height:
                top += r.height
    return left, right, top


def draw():
    rt = E.rt
    if not rt.active:
        return
    ctx = bpy.context
    area, region, rv3d = ctx.area, ctx.region, ctx.region_data
    if area is None or region is None or rv3d is None:
        return
    if ctx.scene is None or ctx.scene.name != E.LESSON_SCENE or area.as_pointer() != rt.main_area_ptr:
        return
    s = _scale()
    left, right, top = _pads(area, region)
    W, H = region.width, region.height
    buttons = {}
    gpu.state.blend_set('ALPHA')
    try:
        card_rect = _draw_card(rt, s, W - right - 14 * s, 14 * s, region, buttons)
        _draw_cheats(rt, s, left + 12 * s, H - top - 12 * s)
        _draw_bubble(rt, s, region, rv3d, left, right, top, card_rect, buttons)
    finally:
        gpu.state.blend_set('NONE')
    rt.buttons = buttons


def _to_win(region, x0, y0, x1, y1):
    return (region.x + x0, region.y + y0, region.x + x1, region.y + y1)


# ------------------------------------------------------------ bubble
def _draw_bubble(rt, s, region, rv3d, left, right, top, card_rect, buttons):
    src, t0 = E.current_text()
    if not src:
        return
    size = 15 * s
    lh = size * 1.42
    pad = 14 * s
    name_h = 16 * s
    toks = tokens(src)
    lines, widest = layout(toks, 330 * s, size)
    w = max(widest, tw("BLENDERBOT", 10 * s)) + pad * 2
    h = len(lines) * lh + pad * 2 + name_h
    total = sum(len(t[0]) for t in toks)
    reveal = total if (rt.reveal_all or t0 == 0.0) else int((time.perf_counter() - t0) * E.TYPE_CPS)
    reveal = min(reveal, total)

    W, H = region.width, region.height
    m = 12 * s
    xmin, xmax = left + m, W - right - m
    ymin, ymax = m, H - top - m

    co = bot.anchor_world()
    p = rv3d.perspective_matrix @ Vector((co.x, co.y, co.z, 1.0))
    onscreen = False
    ax = ay = 0.0
    if p.w > 1e-6:
        ax = (p.x / p.w + 1) * 0.5 * W
        ay = (p.y / p.w + 1) * 0.5 * H
        onscreen = xmin <= ax <= xmax and ymin <= ay <= ymax
        dirv = Vector((ax - W / 2, ay - H / 2))
    else:
        dirv = Vector((-p.x, -p.y))

    if onscreen:
        bx = ax + 18 * s
        by = ay + 22 * s
        bx = min(max(bx, xmin), xmax - w)
        by = min(max(by, ymin), ymax - h)
        # avoid sitting on the task card
        cx0, cy0, cx1, cy1 = card_rect
        if bx < cx1 and bx + w > cx0 and by < cy1 and by + h > cy0:
            by = cy1 + 8 * s
            if by + h > ymax:
                bx = cx0 - w - 8 * s
                by = min(max(ay - h / 2, ymin), ymax - h)
        # tail
        if ay < by:
            tx = min(max(ax, bx + 18 * s), bx + w - 18 * s)
            tri((tx - 9 * s, by + 1), (tx + 9 * s, by + 1), (ax, ay), BUBBLE)
        elif ay > by + h:
            tx = min(max(ax, bx + 18 * s), bx + w - 18 * s)
            tri((tx - 9 * s, by + h - 1), (tx + 9 * s, by + h - 1), (ax, ay), BUBBLE)
        else:
            ty = min(max(ay, by + 14 * s), by + h - 14 * s)
            ex = bx if ax < bx else bx + w
            tri((ex, ty - 9 * s), (ex, ty + 9 * s), (ax, ay), BUBBLE)
    else:
        if dirv.length < 1e-6:
            dirv = Vector((0, -1))
        d = dirv.normalized()
        cx = W / 2 + d.x * W
        cy = H / 2 + d.y * H
        bx = min(max(cx - w / 2, xmin + 20 * s), xmax - w - 20 * s)
        by = min(max(cy - h / 2, ymin + 20 * s), ymax - h - 20 * s)
        # arrow pointing toward Blenderbot
        mx, my = bx + w / 2, by + h / 2
        ex, ey = mx + d.x * (w / 2 + 6 * s), my + d.y * (h / 2 + 6 * s)
        ex = min(max(ex, bx - 14 * s), bx + w + 14 * s)
        ey = min(max(ey, by - 14 * s), by + h + 14 * s)
        perp = Vector((-d.y, d.x)) * 11 * s
        tip = Vector((ex, ey)) + d * 16 * s
        pulse = 0.75 + 0.25 * math.sin(time.perf_counter() * 6)
        tri((ex + perp.x, ey + perp.y), (ex - perp.x, ey - perp.y), (tip.x, tip.y),
            (ORANGE[0], ORANGE[1], ORANGE[2], pulse))

    rrect(bx, by, bx + w, by + h, 12 * s, BUBBLE)
    text(bx + pad, by + h - pad - 10 * s, "BLENDERBOT", 10 * s, ORANGE)
    if not onscreen:
        text(bx + pad + tw("BLENDERBOT  ", 10 * s), by + h - pad - 10 * s, "(I'm over here!)", 10 * s, DIM)
    draw_rich(lines, bx + pad, by + h - pad - name_h, size, lh, INK, (0.85, 0.38, 0.0, 1), reveal)
    buttons['bubble'] = _to_win(region, bx, by, bx + w, by + h)


# ------------------------------------------------------------ task card
def _btn_text(label, x, y, size, color, hover):
    text(x, y, label, size, TXT if hover else color)
    return tw(label, size)


def _draw_card(rt, s, x1, y0, region, buttons):
    st = rt.step()
    W = 300 * s
    x0 = x1 - W
    pad = 14 * s
    row = 22 * s
    fs = 12.5 * s
    total = len(rt.lesson.steps)
    n_tasks = len(st.tasks)
    body_rows = n_tasks if n_tasks else 1
    bar = (not rt.step_done and n_tasks and st.tasks[rt.task_index].bar)
    h = pad + 14 * s + 10 * s + body_rows * row + (10 * s if bar else 0) + 12 * s + 1 + 12 * s + 26 * s + pad
    y1 = y0 + h
    rrect(x0, y0, x1, y1, 12 * s, CARD)

    # title row
    y = y1 - pad - 11 * s
    title = f"{st.title.upper()}"
    text(x0 + pad, y, title, 10.5 * s, ORANGE)
    text(x0 + pad + tw(title + "   ", 10.5 * s), y, f"{rt.index + 1} / {total}", 10.5 * s, DIM)
    ex_w = tw("Exit", 10.5 * s)
    hov = rt.hover == 'exit'
    text(x1 - pad - ex_w, y, "Exit", 10.5 * s, TXT if hov else DIM)
    buttons['exit'] = _to_win(region, x1 - pad - ex_w - 4 * s, y - 5 * s, x1 - pad + 4 * s, y + 14 * s)

    y -= 10 * s
    # tasks
    if n_tasks:
        for i, task in enumerate(st.tasks):
            y -= row
            cy = y + row / 2 - 2 * s
            label = keys.fmt(task.label)
            if i < rt.task_index or rt.step_done:
                circle(x0 + pad + 6 * s, cy, 6 * s, GREEN)
                col = DIM
            elif i == rt.task_index:
                circle(x0 + pad + 6 * s, cy, 6 * s, ORANGE)
                circle(x0 + pad + 6 * s, cy, 3 * s, CARD)
                col = TXT
            else:
                circle(x0 + pad + 6 * s, cy, 6 * s, GREY)
                col = DIM
            max_w = W - pad * 2 - 22 * s
            while label and tw(label, fs) > max_w:
                label = label[:-2]
            text(x0 + pad + 20 * s, cy - fs * 0.35, label, fs, col)
            if bar and i == rt.task_index:
                y -= 10 * s
                bx0, bx1 = x0 + pad + 20 * s, x1 - pad
                rrect(bx0, y + 2 * s, bx1, y + 6 * s, 2 * s, GREY)
                p = max(0.0, min(1.0, rt.task_progress))
                if p > 0.01:
                    rrect(bx0, y + 2 * s, bx0 + (bx1 - bx0) * p, y + 6 * s, 2 * s, ORANGE)
    else:
        y -= row
        text(x0 + pad, y + row / 2 - fs * 0.6, "Click Next when you're ready.", fs, DIM)

    y -= 12 * s
    rrect(x0 + pad, y, x1 - pad, y + 1, 0, CARD_LINE)
    y -= 12 * s + 26 * s

    # footer: Hint · Restart · Skip            [ Next ]
    fx = x0 + pad
    ty = y + 13 * s - 4.5 * s
    for name, label in (('hint', "Hint"), ('restart', "Restart"), ('skip', "Skip")):
        if name == 'hint' and not st.hint:
            continue
        if name == 'skip' and rt.step_done:
            continue
        wlab = _btn_text(label, fx, ty, 12 * s, DIM, rt.hover == name)
        buttons[name] = _to_win(region, fx - 4 * s, y, fx + wlab + 4 * s, y + 26 * s)
        fx += wlab + 16 * s

    last = rt.index >= total - 1
    nlabel = "Finish" if last else "Next"
    nw = 78 * s
    nx0, nx1 = x1 - pad - nw, x1 - pad
    if rt.step_done:
        k = 0.82 + 0.18 * math.sin(time.perf_counter() * 4.5)
        col = (ORANGE[0] * k, ORANGE[1] * k, ORANGE[2] * k, 1)
        if rt.hover == 'next':
            col = (1.0, 0.66, 0.3, 1)
        rrect(nx0, y, nx1, y + 26 * s, 13 * s, col)
        tcol = (1, 1, 1, 1)
    else:
        rrect(nx0, y, nx1, y + 26 * s, 13 * s, GREY)
        tcol = DIM
    lw = tw(nlabel, 12.5 * s)
    text((nx0 + nx1) / 2 - lw / 2, y + 13 * s - 4.5 * s, nlabel, 12.5 * s, tcol)
    buttons['next'] = _to_win(region, nx0, y, nx1, y + 26 * s)
    return (x0, y0, x1, y1)


# ------------------------------------------------------------ cheat sheet
def _draw_cheats(rt, s, x0, y1):
    if not rt.learned:
        return
    L = keys.labels()
    fs = 11.5 * s
    pad = 12 * s
    row = 19 * s
    rows = []
    for action, key in rt.learned:
        k = L.get(key, keys.fmt(key))
        rows.append((action, k))
    kw = max(tw(k, fs) for _, k in rows)
    aw = max(tw(a, fs) for a, _ in rows)
    W = pad * 2 + aw + 18 * s + kw
    h = pad * 2 + 14 * s + len(rows) * row
    y0 = y1 - h
    rrect(x0, y0, x0 + W, y1, 10 * s, (0.1, 0.11, 0.13, 0.8))
    text(x0 + pad, y1 - pad - 9 * s, "LEARNED", 10 * s, ORANGE)
    y = y1 - pad - 14 * s
    for a, k in rows:
        y -= row
        text(x0 + pad, y + 5 * s, a, fs, TXT)
        text(x0 + W - pad - tw(k, fs), y + 5 * s, k, fs, DIM)
