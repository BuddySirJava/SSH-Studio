import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GObject, GLib
from gettext import gettext as _


@Gtk.Template(resource_path="/io/github/BuddySirJava/SSH-Studio/ui/search_bar.ui")
class SshStudioSearchBar(Gtk.Box):

    __gtype_name__ = "SearchBar"

    search_entry = Gtk.Template.Child()

    __gsignals__ = {"search-changed": (GObject.SignalFlags.RUN_LAST, None, (str,))}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.search_timeout = None
        self._connect_signals()

    def _connect_signals(self):
        if self.search_entry:
            self.search_entry.connect("search-changed", self._on_search_changed)

    def _on_search_changed(self, entry):
        query = entry.get_text()

        if self.search_timeout:
            GLib.source_remove(self.search_timeout)

        self.search_timeout = GLib.timeout_add(300, self._perform_search, query)

    def _perform_search(self, query: str):
        self.emit("search-changed", query)
        self.search_timeout = None
        return False

    def get_search_text(self) -> str:
        return self.search_entry.get_text()

    def set_search_text(self, text: str):
        self.search_entry.set_text(text)

    def clear_search(self):
        self.search_entry.set_text("")
        self.emit("search-changed", "")

    def grab_focus(self):
        self.search_entry.grab_focus()


# Backward-compatibility alias for older imports/templates
SearchBar = SshStudioSearchBar
