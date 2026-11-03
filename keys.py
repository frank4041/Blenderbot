"""Keymap-aware hotkey labels, so the bot always names the keys *this* user presses."""
import bpy


def _kmi_label(km_name, idname):
    try:
        kc = bpy.context.window_manager.keyconfigs.user
        km = kc.keymaps.get(km_name)
        if km is None:
            return None
        cands = [k for k in km.keymap_items
                 if k.idname == idname and k.active and k.map_type == 'KEYBOARD']
        cands.sort(key=lambda k: (k.ctrl == 1) + (k.shift == 1) + (k.alt == 1) + (k.oskey == 1))
        for kmi in cands[:1]:
            parts = []
            if kmi.ctrl == 1:
                parts.append("Ctrl")
            if kmi.shift == 1:
                parts.append("Shift")
            if kmi.alt == 1:
                parts.append("Alt")
            if kmi.oskey == 1:
                parts.append("Win")
            name = kmi.bl_rna.properties['type'].enum_items[kmi.type].name
            parts.append(name)
            return " + ".join(parts)
    except Exception:
        return None
    return None


def labels():
    inputs = bpy.context.preferences.inputs
    emulate = inputs.use_mouse_emulate_3_button
    L = {}
    if emulate:
        L['orbit'] = "Alt + Left Mouse"
        L['pan'] = "Shift + Alt + Left Mouse"
        L['zoom_drag'] = "Ctrl + Alt + Left Mouse"
    else:
        L['orbit'] = "Middle Mouse"
        L['pan'] = "Shift + Middle Mouse"
        L['zoom_drag'] = "Ctrl + Middle Mouse"
    L['zoom'] = "Scroll Wheel"
    L['select'] = "Left-click"
    L['frame'] = _kmi_label("3D View", "view3d.view_selected") or "Numpad ."
    L['grab'] = _kmi_label("Object Mode", "transform.translate") or "G"
    L['rotate'] = _kmi_label("Object Mode", "transform.rotate") or "R"
    L['scale'] = _kmi_label("Object Mode", "transform.resize") or "S"
    return L


def fmt(text):
    """Fill {orbit}-style placeholders with the user's real keys."""
    if not text:
        return text
    try:
        return text.format(**labels())
    except (KeyError, IndexError, ValueError):
        return text
