import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk
from gettext import gettext as _


@Gtk.Template(
    resource_path="/io/github/BuddySirJava/SSH-Studio/ui/keyboard_shortcuts_dialog.ui"
)
class KeyboardShortcutsDialog(Adw.Dialog):
    """Dialog showing keyboard shortcuts for SSH Studio."""

    __gtype_name__ = "KeyboardShortcutsDialog"

    def __init__(self, parent=None):
        super().__init__()
        self._parent = parent
        try:
            self.set_title(_("Keyboard Shortcuts"))
        except Exception:
            pass
        try:
            self.set_default_size(680, 250)
        except Exception:
            pass
        try:
            if hasattr(self, "set_content_width"):
                self.set_content_width(680)
            if hasattr(self, "set_content_height"):
                self.set_content_height(540)
        except Exception:
            pass

        self._setup_keyboard_shortcuts()

    def _setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts for the shortcuts dialog."""
        key_controller = Gtk.EventControllerKey.new()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_controller)

    def _on_key_pressed(self, controller, keyval, keycode, state):
        """Handle key presses in the shortcuts dialog."""
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False
