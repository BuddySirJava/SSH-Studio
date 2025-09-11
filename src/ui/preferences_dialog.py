import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gio, GObject, Adw, GLib
from gettext import gettext as _
import os
import json
from pathlib import Path


@Gtk.Template(resource_path="/com/sshstudio/app/ui/preferences_dialog.ui")
class PreferencesDialog(Adw.PreferencesWindow):
    """Application preferences dialog using Adwaita components."""

    __gtype_name__ = "PreferencesDialog"

    config_path_entry = Gtk.Template.Child()
    config_path_button = Gtk.Template.Child()
    backup_dir_entry = Gtk.Template.Child()
    backup_dir_button = Gtk.Template.Child()
    auto_backup_switch = Gtk.Template.Child()
    editor_font_spin = Gtk.Template.Child()
    dark_theme_switch = Gtk.Template.Child()
    raw_wrap_switch = Gtk.Template.Child()

    def __init__(self, parent):
        super().__init__(transient_for=parent, modal=True)
        try:
            self.set_title(_("Preferences"))
        except Exception:
            pass
        try:
            self.set_default_size(600, 500)
        except Exception:
            pass
        self._load_preferences_safely()
        GLib.idle_add(self._connect_signals)

    def _connect_signals(self):
        self.config_path_button.connect("clicked", self._on_config_path_clicked)
        self.backup_dir_button.connect("clicked", self._on_backup_dir_clicked)
        self.connect("close-request", self._on_close_request)
        self.config_path_entry.connect("changed", self._on_entry_changed)
        self.backup_dir_entry.connect("changed", self._on_entry_changed)
        self.auto_backup_switch.connect("notify::active", self._on_switch_toggled)
        self.dark_theme_switch.connect("notify::active", self._on_switch_toggled)
        self.raw_wrap_switch.connect("notify::active", self._on_switch_toggled)
        self.editor_font_spin.connect("notify::value", self._on_spin_changed)

        self.editor_font_spin.get_adjustment().connect(
            "value-changed", self._on_spin_changed
        )

    def _on_config_path_clicked(self, button):
        dialog = Gtk.FileChooserDialog(
            title=_("Choose SSH Config File"),
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("Open"), Gtk.ResponseType.OK)
        dialog.connect("response", self._on_file_chooser_response)
        dialog.present()

    def _on_file_chooser_response(self, dialog, response_id):
        if response_id == Gtk.ResponseType.OK:
            filename = dialog.get_file().get_path()
            self.config_path_entry.set_text(filename)
        dialog.destroy()

    def _on_backup_dir_clicked(self, button):
        dialog = Gtk.FileChooserDialog(
            title=_("Choose Backup Directory"),
            transient_for=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
        )
        dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("Select"), Gtk.ResponseType.OK)
        dialog.connect("response", self._on_backup_dir_response)
        dialog.present()

    def _on_backup_dir_response(self, dialog, response_id):
        if response_id == Gtk.ResponseType.OK:
            folder = dialog.get_file()
            if folder:
                self.backup_dir_entry.set_text(folder.get_path())
        dialog.destroy()

    def _get_config_dir(self) -> str:
        base_dir = GLib.get_user_config_dir() or os.path.join(
            str(Path.home()), ".config"
        )
        return os.path.join(base_dir, "ssh-studio")

    def _get_prefs_path(self) -> str:
        return os.path.join(self._get_config_dir(), "preferences.json")

    def _ensure_config_dir(self) -> None:
        os.makedirs(self._get_config_dir(), exist_ok=True)

    def _set_default_preferences(self) -> None:
        """Set default preference values."""
        import os

        default_ssh_config = os.path.expanduser("~/.ssh/config")
        self.config_path_entry.set_text(default_ssh_config)

        default_backup = os.path.expanduser("~/.ssh/backups")
        self.backup_dir_entry.set_text(default_backup)

        self.auto_backup_switch.set_active(True)
        self.dark_theme_switch.set_active(False)
        self.raw_wrap_switch.set_active(True)

        self.editor_font_spin.set_value(12.0)

    def _load_preferences_safely(self) -> None:
        try:
            path = self._get_prefs_path()
            if os.path.exists(path) and os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self.set_preferences(data)
                else:
                    self._set_default_preferences()
            else:
                self._set_default_preferences()
        except Exception:
            self._set_default_preferences()

    def _save_preferences_safely(self) -> None:
        try:
            self._ensure_config_dir()
            prefs = self.get_preferences()
            target_path = self._get_prefs_path()
            tmp_path = target_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(prefs, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, target_path)
        except Exception:
            pass

    def _on_entry_changed(self, entry):
        self._save_preferences_safely()

    def _on_switch_toggled(self, switch, pspec):
        self._save_preferences_safely()

    def _on_spin_changed(self, spin, pspec=None):
        self._save_preferences_safely()

    def _on_close_request(self, window):
        self._save_preferences_safely()
        return False

    def get_preferences(self) -> dict:
        return {
            "config_path": self.config_path_entry.get_text(),
            "backup_dir": self.backup_dir_entry.get_text(),
            "auto_backup": self.auto_backup_switch.get_active(),
            "editor_font_size": int(self.editor_font_spin.get_value()),
            "prefer_dark_theme": self.dark_theme_switch.get_active(),
            "raw_wrap_lines": self.raw_wrap_switch.get_active(),
        }

    def set_preferences(self, prefs: dict):
        if "config_path" in prefs:
            self.config_path_entry.set_text(prefs["config_path"])
        if "backup_dir" in prefs:
            self.backup_dir_entry.set_text(prefs["backup_dir"])
        if "auto_backup" in prefs:
            self.auto_backup_switch.set_active(bool(prefs["auto_backup"]))
        if "editor_font_size" in prefs:
            self.editor_font_spin.set_value(float(prefs["editor_font_size"]))
        if "prefer_dark_theme" in prefs:
            self.dark_theme_switch.set_active(bool(prefs["prefer_dark_theme"]))
        if "raw_wrap_lines" in prefs:
            self.raw_wrap_switch.set_active(bool(prefs["raw_wrap_lines"]))
