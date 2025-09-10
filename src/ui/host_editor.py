import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GObject, Gio, Gdk, GLib, Adw
import shlex
import subprocess
import threading

try:
	from ssh_config_studio.ssh_config_parser import SSHHost, SSHOption
	from ssh_config_studio.ui.test_connection_dialog import TestConnectionDialog
except ImportError:
	from ssh_config_parser import SSHHost, SSHOption
	from ui.test_connection_dialog import TestConnectionDialog
import difflib
import copy
from gettext import gettext as _
import os

@Gtk.Template(resource_path="/com/sshconfigstudio/app/ui/host_editor.ui")
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
    custom_options_list = Gtk.Template.Child()
    custom_options_expander = Gtk.Template.Child()
    add_custom_button = Gtk.Template.Child()
    raw_text_view = Gtk.Template.Child()
    copy_row = Gtk.Template.Child()
    test_row = Gtk.Template.Child()
    save_button = Gtk.Template.Child()
    revert_button = Gtk.Template.Child()

    __gsignals__ = {
        'host-changed': (GObject.SignalFlags.RUN_LAST, None, (object,)),
        'editor-validity-changed': (GObject.SignalFlags.RUN_LAST, None, (bool,)),
        'host-save': (GObject.SignalFlags.RUN_LAST, None, (object,)),
        'show-toast': (GObject.SignalFlags.RUN_LAST, None, (str,))
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
        try:
            css = Gtk.CssProvider()
            css.load_from_data(b"""
            .error-label { color: #e01b24; }
            .entry-error { border-color: #e01b24; }
            """)
            Gtk.StyleContext.add_provider_for_display(
                Gtk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
        except Exception:
            pass
        self._connect_signals()

        self.buffer = self.raw_text_view.get_buffer()
        self.tag_add = self.buffer.create_tag("added", background="#aaffaa", foreground="black")
        self.tag_removed = self.buffer.create_tag("removed", background="#ffaaaa", foreground="black")
        self.tag_changed = self.buffer.create_tag("changed", background="#ffffaa", foreground="black")

        self.save_button.set_sensitive(False)
        self.revert_button.set_sensitive(False)

    def set_app(self, app):
        self.app = app

    def _show_message(self, message: str):
        """Show a message using toast by emitting a signal."""
        self.emit("show-toast", message)

    def _connect_signals(self):
        # Helper to mark an option as touched and forward to generic handler
        def connect_touch(widget, signal_name: str, option_key: str):
            if not widget:
                return
            def handler(*args):
                # Ignore programmatic changes during load
                if self.is_loading:
                    return
                self._touched_options.add(option_key)
                self._on_field_changed(widget)
            widget.connect(signal_name, handler)

        # Basics
        connect_touch(self.patterns_entry, "changed", "__patterns__")
        connect_touch(self.hostname_entry, "changed", "HostName")
        connect_touch(self.user_entry, "changed", "User")
        connect_touch(self.port_entry, "changed", "Port")
        connect_touch(self.identity_entry, "changed", "IdentityFile")
        connect_touch(self.forward_agent_switch, "state-set", "ForwardAgent")

        connect_touch(self.proxy_jump_entry, "changed", "ProxyJump")
        connect_touch(self.proxy_cmd_entry, "changed", "ProxyCommand")
        connect_touch(self.local_forward_entry, "changed", "LocalForward")
        connect_touch(self.remote_forward_entry, "changed", "RemoteForward")

        connect_touch(self.compression_switch, "state-set", "Compression")
        connect_touch(self.serveralive_interval_entry, "changed", "ServerAliveInterval")
        connect_touch(self.serveralive_count_entry, "changed", "ServerAliveCountMax")
        connect_touch(self.tcp_keepalive_switch, "state-set", "TCPKeepAlive")
        if hasattr(self, 'strict_host_key_row') and self.strict_host_key_row:
            self.strict_host_key_row.connect(
                "notify::selected",
                lambda *args: (None if self.is_loading else (self._touched_options.add('StrictHostKeyChecking'), self._on_field_changed(self.strict_host_key_row)))
            )

        if hasattr(self, 'add_keys_to_agent_row') and self.add_keys_to_agent_row:
            self.add_keys_to_agent_row.connect(
                "notify::selected",
                lambda *args: (None if self.is_loading else (self._touched_options.add('AddKeysToAgent'), self._on_field_changed(self.add_keys_to_agent_row)))
            )
        connect_touch(getattr(self, 'pubkey_auth_switch', None), "state-set", "PubkeyAuthentication")
        connect_touch(getattr(self, 'password_auth_switch', None), "state-set", "PasswordAuthentication")
        connect_touch(getattr(self, 'kbd_interactive_auth_switch', None), "state-set", "KbdInteractiveAuthentication")
        connect_touch(getattr(self, 'gssapi_auth_switch', None), "state-set", "GSSAPIAuthentication")
        connect_touch(getattr(self, 'preferred_authentications_entry', None), "changed", "PreferredAuthentications")
        connect_touch(getattr(self, 'identity_agent_entry', None), "changed", "IdentityAgent")
        connect_touch(getattr(self, 'connect_timeout_entry', None), "changed", "ConnectTimeout")
        if hasattr(self, 'request_tty_row') and self.request_tty_row:
            self.request_tty_row.connect(
                "notify::selected",
                lambda *args: (None if self.is_loading else (self._touched_options.add('RequestTTY'), self._on_field_changed(self.request_tty_row)))
            )
        if hasattr(self, 'log_level_row') and self.log_level_row:
            self.log_level_row.connect(
                "notify::selected",
                lambda *args: (None if self.is_loading else (self._touched_options.add('LogLevel'), self._on_field_changed(self.log_level_row)))
            )
        connect_touch(getattr(self, 'verify_host_key_dns_switch', None), "state-set", "VerifyHostKeyDNS")
        if hasattr(self, 'canonicalize_hostname_row') and self.canonicalize_hostname_row:
            self.canonicalize_hostname_row.connect(
                "notify::selected",
                lambda *args: (None if self.is_loading else (self._touched_options.add('CanonicalizeHostname'), self._on_field_changed(self.canonicalize_hostname_row)))
            )
        connect_touch(getattr(self, 'canonical_domains_entry', None), "changed", "CanonicalDomains")
        if hasattr(self, 'control_master_row') and self.control_master_row:
            self.control_master_row.connect(
                "notify::selected",
                lambda *args: (None if self.is_loading else (self._touched_options.add('ControlMaster'), self._on_field_changed(self.control_master_row)))
            )
        connect_touch(getattr(self, 'control_persist_entry', None), "changed", "ControlPersist")
        connect_touch(getattr(self, 'control_path_entry', None), "changed", "ControlPath")
        
        self._raw_changed_handler_id = self.raw_text_view.get_buffer().connect("changed", self._on_raw_text_changed)

        self._connect_buttons()

    def _connect_buttons(self):
        self.identity_button.connect("clicked", self._on_identity_file_clicked)
        if hasattr(self, 'identity_pick_button') and self.identity_pick_button:
            self.identity_pick_button.connect("clicked", self._on_identity_pick_clicked)
        self.add_custom_button.connect("clicked", self._on_add_custom_option)
        self.copy_row.connect("activated", lambda r: self._on_copy_ssh_command(None))
        self.test_row.connect("activated", lambda r: self._on_test_connection(None))
        self.save_button.connect("clicked", self._on_save_clicked)
        self.revert_button.connect("clicked", self._on_revert_clicked)
    
    def load_host(self, host: SSHHost):
        self.is_loading = True
        # Reset touched state for a fresh load
        self._touched_options.clear()
        self.current_host = host
        self.original_host_state = copy.deepcopy(host)
        
        if not host:
            self._clear_all_fields()
            self.is_loading = False
            return
        
        self.patterns_entry.set_text(" ".join(host.patterns))
        self.hostname_entry.set_text(host.get_option('HostName') or "")
        self.user_entry.set_text(host.get_option('User') or "")
        self.port_entry.set_text(host.get_option('Port') or "")
        self.identity_entry.set_text(host.get_option('IdentityFile') or "")
        
        forward_agent = host.get_option('ForwardAgent')
        self.forward_agent_switch.set_active(forward_agent == 'yes')
        
        self.proxy_jump_entry.set_text(host.get_option('ProxyJump') or "")
        self.proxy_cmd_entry.set_text(host.get_option('ProxyCommand') or "")
        self.local_forward_entry.set_text(host.get_option('LocalForward') or "")
        self.remote_forward_entry.set_text(host.get_option('RemoteForward') or "")

        compression = (host.get_option('Compression') or 'no').lower() == 'yes'
        self.compression_switch.set_active(compression)

        # ServerAliveInterval default 0 (disabled)
        self.serveralive_interval_entry.set_text(host.get_option('ServerAliveInterval') or "0")

        # ServerAliveCountMax default 3
        self.serveralive_count_entry.set_text(host.get_option('ServerAliveCountMax') or "3")

        # TCPKeepAlive default yes
        tcp_keepalive = (host.get_option('TCPKeepAlive') or 'yes').lower() == 'yes'
        self.tcp_keepalive_switch.set_active(tcp_keepalive)

        # StrictHostKeyChecking default ask
        shk = (host.get_option('StrictHostKeyChecking') or 'ask').lower()
        # Map to index in ["ask", "yes", "no"]
        mapping = { 'ask': 0, 'yes': 1, 'no': 2 }
        self.strict_host_key_row.set_selected(mapping.get(shk, 0))

        # Authentication and keys
        self.pubkey_auth_switch.set_active(((host.get_option('PubkeyAuthentication') or 'yes').lower()) == 'yes')
        self.password_auth_switch.set_active(((host.get_option('PasswordAuthentication') or 'no').lower()) == 'yes')
        self.kbd_interactive_auth_switch.set_active(((host.get_option('KbdInteractiveAuthentication') or 'no').lower()) == 'yes')
        self.gssapi_auth_switch.set_active(((host.get_option('GSSAPIAuthentication') or 'no').lower()) == 'yes')
        aka = (host.get_option('AddKeysToAgent') or 'no').lower()
        self._combo_select(self.add_keys_to_agent_row, ['no','yes','ask','confirm'], aka)
        self.preferred_authentications_entry.set_text(host.get_option('PreferredAuthentications') or "")
        self.identity_agent_entry.set_text(host.get_option('IdentityAgent') or "")

        # Connection behavior
        self.connect_timeout_entry.set_text(host.get_option('ConnectTimeout') or "8")
        self._combo_select(self.request_tty_row, ['auto','no','yes','force'], (host.get_option('RequestTTY') or 'auto').lower())
        self._combo_select(self.log_level_row, ['quiet','fatal','error','info','verbose','debug','debug1','debug2','debug3'], (host.get_option('LogLevel') or 'info').lower())
        self.verify_host_key_dns_switch.set_active(((host.get_option('VerifyHostKeyDNS') or 'no').lower()) == 'yes')
        self._combo_select(self.canonicalize_hostname_row, ['no','yes','always'], (host.get_option('CanonicalizeHostname') or 'no').lower())
        self.canonical_domains_entry.set_text(host.get_option('CanonicalDomains') or "")

        # Multiplexing
        self._combo_select(self.control_master_row, ['no','yes','ask','auto','autoask'], (host.get_option('ControlMaster') or 'no').lower())
        self.control_persist_entry.set_text(host.get_option('ControlPersist') or "")
        self.control_path_entry.set_text(host.get_option('ControlPath') or "")
        
        self._load_custom_options(host)

        self.raw_text_view.get_buffer().set_text("\n".join(host.raw_lines))
        self.original_raw_content = "\n".join(host.raw_lines)
        
        self.is_loading = False
        self.revert_button.set_sensitive(False)

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
        if hasattr(self, 'compression_switch'):
            self.compression_switch.set_active(False)
        if hasattr(self, 'serveralive_interval_entry'):
            self.serveralive_interval_entry.set_text("0")
        if hasattr(self, 'serveralive_count_entry'):
            self.serveralive_count_entry.set_text("3")
        if hasattr(self, 'tcp_keepalive_switch'):
            self.tcp_keepalive_switch.set_active(True)
        if hasattr(self, 'strict_host_key_row'):
            self.strict_host_key_row.set_selected(0)
        self._clear_custom_options()
    
    def _load_custom_options(self, host: SSHHost):
        """Loads custom SSH options into the custom options list."""
        self._clear_custom_options()
        
        common_options = {
            'HostName', 'User', 'Port', 'IdentityFile', 'ForwardAgent',
            'ProxyJump', 'ProxyCommand', 'LocalForward', 'RemoteForward'
        }
        
        for option in host.options:
            if option.key not in common_options:
                self._add_custom_option_row(option.key, option.value)
    
    def _clear_custom_options(self):
        """Clears all custom option rows from the list."""
        while self.custom_options_list.get_first_child():
            self.custom_options_list.remove(self.custom_options_list.get_first_child())
    
    def _add_custom_option_row(self, key: str = "", value: str = ""):
        """Adds a new row for a custom option to the list."""
        # Create a modern Adw.ActionRow for the custom option
        action_row = Adw.ActionRow()
        action_row.set_title(key if key else _("New Custom Option"))
        action_row.set_subtitle(value if value else _("Enter option name and value"))
        action_row.set_activatable(False)
        action_row.add_css_class("custom-option-row")

        # Create entry container with proper spacing
        entry_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        entry_container.set_spacing(12)
        entry_container.set_hexpand(True)
        entry_container.set_margin_start(12)
        entry_container.set_margin_end(12)

        # Key entry with label
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

        # Value entry with label
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

        # Remove button with modern styling
        remove_button = Gtk.Button()
        remove_button.set_icon_name("user-trash-symbolic")
        remove_button.add_css_class("flat")
        remove_button.add_css_class("destructive-action")
        remove_button.set_tooltip_text(_("Remove this custom option"))
        remove_button.set_valign(Gtk.Align.CENTER)
        remove_button.connect("clicked", self._on_remove_custom_option, action_row)

        # Add everything to the action row
        action_row.add_suffix(entry_container)
        action_row.add_suffix(remove_button)

        # Store references for easy access
        action_row.key_entry = key_entry
        action_row.value_entry = value_entry
        
        # Add to the list
        self.custom_options_list.append(action_row)
        
        # Connect change handlers
        key_entry.connect("changed", self._on_custom_option_changed)
        value_entry.connect("changed", self._on_custom_option_changed)

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

        current_text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)
        current_lines = current_text.splitlines()
        original_lines = self.original_raw_content.splitlines()

        if self.buffer is None:
            try:
                self.buffer = self.raw_text_view.get_buffer()
            except Exception:
                return
        self.buffer.remove_all_tags(self.buffer.get_start_iter(), self.buffer.get_end_iter())

        s = difflib.SequenceMatcher(None, original_lines, current_lines)

        for opcode, i1, i2, j1, j2 in s.get_opcodes():
            if opcode == 'equal':
                pass
            elif opcode == 'insert':
                for line_idx in range(j1, j2):
                    if line_idx >= len(current_lines):
                        continue
                    success, start_iter = self.buffer.get_iter_at_line(line_idx)
                    if not success:
                        continue
                    end_iter = start_iter.copy()
                    end_iter.forward_to_line_end()
                    self.buffer.apply_tag(self.tag_add, start_iter, end_iter)
            elif opcode == 'delete':
                pass
            elif opcode == 'replace':
                for line_idx in range(j1, j2):
                    if line_idx >= len(current_lines):
                        continue
                    success, start_iter = self.buffer.get_iter_at_line(line_idx)
                    if not success:
                        continue
                    end_iter = start_iter.copy()
                    end_iter.forward_to_line_end()
                    self.buffer.apply_tag(self.tag_changed, start_iter, end_iter)

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
            self.app._show_error(f"Invalid raw host configuration: {e}")
        except Exception as e:
            self.app._show_error(f"Error parsing raw host config: {e}")

    
    def _update_host_from_fields(self):
        """Updates the current host object based on GUI field values.
        Only updates options the user interacted with (touched). Defaults are not written.
        """
        if not self.current_host:
            return

        # Patterns are special
        if '__patterns__' in self._touched_options:
            patterns_text = self.patterns_entry.get_text().strip()
            self.current_host.patterns = [p.strip() for p in patterns_text.split()] if patterns_text else []

        def update_if_touched(key: str, value: str | None, default_absent_values: list[str] | None = None):
            if key not in self._touched_options:
                return
            v = (value or "").strip()
            if default_absent_values and v.lower() in [d.lower() for d in default_absent_values]:
                self.current_host.remove_option(key)
            elif v == "":
                self.current_host.remove_option(key)
            else:
                self.current_host.set_option(key, v)

        # Basics
        update_if_touched('HostName', self.hostname_entry.get_text())
        update_if_touched('User', self.user_entry.get_text())
        update_if_touched('Port', self.port_entry.get_text())
        update_if_touched('IdentityFile', self.identity_entry.get_text())
        if 'ForwardAgent' in self._touched_options:
            fa = 'yes' if self.forward_agent_switch.get_active() else 'no'
            update_if_touched('ForwardAgent', fa, default_absent_values=['no'])

        update_if_touched('ProxyJump', self.proxy_jump_entry.get_text())
        update_if_touched('ProxyCommand', self.proxy_cmd_entry.get_text())
        update_if_touched('LocalForward', self.local_forward_entry.get_text())
        update_if_touched('RemoteForward', self.remote_forward_entry.get_text())

        # Advanced
        if 'Compression' in self._touched_options:
            comp = 'yes' if (self.compression_switch and self.compression_switch.get_active()) else 'no'
            update_if_touched('Compression', comp, default_absent_values=['no'])
        if 'ServerAliveInterval' in self._touched_options:
            interval = self.serveralive_interval_entry.get_text().strip() if self.serveralive_interval_entry else ""
            # default 0 => omit
            update_if_touched('ServerAliveInterval', interval, default_absent_values=['0'])
        if 'ServerAliveCountMax' in self._touched_options:
            countmax = self.serveralive_count_entry.get_text().strip() if self.serveralive_count_entry else ""
            # default 3 => omit
            update_if_touched('ServerAliveCountMax', countmax, default_absent_values=['3'])
        if 'TCPKeepAlive' in self._touched_options:
            tka = 'yes' if (self.tcp_keepalive_switch and self.tcp_keepalive_switch.get_active()) else 'no'
            # default yes => omit when yes
            update_if_touched('TCPKeepAlive', tka, default_absent_values=['yes'])
        if 'StrictHostKeyChecking' in self._touched_options and self.strict_host_key_row:
            idx = self.strict_host_key_row.get_selected()
            mapping = ["ask", "yes", "no"]
            val = mapping[idx] if 0 <= idx < len(mapping) else "ask"
            update_if_touched('StrictHostKeyChecking', val, default_absent_values=['ask'])

        # Authentication and keys
        if 'PubkeyAuthentication' in self._touched_options:
            update_if_touched('PubkeyAuthentication', 'yes' if (self.pubkey_auth_switch and self.pubkey_auth_switch.get_active()) else 'no', default_absent_values=['yes'])
        if 'PasswordAuthentication' in self._touched_options:
            # default yes -> omit when yes
            update_if_touched('PasswordAuthentication', 'yes' if (self.password_auth_switch and self.password_auth_switch.get_active()) else 'no', default_absent_values=['yes'])
        if 'KbdInteractiveAuthentication' in self._touched_options:
            # default yes -> omit when yes
            update_if_touched('KbdInteractiveAuthentication', 'yes' if (self.kbd_interactive_auth_switch and self.kbd_interactive_auth_switch.get_active()) else 'no', default_absent_values=['yes'])
        if 'GSSAPIAuthentication' in self._touched_options:
            # default no -> omit when no
            update_if_touched('GSSAPIAuthentication', 'yes' if (self.gssapi_auth_switch and self.gssapi_auth_switch.get_active()) else 'no', default_absent_values=['no'])
        update_if_touched('PreferredAuthentications', getattr(self, 'preferred_authentications_entry', None).get_text() if hasattr(self, 'preferred_authentications_entry') and self.preferred_authentications_entry else "")
        update_if_touched('IdentityAgent', getattr(self, 'identity_agent_entry', None).get_text() if hasattr(self, 'identity_agent_entry') and self.identity_agent_entry else "")
        if 'AddKeysToAgent' in self._touched_options and self.add_keys_to_agent_row:
            aka_idx = self.add_keys_to_agent_row.get_selected(); aka_map = ['no','yes','ask','confirm']
            val = aka_map[aka_idx] if 0 <= aka_idx < len(aka_map) else 'no'
            update_if_touched('AddKeysToAgent', val, default_absent_values=['no'])

        # Connection behavior
        if 'ConnectTimeout' in self._touched_options:
            ct = self.connect_timeout_entry.get_text().strip() if self.connect_timeout_entry else ""
            # omit when empty or 0
            if ct == '0':
                ct = ''
            update_if_touched('ConnectTimeout', ct)
        if 'RequestTTY' in self._touched_options and self.request_tty_row:
            idx = self.request_tty_row.get_selected(); rtty_map = ['auto','no','yes','force']
            val = rtty_map[idx] if 0 <= idx < len(rtty_map) else 'auto'
            update_if_touched('RequestTTY', val, default_absent_values=['auto'])
        if 'LogLevel' in self._touched_options and self.log_level_row:
            idx = self.log_level_row.get_selected(); lvl_map = ['QUIET','FATAL','ERROR','INFO','VERBOSE','DEBUG','DEBUG1','DEBUG2','DEBUG3']
            val = lvl_map[idx] if 0 <= idx < len(lvl_map) else 'INFO'
            update_if_touched('LogLevel', val, default_absent_values=['INFO'])
        if 'VerifyHostKeyDNS' in self._touched_options:
            vhk = 'yes' if (self.verify_host_key_dns_switch and self.verify_host_key_dns_switch.get_active()) else 'no'
            update_if_touched('VerifyHostKeyDNS', vhk, default_absent_values=['no'])
        if 'CanonicalizeHostname' in self._touched_options and self.canonicalize_hostname_row:
            idx = self.canonicalize_hostname_row.get_selected(); can_map = ['no','yes','always']
            val = can_map[idx] if 0 <= idx < len(can_map) else 'no'
            update_if_touched('CanonicalizeHostname', val, default_absent_values=['no'])
        update_if_touched('CanonicalDomains', getattr(self, 'canonical_domains_entry', None).get_text() if hasattr(self, 'canonical_domains_entry') and self.canonical_domains_entry else "")

        # Multiplexing
        if 'ControlMaster' in self._touched_options and self.control_master_row:
            idx = self.control_master_row.get_selected(); cm_map = ['no','yes','ask','auto','autoask']
            val = cm_map[idx] if 0 <= idx < len(cm_map) else 'no'
            update_if_touched('ControlMaster', val, default_absent_values=['no'])
        update_if_touched('ControlPersist', getattr(self, 'control_persist_entry', None).get_text() if hasattr(self, 'control_persist_entry') and self.control_persist_entry else "")
        update_if_touched('ControlPath', getattr(self, 'control_path_entry', None).get_text() if hasattr(self, 'control_path_entry') and self.control_path_entry else "")
        
        self._update_custom_options()
    
    def _update_host_option(self, key: str, value: str):
        """Helper to update or remove a single SSH option on the current host."""
        if value.strip():
            self.current_host.set_option(key, value.strip())
        else:
            self.current_host.remove_option(key)
    
    def _update_custom_options(self):
        """Updates custom options on the current host based on the listbox content."""
        common_options = {
            'HostName', 'User', 'Port', 'IdentityFile', 'ForwardAgent',
            'ProxyJump', 'ProxyCommand', 'LocalForward', 'RemoteForward',
            'Compression', 'ServerAliveInterval', 'ServerAliveCountMax', 'TCPKeepAlive', 'StrictHostKeyChecking',
            'PubkeyAuthentication', 'PasswordAuthentication', 'KbdInteractiveAuthentication', 'GSSAPIAuthentication',
            'AddKeysToAgent', 'PreferredAuthentications', 'IdentityAgent',
            'ConnectTimeout', 'RequestTTY', 'LogLevel', 'VerifyHostKeyDNS', 'CanonicalizeHostname', 'CanonicalDomains',
            'ControlMaster', 'ControlPersist', 'ControlPath'
        }

        self.current_host.options = [opt for opt in self.current_host.options if opt.key in common_options]
        
        for action_row in self.custom_options_list:
            # Access the stored entry references
            if hasattr(action_row, 'key_entry') and hasattr(action_row, 'value_entry'):
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
            action=Gtk.FileChooserAction.OPEN
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
        dlg.connect('key-selected', on_key_selected)
        def on_generate(*_):
            from .generate_key_dialog import GenerateKeyDialog
            gen = GenerateKeyDialog(self)
            def after_gen(*__):
                opts = gen.get_options(); gen.close()
                try:
                    import subprocess
                    from pathlib import Path
                    ssh_dir = Path.home()/'.ssh'; ssh_dir.mkdir(parents=True, exist_ok=True)
                    name = opts.get('name') or 'id_ed25519'
                    base = name; i = 0
                    while (ssh_dir/name).exists(): i+=1; name = f"{base}_{i}"
                    key_path = ssh_dir/name
                    key_type = (opts.get('type') or 'ed25519').lower()
                    comment = opts.get('comment') or 'ssh-config-studio'
                    passphrase = opts.get('passphrase') or ''
                    if key_type == 'rsa':
                        size = int(opts.get('size') or 2048)
                        cmd = ['ssh-keygen','-t','rsa','-b',str(size),'-f',str(key_path),'-N',passphrase,'-C',comment]
                    elif key_type == 'ecdsa':
                        cmd = ['ssh-keygen','-t','ecdsa','-f',str(key_path),'-N',passphrase,'-C',comment]
                    else:
                        cmd = ['ssh-keygen','-t','ed25519','-f',str(key_path),'-N',passphrase,'-C',comment]
                    subprocess.run(cmd, check=True)
                    try:
                        dlg._load_keys()
                    except Exception:
                        pass
                    self.identity_entry.set_text(str(key_path))
                except Exception:
                    pass
            gen.generate_btn.connect('clicked', after_gen)
            gen.present(self.get_root())
        dlg.generate_btn.connect('clicked', on_generate)
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
                    "text/plain",
                    GLib.Bytes.new(command.encode("utf-8"))
                )

                clipboard.set_content(content_provider)

                primary = display.get_primary_clipboard()
                if primary:
                    primary.set_content(content_provider)

            except Exception as e:
                try:
                    import subprocess
                    result = subprocess.run(['xclip', '-selection', 'clipboard'], 
                                         input=command, text=True, capture_output=True)
                    if result.returncode == 0:
                        self._show_message(_(f"SSH command copied: {command}"))
                        return
                except Exception:
                    pass

                try:
                    import subprocess
                    result = subprocess.run(['xsel', '--clipboard', '--input'], 
                                         input=command, text=True, capture_output=True)
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

        if sorted(self.current_host.patterns) != sorted(self.original_host_state.patterns):
            return True

        if len(self.current_host.options) != len(self.original_host_state.options):
            return True

        current_options_dict = {opt.key.lower(): opt.value for opt in self.current_host.options}
        original_options_dict = {opt.key.lower(): opt.value for opt in self.original_host_state.options}

        if current_options_dict != original_options_dict:
            return True

        current_raw_clean = [line.rstrip('\n') for line in self.current_host.raw_lines]
        original_raw_clean = [line.rstrip('\n') for line in self.original_host_state.raw_lines]

        return current_raw_clean != original_raw_clean

    def _collect_field_errors(self) -> dict:
        errors: dict[str, str] = {}
        self._clear_field_errors()

        patterns_text = self.patterns_entry.get_text().strip()
        if not patterns_text:
            errors['patterns'] = _("Host name (patterns) is required.")

        port_text = self.port_entry.get_text().strip()
        if port_text:
            try:
                port = int(port_text)
                if not (1 <= port <= 65535):
                    errors['port'] = _("Port must be between 1 and 65535.")
            except ValueError:
                errors['port'] = _("Port must be numeric.")

        # Mark invalid custom option keys with red border and tooltip
        for action_row in self.custom_options_list:
            if hasattr(action_row, 'key_entry'):
                key_entry = action_row.key_entry
                if key_entry and isinstance(key_entry, Gtk.Entry):
                    key = key_entry.get_text().strip()
                    key_entry.remove_css_class("entry-error")
                    if not key:
                        key_entry.add_css_class("entry-error")
                        key_entry.set_tooltip_text(_("Custom option key cannot be empty."))

        # Apply inline error texts
        if 'patterns' in errors:
            self.patterns_error_label.set_text(errors['patterns'])
            self.patterns_error_label.set_visible(True)
            self.patterns_entry.add_css_class("entry-error")
        else:
            self.patterns_entry.remove_css_class("entry-error")
        if 'port' in errors:
            self.port_error_label.set_text(errors['port'])
            self.port_error_label.set_visible(True)
            self.port_entry.add_css_class("entry-error")
        else:
            self.port_entry.remove_css_class("entry-error")

        # Validate numbers for ServerAliveInterval and ServerAliveCountMax
        try:
            if hasattr(self, 'serveralive_interval_entry') and self.serveralive_interval_entry:
                interval_text = self.serveralive_interval_entry.get_text().strip()
                if interval_text:
                    interval_val = int(interval_text)
                    if interval_val < 0:
                        errors['sai'] = _("ServerAliveInterval must be >= 0.")
        except ValueError:
            errors['sai'] = _("ServerAliveInterval must be numeric.")

        try:
            if hasattr(self, 'serveralive_count_entry') and self.serveralive_count_entry:
                count_text = self.serveralive_count_entry.get_text().strip()
                if count_text:
                    count_val = int(count_text)
                    if count_val < 1:
                        errors['sacm'] = _("ServerAliveCountMax must be >= 1.")
        except ValueError:
            errors['sacm'] = _("ServerAliveCountMax must be numeric.")

        # Apply error styles to advanced fields
        if 'sai' in errors and self.serveralive_interval_entry:
            self.serveralive_interval_entry.add_css_class("entry-error")
        else:
            if self.serveralive_interval_entry:
                self.serveralive_interval_entry.remove_css_class("entry-error")

        if 'sacm' in errors and self.serveralive_count_entry:
            self.serveralive_count_entry.add_css_class("entry-error")
        else:
            if self.serveralive_count_entry:
                self.serveralive_count_entry.remove_css_class("entry-error")

        # ConnectTimeout numeric validation
        try:
            if self.connect_timeout_entry:
                ct_text = self.connect_timeout_entry.get_text().strip()
                if ct_text:
                    ct_val = int(ct_text)
                    if ct_val < 1:
                        errors['ct'] = _("ConnectTimeout must be >= 1.")
        except ValueError:
            errors['ct'] = _("ConnectTimeout must be numeric.")
        if 'ct' in errors and self.connect_timeout_entry:
            self.connect_timeout_entry.add_css_class("entry-error")
        else:
            if self.connect_timeout_entry:
                self.connect_timeout_entry.remove_css_class("entry-error")

        return errors

    def _clear_field_errors(self):
        if hasattr(self, 'patterns_error_label'):
            self.patterns_error_label.set_visible(False)
        if hasattr(self, 'port_error_label'):
            self.port_error_label.set_visible(False)
        if hasattr(self, 'patterns_entry'):
            self.patterns_entry.remove_css_class("entry-error")
        if hasattr(self, 'port_entry'):
            self.port_entry.remove_css_class("entry-error")
        for action_row in self.custom_options_list:
            if hasattr(action_row, 'key_entry'):
                key_entry = action_row.key_entry
                if key_entry and isinstance(key_entry, Gtk.Entry):
                    key_entry.remove_css_class("entry-error")
        if hasattr(self, 'serveralive_interval_entry') and self.serveralive_interval_entry:
            self.serveralive_interval_entry.remove_css_class("entry-error")
        if hasattr(self, 'serveralive_count_entry') and self.serveralive_count_entry:
            self.serveralive_count_entry.remove_css_class("entry-error")
        if hasattr(self, 'connect_timeout_entry') and self.connect_timeout_entry:
            self.connect_timeout_entry.remove_css_class("entry-error")

    def _combo_select(self, combo_row, values: list[str], value: str):
        try:
            lower_values = [v.lower() for v in values]
            idx = lower_values.index(value.lower()) if value.lower() in lower_values else 0
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
        if self.current_host:
            self.emit("host-save", self.current_host)

    def _on_revert_clicked(self, button):
        """Reverts the current host's changes to its last loaded state by reloading the configuration."""
        if not self.current_host:
            return

        if not hasattr(self, 'original_host_state') or not self.original_host_state:
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

        if self.buffer is not None:
            self.buffer.remove_all_tags(self.buffer.get_start_iter(), self.buffer.get_end_iter())
        self.emit("host-changed", self.current_host)
        self.revert_button.set_sensitive(False)
        if hasattr(self, 'save_button'):
            self.save_button.set_sensitive(False)
        self._show_message(_(f"Reverted changes for {self.current_host.patterns[0]}"))
        self._touched_options.clear()

    def _update_button_sensitivity(self):
        """Updates the sensitivity of save and revert buttons based on dirty state and validity."""
        is_dirty = self.is_host_dirty()
        field_errors = self._collect_field_errors() # This also applies error styling
        is_valid = not bool(field_errors)
        self.save_button.set_sensitive(is_dirty and is_valid)
        self.revert_button.set_sensitive(is_dirty)


    def _on_test_connection(self, button):
        if not self.current_host:
            return
        
        dialog = TestConnectionDialog(parent=self.get_root())
        
        hostname = self.hostname_entry.get_text().strip()
        if not hostname and self.current_host.patterns:
            hostname = self.current_host.patterns[0]  # Fallback to pattern if hostname is empty

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
            "-o", "BatchMode=yes",
            "-o", "NumberOfPasswordPrompts=0",
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

        # Append all other configured options as -o Key=Value so the test reflects the host settings
        special_keys = {
            'Host', 'HostName', 'User', 'Port', 'IdentityFile', 'ProxyJump'
        }

        # Build a dict of current options
        options_dict = {}
        try:
            for opt in self.current_host.options:
                options_dict[opt.key] = opt.value
        except Exception:
            pass

        # Ensure some sensible defaults only if not explicitly set by the user in the editor
        def maybe_add_default(key: str, value: str):
            if key not in options_dict or not (options_dict.get(key) or "").strip():
                command.extend(["-o", f"{key}={value}"])

        # Respect user selections first, then add safe defaults
        for key, value in options_dict.items():
            if key in special_keys:
                continue
            if (value or "").strip():
                command.extend(["-o", f"{key}={value}"])

        # Safe defaults if not set
        maybe_add_default("ConnectTimeout", "8")
        maybe_add_default("StrictHostKeyChecking", "accept-new")
        maybe_add_default("ControlMaster", "no")
        maybe_add_default("ControlPath", "none")
        maybe_add_default("ControlPersist", "no")

        # Target and command
        command += [hostname, "exit"]

        dialog.start_test(command, hostname)
        dialog.present()

    def _sync_fields_from_host(self):
        if not self.current_host:
            return
        self.is_loading = True
        self.patterns_entry.set_text(" ".join(self.current_host.patterns))
        self.hostname_entry.set_text(self.current_host.get_option('HostName') or "")
        self.user_entry.set_text(self.current_host.get_option('User') or "")
        self.port_entry.set_text(self.current_host.get_option('Port') or "")
        self.identity_entry.set_text(self.current_host.get_option('IdentityFile') or "")
        self.forward_agent_switch.set_active((self.current_host.get_option('ForwardAgent') or "").lower() == 'yes')
        self.proxy_jump_entry.set_text(self.current_host.get_option('ProxyJump') or "")
        self.proxy_cmd_entry.set_text(self.current_host.get_option('ProxyCommand') or "")
        self.local_forward_entry.set_text(self.current_host.get_option('LocalForward') or "")
        self.remote_forward_entry.set_text(self.current_host.get_option('RemoteForward') or "")
        # Advanced
        self.compression_switch.set_active((self.current_host.get_option('Compression') or 'no').lower() == 'yes')
        self.serveralive_interval_entry.set_text(self.current_host.get_option('ServerAliveInterval') or "0")
        self.serveralive_count_entry.set_text(self.current_host.get_option('ServerAliveCountMax') or "3")
        self.tcp_keepalive_switch.set_active((self.current_host.get_option('TCPKeepAlive') or 'yes').lower() == 'yes')
        shk2 = (self.current_host.get_option('StrictHostKeyChecking') or 'ask').lower()
        mapping2 = { 'ask': 0, 'yes': 1, 'no': 2 }
        self.strict_host_key_row.set_selected(mapping2.get(shk2, 0))
        self._load_custom_options(self.current_host)
        self.is_loading = False
