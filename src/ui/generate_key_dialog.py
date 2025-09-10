import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw
from gettext import gettext as _


@Gtk.Template(resource_path="/com/sshconfigstudio/app/ui/generate_key_dialog.ui")
class GenerateKeyDialog(Adw.Dialog):
    __gtype_name__ = "GenerateKeyDialog"

    toast_overlay = Gtk.Template.Child()
    type_row = Gtk.Template.Child()
    size_row = Gtk.Template.Child()
    name_row = Gtk.Template.Child()
    comment_row = Gtk.Template.Child()
    pass_row = Gtk.Template.Child()
    cancel_btn = Gtk.Template.Child()
    generate_btn = Gtk.Template.Child()

    def __init__(self, parent):
        super().__init__()
        self.cancel_btn.connect("clicked", lambda *_: self.close())
        self._populate_types()
        self._populate_sizes()
        self._sync_size_visibility()
        self.type_row.connect("notify::selected-item", self._on_type_changed)

    def _populate_types(self):
        store = Gtk.StringList.new(["ed25519", "rsa", "ecdsa"])
        try:
            self.type_row.set_model(store)
            self.type_row.set_selected(0)
        except Exception:
            pass

    def _populate_sizes(self):
        store = Gtk.StringList.new(["1024", "2048", "3072", "4096", "8192"])
        try:
            self.size_row.set_model(store)
            self.size_row.set_selected(1)
        except Exception:
            pass

    def _on_type_changed(self, *_):
        self._sync_size_visibility()

    def _sync_size_visibility(self):
        try:
            item = self.type_row.get_selected_item()
            key_type = item.get_string() if item else "ed25519"
            self.size_row.set_visible(key_type == "rsa")
        except Exception:
            pass

    def get_options(self):
        key_type = self.type_row.get_selected_item().get_string() if self.type_row.get_selected_item() else "ed25519"
        size_item = self.size_row.get_selected_item()
        size = int(size_item.get_string()) if size_item and self.size_row.get_visible() else 2048
        name = self.name_row.get_text() or "id_ed25519"
        comment = self.comment_row.get_text() or "ssh-config-studio"
        passphrase = self.pass_row.get_text() or ""
        return {
            "type": key_type,
            "size": size,
            "name": name,
            "comment": comment,
            "passphrase": passphrase,
        }


