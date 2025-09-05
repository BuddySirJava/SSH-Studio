import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, GObject, Pango, Adw
from gettext import gettext as _

try:
	from ssh_config_studio.ssh_config_parser import SSHHost, SSHOption
except ImportError:
	from ssh_config_parser import SSHHost, SSHOption

@Gtk.Template(resource_path="/com/sshconfigstudio/app/ui/host_list.ui")
class HostList(Gtk.Box):
    
    __gtype_name__ = "HostList"

    list_box = Gtk.Template.Child()

    __gsignals__ = {
        'host-selected': (GObject.SignalFlags.RUN_LAST, None, (object,)),
        'host-added': (GObject.SignalFlags.RUN_LAST, None, (object,)),
        'host-deleted': (GObject.SignalFlags.RUN_LAST, None, (object,))
    }
    
    def __init__(self):
        super().__init__()
        
        self.hosts = []
        self.filtered_hosts = []
        self.current_filter = ""
        self._selected_host = None
        self._suppress_selection_emit = False
        
        self._connect_signals()
        
        self.list_store = Gtk.ListStore(str, str, str, str, str, object)
        if hasattr(self, 'tree_view') and self.tree_view is not None:
            self.tree_view.set_model(self.list_store)
            self._setup_columns()
        self._rebuild_listbox_rows()
    
    def _setup_columns(self):
        def add_text_column(title: str, col_index: int, expand: bool = False, min_width: int | None = None):
            renderer = Gtk.CellRendererText()
            renderer.set_property("ypad", 6)
            renderer.set_property("xpad", 8)
            column = Gtk.TreeViewColumn(title, renderer, text=col_index)
            if expand:
                column.set_expand(True)
            if min_width is not None:
                column.set_min_width(min_width)
            self.tree_view.append_column(column)

        add_text_column(_("Host"), 0, True, 120)
        add_text_column(_("HostName"), 1, True, 150)
        add_text_column(_("User"), 2, False, 80)
        add_text_column(_("Port"), 3, False, 60)
        add_text_column(_("Identity"), 4, True, 120)

    def _connect_signals(self):
        if hasattr(self, 'tree_view') and self.tree_view is not None:
            selection = self.tree_view.get_selection()
            selection.connect("changed", self._on_selection_changed)
        if hasattr(self, 'list_box') and self.list_box is not None:
            self.list_box.connect("row-selected", self._on_row_selected)

    def load_hosts(self, hosts: list):
        self.hosts = hosts
        self.filtered_hosts = hosts.copy()
        self._refresh_view()
        self._update_count()

    def filter_hosts(self, query: str):
        self.current_filter = query.lower()

        if not query:
            self.filtered_hosts = self.hosts.copy()
        else:
            self.filtered_hosts = []
            for host in self.hosts:
                searchable_text = (
                    " ".join(host.patterns) + " " +
                    (host.get_option('HostName') or "") + " " +
                    (host.get_option('User') or "") + " " +
                    (host.get_option('IdentityFile') or "")
                ).lower()

                if self.current_filter in searchable_text:
                    self.filtered_hosts.append(host)

        self._refresh_view()
        self._update_count()

    def _refresh_view(self):
        if hasattr(self, 'tree_view') and self.tree_view is not None:
            selection = self.tree_view.get_selection()
            model, selected_iter = selection.get_selected()
        else:
            model = self.list_store
            selected_iter = None
        previously_selected_host = None
        if selected_iter:
            previously_selected_host = model.get_value(selected_iter, 5)

        self.list_store.clear()

        for host in self.filtered_hosts:
            host_patterns = ", ".join(host.patterns)
            hostname = host.get_option('HostName') or ""
            user = host.get_option('User') or ""
            port = host.get_option('Port') or ""
            identity_file = host.get_option('IdentityFile') or ""

            self.list_store.append([
                host_patterns,
                hostname,
                user,
                port,
                identity_file,
                host
            ])

        if hasattr(self, 'list_box') and self.list_box is not None:
            self._rebuild_listbox_rows()
        if previously_selected_host:
            self.select_host(previously_selected_host)

    def _update_count(self):
        total = len(self.hosts)
        filtered = len(self.filtered_hosts)
        
        if hasattr(self, 'count_label') and self.count_label is not None:
            if filtered == total:
                try:
                    self.count_label.set_text(_(f"{total} hosts"))
                except Exception:
                    pass
            else:
                try:
                    self.count_label.set_text(_(f"{filtered} of {total} hosts"))
                except Exception:
                    pass

    def _on_selection_changed(self, selection):
        model, tree_iter = selection.get_selected()
        if tree_iter:
            host = model.get_value(tree_iter, 5)
            self.emit("host-selected", host)

    def add_host(self):
        """Add a new host."""
        new_host = SSHHost(patterns=["new-host"])
        self.emit("host-added", new_host)

        self.filter_hosts(self.current_filter)

        self.select_host(new_host)

    def duplicate_host(self):
        """Duplicate the selected host."""
        original_host = self._get_selected_host()
        if original_host is not None:
            duplicated_host = self._duplicate_host(original_host)

            self.emit("host-added", duplicated_host)

            self.filter_hosts(self.current_filter)

            self.select_host(duplicated_host)

    def delete_host(self):
        """Delete the selected host."""
        host = self._get_selected_host()
        if host is not None:

            dialog = Gtk.MessageDialog(
                transient_for=self.get_root(),
                message_type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.NONE,
                text=_(f"Delete host '{', '.join(host.patterns)}'?"),
            )
            dialog.add_buttons(
                _("No"), Gtk.ResponseType.NO,
                _("Yes"), Gtk.ResponseType.YES,
            )

            def on_response(dlg, response_id):
                if response_id == Gtk.ResponseType.YES:
                    self.emit("host-deleted", host)
                    if host in self.hosts:
                        self.hosts.remove(host)
                    if host in self.filtered_hosts:
                        self.filtered_hosts.remove(host)
                    self._refresh_view()
                    self._update_count()
                dlg.destroy()

            dialog.connect("response", on_response)
            dialog.present()

    def _duplicate_host(self, original_host: SSHHost) -> SSHHost:
        duplicated_host = SSHHost()

        duplicated_host.patterns = [f"{pattern}-copy" for pattern in original_host.patterns]

        for option in original_host.options:
            duplicated_option = SSHOption(
                key=option.key,
                value=option.value,
                indentation=option.indentation
            )
            duplicated_host.options.append(duplicated_option)

        return duplicated_host


    def select_host(self, host: SSHHost):
        for index, row in enumerate(self.list_store):
            if row[5] == host:
                if hasattr(self, 'tree_view') and self.tree_view is not None:
                    tree_iter = self.list_store.iter_nth_child(None, index)
                    if tree_iter is None:
                        return
                    selection = self.tree_view.get_selection()
                    self._suppress_selection_emit = True
                    selection.select_iter(tree_iter)
                    path = self.list_store.get_path(tree_iter)
                    if path is not None:
                        self.tree_view.scroll_to_cell(path, None, False, 0, 0)
                elif hasattr(self, 'list_box') and self.list_box is not None:
                    row_widget = self.list_box.get_row_at_index(index)
                    if row_widget is not None:
                        self._suppress_selection_emit = True
                        self.list_box.select_row(row_widget)
                        try:
                            row_widget.grab_focus()
                        except Exception:
                            pass
                break

    def _rebuild_listbox_rows(self):
        if not hasattr(self, 'list_box') or self.list_box is None:
            return
        while (child := self.list_box.get_first_child()) is not None:
            self.list_box.remove(child)

        for row in self.list_store:
            host = row[5]
            patterns = row[0]
            hostname = row[1]
            user = row[2]

            action_row = Adw.ActionRow()
            action_row.set_title(patterns)
            try:
                subtitle_text = f"{user}@{hostname}" if (hostname or user) else (hostname or patterns)
                action_row.set_subtitle(subtitle_text)
            except Exception:
                pass
            action_row.set_activatable(True)
            try:
                action_row.set_selectable(True)
            except Exception:
                pass
            action_row._host_ref = host
            try:
                dup_btn = Gtk.Button()
                dup_btn.set_icon_name("edit-copy-symbolic")
                dup_btn.add_css_class("flat")
                def on_dup_clicked(btn, h=host):
                    if h in self.hosts:
                        duplicated_host = self._duplicate_host(h)
                        self.emit("host-added", duplicated_host)
                        self.filter_hosts(self.current_filter)
                        self.select_host(duplicated_host)
                dup_btn.connect("clicked", on_dup_clicked)
                action_row.add_suffix(dup_btn)
            except Exception:
                pass

            try:
                del_btn = Gtk.Button()
                del_btn.set_icon_name("edit-delete-symbolic")
                del_btn.add_css_class("destructive-action")
                del_btn.add_css_class("flat")
                def on_del_clicked(btn, h=host):
                    self._confirm_and_delete(h)
                del_btn.connect("clicked", on_del_clicked)
                action_row.add_suffix(del_btn)
            except Exception:
                pass

            self.list_box.append(action_row)

    def _on_row_selected(self, listbox, row):
        if row is None:
            return
        host = getattr(row, "_host_ref", None)
        if host is not None:
            self.emit("host-selected", host)

    def _confirm_and_delete(self, host):
        if host is None:
            return
        dialog = Gtk.MessageDialog(
            transient_for=self.get_root(),
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.NONE,
            text=_(f"Delete host '{', '.join(host.patterns)}'?")
        )
        dialog.add_buttons(
            _("No"), Gtk.ResponseType.NO,
            _("Yes"), Gtk.ResponseType.YES,
        )

        def on_response(dlg, response_id):
            if response_id == Gtk.ResponseType.YES:
                self.emit("host-deleted", host)
                if host in self.hosts:
                    self.hosts.remove(host)
                if host in self.filtered_hosts:
                    self.filtered_hosts.remove(host)
                self._refresh_view()
                self._update_count()
            dlg.destroy()

        dialog.connect("response", on_response)
        dialog.present()


    def _get_selected_host(self):
        if hasattr(self, 'list_box') and self.list_box is not None:
            try:
                row = self.list_box.get_selected_row()
            except Exception:
                row = None
            if row is not None:
                host = getattr(row, "_host_ref", None)
                if host is not None:
                    return host
        if hasattr(self, 'tree_view') and self.tree_view is not None:
            selection = self.tree_view.get_selection()
            model, tree_iter = selection.get_selected()
            if tree_iter:
                return model.get_value(tree_iter, 5)
        return self._selected_host
