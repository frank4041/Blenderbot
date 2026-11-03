"""Blenderbot: an interactive guide that teaches Blender inside Blender."""

from . import engine, ui


def register():
    ui.register()


def unregister():
    engine.stop(restore=True)
    ui.unregister()
