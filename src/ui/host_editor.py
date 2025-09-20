import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")
from gi.repository import Gtk, GObject, Gdk, GLib, Adw, GtkSource

try:
    from ssh_studio.ssh_config_parser import SSHHost, SSHOption
    from ssh_studio.ui.test_connection_dialog import TestConnectionDialog
except ImportError:
    from ssh_config_parser import SSHHost, SSHOption
    from ui.test_connection_dialog import TestConnectionDialog
import difflib
import copy
from gettext import gettext as _
import os


@Gtk.Template(resource_path="/io/github/BuddySirJava/SSH-Studio/ui/host_editor.ui")
class HostEditor(Gtk.Box):

    __gtype_name__ = "HostEditor"

    viewstack = Gtk.Template.Child()
    patterns_entry = Gtk.Template.Child()
    patterns_error_label = Gtk.Template.Child()
    hostname_entry = Gtk.Template.Child()
    user_entry = Gtk.Template.Child()
    port_entry = Gtk.Template.Child()
    port_error_label = Gtk.Template.Child()
    identity_entry = Gtk.Template.Child()
    identity_button = Gtk.Template.Child()
    identity_pick_button = Gtk.Template.Child()
    forward_agent_switch = Gtk.Template.Child()
    proxy_jump_entry = Gtk.Template.Child()
    proxy_cmd_entry = Gtk.Template.Child()
    local_forward_entry = Gtk.Template.Child()
    remote_forward_entry = Gtk.Template.Child()
    compression_switch = Gtk.Template.Child()
    serveralive_interval_entry = Gtk.Template.Child()
    serveralive_count_entry = Gtk.Template.Child()
    tcp_keepalive_switch = Gtk.Template.Child()
    strict_host_key_row = Gtk.Template.Child()
    pubkey_auth_switch = Gtk.Template.Child()
    password_auth_switch = Gtk.Template.Child()
    kbd_interactive_auth_switch = Gtk.Template.Child()
    gssapi_auth_switch = Gtk.Template.Child()
    add_keys_to_agent_row = Gtk.Template.Child()
    preferred_authentications_entry = Gtk.Template.Child()
    identity_agent_entry = Gtk.Template.Child()
    connect_timeout_entry = Gtk.Template.Child()
    request_tty_row = Gtk.Template.Child()
    log_level_row = Gtk.Template.Child()
    verify_host_key_dns_switch = Gtk.Template.Child()
    canonicalize_hostname_row = Gtk.Template.Child()
    canonical_domains_entry = Gtk.Template.Child()
    control_master_row = Gtk.Template.Child()
    control_persist_entry = Gtk.Template.Child()
    control_path_entry = Gtk.Template.Child()
    raw_text_view = Gtk.Template.Child()
    copy_row = Gtk.Template.Child()
    test_row = Gtk.Template.Child()
    save_button = Gtk.Template.Child()
    revert_button = Gtk.Template.Child()
    banner_revealer = Gtk.Template.Child()

    __gsignals__ = {
        "host-changed": (GObject.SignalFlags.RUN_LAST, None, (object,)),
        "editor-validity-changed": (GObject.SignalFlags.RUN_LAST, None, (bool,)),
        "host-save": (GObject.SignalFlags.RUN_LAST, None, (object,)),
        "show-toast": (GObject.SignalFlags.RUN_LAST, None, (str,)),
    }

    def __init__(self):
        super().__init__()
        self.set_visible(False)
        self.app = None
        self.current_host = None
        self.is_loading = False
        self._programmatic_raw_update = False
        self._editor_valid = True
        self._touched_options: set[str] = set()
        self._wired_global_buttons = False
        try:
            css = Gtk.CssProvider()
            css.load_from_data(
                b"""
            .error-label { color: #e01b24; }
            .entry-error { border-color: #e01b24; }
            """
            )
            Gtk.StyleContext.add_provider_for_display(
                Gtk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
        except Exception:
            pass

        self.buffer = None
        self._replace_textview_with_sourceview()
        self._setup_syntax_highlighting()

        self._connect_signals()

        self._ensure_buffer_initialized()
        if self.buffer is not None:
            self._create_diff_tags()
            self._show_helpful_placeholder()

        try:
            if getattr(self, "save_button", None):
                self.save_button.set_sensitive(False)
            if getattr(self, "revert_button", None):
                self.revert_button.set_sensitive(False)
            if getattr(self, "banner_revealer", None):
                self.banner_revealer.set_reveal_child(False)
        except Exception:
            pass
        try:
            main_window = self.get_root()
            if (
                hasattr(main_window, "global_actionbar")
                and main_window.global_actionbar is not None
            ):
                self.banner_revealer.set_visible(False)
        except Exception:
            pass

        GLib.idle_add(self._wire_global_buttons)

        try:
            key_ctrl = Gtk.EventControllerKey.new()
            key_ctrl.connect("key-pressed", self._on_key_pressed)
            self.add_controller(key_ctrl)
        except Exception:
            pass

    def set_app(self, app):
        self.app = app

    def _wire_global_buttons(self):
        try:
            main_window = self.get_root()
        except Exception:
            main_window = None
        if not main_window:
            return True
        if self._wired_global_buttons:
            return False
        try:
            if hasattr(main_window, "save_button") and main_window.save_button:
                self.save_button = main_window.save_button
                self.save_button.connect("clicked", self._on_save_clicked)
            if hasattr(main_window, "revert_button") and main_window.revert_button:
                self.revert_button = main_window.revert_button
                self.revert_button.connect("clicked", self._on_revert_clicked)
            if hasattr(main_window, "unsaved_label"):
                self._unsaved_label = main_window.unsaved_label
        except Exception:
            pass
        self._wired_global_buttons = True
        return False

    def _on_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_s and (state & Gdk.ModifierType.CONTROL_MASK):
            if (
                hasattr(self, "save_button")
                and self.save_button
                and self.save_button.get_sensitive()
            ):
                self.save_button.activate()
                return True
            return False

        if keyval == Gdk.KEY_z and (state & Gdk.ModifierType.CONTROL_MASK):
            # TODO: Implement undo functionality (Im bored)
            return False

        if keyval == Gdk.KEY_Escape:
            try:
                root = self.get_root()
                if root and hasattr(root, "get_focus"):
                    focused_widget = root.get_focus()
                    if focused_widget:
                        root.set_focus(None)
                        return True
            except Exception:
                pass
            return False

        if keyval == Gdk.KEY_Tab:
            return self._handle_tab_navigation(state & Gdk.ModifierType.SHIFT_MASK)

        return False

    def _handle_tab_navigation(self, shift_pressed: bool):
        """Handle Tab/Shift+Tab navigation between form fields."""
        focusable_widgets = [
            self.patterns_entry,
            self.hostname_entry,
            self.user_entry,
            self.port_entry,
            self.identity_entry,
            self.identity_button,
            self.identity_pick_button,
            self.forward_agent_switch,
            self.proxy_jump_entry,
            self.proxy_cmd_entry,
            self.local_forward_entry,
            self.remote_forward_entry,
            self.compression_switch,
            self.serveralive_interval_entry,
            self.serveralive_count_entry,
            self.tcp_keepalive_switch,
            self.pubkey_auth_switch,
            self.password_auth_switch,
            self.kbd_interactive_auth_switch,
            self.gssapi_auth_switch,
            self.preferred_authentications_entry,
            self.identity_agent_entry,
            self.connect_timeout_entry,
        ]

        focusable_widgets = [w for w in focusable_widgets if w is not None]

        if not focusable_widgets:
            return False

        current_focus = None
        try:
            root = self.get_root()
            if root and hasattr(root, "get_focus"):
                current_focus = root.get_focus()
        except Exception:
            pass

        current_index = -1

        for i, widget in enumerate(focusable_widgets):
            if widget == current_focus:
                current_index = i
                break

        if current_index == -1:
            for i, widget in enumerate(focusable_widgets):
                if widget.has_focus():
                    current_index = i
                    break

            if current_index == -1:
                return False

        if shift_pressed:
            next_index = (current_index - 1) % len(focusable_widgets)
        else:
            next_index = (current_index + 1) % len(focusable_widgets)

        focusable_widgets[next_index].grab_focus()
        return True

    def _show_message(self, message: str):
        """Show a message using toast by emitting a signal."""
        self.emit("show-toast", message)

    def _connect_signals(self):
        def connect_touch(widget, signal_name: str, option_key: str):
            if not widget:
                return

            def handler(*args):
                if self.is_loading:
                    return
                self._touched_options.add(option_key)
                self._on_field_changed(widget)

            widget.connect(signal_name, handler)

        def connect_entry_row_text(widget, option_key: str):
            if not widget:
                return

            def on_notify_text(*_args):
                if self.is_loading:
                    return
                self._touched_options.add(option_key)
                self._on_field_changed(widget)

            widget.connect("notify::text", on_notify_text)

        connect_entry_row_text(self.patterns_entry, "__patterns__")
        connect_entry_row_text(self.hostname_entry, "HostName")
        connect_entry_row_text(self.user_entry, "User")
        connect_entry_row_text(self.port_entry, "Port")
        connect_entry_row_text(self.identity_entry, "IdentityFile")
        connect_touch(self.forward_agent_switch, "state-set", "ForwardAgent")

        connect_entry_row_text(self.proxy_jump_entry, "ProxyJump")
        connect_entry_row_text(self.proxy_cmd_entry, "ProxyCommand")
        connect_entry_row_text(self.local_forward_entry, "LocalForward")
        connect_entry_row_text(self.remote_forward_entry, "RemoteForward")

        connect_touch(self.compression_switch, "state-set", "Compression")
        connect_entry_row_text(self.serveralive_interval_entry, "ServerAliveInterval")
        connect_entry_row_text(self.serveralive_count_entry, "ServerAliveCountMax")
        connect_touch(self.tcp_keepalive_switch, "state-set", "TCPKeepAlive")
        if hasattr(self, "strict_host_key_row") and self.strict_host_key_row:
            self.strict_host_key_row.connect(
                "notify::selected",
                lambda *args: (
                    None
                    if self.is_loading
                    else (
                        self._touched_options.add("StrictHostKeyChecking"),
                        self._on_field_changed(self.strict_host_key_row),
                    )
                ),
            )

        if hasattr(self, "add_keys_to_agent_row") and self.add_keys_to_agent_row:
            self.add_keys_to_agent_row.connect(
                "notify::selected",
                lambda *args: (
                    None
                    if self.is_loading
                    else (
                        self._touched_options.add("AddKeysToAgent"),
                        self._on_field_changed(self.add_keys_to_agent_row),
                    )
                ),
            )
        connect_touch(
            getattr(self, "pubkey_auth_switch", None),
            "state-set",
            "PubkeyAuthentication",
        )
        connect_touch(
            getattr(self, "password_auth_switch", None),
            "state-set",
            "PasswordAuthentication",
        )
        connect_touch(
            getattr(self, "kbd_interactive_auth_switch", None),
            "state-set",
            "KbdInteractiveAuthentication",
        )
        connect_touch(
            getattr(self, "gssapi_auth_switch", None),
            "state-set",
            "GSSAPIAuthentication",
        )
        connect_entry_row_text(
            getattr(self, "preferred_authentications_entry", None),
            "PreferredAuthentications",
        )
        connect_entry_row_text(
            getattr(self, "identity_agent_entry", None), "IdentityAgent"
        )
        connect_entry_row_text(
            getattr(self, "connect_timeout_entry", None), "ConnectTimeout"
        )
        if hasattr(self, "request_tty_row") and self.request_tty_row:
            self.request_tty_row.connect(
                "notify::selected",
                lambda *args: (
                    None
                    if self.is_loading
                    else (
                        self._touched_options.add("RequestTTY"),
                        self._on_field_changed(self.request_tty_row),
                    )
                ),
            )
        if hasattr(self, "log_level_row") and self.log_level_row:
            self.log_level_row.connect(
                "notify::selected",
                lambda *args: (
                    None
                    if self.is_loading
                    else (
                        self._touched_options.add("LogLevel"),
                        self._on_field_changed(self.log_level_row),
                    )
                ),
            )
        connect_touch(
            getattr(self, "verify_host_key_dns_switch", None),
            "state-set",
            "VerifyHostKeyDNS",
        )
        if (
            hasattr(self, "canonicalize_hostname_row")
            and self.canonicalize_hostname_row
        ):
            self.canonicalize_hostname_row.connect(
                "notify::selected",
                lambda *args: (
                    None
                    if self.is_loading
                    else (
                        self._touched_options.add("CanonicalizeHostname"),
                        self._on_field_changed(self.canonicalize_hostname_row),
                    )
                ),
            )
        connect_entry_row_text(
            getattr(self, "canonical_domains_entry", None), "CanonicalDomains"
        )
        if hasattr(self, "control_master_row") and self.control_master_row:
            self.control_master_row.connect(
                "notify::selected",
                lambda *args: (
                    None
                    if self.is_loading
                    else (
                        self._touched_options.add("ControlMaster"),
                        self._on_field_changed(self.control_master_row),
                    )
                ),
            )
        connect_entry_row_text(
            getattr(self, "control_persist_entry", None), "ControlPersist"
        )
        connect_entry_row_text(getattr(self, "control_path_entry", None), "ControlPath")

        if self.buffer:
            self._raw_changed_handler_id = self.buffer.connect(
                "changed", self._on_raw_text_changed
            )

        self._connect_buttons()

    def _connect_buttons(self):
        if hasattr(self, "identity_button") and self.identity_button:
            self.identity_button.connect("clicked", self._on_identity_file_clicked)
        if hasattr(self, "identity_pick_button") and self.identity_pick_button:
            self.identity_pick_button.connect("clicked", self._on_identity_pick_clicked)
        if hasattr(self, "copy_row") and self.copy_row:
            self.copy_row.connect(
                "activated", lambda r: self._on_copy_ssh_command(None)
            )
        if hasattr(self, "test_row") and self.test_row:
            self.test_row.connect("activated", lambda r: self._on_test_connection(None))
        try:
            if getattr(self, "save_button", None) is not None:
                self.save_button.connect("clicked", self._on_save_clicked)
        except Exception:
            pass
        try:
            if getattr(self, "revert_button", None) is not None:
                self.revert_button.connect("clicked", self._on_revert_clicked)
        except Exception:
            pass
        try:
            main_window = self.get_root()
            if getattr(main_window, "save_button", None) is not None:
                main_window.save_button.connect("clicked", self._on_save_clicked)
            if getattr(main_window, "revert_button", None) is not None:
                main_window.revert_button.connect("clicked", self._on_revert_clicked)
        except Exception:
            pass

    def load_host(self, host: SSHHost):
        self.is_loading = True
        self._touched_options.clear()
        self.current_host = host
        self.original_host_state = copy.deepcopy(host)

        if not host:
            self._clear_all_fields()
            self.is_loading = False
            return

        def _safe_set_entry_text(row, text):
            try:
                if row is not None:
                    row.set_text(text)
            except Exception:
                pass

        _safe_set_entry_text(
            getattr(self, "patterns_entry", None), " ".join(host.patterns)
        )
        _safe_set_entry_text(
            getattr(self, "hostname_entry", None), host.get_option("HostName") or ""
        )
        _safe_set_entry_text(
            getattr(self, "user_entry", None), host.get_option("User") or ""
        )
        _safe_set_entry_text(
            getattr(self, "port_entry", None), host.get_option("Port") or ""
        )
        _safe_set_entry_text(
            getattr(self, "identity_entry", None), host.get_option("IdentityFile") or ""
        )

        forward_agent = host.get_option("ForwardAgent")
        try:
            if getattr(self, "forward_agent_switch", None) is not None:
                self.forward_agent_switch.set_active(forward_agent == "yes")
        except Exception:
            pass

        _safe_set_entry_text(
            getattr(self, "proxy_jump_entry", None), host.get_option("ProxyJump") or ""
        )
        _safe_set_entry_text(
            getattr(self, "proxy_cmd_entry", None),
            host.get_option("ProxyCommand") or "",
        )
        _safe_set_entry_text(
            getattr(self, "local_forward_entry", None),
            host.get_option("LocalForward") or "",
        )
        _safe_set_entry_text(
            getattr(self, "remote_forward_entry", None),
            host.get_option("RemoteForward") or "",
        )

        compression = (host.get_option("Compression") or "no").lower() == "yes"
        try:
            if getattr(self, "compression_switch", None) is not None:
                self.compression_switch.set_active(compression)
        except Exception:
            pass

        self.serveralive_interval_entry.set_text(
            host.get_option("ServerAliveInterval") or "0"
        )

        self.serveralive_count_entry.set_text(
            host.get_option("ServerAliveCountMax") or "3"
        )

        tcp_keepalive = (host.get_option("TCPKeepAlive") or "yes").lower() == "yes"
        self.tcp_keepalive_switch.set_active(tcp_keepalive)

        shk = (host.get_option("StrictHostKeyChecking") or "ask").lower()
        mapping = {"ask": 0, "yes": 1, "no": 2}
        self.strict_host_key_row.set_selected(mapping.get(shk, 0))

        # Authentication and keys
        self.pubkey_auth_switch.set_active(
            ((host.get_option("PubkeyAuthentication") or "yes").lower()) == "yes"
        )
        self.password_auth_switch.set_active(
            ((host.get_option("PasswordAuthentication") or "no").lower()) == "yes"
        )
        self.kbd_interactive_auth_switch.set_active(
            ((host.get_option("KbdInteractiveAuthentication") or "no").lower()) == "yes"
        )
        self.gssapi_auth_switch.set_active(
            ((host.get_option("GSSAPIAuthentication") or "no").lower()) == "yes"
        )
        aka = (host.get_option("AddKeysToAgent") or "no").lower()
        self._combo_select(
            self.add_keys_to_agent_row, ["no", "yes", "ask", "confirm"], aka
        )
        self.preferred_authentications_entry.set_text(
            host.get_option("PreferredAuthentications") or ""
        )
        self.identity_agent_entry.set_text(host.get_option("IdentityAgent") or "")

        # Connection behavior
        self.connect_timeout_entry.set_text(host.get_option("ConnectTimeout") or "8")
        self._combo_select(
            self.request_tty_row,
            ["auto", "no", "yes", "force"],
            (host.get_option("RequestTTY") or "auto").lower(),
        )
        self._combo_select(
            self.log_level_row,
            [
                "quiet",
                "fatal",
                "error",
                "info",
                "verbose",
                "debug",
                "debug1",
                "debug2",
                "debug3",
            ],
            (host.get_option("LogLevel") or "info").lower(),
        )
        self.verify_host_key_dns_switch.set_active(
            ((host.get_option("VerifyHostKeyDNS") or "no").lower()) == "yes"
        )
        self._combo_select(
            self.canonicalize_hostname_row,
            ["no", "yes", "always"],
            (host.get_option("CanonicalizeHostname") or "no").lower(),
        )
        self.canonical_domains_entry.set_text(host.get_option("CanonicalDomains") or "")

        # Multiplexing
        self._combo_select(
            self.control_master_row,
            ["no", "yes", "ask", "auto", "autoask"],
            (host.get_option("ControlMaster") or "no").lower(),
        )
        self.control_persist_entry.set_text(host.get_option("ControlPersist") or "")
        self.control_path_entry.set_text(host.get_option("ControlPath") or "")

        self.raw_text_view.get_buffer().set_text("\n".join(host.raw_lines))
        self.original_raw_content = "\n".join(host.raw_lines)

        self.is_loading = False
        self.revert_button.set_sensitive(False)
        self.banner_revealer.set_reveal_child(False)
        try:
            main_window = self.get_root()
            if (
                hasattr(main_window, "global_actionbar")
                and main_window.global_actionbar
            ):
                main_window.unsaved_label.set_visible(False)
                main_window.save_button.set_visible(False)
                main_window.revert_button.set_visible(False)
        except Exception:
            pass

        self._programmatic_raw_update = True
        try:
            self._on_raw_text_changed(self.raw_text_view.get_buffer())
        finally:
            self._programmatic_raw_update = False

    def _clear_all_fields(self):
        """Clears all input fields and custom options."""
        self.patterns_entry.set_text("")
        self.hostname_entry.set_text("")
        self.user_entry.set_text("")
        self.port_entry.set_text("")
        self.identity_entry.set_text("")
        self.forward_agent_switch.set_active(False)
        self.proxy_jump_entry.set_text("")
        self.proxy_cmd_entry.set_text("")
        self.local_forward_entry.set_text("")
        self.remote_forward_entry.set_text("")
        if hasattr(self, "compression_switch"):
            self.compression_switch.set_active(False)
        if hasattr(self, "serveralive_interval_entry"):
            self.serveralive_interval_entry.set_text("0")
        if hasattr(self, "serveralive_count_entry"):
            self.serveralive_count_entry.set_text("3")
        if hasattr(self, "tcp_keepalive_switch"):
            self.tcp_keepalive_switch.set_active(True)
        if hasattr(self, "strict_host_key_row"):
            self.strict_host_key_row.set_selected(0)

    def _load_custom_options(self, host: SSHHost):
        """Loads custom SSH options into the custom options list."""
        if not hasattr(self, "custom_options_list") or not self.custom_options_list:
            return

        self._clear_custom_options()

        common_options = {
            "HostName",
            "User",
            "Port",
            "IdentityFile",
            "ForwardAgent",
            "ProxyJump",
            "ProxyCommand",
            "LocalForward",
            "RemoteForward",
        }

        for option in host.options:
            if option.key not in common_options:
                self._add_custom_option_row(option.key, option.value)

    def _clear_custom_options(self):
        """Clears all custom option rows from the list."""
        if not hasattr(self, "custom_options_list") or not self.custom_options_list:
            return
        child = self.custom_options_list.get_first_child()
        while child:
            self.custom_options_list.remove(child)
            child = self.custom_options_list.get_first_child()

    def _add_custom_option_row(self, key: str = "", value: str = ""):
        """Adds a new row for a custom option to the list."""
        action_row = Adw.ActionRow()
        action_row.set_title(key if key else _("New Custom Option"))
        action_row.set_subtitle(value if value else _("Enter option name and value"))
        action_row.set_activatable(False)
        action_row.add_css_class("custom-option-row")

        entry_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        entry_container.set_spacing(12)
        entry_container.set_hexpand(True)
        entry_container.set_margin_start(12)
        entry_container.set_margin_end(12)

        key_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        key_box.set_spacing(4)

        key_label = Gtk.Label(label=_("Option Name"))
        key_label.set_xalign(0)
        key_label.add_css_class("dim-label")
        key_label.add_css_class("caption")
        key_box.append(key_label)

        key_entry = Gtk.Entry()
        key_entry.set_text(key)
        key_entry.set_placeholder_text(_("e.g., Compression"))
        key_entry.set_size_request(160, -1)
        key_entry.add_css_class("custom-option-key")
        key_entry.connect("changed", self._on_custom_option_key_changed, action_row)
        key_box.append(key_entry)

        value_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        value_box.set_spacing(4)
        value_box.set_hexpand(True)

        value_label = Gtk.Label(label=_("Value"))
        value_label.set_xalign(0)
        value_label.add_css_class("dim-label")
        value_label.add_css_class("caption")
        value_box.append(value_label)

        value_entry = Gtk.Entry()
        value_entry.set_text(value)
        value_entry.set_placeholder_text(_("e.g., yes"))
        value_entry.set_hexpand(True)
        value_entry.add_css_class("custom-option-value")
        value_entry.connect("changed", self._on_custom_option_value_changed, action_row)
        value_box.append(value_entry)

        entry_container.append(key_box)
        entry_container.append(value_box)

        remove_button = Gtk.Button()
        remove_button.set_icon_name("user-trash-symbolic")
        remove_button.add_css_class("flat")
        remove_button.add_css_class("destructive-action")
        remove_button.set_tooltip_text(_("Remove this custom option"))
        remove_button.set_valign(Gtk.Align.CENTER)
        remove_button.connect("clicked", self._on_remove_custom_option, action_row)

        action_row.add_suffix(entry_container)
        action_row.add_suffix(remove_button)

        action_row.key_entry = key_entry
        action_row.value_entry = value_entry

        if hasattr(self, "custom_options_list") and self.custom_options_list:
            self.custom_options_list.append(action_row)

        key_entry.connect("changed", self._on_custom_option_changed)
        value_entry.connect("changed", self._on_custom_option_changed)

        if hasattr(self, "custom_options_expander") and self.custom_options_expander:
            if not self.custom_options_expander.get_expanded():
                self.custom_options_expander.set_expanded(True)

    def _on_field_changed(self, widget, *args):
        """Handle changes in basic and networking fields to update host and dirty state."""
        if self.is_loading or not self.current_host:
            return

        self._update_button_sensitivity()

        self._validate_and_update_host()

    def _on_custom_option_changed(self, widget, *args):
        """Handle changes in custom option fields to update host and dirty state."""
        if self.is_loading or not self.current_host:
            return

        self._update_button_sensitivity()

        self._validate_and_update_host()

    def _on_custom_option_key_changed(self, widget, action_row):
        """Handle changes in custom option key field to update the row title."""
        key = widget.get_text().strip()
        if key:
            action_row.set_title(key)
        else:
            action_row.set_title(_("New Custom Option"))

    def _on_custom_option_value_changed(self, widget, action_row):
        """Handle changes in custom option value field to update the row subtitle."""
        value = widget.get_text().strip()
        if value:
            action_row.set_subtitle(value)
        else:
            action_row.set_subtitle(_("Enter option name and value"))

    def _update_raw_text_from_host(self):
        """Updates the raw text view based on the current host's structured data."""
        if not self.current_host:
            return

        self.is_loading = True

        generated_raw_lines = self._generate_raw_lines_from_host()
        buffer = self.raw_text_view.get_buffer()
        if hasattr(self, "_raw_changed_handler_id"):
            buffer.handler_block(self._raw_changed_handler_id)
        buffer.set_text("\n".join(generated_raw_lines))
        if hasattr(self, "_raw_changed_handler_id"):
            buffer.handler_unblock(self._raw_changed_handler_id)

        self.is_loading = False

        self._programmatic_raw_update = True
        self._on_raw_text_changed(self.raw_text_view.get_buffer())
        self._programmatic_raw_update = False

    def _generate_raw_lines_from_host(self) -> list[str]:
        """Generates raw lines for the current host based on its structured data."""
        lines = []
        if self.current_host:
            if self.current_host.patterns:
                lines.append(f"Host {' '.join(self.current_host.patterns)}")

            for opt in self.current_host.options:
                lines.append(str(opt))

            if self.current_host.options and lines[-1].strip() != "":
                lines.append("")

        return lines

    def _on_raw_text_changed(self, buffer):
        """Handle changes in the raw text view, parse, validate, and apply diff highlighting."""
        if self.is_loading or not self.current_host:
            return

        current_text = buffer.get_text(
            buffer.get_start_iter(), buffer.get_end_iter(), False
        )
        current_lines = current_text.splitlines()
        original_lines = self.original_raw_content.splitlines()

        self._ensure_buffer_initialized()
        if self.buffer is None:
            return

        if self._is_source_view():
            self._apply_subtle_diff_highlighting(current_lines, original_lines)
        else:
            self.buffer.remove_all_tags(
                self.buffer.get_start_iter(), self.buffer.get_end_iter()
            )
            self._apply_full_diff_highlighting(current_lines, original_lines)

        if not self._programmatic_raw_update:
            self._parse_and_validate_raw_text(current_lines)
            self._update_button_sensitivity()

    def _parse_and_validate_raw_text(self, current_lines: list[str]):
        """Parses raw lines and updates current_host and UI fields if valid."""
        try:
            temp_host = SSHHost.from_raw_lines(current_lines)
            self.current_host.patterns = temp_host.patterns
            self.current_host.options = temp_host.options
            self.current_host.raw_lines = current_lines
            self.emit("host-changed", self.current_host)
            self._sync_fields_from_host()
            self._update_button_sensitivity()
        except ValueError as e:
            error_msg = str(e)
            if "No Host declaration found" in error_msg:
                if any(
                    line.strip() and not line.strip().startswith("#")
                    for line in current_lines
                ):
                    self.app._show_error(
                        "SSH host configuration must start with 'Host' declaration"
                    )
            else:
                self.app._show_error(f"Invalid raw host configuration: {e}")
        except Exception as e:
            self.app._show_error(f"Error parsing raw host config: {e}")

    def _update_host_from_fields(self):
        """Updates the current host object based on GUI field values.
        Only updates options the user interacted with (touched). Defaults are not written.
        """
        if not self.current_host:
            return

        if "__patterns__" in self._touched_options:
            patterns_text = self.patterns_entry.get_text().strip()
            self.current_host.patterns = (
                [p.strip() for p in patterns_text.split()] if patterns_text else []
            )

        def update_if_touched(
            key: str, value: str | None, default_absent_values: list[str] | None = None
        ):
            if key not in self._touched_options:
                return
            v = (value or "").strip()
            if default_absent_values and v.lower() in [
                d.lower() for d in default_absent_values
            ]:
                self.current_host.remove_option(key)
            elif v == "":
                self.current_host.remove_option(key)
            else:
                self.current_host.set_option(key, v)

        update_if_touched("HostName", self.hostname_entry.get_text())
        update_if_touched("User", self.user_entry.get_text())
        update_if_touched("Port", self.port_entry.get_text())
        update_if_touched("IdentityFile", self.identity_entry.get_text())
        if "ForwardAgent" in self._touched_options:
            fa = "yes" if self.forward_agent_switch.get_active() else "no"
            update_if_touched("ForwardAgent", fa, default_absent_values=["no"])

        update_if_touched("ProxyJump", self.proxy_jump_entry.get_text())
        update_if_touched("ProxyCommand", self.proxy_cmd_entry.get_text())
        update_if_touched("LocalForward", self.local_forward_entry.get_text())
        update_if_touched("RemoteForward", self.remote_forward_entry.get_text())

        if "Compression" in self._touched_options:
            comp = (
                "yes"
                if (self.compression_switch and self.compression_switch.get_active())
                else "no"
            )
            update_if_touched("Compression", comp, default_absent_values=["no"])
        if "ServerAliveInterval" in self._touched_options:
            interval = (
                self.serveralive_interval_entry.get_text().strip()
                if self.serveralive_interval_entry
                else ""
            )
            update_if_touched(
                "ServerAliveInterval", interval, default_absent_values=["0"]
            )
        if "ServerAliveCountMax" in self._touched_options:
            countmax = (
                self.serveralive_count_entry.get_text().strip()
                if self.serveralive_count_entry
                else ""
            )
            update_if_touched(
                "ServerAliveCountMax", countmax, default_absent_values=["3"]
            )
        if "TCPKeepAlive" in self._touched_options:
            tka = (
                "yes"
                if (
                    self.tcp_keepalive_switch and self.tcp_keepalive_switch.get_active()
                )
                else "no"
            )
            update_if_touched("TCPKeepAlive", tka, default_absent_values=["yes"])
        if (
            "StrictHostKeyChecking" in self._touched_options
            and self.strict_host_key_row
        ):
            idx = self.strict_host_key_row.get_selected()
            mapping = ["ask", "yes", "no"]
            val = mapping[idx] if 0 <= idx < len(mapping) else "ask"
            update_if_touched(
                "StrictHostKeyChecking", val, default_absent_values=["ask"]
            )

        if "PubkeyAuthentication" in self._touched_options:
            update_if_touched(
                "PubkeyAuthentication",
                (
                    "yes"
                    if (
                        self.pubkey_auth_switch and self.pubkey_auth_switch.get_active()
                    )
                    else "no"
                ),
                default_absent_values=["yes"],
            )
        if "PasswordAuthentication" in self._touched_options:
            update_if_touched(
                "PasswordAuthentication",
                (
                    "yes"
                    if (
                        self.password_auth_switch
                        and self.password_auth_switch.get_active()
                    )
                    else "no"
                ),
                default_absent_values=["yes"],
            )
        if "KbdInteractiveAuthentication" in self._touched_options:
            update_if_touched(
                "KbdInteractiveAuthentication",
                (
                    "yes"
                    if (
                        self.kbd_interactive_auth_switch
                        and self.kbd_interactive_auth_switch.get_active()
                    )
                    else "no"
                ),
                default_absent_values=["yes"],
            )
        if "GSSAPIAuthentication" in self._touched_options:
            update_if_touched(
                "GSSAPIAuthentication",
                (
                    "yes"
                    if (
                        self.gssapi_auth_switch and self.gssapi_auth_switch.get_active()
                    )
                    else "no"
                ),
                default_absent_values=["no"],
            )
        update_if_touched(
            "PreferredAuthentications",
            (
                getattr(self, "preferred_authentications_entry", None).get_text()
                if hasattr(self, "preferred_authentications_entry")
                and self.preferred_authentications_entry
                else ""
            ),
        )
        update_if_touched(
            "IdentityAgent",
            (
                getattr(self, "identity_agent_entry", None).get_text()
                if hasattr(self, "identity_agent_entry") and self.identity_agent_entry
                else ""
            ),
        )
        if "AddKeysToAgent" in self._touched_options and self.add_keys_to_agent_row:
            aka_idx = self.add_keys_to_agent_row.get_selected()
            aka_map = ["no", "yes", "ask", "confirm"]
            val = aka_map[aka_idx] if 0 <= aka_idx < len(aka_map) else "no"
            update_if_touched("AddKeysToAgent", val, default_absent_values=["no"])

        if "ConnectTimeout" in self._touched_options:
            ct = (
                self.connect_timeout_entry.get_text().strip()
                if self.connect_timeout_entry
                else ""
            )
            if ct == "0":
                ct = ""
            update_if_touched("ConnectTimeout", ct)
        if "RequestTTY" in self._touched_options and self.request_tty_row:
            idx = self.request_tty_row.get_selected()
            rtty_map = ["auto", "no", "yes", "force"]
            val = rtty_map[idx] if 0 <= idx < len(rtty_map) else "auto"
            update_if_touched("RequestTTY", val, default_absent_values=["auto"])
        if "LogLevel" in self._touched_options and self.log_level_row:
            idx = self.log_level_row.get_selected()
            lvl_map = [
                "QUIET",
                "FATAL",
                "ERROR",
                "INFO",
                "VERBOSE",
                "DEBUG",
                "DEBUG1",
                "DEBUG2",
                "DEBUG3",
            ]
            val = lvl_map[idx] if 0 <= idx < len(lvl_map) else "INFO"
            update_if_touched("LogLevel", val, default_absent_values=["INFO"])
        if "VerifyHostKeyDNS" in self._touched_options:
            vhk = (
                "yes"
                if (
                    self.verify_host_key_dns_switch
                    and self.verify_host_key_dns_switch.get_active()
                )
                else "no"
            )
            update_if_touched("VerifyHostKeyDNS", vhk, default_absent_values=["no"])
        if (
            "CanonicalizeHostname" in self._touched_options
            and self.canonicalize_hostname_row
        ):
            idx = self.canonicalize_hostname_row.get_selected()
            can_map = ["no", "yes", "always"]
            val = can_map[idx] if 0 <= idx < len(can_map) else "no"
            update_if_touched("CanonicalizeHostname", val, default_absent_values=["no"])
        update_if_touched(
            "CanonicalDomains",
            (
                getattr(self, "canonical_domains_entry", None).get_text()
                if hasattr(self, "canonical_domains_entry")
                and self.canonical_domains_entry
                else ""
            ),
        )

        if "ControlMaster" in self._touched_options and self.control_master_row:
            idx = self.control_master_row.get_selected()
            cm_map = ["no", "yes", "ask", "auto", "autoask"]
            val = cm_map[idx] if 0 <= idx < len(cm_map) else "no"
            update_if_touched("ControlMaster", val, default_absent_values=["no"])
        update_if_touched(
            "ControlPersist",
            (
                getattr(self, "control_persist_entry", None).get_text()
                if hasattr(self, "control_persist_entry") and self.control_persist_entry
                else ""
            ),
        )
        update_if_touched(
            "ControlPath",
            (
                getattr(self, "control_path_entry", None).get_text()
                if hasattr(self, "control_path_entry") and self.control_path_entry
                else ""
            ),
        )

    def _update_host_option(self, key: str, value: str):
        """Helper to update or remove a single SSH option on the current host."""
        if value.strip():
            self.current_host.set_option(key, value.strip())
        else:
            self.current_host.remove_option(key)

    def _update_custom_options(self):
        """Updates custom options on the current host based on the listbox content."""
        common_options = {
            "HostName",
            "User",
            "Port",
            "IdentityFile",
            "ForwardAgent",
            "ProxyJump",
            "ProxyCommand",
            "LocalForward",
            "RemoteForward",
            "Compression",
            "ServerAliveInterval",
            "ServerAliveCountMax",
            "TCPKeepAlive",
            "StrictHostKeyChecking",
            "PubkeyAuthentication",
            "PasswordAuthentication",
            "KbdInteractiveAuthentication",
            "GSSAPIAuthentication",
            "AddKeysToAgent",
            "PreferredAuthentications",
            "IdentityAgent",
            "ConnectTimeout",
            "RequestTTY",
            "LogLevel",
            "VerifyHostKeyDNS",
            "CanonicalizeHostname",
            "CanonicalDomains",
            "ControlMaster",
            "ControlPersist",
            "ControlPath",
        }

        self.current_host.options = [
            opt for opt in self.current_host.options if opt.key in common_options
        ]

        if hasattr(self, "custom_options_list") and self.custom_options_list:
            for action_row in self.custom_options_list:
                if hasattr(action_row, "key_entry") and hasattr(
                    action_row, "value_entry"
                ):
                    key_entry = action_row.key_entry
                    value_entry = action_row.value_entry
                    if key_entry and value_entry:
                        key = key_entry.get_text().strip()
                        value = value_entry.get_text().strip()
                        if key and value:
                            self.current_host.set_option(key, value)

    def _on_identity_file_clicked(self, button):
        dialog = Gtk.FileChooserDialog(
            title=_("Choose Identity File"),
            transient_for=self.get_root(),
            action=Gtk.FileChooserAction.OPEN,
        )

        dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("Open"), Gtk.ResponseType.OK)

        filter_text = Gtk.FileFilter()
        filter_text.set_name(_("SSH Keys"))
        filter_text.add_pattern("*.pem")
        filter_text.add_pattern("id_*")
        dialog.add_filter(filter_text)

        dialog.connect("response", self._on_identity_file_response)
        dialog.present()

    def _on_identity_pick_clicked(self, button):
        from .key_picker_dialog import KeyPickerDialog

        dlg = KeyPickerDialog(self)

        def on_key_selected(dlg_obj, private_path: str):
            if private_path:
                self.identity_entry.set_text(private_path)

        dlg.connect("key-selected", on_key_selected)

        def on_generate(*_):
            from .generate_key_dialog import GenerateKeyDialog

            gen = GenerateKeyDialog(self)

            def after_gen(*__):
                opts = gen.get_options()
                gen.close()
                try:
                    import subprocess
                    from pathlib import Path

                    ssh_dir = Path.home() / ".ssh"
                    ssh_dir.mkdir(parents=True, exist_ok=True)
                    name = opts.get("name") or "id_ed25519"
                    base = name
                    i = 0
                    while (ssh_dir / name).exists():
                        i += 1
                        name = f"{base}_{i}"
                    key_path = ssh_dir / name
                    key_type = (opts.get("type") or "ed25519").lower()
                    comment = opts.get("comment") or "ssh-studio"
                    passphrase = opts.get("passphrase") or ""
                    if key_type == "rsa":
                        size = int(opts.get("size") or 2048)
                        cmd = [
                            "ssh-keygen",
                            "-t",
                            "rsa",
                            "-b",
                            str(size),
                            "-f",
                            str(key_path),
                            "-N",
                            passphrase,
                            "-C",
                            comment,
                        ]
                    elif key_type == "ecdsa":
                        cmd = [
                            "ssh-keygen",
                            "-t",
                            "ecdsa",
                            "-f",
                            str(key_path),
                            "-N",
                            passphrase,
                            "-C",
                            comment,
                        ]
                    else:
                        cmd = [
                            "ssh-keygen",
                            "-t",
                            "ed25519",
                            "-f",
                            str(key_path),
                            "-N",
                            passphrase,
                            "-C",
                            comment,
                        ]
                    subprocess.run(cmd, check=True)
                    try:
                        dlg._load_keys()
                    except Exception:
                        pass
                    self.identity_entry.set_text(str(key_path))
                except Exception:
                    pass

            gen.generate_btn.connect("clicked", after_gen)
            gen.present(self.get_root())

        dlg.generate_btn.connect("clicked", on_generate)
        dlg.present(self.get_root())

    def _on_identity_file_response(self, dialog, response_id):
        try:
            if response_id == Gtk.ResponseType.OK:
                file = dialog.get_file()
                if file:
                    self.identity_entry.set_text(file.get_path())
        finally:
            dialog.destroy()

    def _on_add_custom_option(self, button):
        self._add_custom_option_row()

    def _on_remove_custom_option(self, button, action_row):
        """Handle remove custom option button click."""
        if hasattr(self, "custom_options_list") and self.custom_options_list:
            self.custom_options_list.remove(action_row)
        self._update_host_from_fields()
        self.emit("host-changed", self.current_host)
        self._show_message(_("Custom option removed"))

    def _on_copy_ssh_command(self, button):
        """Copy the generated SSH command to the clipboard and show a toast."""
        if not self.current_host:
            self._show_message(_("No host selected"))
            return

        try:
            hostname = self.hostname_entry.get_text().strip()
            if not hostname and self.current_host.patterns:
                hostname = self.current_host.patterns[0]
            if not hostname:
                self._show_message(_("No hostname or pattern available"))
                return

            command = f"ssh {hostname}"

            try:
                display = Gdk.Display.get_default()
                if not display:
                    self._show_message(_("Failed to access display"))
                    return

                clipboard = display.get_clipboard()

                content_provider = Gdk.ContentProvider.new_for_bytes(
                    "text/plain", GLib.Bytes.new(command.encode("utf-8"))
                )

                clipboard.set_content(content_provider)

                primary = display.get_primary_clipboard()
                if primary:
                    primary.set_content(content_provider)

            except Exception as e:
                try:
                    import subprocess

                    result = subprocess.run(
                        ["xclip", "-selection", "clipboard"],
                        input=command,
                        text=True,
                        capture_output=True,
                    )
                    if result.returncode == 0:
                        self._show_message(_(f"SSH command copied: {command}"))
                        return
                except Exception:
                    pass

                try:
                    import subprocess

                    result = subprocess.run(
                        ["xsel", "--clipboard", "--input"],
                        input=command,
                        text=True,
                        capture_output=True,
                    )
                    if result.returncode == 0:
                        self._show_message(_(f"SSH command copied: {command}"))
                        return
                except Exception:
                    pass

                raise e

            self._show_message(_(f"SSH command copied: {command}"))

        except Exception as e:
            self._show_message(_(f"Failed to copy command: {str(e)}"))

    def set_wrap_mode(self, wrap: bool):
        """Set the wrap mode for the raw text view based on preferences."""
        try:
            if wrap:
                self.raw_text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            else:
                self.raw_text_view.set_wrap_mode(Gtk.WrapMode.NONE)
        except Exception:
            pass

    def is_host_dirty(self) -> bool:
        """Checks if the current host has unsaved changes compared to its original loaded state."""
        if not self.current_host or not self.original_host_state:
            return False

        if sorted(self.current_host.patterns) != sorted(
            self.original_host_state.patterns
        ):
            return True

        if len(self.current_host.options) != len(self.original_host_state.options):
            return True

        current_options_dict = {
            opt.key.lower(): opt.value for opt in self.current_host.options
        }
        original_options_dict = {
            opt.key.lower(): opt.value for opt in self.original_host_state.options
        }

        if current_options_dict != original_options_dict:
            return True

        current_raw_clean = [line.rstrip("\n") for line in self.current_host.raw_lines]
        original_raw_clean = [
            line.rstrip("\n") for line in self.original_host_state.raw_lines
        ]

        return current_raw_clean != original_raw_clean

    def _collect_field_errors(self) -> dict:
        errors: dict[str, str] = {}
        self._clear_field_errors()

        patterns_text = self.patterns_entry.get_text().strip()
        if not patterns_text:
            errors["patterns"] = _("Host name (patterns) is required.")

        port_text = self.port_entry.get_text().strip()
        if port_text:
            try:
                port = int(port_text)
                if not (1 <= port <= 65535):
                    errors["port"] = _("Port must be between 1 and 65535.")
            except ValueError:
                errors["port"] = _("Port must be numeric.")

        if "patterns" in errors:
            self.patterns_error_label.set_text(errors["patterns"])
            self.patterns_error_label.set_visible(True)
            self.patterns_entry.add_css_class("entry-error")
        else:
            self.patterns_entry.remove_css_class("entry-error")
        if "port" in errors:
            self.port_error_label.set_text(errors["port"])
            self.port_error_label.set_visible(True)
            self.port_entry.add_css_class("entry-error")
        else:
            self.port_entry.remove_css_class("entry-error")

        try:
            if (
                hasattr(self, "serveralive_interval_entry")
                and self.serveralive_interval_entry
            ):
                interval_text = self.serveralive_interval_entry.get_text().strip()
                if interval_text:
                    interval_val = int(interval_text)
                    if interval_val < 0:
                        errors["sai"] = _("ServerAliveInterval must be >= 0.")
        except ValueError:
            errors["sai"] = _("ServerAliveInterval must be numeric.")

        try:
            if (
                hasattr(self, "serveralive_count_entry")
                and self.serveralive_count_entry
            ):
                count_text = self.serveralive_count_entry.get_text().strip()
                if count_text:
                    count_val = int(count_text)
                    if count_val < 1:
                        errors["sacm"] = _("ServerAliveCountMax must be >= 1.")
        except ValueError:
            errors["sacm"] = _("ServerAliveCountMax must be numeric.")

        if "sai" in errors and self.serveralive_interval_entry:
            self.serveralive_interval_entry.add_css_class("entry-error")
        else:
            if self.serveralive_interval_entry:
                self.serveralive_interval_entry.remove_css_class("entry-error")

        if "sacm" in errors and self.serveralive_count_entry:
            self.serveralive_count_entry.add_css_class("entry-error")
        else:
            if self.serveralive_count_entry:
                self.serveralive_count_entry.remove_css_class("entry-error")

        try:
            if self.connect_timeout_entry:
                ct_text = self.connect_timeout_entry.get_text().strip()
                if ct_text:
                    ct_val = int(ct_text)
                    if ct_val < 1:
                        errors["ct"] = _("ConnectTimeout must be >= 1.")
        except ValueError:
            errors["ct"] = _("ConnectTimeout must be numeric.")
        if "ct" in errors and self.connect_timeout_entry:
            self.connect_timeout_entry.add_css_class("entry-error")
        else:
            if self.connect_timeout_entry:
                self.connect_timeout_entry.remove_css_class("entry-error")

        return errors

    def _clear_field_errors(self):
        if hasattr(self, "patterns_error_label"):
            self.patterns_error_label.set_visible(False)
        if hasattr(self, "port_error_label"):
            self.port_error_label.set_visible(False)
        if hasattr(self, "patterns_entry"):
            self.patterns_entry.remove_css_class("entry-error")
        if hasattr(self, "port_entry"):
            self.port_entry.remove_css_class("entry-error")

        if (
            hasattr(self, "serveralive_interval_entry")
            and self.serveralive_interval_entry
        ):
            self.serveralive_interval_entry.remove_css_class("entry-error")
        if hasattr(self, "serveralive_count_entry") and self.serveralive_count_entry:
            self.serveralive_count_entry.remove_css_class("entry-error")
        if hasattr(self, "connect_timeout_entry") and self.connect_timeout_entry:
            self.connect_timeout_entry.remove_css_class("entry-error")

    def _combo_select(self, combo_row, values: list[str], value: str):
        try:
            lower_values = [v.lower() for v in values]
            idx = (
                lower_values.index(value.lower())
                if value.lower() in lower_values
                else 0
            )
            combo_row.set_selected(idx)
        except Exception:
            try:
                combo_row.set_selected(0)
            except Exception:
                pass

    def _validate_and_update_host(self):
        field_errors = self._collect_field_errors()
        if field_errors:
            self._editor_valid = False
            self.emit("editor-validity-changed", False)
            self._update_button_sensitivity()
            return
        else:
            self._editor_valid = True
            self.emit("editor-validity-changed", True)

        self._update_host_from_fields()
        self.emit("host-changed", self.current_host)
        GLib.idle_add(lambda: (self._update_raw_text_from_host(), False)[1])
        self._update_button_sensitivity()

    def _on_save_clicked(self, button):
        """Handle save button click."""
        if not self.current_host:
            return
        try:
            field_errors = self._collect_field_errors()
            if field_errors:
                try:
                    self._show_message(_("Fix validation errors before saving"))
                except Exception:
                    pass
                return
        except Exception:
            pass

        try:
            self._update_host_from_fields()
            self._update_raw_text_from_host()
        except Exception:
            pass
        try:
            buffer = self.raw_text_view.get_buffer()
            current_text = buffer.get_text(
                buffer.get_start_iter(), buffer.get_end_iter(), False
            )
            current_lines = current_text.splitlines()
            temp_host = SSHHost.from_raw_lines(current_lines)
            self.current_host.patterns = temp_host.patterns
            self.current_host.options = temp_host.options
            self.current_host.raw_lines = current_lines
        except Exception as e:
            try:
                self._show_message(
                    _(f"Failed to parse current host before saving: {e}")
                )
            except Exception:
                pass
            return

        try:
            main_window = self.app or self.get_root()
            parser = getattr(main_window, "parser", None)
            if parser is not None:
                try:
                    cfg = parser.config
                    target_index = None
                    for idx, h in enumerate(getattr(cfg, "hosts", []) or []):
                        if h is self.current_host:
                            target_index = idx
                            break
                        try:
                            if set(h.patterns) == set(
                                self.original_host_state.patterns
                            ):
                                target_index = idx
                                break
                        except Exception:
                            pass
                    if target_index is None:
                        for idx, h in enumerate(getattr(cfg, "hosts", []) or []):
                            try:
                                if set(h.patterns) == set(self.current_host.patterns):
                                    target_index = idx
                                    break
                            except Exception:
                                pass
                    if target_index is not None:
                        cfg.hosts[target_index].patterns = list(
                            self.current_host.patterns
                        )
                        cfg.hosts[target_index].options = list(
                            self.current_host.options
                        )
                        cfg.hosts[target_index].raw_lines = list(
                            self.current_host.raw_lines
                        )
                    else:
                        try:
                            cfg.hosts.append(self.current_host)
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    warnings = parser.validate()
                    if warnings:
                        try:
                            self._show_message(_(f"Validation: {warnings[0]}"))
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    parser.write(backup=True)
                except Exception as e:
                    try:
                        self.app._show_error(
                            _(f"Failed to save {parser.config_path}: {e}")
                        )
                    except Exception:
                        pass
                    return
                try:
                    expected_content = parser._generate_content()
                    try:
                        with open(parser.config_path, "r", encoding="utf-8") as f:
                            on_disk = f.read()
                    except FileNotFoundError:
                        on_disk = ""
                    if on_disk != expected_content:
                        parser._atomic_write(expected_content)
                        try:
                            with open(parser.config_path, "r", encoding="utf-8") as f:
                                verify = f.read()
                        except Exception:
                            verify = None
                        if verify != expected_content:
                            try:
                                self.app._show_error(
                                    _(
                                        f"Failed to persist changes to {parser.config_path}. Check permissions / sandbox."
                                    )
                                )
                            except Exception:
                                pass
                except Exception:
                    pass
                self.original_host_state = copy.deepcopy(self.current_host)
                self.original_raw_content = "\n".join(self.current_host.raw_lines)
                self._ensure_buffer_initialized()
                if self.buffer is not None:
                    try:
                        self.buffer.remove_all_tags(
                            self.buffer.get_start_iter(), self.buffer.get_end_iter()
                        )
                    except Exception:
                        pass
                try:
                    self._show_message(_(f"Configuration saved → {parser.config_path}"))
                except Exception:
                    pass
                try:
                    if hasattr(main_window, "_write_and_reload"):
                        main_window._write_and_reload(show_status=False)
                except Exception:
                    pass
            else:
                self.emit("host-save", self.current_host)
                if main_window and hasattr(main_window, "_write_and_reload"):
                    main_window._write_and_reload(show_status=True)
                elif main_window and hasattr(main_window, "_on_save_clicked"):
                    main_window._on_save_clicked(None)
        finally:
            try:
                self._touched_options.clear()
                self._update_button_sensitivity()
            except Exception:
                pass

    def _on_revert_clicked(self, button):
        """Reverts the current host's changes to its last loaded state by reloading the configuration."""
        if not self.current_host:
            return

        if not hasattr(self, "original_host_state") or not self.original_host_state:
            return
        self.is_loading = True
        self.current_host.patterns = copy.deepcopy(self.original_host_state.patterns)
        self.current_host.options = copy.deepcopy(self.original_host_state.options)
        self.current_host.raw_lines = copy.deepcopy(self.original_host_state.raw_lines)

        self._sync_fields_from_host()

        buffer = self.raw_text_view.get_buffer()
        if hasattr(self, "_raw_changed_handler_id"):
            buffer.handler_block(self._raw_changed_handler_id)
        self._programmatic_raw_update = True
        buffer.set_text("\n".join(self.current_host.raw_lines))
        if hasattr(self, "_raw_changed_handler_id"):
            buffer.handler_unblock(self._raw_changed_handler_id)
        self._programmatic_raw_update = False
        self.original_raw_content = "\n".join(self.current_host.raw_lines)
        self.is_loading = False

        self._ensure_buffer_initialized()
        if self.buffer is not None:
            self.buffer.remove_all_tags(
                self.buffer.get_start_iter(), self.buffer.get_end_iter()
            )
        self.emit("host-changed", self.current_host)
        self.revert_button.set_sensitive(False)
        if hasattr(self, "save_button"):
            self.save_button.set_sensitive(False)
        self.banner_revealer.set_reveal_child(False)
        self._show_message(_(f"Reverted changes for {self.current_host.patterns[0]}"))
        self._touched_options.clear()
        self._update_button_sensitivity()

    def _update_button_sensitivity(self):
        """Updates the sensitivity of save and revert buttons based on dirty state and validity."""
        is_dirty = self.is_host_dirty()
        field_errors = self._collect_field_errors()
        is_valid = not bool(field_errors)
        try:
            if getattr(self, "save_button", None):
                self.save_button.set_sensitive(is_dirty and is_valid)
            if getattr(self, "revert_button", None):
                self.revert_button.set_sensitive(is_dirty)
            if getattr(self, "banner_revealer", None) and hasattr(
                self.banner_revealer, "set_reveal_child"
            ):
                self.banner_revealer.set_reveal_child(is_dirty)
            mw = self.get_root()
            if hasattr(mw, "unsaved_label") and mw.unsaved_label:
                mw.unsaved_label.set_visible(is_dirty)
            if hasattr(mw, "save_button") and mw.save_button:
                mw.save_button.set_visible(is_dirty)
                mw.save_button.set_sensitive(is_dirty and is_valid)
            if hasattr(mw, "revert_button") and mw.revert_button:
                mw.revert_button.set_visible(is_dirty)
                mw.revert_button.set_sensitive(is_dirty)
        except Exception:
            pass
        try:
            main_window = self.get_root()
            if (
                hasattr(main_window, "global_actionbar")
                and main_window.global_actionbar
            ):
                main_window.unsaved_label.set_visible(is_dirty)
                main_window.save_button.set_visible(is_dirty and is_valid)
                main_window.revert_button.set_visible(is_dirty)
        except Exception:
            pass

    def _on_test_connection(self, button):
        if not self.current_host:
            return

        dialog = TestConnectionDialog(parent=self.get_root())

        hostname = self.hostname_entry.get_text().strip()
        if not hostname and self.current_host.patterns:
            hostname = self.current_host.patterns[0]

        ssh_exec = ["ssh"]
        try:
            if os.environ.get("FLATPAK_ID"):
                ssh_exec = ["flatpak-spawn", "--host", "ssh"]
        except Exception:
            pass

        command = [
            *ssh_exec,
            "-q",
            "-T",
            "-o",
            "BatchMode=yes",
            "-o",
            "NumberOfPasswordPrompts=0",
        ]

        user_val = self.user_entry.get_text().strip()
        port_val = self.port_entry.get_text().strip()
        ident_val = self.identity_entry.get_text().strip()
        proxy_jump_val = self.proxy_jump_entry.get_text().strip()

        if user_val:
            command += ["-l", user_val]
        if port_val:
            command += ["-p", port_val]
        if ident_val:
            command += ["-i", ident_val]
        if proxy_jump_val:
            command += ["-J", proxy_jump_val]

        special_keys = {"Host", "HostName", "User", "Port", "IdentityFile", "ProxyJump"}

        options_dict = {}
        try:
            for opt in self.current_host.options:
                options_dict[opt.key] = opt.value
        except Exception:
            pass

        def maybe_add_default(key: str, value: str):
            if key not in options_dict or not (options_dict.get(key) or "").strip():
                command.extend(["-o", f"{key}={value}"])

        for key, value in options_dict.items():
            if key in special_keys:
                continue
            if (value or "").strip():
                command.extend(["-o", f"{key}={value}"])

        maybe_add_default("ConnectTimeout", "8")
        maybe_add_default("StrictHostKeyChecking", "accept-new")
        maybe_add_default("ControlMaster", "no")
        maybe_add_default("ControlPath", "none")
        maybe_add_default("ControlPersist", "no")

        command += [hostname, "exit"]

        dialog.start_test(command, hostname)
        dialog.present()

    def _sync_fields_from_host(self):
        if not self.current_host:
            return
        self.is_loading = True
        self.patterns_entry.set_text(" ".join(self.current_host.patterns))
        self.hostname_entry.set_text(self.current_host.get_option("HostName") or "")
        self.user_entry.set_text(self.current_host.get_option("User") or "")
        self.port_entry.set_text(self.current_host.get_option("Port") or "")
        self.identity_entry.set_text(self.current_host.get_option("IdentityFile") or "")
        self.forward_agent_switch.set_active(
            (self.current_host.get_option("ForwardAgent") or "").lower() == "yes"
        )
        self.proxy_jump_entry.set_text(self.current_host.get_option("ProxyJump") or "")
        self.proxy_cmd_entry.set_text(
            self.current_host.get_option("ProxyCommand") or ""
        )
        self.local_forward_entry.set_text(
            self.current_host.get_option("LocalForward") or ""
        )
        self.remote_forward_entry.set_text(
            self.current_host.get_option("RemoteForward") or ""
        )
        self.compression_switch.set_active(
            (self.current_host.get_option("Compression") or "no").lower() == "yes"
        )
        self.serveralive_interval_entry.set_text(
            self.current_host.get_option("ServerAliveInterval") or "0"
        )
        self.serveralive_count_entry.set_text(
            self.current_host.get_option("ServerAliveCountMax") or "3"
        )
        self.tcp_keepalive_switch.set_active(
            (self.current_host.get_option("TCPKeepAlive") or "yes").lower() == "yes"
        )
        shk2 = (self.current_host.get_option("StrictHostKeyChecking") or "ask").lower()
        mapping2 = {"ask": 0, "yes": 1, "no": 2}
        self.strict_host_key_row.set_selected(mapping2.get(shk2, 0))
        self._load_custom_options(self.current_host)
        self.is_loading = False

    def _replace_textview_with_sourceview(self):
        """Replace the regular TextView with GtkSourceView for syntax highlighting."""
        if not self.raw_text_view:
            return

        try:
            parent = self.raw_text_view.get_parent()
            if not parent:
                return

            source_view = GtkSource.View()

            source_view.set_monospace(True)
            source_view.set_wrap_mode(Gtk.WrapMode.NONE)
            source_view.set_editable(True)
            source_view.set_hexpand(True)
            source_view.set_vexpand(True)
            source_view.set_left_margin(8)
            source_view.set_right_margin(8)
            source_view.set_top_margin(6)
            source_view.set_bottom_margin(6)

            source_view.get_style_context().add_class("raw-editor")

            source_view.set_show_line_numbers(True)
            source_view.set_highlight_current_line(True)
            source_view.set_auto_indent(True)
            source_view.set_indent_on_tab(True)
            source_view.set_tab_width(4)
            source_view.set_insert_spaces_instead_of_tabs(True)

            parent.set_child(None)
            parent.set_child(source_view)

            self.raw_text_view = source_view

        except Exception as e:
            print(f"Warning: Could not replace TextView with GtkSourceView: {e}")
            pass

    def _show_helpful_placeholder(self):
        """Show helpful placeholder text when the raw editor is empty or invalid."""
        if not self.raw_text_view or not self.buffer:
            return

        current_text = self.buffer.get_text(
            self.buffer.get_start_iter(), self.buffer.get_end_iter(), False
        ).strip()

        if not current_text or not current_text.lower().startswith("host "):
            placeholder_text = """# SSH Host Configuration
# Start with a Host declaration, for example:
Host myserver
    HostName example.com
    User myuser
    Port 22
    IdentityFile ~/.ssh/id_rsa

# Add any other SSH options as needed"""

            if not current_text:
                self.buffer.set_text(placeholder_text)
                start = self.buffer.get_start_iter()
                end = self.buffer.get_end_iter()
                self.buffer.select_range(start, end)

    def _ensure_buffer_initialized(self):
        """Ensure the text buffer is initialized."""
        if not self.buffer and self.raw_text_view:
            try:
                self.buffer = self.raw_text_view.get_buffer()
                if self.buffer and not hasattr(self, "_raw_changed_handler_id"):
                    self._raw_changed_handler_id = self.buffer.connect(
                        "changed", self._on_raw_text_changed
                    )
            except Exception:
                pass

    def _is_source_view(self):
        """Check if we're using GtkSourceView."""
        return (
            self.raw_text_view
            and hasattr(self.raw_text_view, "get_buffer")
            and isinstance(self.raw_text_view.get_buffer(), GtkSource.Buffer)
        )

    def _create_diff_tags(self):
        """Create diff highlighting tags with appropriate colors based on editor type."""
        if self._is_source_view():
            self.tag_add = self.buffer.create_tag(
                "added", background_rgba=Gdk.RGBA(0.2, 0.4, 0.2, 0.3)
            )
            self.tag_removed = self.buffer.create_tag(
                "removed", background_rgba=Gdk.RGBA(0.4, 0.2, 0.2, 0.3)
            )
            self.tag_changed = self.buffer.create_tag(
                "changed", background_rgba=Gdk.RGBA(0.4, 0.4, 0.2, 0.3)
            )
        else:
            self.tag_add = self.buffer.create_tag(
                "added", background="#aaffaa", foreground="black"
            )
            self.tag_removed = self.buffer.create_tag(
                "removed", background="#ffaaaa", foreground="black"
            )
            self.tag_changed = self.buffer.create_tag(
                "changed", background="#ffffaa", foreground="black"
            )

    def _apply_full_diff_highlighting(self, current_lines, original_lines):
        """Apply full diff highlighting for regular TextView."""
        s = difflib.SequenceMatcher(None, original_lines, current_lines)

        for opcode, i1, i2, j1, j2 in s.get_opcodes():
            if opcode == "equal":
                pass
            elif opcode == "insert":
                for line_idx in range(j1, j2):
                    if line_idx >= len(current_lines):
                        continue
                    success, start_iter = self.buffer.get_iter_at_line(line_idx)
                    if not success:
                        continue
                    end_iter = start_iter.copy()
                    end_iter.forward_to_line_end()
                    self.buffer.apply_tag(self.tag_add, start_iter, end_iter)
            elif opcode == "delete":
                pass
            elif opcode == "replace":
                for line_idx in range(j1, j2):
                    if line_idx >= len(current_lines):
                        continue
                    success, start_iter = self.buffer.get_iter_at_line(line_idx)
                    if not success:
                        continue
                    end_iter = start_iter.copy()
                    end_iter.forward_to_line_end()
                    self.buffer.apply_tag(self.tag_changed, start_iter, end_iter)

    def _apply_subtle_diff_highlighting(self, current_lines, original_lines):
        """Apply subtle diff highlighting for GtkSourceView that doesn't conflict with syntax highlighting."""
        s = difflib.SequenceMatcher(None, original_lines, current_lines)

        for opcode, i1, i2, j1, j2 in s.get_opcodes():
            if opcode == "equal":
                pass
            elif opcode == "insert":
                for line_idx in range(j1, j2):
                    if line_idx >= len(current_lines):
                        continue
                    success, start_iter = self.buffer.get_iter_at_line(line_idx)
                    if not success:
                        continue
                    end_iter = start_iter.copy()
                    end_iter.forward_to_line_end()
                    self.buffer.apply_tag(self.tag_add, start_iter, end_iter)
            elif opcode == "delete":
                pass
            elif opcode == "replace":
                for line_idx in range(j1, j2):
                    if line_idx >= len(current_lines):
                        continue
                    success, start_iter = self.buffer.get_iter_at_line(line_idx)
                    if not success:
                        continue
                    end_iter = start_iter.copy()
                    end_iter.forward_to_line_end()
                    self.buffer.apply_tag(self.tag_changed, start_iter, end_iter)

    def _setup_syntax_highlighting(self):
        """Setup syntax highlighting for the raw text editor."""
        if not self.raw_text_view:
            return

        try:
            source_buffer = self.raw_text_view.get_buffer()
            if not source_buffer:
                return

            self.buffer = source_buffer

            if not isinstance(source_buffer, GtkSource.Buffer):
                return

            language_manager = GtkSource.LanguageManager.get_default()

            ssh_language_ids = [
                "ssh-config",
                "ssh_config",
                "sshconfig",
                "ssh",
                "config",
                "ini",
            ]

            language = None
            for lang_id in ssh_language_ids:
                language = language_manager.get_language(lang_id)
                if language:
                    break

            if not language:
                language = language_manager.get_language(
                    "ini"
                ) or language_manager.get_language("config")

            if language:
                source_buffer.set_language(language)

            style_manager = GtkSource.StyleSchemeManager.get_default()
            style_scheme = (
                style_manager.get_scheme("dark")
                or style_manager.get_scheme("Adwaita-dark")
                or style_manager.get_scheme("default")
            )

            if style_scheme:
                source_buffer.set_style_scheme(style_scheme)

        except Exception as e:
            print(f"Warning: Could not setup syntax highlighting: {e}")
            pass
