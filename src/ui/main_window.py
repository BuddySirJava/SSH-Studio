import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gio, Gdk, Adw, GLib
from pathlib import Path
from gettext import gettext as _
import sys
from .host_list import HostList
from .host_editor import HostEditor
from .welcome_view import WelcomeView
from gi.repository import Gio as _Gio


@Gtk.Template(resource_path="/io/github/BuddySirJava/SSH-Studio/ui/main_window.ui")
class MainWindow(Adw.ApplicationWindow):
    """Main application window for SSH-Studio."""

    __gtype_name__ = "MainWindow"

    main_box = Gtk.Template.Child()
    toast_overlay = Gtk.Template.Child()
    split_view = Gtk.Template.Child()
    content_nav = Gtk.Template.Child()
    host_list = Gtk.Template.Child()
    host_editor = Gtk.Template.Child()
    welcome_view = Gtk.Template.Child()

    def __init__(self, app):
        super().__init__(
            application=app,
        )

        self.app = app
        self.parser = app.parser
        self.is_dirty = False
        self._raw_wrap_lines = False
        self._original_width = -1
        self._original_height = -1

        try:
            if hasattr(self, "host_editor") and self.host_editor is not None:
                self.host_editor.set_app(self)
        except Exception:
            pass

        self._connect_signals()
        self._load_preferences()
        try:
            if hasattr(self.app, "_parse_config_async"):
                self.app._parse_config_async()
        except Exception:
            pass

        self.connect("notify::has-focus", self._on_window_focus_changed)
        self.connect("close-request", self._on_close_request)
        self._show_welcome_view()

        try:
            key_controller = Gtk.EventControllerKey.new()
            key_controller.connect("key-pressed", self._on_key_pressed)
            self.add_controller(key_controller)
        except Exception:
            pass

    def _set_host_editor_visible(self, visible):
        if visible:
            if self._original_width == -1:
                self._original_width = self.get_width()
                self._original_height = self.get_height()
            self.set_default_size(1300, self._original_height)
        elif self._original_width != -1:
            self.set_default_size(self._original_width, self._original_height)
            self._original_width = -1
            self._original_height = -1
        self.host_editor.set_visible(visible)

    def _load_preferences(self):
        """Load preferences from the saved file and apply them to the window."""
        try:
            from .preferences_dialog import PreferencesDialog

            temp_dialog = PreferencesDialog(self)
            prefs = temp_dialog.get_preferences()
            temp_dialog.destroy()

            if prefs.get("editor_font_size"):
                self._editor_font_size = int(prefs["editor_font_size"])
            if "prefer_dark_theme" in prefs:
                self._prefer_dark_theme = bool(prefs["prefer_dark_theme"])
            if "raw_wrap_lines" in prefs:
                self._raw_wrap_lines = bool(prefs["raw_wrap_lines"])

            if hasattr(self, "_prefer_dark_theme") and self._prefer_dark_theme:
                try:
                    from gi.repository import Adw

                    style_manager = Adw.StyleManager.get_default()
                    style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
                except Exception:
                    pass

        except Exception:
            self._editor_font_size = 12
            self._prefer_dark_theme = False
            self._raw_wrap_lines = False

    def show_toast(self, message: str):
        """Show a transient toast using Adw.ToastOverlay."""
        try:
            toast = Adw.Toast.new(message)
            try:
                toast.set_timeout(3)
            except Exception:
                pass
            if hasattr(self, "toast_overlay") and self.toast_overlay is not None:
                self.toast_overlay.add_toast(toast)
        except Exception:
            pass

    def _show_undo_toast(self, message: str, on_undo):
        """Show a toast with an Undo action; executes on_undo when clicked."""
        try:
            toast = Adw.Toast.new(message)
            if hasattr(toast, "set_button_label"):
                try:
                    toast.set_button_label(_("Undo"))
                except Exception:
                    pass
            if hasattr(toast, "connect"):
                try:
                    toast.connect("button-clicked", lambda t: on_undo())
                except Exception:
                    pass
            if hasattr(self, "toast_overlay") and self.toast_overlay is not None:
                self.toast_overlay.add_toast(toast)
            else:
                self.show_toast(message)
        except Exception:
            self.show_toast(message)

    def _setup_split_view(self):
        """Set up the split view between host list and editor."""
        self.host_list = HostList()
        self.host_editor = HostEditor()
        try:
            self.host_editor.set_app(self.app)
        except Exception:
            return

        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_start_child(self.host_list)
        paned.set_end_child(self.host_editor)
        paned.set_position(400)

        self.main_box.append(paned)

    def _connect_signals(self):
        """Connect all the signal handlers."""

        self.host_list.connect("host-selected", self._on_host_selected)
        self.host_list.connect("host-added", self._on_host_added)
        self.host_list.connect("host-deleted", self._on_host_deleted)

        self.host_editor.connect("host-changed", self._on_host_changed)
        self.host_editor.connect("host-save", self._on_host_save)
        self.host_editor.connect(
            "editor-validity-changed", self._on_editor_validity_changed
        )
        self.host_editor.connect("show-toast", self._on_show_toast)


        self.host_list.search_entry.connect("search-changed", self._on_search_changed)

        self._setup_actions()

    def _setup_actions(self):
        actions = Gio.SimpleActionGroup()

        open_action = Gio.SimpleAction.new("open-config", None)
        open_action.connect("activate", self._on_open_config)
        actions.add_action(open_action)

        save_action = Gio.SimpleAction.new("save", None)
        save_action.connect("activate", self._on_save_clicked)
        actions.add_action(save_action)

        reload_action = Gio.SimpleAction.new("reload", None)
        reload_action.connect("activate", self._on_reload)
        actions.add_action(reload_action)

        add_host_action = Gio.SimpleAction.new("add-host", None)
        add_host_action.connect(
            "activate",
            lambda a, p: (
                self.host_editor._on_add_clicked(None)
                if hasattr(self.host_editor, "_on_add_clicked")
                else None
            ),
        )
        actions.add_action(add_host_action)

        duplicate_host_action = Gio.SimpleAction.new("duplicate-host", None)
        duplicate_host_action.connect(
            "activate",
            lambda a, p: (
                self.host_editor._on_duplicate_clicked(None)
                if hasattr(self.host_editor, "_on_duplicate_clicked")
                else None
            ),
        )
        actions.add_action(duplicate_host_action)

        delete_host_action = Gio.SimpleAction.new("delete-host", None)
        delete_host_action.connect(
            "activate",
            lambda a, p: (
                self.host_editor._on_delete_clicked(None)
                if hasattr(self.host_editor, "_on_delete_clicked")
                else None
            ),
        )
        actions.add_action(delete_host_action)

        search_action = Gio.SimpleAction.new("search", None)
        search_action.connect("activate", self._on_search_action)
        actions.add_action(search_action)

        prefs_action = Gio.SimpleAction.new("preferences", None)
        prefs_action.connect("activate", self._on_preferences)
        actions.add_action(prefs_action)

        manage_keys_action = Gio.SimpleAction.new("manage-keys", None)
        manage_keys_action.connect("activate", self._on_manage_keys)
        actions.add_action(manage_keys_action)

        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._on_about)
        actions.add_action(about_action)

        keyboard_shortcuts_action = Gio.SimpleAction.new("keyboard-shortcuts", None)
        keyboard_shortcuts_action.connect("activate", self._on_keyboard_shortcuts)
        actions.add_action(keyboard_shortcuts_action)

        self.insert_action_group("app", actions)

    def _on_search_action(self, action, param):
        """Handle search action."""
        self._toggle_search()

    def _on_key_pressed(self, controller, keyval, keycode, state):
        ctrl_pressed = bool(state & Gdk.ModifierType.CONTROL_MASK)

        if ctrl_pressed:
            if keyval == Gdk.KEY_o:
                self._on_open_config(None, None)
                return True
            elif keyval == Gdk.KEY_s:
                self._on_save_clicked(None)
                return True
            elif keyval == Gdk.KEY_r:
                self._on_reload(None, None)
                return True
            elif keyval == Gdk.KEY_n:
                if hasattr(self.host_editor, "_on_add_clicked"):
                    self.host_editor._on_add_clicked(None)
                return True
            elif keyval == Gdk.KEY_d:
                if hasattr(self.host_editor, "_on_duplicate_clicked"):
                    self.host_editor._on_duplicate_clicked(None)
                return True
            elif keyval == Gdk.KEY_f:
                self._toggle_search()
                return True
            elif keyval == Gdk.KEY_comma:
                self._on_preferences(None, None)
                return True
            elif keyval == Gdk.KEY_k:
                self._on_manage_keys(None, None)
                return True

        if ctrl_pressed and keyval == Gdk.KEY_Delete:
            if hasattr(self.host_editor, "_on_delete_clicked"):
                self.host_editor._on_delete_clicked(None)
            return True

        if keyval == Gdk.KEY_Escape:
            if self.host_list.search_bar.get_visible():
                try:
                    focus_widget = None
                    try:
                        focus_widget = self.get_focus()
                    except Exception:
                        focus_widget = None

                    def _is_descendant(widget, ancestor):
                        try:
                            while widget is not None:
                                if widget == ancestor:
                                    return True
                                widget = widget.get_parent()
                        except Exception:
                            pass
                        return False

                    if not _is_descendant(focus_widget, self.host_list.search_bar):
                        return False

                    self.host_list.search_bar.set_visible(False)
                except Exception:
                    self.host_list.search_bar.set_visible(False)
                self.host_list.search_entry.set_text("")
                self.host_list.filter_hosts("")
                return True
            return False

        if keyval == Gdk.KEY_Return or keyval == Gdk.KEY_KP_Enter:
            if hasattr(self.host_list, "get_selected_host"):
                selected_host = self.host_list.get_selected_host()
                if selected_host:
                    self.host_editor.load_host(selected_host)
                    self._set_host_editor_visible(True)
                    return True
            return False

        if keyval == Gdk.KEY_F2:
            if hasattr(self.host_list, "get_selected_host"):
                selected_host = self.host_list.get_selected_host()
                if selected_host:
                    self.host_editor.load_host(selected_host)
                    self._set_host_editor_visible(True)
                    return True
            return False

        if keyval in [
            Gdk.KEY_Up,
            Gdk.KEY_Down,
            Gdk.KEY_Home,
            Gdk.KEY_End,
            Gdk.KEY_Page_Up,
            Gdk.KEY_Page_Down,
        ]:
            if hasattr(self.host_list, "navigate_with_key"):
                return self.host_list.navigate_with_key(keyval, state)
            return False

        return False

    def _on_escape_pressed(self, shortcut):
        """Handle Escape key press - close search bar if visible."""
        if self.host_list.search_bar.get_visible():
            self.host_list.search_entry.set_text("")
            self.host_list.search_bar.set_visible(False)
            self.host_list.filter_hosts("")

    def _load_config(self):
        """Trigger async config parsing via the application to keep UI responsive."""
        try:
            if hasattr(self.app, "_parse_config_async"):
                self.app._parse_config_async()
        except Exception as e:
            self._show_error(f"Failed to trigger config reload: {e}")

    def _toggle_search(self, force=None):
        try:
            make_visible = True if force is None else bool(force)
            self.host_list.search_bar.set_visible(make_visible)
            if make_visible:
                self.host_list.search_entry.grab_focus()
            else:
                self.host_list.search_entry.set_text("")
                self.host_list.filter_hosts("")
        except Exception:
            pass

    def _on_host_save(self, editor, host):
        """Handle host save signal from editor."""
        self._on_save_clicked(None)

    def _on_window_focus_changed(self, window, param):
        """Hide search bar if window loses focus."""
        if not self.get_has_focus() and self.host_list.search_bar.get_visible():
            self.host_list.search_entry.set_text("")
            self.host_list.search_bar.set_visible(False)
            self.host_list.filter_hosts("")

    def _on_close_request(self, window):
        """Handle window close request - check for unsaved changes."""
        if hasattr(self.host_editor, 'is_host_dirty') and self.host_editor.is_host_dirty():
            return self._show_unsaved_changes_dialog()
        return False

    def _show_unsaved_changes_dialog(self):
        """Show alert dialog asking user what to do with unsaved changes."""
        # Load from blueprint resource
        builder = Gtk.Builder.new_from_resource("/io/github/BuddySirJava/SSH-Studio/ui/unsaved_changes_dialog.ui")
        dialog = builder.get_object("unsaved_changes_dialog")
        dialog.set_close_response("cancel")
        dialog.add_response("discard", _("Discard Changes"))
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("save", _("Save & Quit"))
        dialog.set_response_appearance("discard", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("save")

        def on_response(dialog, response):
            if response == "save":
                try:
                    if hasattr(self.host_editor, 'unsaved_banner') and self.host_editor.unsaved_banner:
                        self.host_editor._on_save_clicked(None)
                    dialog.close()
                    GLib.timeout_add(200, self._delayed_close)
                except Exception as e:
                    self.show_toast(_(f"Failed to save: {e}"))
            elif response == "discard":
                dialog.close()
                self.destroy()
            else:
                dialog.close()
                return True

        dialog.connect("response", on_response)
        dialog.present(self)
        return True

    def _delayed_close(self):
        """Close the window after a short delay to allow save to complete."""
        self.destroy()
        return False

    def on_status_bar_close_clicked(self, button):
        pass

    def _on_save_clicked(self, button):
        if not self.parser:
            return
        try:
            errors = self.parser.validate()
            if errors:
                dialog = Gtk.MessageDialog(
                    transient_for=self,
                    message_type=Gtk.MessageType.WARNING,
                    buttons=Gtk.ButtonsType.OK,
                    text="Validation warnings",
                    secondary_text="\n".join(errors),
                )
                dialog.connect("response", lambda d, r: d.destroy())
                dialog.present()
            self.parser.write(backup=True)
            self.parser.parse()

            self.host_list.load_hosts(self.parser.config.hosts)
            self.is_dirty = False
            self._update_status(_("Configuration saved successfully"))
        except Exception as e:
            self._show_error(f"Failed to save configuration: {e}")

    def _write_and_reload(self, show_status: bool = False):
        """Write the config to disk and reload UI without showing validation dialogs."""
        if not self.parser:
            return
        try:
            self.parser.write(backup=True)
            self.parser.parse()
            self.host_list.load_hosts(self.parser.config.hosts)
            self.is_dirty = False
            if show_status:
                self._update_status(_("Configuration saved"))
        except Exception as e:
            self._show_error(f"Failed to save configuration: {e}")

    def _on_host_selected(self, host_list, host):
        """Handle host selection from the list."""
        self.host_editor.load_host(host)
        self._set_host_editor_visible(True)
        if hasattr(self, "content_nav") and self.content_nav:
            try:
                pages = self.content_nav.get_pages()
                for page in pages:
                    if hasattr(page, "get_tag") and page.get_tag() == "host-editor":
                        self.content_nav.pop_to_page(page)
                        return
            except Exception:
                pass
            self.content_nav.push_by_tag("host-editor")

    def _show_welcome_view(self):
        """Show the welcome view when no host is selected."""
        if hasattr(self, "content_nav") and self.content_nav:
            try:
                pages = self.content_nav.get_pages()
                for page in pages:
                    if hasattr(page, "get_tag") and page.get_tag() == "welcome":
                        self.content_nav.pop_to_page(page)
                        return
            except Exception:
                pass
            self.content_nav.push_by_tag("welcome")

    def _on_host_added(self, host_list, host):
        if self.parser:
            base_pattern = "new-host"
            i = 0
            new_pattern = base_pattern
            existing_patterns = {
                p for h in self.parser.config.hosts for p in h.patterns
            }
            while new_pattern in existing_patterns:
                i += 1
                new_pattern = f"{base_pattern}-{i}"
            host.patterns = [new_pattern]
            host.raw_lines = [f"Host {new_pattern}"]

            self.parser.config.add_host(host)
            self.is_dirty = True

            def undo_add():
                try:
                    if host in self.parser.config.hosts:
                        self.parser.config.remove_host(host)
                    self.is_dirty = self.parser.config.is_dirty()
                    self.host_list.load_hosts(self.parser.config.hosts)
                    try:
                        if not self.parser.config.hosts:
                            self._set_host_editor_visible(False)
                    except Exception:
                        pass
                except Exception:
                    pass

            self._show_undo_toast(_("Host added"), undo_add)
            self._set_host_editor_visible(True)
            self.host_editor.load_host(host)

    def _on_host_deleted(self, host_list, host):
        """Handle host deletion."""
        if self.parser:
            try:
                original_index = self.parser.config.hosts.index(host)
            except ValueError:
                original_index = None
            self.parser.config.remove_host(host)
            self._write_and_reload(show_status=False)

            def undo_delete():
                try:
                    if original_index is None:
                        self.parser.config.add_host(host)
                    else:
                        self.parser.config.hosts.insert(original_index, host)
                    self._write_and_reload(show_status=False)
                    try:
                        self.host_list.select_host(host)
                        self._set_host_editor_visible(True)
                        self.host_editor.load_host(host)
                    except Exception:
                        pass
                except Exception:
                    pass

            self._show_undo_toast(_("Host deleted"), undo_delete)

            if not self.parser.config.hosts:
                self.host_editor.current_host = None
                self.host_editor._clear_all_fields()
                self._set_host_editor_visible(False)
                self.is_dirty = False

            else:
                self.host_list.select_host(self.parser.config.hosts[0])

    def _on_host_changed(self, editor, host):
        self.is_dirty = self.parser.config.is_dirty()

    def _on_editor_validity_changed(self, editor, is_valid: bool):
        # The banner handles its own sensitivity based on validity
        pass

    def _on_show_toast(self, editor, message: str):
        """Handle show-toast signal from host editor."""
        self.show_toast(message)

    def _on_search_changed(self, search_bar, query):
        """Handle search query changes."""
        self.host_list.filter_hosts(query)

    def _on_open_config(self, action, param):
        """Handle open config action."""
        dialog = Gtk.FileChooserNative.new(
            title=_("Open SSH Config File"),
            parent=self,
            action=Gtk.FileChooserAction.OPEN,
            accept_label=_("Open"),
            cancel_label=_("Cancel"),
        )

        def on_file_chooser_response(dlg, response_id):
            if response_id == Gtk.ResponseType.ACCEPT:
                file = dlg.get_file()
                if file:
                    self.parser.config_path = Path(file.get_path())
                    self._load_config()
            dlg.destroy()

        dialog.connect("response", on_file_chooser_response)
        dialog.show()

    def _on_reload(self, action, param):
        """Handle reload action."""
        self._load_config()

    def _on_manage_keys(self, action, param):
        """Open the SSH Key Manager dialog."""
        from .ssh_key_manager_dialog import SSHKeyManagerDialog

        dialog = SSHKeyManagerDialog(self)
        dialog.present(self)

    def _on_preferences(self, action, param):
        """Handle preferences action."""
        from .preferences_dialog import PreferencesDialog

        dialog = PreferencesDialog(self)

        current_prefs = {
            "config_path": str(self.parser.config_path) if self.parser else "",
            "backup_dir": str(getattr(self.parser, "backup_dir", "") or ""),
            "auto_backup": bool(getattr(self.parser, "auto_backup_enabled", True)),
            "editor_font_size": getattr(self, "_editor_font_size", 12),
            "prefer_dark_theme": getattr(self, "_prefer_dark_theme", False),
            "raw_wrap_lines": getattr(self, "_raw_wrap_lines", False),
        }
        dialog.set_preferences(current_prefs)

        def on_close_request(dlg):
            prefs = dlg.get_preferences()
            if self.parser:
                if prefs.get("config_path"):
                    self.parser.config_path = Path(prefs["config_path"])
                self.parser.auto_backup_enabled = bool(prefs.get("auto_backup", True))
                backup_dir_val = prefs.get("backup_dir") or None
                self.parser.backup_dir = (
                    Path(backup_dir_val).expanduser() if backup_dir_val else None
                )
            font_size = int(prefs.get("editor_font_size") or 12)
            self._editor_font_size = font_size
            try:
                provider = Gtk.CssProvider()
                provider.load_from_data(
                    f".editor-pane textview {{font-size: {font_size}pt;}}".encode()
                )
                Gtk.StyleContext.add_provider_for_display(
                    Gtk.Display.get_default(),
                    provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                )
            except Exception:
                pass
            prefer_dark = bool(prefs.get("prefer_dark_theme", False))
            self._prefer_dark_theme = prefer_dark
            try:
                style_manager = Adw.StyleManager.get_default()
                if style_manager is not None:
                    style_manager.set_color_scheme(
                        Adw.ColorScheme.PREFER_DARK
                        if prefer_dark
                        else Adw.ColorScheme.DEFAULT
                    )
            except Exception:
                pass
            raw_wrap = bool(prefs.get("raw_wrap_lines", False))
            self._raw_wrap_lines = raw_wrap
            try:
                self.host_editor.set_wrap_mode(raw_wrap)
            except Exception:
                pass
            if self.parser:
                self._load_config()
            self._update_status(_("Preferences saved"))
            return False

        dialog.connect("close-attempt", on_close_request)
        dialog.present(self)

    def _on_keyboard_shortcuts(self, action, param):
        """Open the keyboard shortcuts dialog."""
        from .keyboard_shortcuts_dialog import KeyboardShortcutsDialog

        dialog = KeyboardShortcutsDialog(self)
        dialog.present()

    def _on_about(self, action, param):
        """Show the about dialog using Adwaita's AboutWindow."""
        about_window = Adw.AboutWindow(
            transient_for=self,
            application_name=_("SSH-Studio"),
            application_icon="io.github.BuddySirJava.SSH-Studio",
            version="1.3.0",
            developer_name=_("Made with ❤️ by Mahyar Darvishi"),
            website="https://github.com/BuddySirJava/ssh-studio",
            issue_url="https://github.com/BuddySirJava/ssh-studio/issues",
            developers=["Mahyar Darvishi"],
            copyright=_("© 2025 Mahyar Darvishi"),
            license_type=Gtk.License.MIT_X11,
            comments=_(
                "A native Python + GTK application for managing SSH configuration files"
            ),
        )

        try:
            texture = Gdk.Texture.new_from_resource(
                "/io/github/BuddySirJava/SSH-Studio/media/icon_256.png"
            )
            about_window.set_logo(texture)
        except Exception:
            pass
        about_window.set_debug_info(
            f"""
SSH-Studio {about_window.get_version()}
GTK {Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()}
Adwaita {Adw.get_major_version()}.{Adw.get_minor_version()}.{Adw.get_micro_version()}
Python {sys.version}
        """.strip()
        )

        about_window.present()

    def _update_status(self, message: str):
        """Update the status bar with a message."""
        self.show_toast(message)

    def _hide_status(self):
        """Hide the status bar."""
        return False

    def _show_error(self, message: str):
        """Show an error message in the status bar."""
        self.show_toast(message)

    def _show_warning(self, title: str, message: str):
        """Show a warning dialog."""
        dialog = Gtk.MessageDialog(
            transient_for=self,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK,
            text=title,
            secondary_text=message,
        )
        dialog.present()
