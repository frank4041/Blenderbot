import bpy
from bpy.app.handlers import persistent

from . import engine as E
from .lessons import LESSONS, BEYOND


class BLENDERBOT_OT_start(bpy.types.Operator):
    """Start an interactive lesson with Blenderbot (opens in its own scene, your work is untouched)"""
    bl_idname = "blenderbot.start"
    bl_label = "Start Lesson"
    bl_options = {'REGISTER', 'UNDO'}

    lesson: bpy.props.StringProperty(default="basics")

    def execute(self, context):
        lesson = LESSONS.get(self.lesson)
        if lesson is None:
            self.report({'ERROR'}, f"Unknown lesson {self.lesson}")
            return {'CANCELLED'}
        E.start(context, lesson)
        bpy.ops.blenderbot.watch('INVOKE_DEFAULT')
        return {'FINISHED'}


class BLENDERBOT_OT_watch(bpy.types.Operator):
    """Watches input during a lesson (clicks on the overlay, Maya habits)"""
    bl_idname = "blenderbot.watch"
    bl_label = "Blenderbot Watcher"
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        self.session = E.rt.session
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if not E.rt.active or E.rt.session != self.session:
            return {'FINISHED'}
        try:
            if E.handle_event(event):
                return {'RUNNING_MODAL'}
        except Exception:
            import traceback
            traceback.print_exc()
        return {'PASS_THROUGH'}


class BLENDERBOT_OT_action(bpy.types.Operator):
    """Lesson control"""
    bl_idname = "blenderbot.action"
    bl_label = "Blenderbot"
    bl_options = {'INTERNAL'}

    action: bpy.props.EnumProperty(items=[
        ('next', "Next", ""), ('skip', "Skip", ""), ('restart', "Restart step", ""),
        ('hint', "Hint", ""), ('exit', "Exit lesson", ""),
    ])

    def execute(self, context):
        E.click(self.action)
        return {'FINISHED'}


class VIEW3D_PT_blenderbot(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Blenderbot"
    bl_label = "Blenderbot"

    def draw(self, context):
        layout = self.layout
        rt = E.rt
        wm = context.window_manager
        if rt.active:
            st = rt.step()
            col = layout.column(align=True)
            col.label(text=f"{rt.lesson.name}: step {rt.index + 1} of {len(rt.lesson.steps)}")
            col.label(text=st.title, icon='PLAY')
            row = layout.row(align=True)
            sub = row.row(align=True)
            sub.enabled = rt.step_done
            sub.operator("blenderbot.action", text="Next", icon='TRIA_RIGHT').action = 'next'
            row.operator("blenderbot.action", text="Skip").action = 'skip'
            row = layout.row(align=True)
            row.operator("blenderbot.action", text="Hint", icon='QUESTION').action = 'hint'
            row.operator("blenderbot.action", text="Restart step", icon='FILE_REFRESH').action = 'restart'
            layout.operator("blenderbot.action", text="Exit lesson", icon='CANCEL').action = 'exit'
            return

        box = layout.box()
        box.label(text="The Basics", icon='OUTLINER_OB_ARMATURE')
        lesson = LESSONS["basics"]
        box.label(text="Move around, select, move, rotate, scale.")
        box.operator("blenderbot.start", text="Start", icon='PLAY').lesson = "basics"

        layout.separator()
        layout.prop(wm, "blenderbot_beyond", text="Beyond the basics")
        if wm.blenderbot_beyond:
            col = layout.column(align=True)
            for name, blurb in BEYOND:
                b = col.box()
                b.enabled = False
                b.label(text=f"{name} (coming soon)", icon='LOCKED')
                b.label(text=blurb)


@persistent
def _on_load(_):
    E.stop(restore=False)


classes = (BLENDERBOT_OT_start, BLENDERBOT_OT_watch, BLENDERBOT_OT_action, VIEW3D_PT_blenderbot)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.WindowManager.blenderbot_beyond = bpy.props.BoolProperty(
        name="Beyond the basics",
        description="Opt in to show the extra chapters that go past the basics",
        default=False)
    if _on_load not in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.append(_on_load)


def unregister():
    if _on_load in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.remove(_on_load)
    del bpy.types.WindowManager.blenderbot_beyond
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
