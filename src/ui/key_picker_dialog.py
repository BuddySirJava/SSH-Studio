import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GObject
from gettext import gettext as _
from pathlib import Path


@Gtk.Template(
    resource_path="/io/github/BuddySirJava/SSH-Studio/ui/key_picker_dialog.ui"
)
class KeyPickerDialog(Adw.Dialog):
    __gtype_name__ = "KeyPickerDialog"

    __gsignals__ = {
        "key-selected": (GObject.SignalFlags.RUN_LAST, None, (str,)),
    }

    toast_overlay = Gtk.Template.Child()
    public_list = Gtk.Template.Child()
    cancel_btn = Gtk.Template.Child()
    use_btn = Gtk.Template.Child()
    generate_btn = Gtk.Template.Child()

    def __init__(self, parent):
        super().__init__()
        self.cancel_btn.connect("clicked", lambda *_: self.close())
        self.use_btn.connect("clicked", self._on_use)
        self.public_list.connect("row-selected", self._on_selection_changed)
        self._load_keys()

    def _load_keys(self):
        ssh_dir = Path.home() / ".ssh"
        for lst in (self.public_list,):
            row = lst.get_first_child()
            while row is not None:
                nxt = row.get_next_sibling()
                lst.remove(row)
                row = nxt
        if ssh_dir.exists():
            for path in sorted(ssh_dir.iterdir()):
                if not path.is_file():
                    continue
                name = path.name
                if name in {"config", "known_hosts", "authorized_keys"}:
                    continue
                if name.endswith(".pub"):
                    self.public_list.append(self._row_for(path))
        self._update_use_sensitivity()

    def _row_for(self, path: Path):
        row = Gtk.ListBoxRow()
        action = Adw.ActionRow()
        action.set_title(path.name)
        action.set_subtitle(str(path))
        action.set_activatable(True)
        row.set_child(action)
        row.path_value = str(path)
        return row

    def _on_selection_changed(self, *_):
        self._update_use_sensitivity()

    def _update_use_sensitivity(self):
        has_sel = bool(self.public_list.get_selected_row())
        try:
            self.use_btn.set_sensitive(has_sel)
        except Exception:
            pass

    def _on_use(self, *_):
        row = self.public_list.get_selected_row()
        if row and hasattr(row, "path_value"):
            path = Path(row.path_value)
            private = path.with_suffix("") if path.suffix == ".pub" else path
            self.selected_path = str(private)
            try:
                self.emit("key-selected", self.selected_path)
            finally:
                self.close()
