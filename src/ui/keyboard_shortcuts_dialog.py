import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk
from gettext import gettext as _


class KeyboardShortcutsDialog:

    def __init__(self, parent=None):
        builder = Gtk.Builder.new_from_resource(
            "/io/github/BuddySirJava/SSH-Studio/ui/keyboard_shortcuts_dialog.ui"
        )
        try:
            builder.set_translation_domain("ssh-studio")
        except Exception:
            pass
        self._dialog = builder.get_object("keyboard_shortcuts_dialog")
        if parent is not None:
            try:
                self._dialog.set_transient_for(parent)
            except Exception:
                pass

        key_controller = Gtk.EventControllerKey.new()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self._dialog.add_controller(key_controller)

    def _on_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self._dialog.close()
            return True
        return False

    def present(self, parent=None):
        if parent is not None:
            self._dialog.present(parent)
        else:
            self._dialog.present()

    def close(self):
        self._dialog.close()
