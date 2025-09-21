import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, GObject, Adw, Gdk
from gettext import gettext as _

try:
    from ssh_studio.ssh_config_parser import SSHHost, SSHOption
except ImportError:
    from ssh_config_parser import SSHHost, SSHOption


@Gtk.Template(resource_path="/io/github/BuddySirJava/SSH-Studio/ui/host_list.ui")
class HostList(Gtk.Box):

    __gtype_name__ = "HostList"

    list_box = Gtk.Template.Child()
    count_label = Gtk.Template.Child()
    add_bottom_button = Gtk.Template.Child()
    search_button = Gtk.Template.Child()
    search_bar = Gtk.Template.Child()
    search_entry = Gtk.Template.Child()

    __gsignals__ = {
        "host-selected": (GObject.SignalFlags.RUN_LAST, None, (object,)),
        "host-added": (GObject.SignalFlags.RUN_LAST, None, (object,)),
        "host-deleted": (GObject.SignalFlags.RUN_LAST, None, (object,)),
    }

    def __init__(self):
        super().__init__()

        self.hosts = []
        self.filtered_hosts = []
        self.current_filter = ""
        self._selected_host = None

        self._connect_signals()

        self.list_store = Gtk.ListStore(str, str, str, str, str, object)
        if hasattr(self, "tree_view") and self.tree_view is not None:
            self.tree_view.set_model(self.list_store)
            self._setup_columns()
        self._rebuild_listbox_rows()

        self._update_bottom_toolbar_sensitivity()

    def _setup_columns(self):
        def add_text_column(
            title: str,
            col_index: int,
            expand: bool = False,
            min_width: int | None = None,
        ):
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
        if hasattr(self, "tree_view") and self.tree_view is not None:
            selection = self.tree_view.get_selection()
            selection.connect("changed", self._on_selection_changed)
        if hasattr(self, "list_box") and self.list_box is not None:
            self.list_box.connect("row-selected", self._on_row_selected)

        try:
            if self.add_bottom_button:
                self.add_bottom_button.connect("clicked", lambda b: self.add_host())
        except Exception:
            pass

        try:
            if self.search_button:
                self.search_button.connect("clicked", self._on_search_button_clicked)
        except Exception:
            pass

        try:
            if self.search_entry:
                self.search_entry.connect("search-changed", self._on_search_changed)
        except Exception:
            pass

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
                    " ".join(host.patterns)
                    + " "
                    + (host.get_option("HostName") or "")
                    + " "
                    + (host.get_option("User") or "")
                    + " "
                    + (host.get_option("IdentityFile") or "")
                ).lower()

                if self.current_filter in searchable_text:
                    self.filtered_hosts.append(host)

        self._refresh_view()
        self._update_count()

    def _refresh_view(self):
        if hasattr(self, "tree_view") and self.tree_view is not None:
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
            hostname = host.get_option("HostName") or ""
            user = host.get_option("User") or ""
            port = host.get_option("Port") or ""
            identity_file = host.get_option("IdentityFile") or ""

            self.list_store.append(
                [host_patterns, hostname, user, port, identity_file, host]
            )

        if hasattr(self, "list_box") and self.list_box is not None:
            self._rebuild_listbox_rows()
        if previously_selected_host:
            self.select_host(previously_selected_host)

    def _update_count(self):
        total = len(self.hosts)
        filtered = len(self.filtered_hosts)

        if filtered == total:
            self.count_label.set_text(_(f"{total} hosts"))
        else:
            self.count_label.set_text(_(f"{filtered} of {total} hosts"))

    def _on_selection_changed(self, selection):
        model, tree_iter = selection.get_selected()
        if tree_iter:
            host = model.get_value(tree_iter, 5)
            self.emit("host-selected", host)
        self._update_bottom_toolbar_sensitivity()

    def _on_duplicate_host_clicked(self, button, host):
        """Handle duplicate host button click from an ActionRow."""
        self.duplicate_host(host)

    def _on_delete_host_clicked(self, button, host):
        """Handle delete host button click from an ActionRow."""
        self.delete_host(host)

    def add_host(self):
        """Add a new host."""
        new_host = SSHHost(patterns=["new-host"])
        self.emit("host-added", new_host)

        self.filter_hosts(self.current_filter)

        self.select_host(new_host)

    def duplicate_host(self, original_host: SSHHost = None):
        """Duplicate the selected host."""
        if original_host is None:
            original_host = self._get_selected_host()
        if original_host is not None:
            duplicated_host = self._duplicate_host(original_host)

            self.emit("host-added", duplicated_host)

            self.filter_hosts(self.current_filter)

            self.select_host(duplicated_host)

    def delete_host(self, host_to_delete: SSHHost = None):
        """Delete the selected host."""
        if host_to_delete is None:
            host_to_delete = self._get_selected_host()
        if host_to_delete is not None:
            title = _("Delete host?")
            body = _(f"Delete host '{', '.join(host_to_delete.patterns)}'?")
            dialog = Adw.AlertDialog.new(title, body)
            dialog.add_response("cancel", _("Cancel"))
            dialog.add_response("delete", _("Delete"))
            try:
                dialog.set_response_appearance(
                    "delete", Adw.ResponseAppearance.DESTRUCTIVE
                )
                dialog.set_default_response("cancel")
                dialog.set_close_response("cancel")
            except Exception:
                pass

            def on_response(dlg, response):
                if response == "delete":
                    self.emit("host-deleted", host_to_delete)
                    if host_to_delete in self.hosts:
                        self.hosts.remove(host_to_delete)
                    if host_to_delete in self.filtered_hosts:
                        self.filtered_hosts.remove(host_to_delete)
                    self._refresh_view()
                    self._update_count()

            dialog.connect("response", on_response)
            try:
                dialog.present(self.get_root())
            except Exception:
                dialog.present(None)

    def _duplicate_host(self, original_host: SSHHost) -> SSHHost:
        duplicated_host = SSHHost()

        duplicated_host.patterns = [
            f"{pattern}-copy" for pattern in original_host.patterns
        ]

        for option in original_host.options:
            duplicated_option = SSHOption(
                key=option.key, value=option.value, indentation=option.indentation
            )
            duplicated_host.options.append(duplicated_option)

        return duplicated_host

    def select_host(self, host: SSHHost):
        for index, row in enumerate(self.list_store):
            if row[5] == host:
                if hasattr(self, "tree_view") and self.tree_view is not None:
                    tree_iter = self.list_store.iter_nth_child(None, index)
                    if tree_iter is None:
                        return
                    selection = self.tree_view.get_selection()
                    selection.select_iter(tree_iter)
                    path = self.list_store.get_path(tree_iter)
                    if path is not None:
                        self.tree_view.scroll_to_cell(path, None, False, 0, 0)
                elif hasattr(self, "list_box") and self.list_box is not None:
                    row_widget = self.list_box.get_row_at_index(index)
                    if row_widget is not None:
                        self.list_box.select_row(row_widget)
                        try:
                            row_widget.grab_focus()
                        except Exception:
                            pass
                break

    def get_selected_host(self) -> SSHHost | None:
        """Get the currently selected host."""
        if hasattr(self, "tree_view") and self.tree_view is not None:
            selection = self.tree_view.get_selection()
            model, tree_iter = selection.get_selected()
            if tree_iter is not None:
                return model[tree_iter][5]
        elif hasattr(self, "list_box") and self.list_box is not None:
            selected_row = self.list_box.get_selected_row()
            if selected_row is not None and hasattr(selected_row, "_host_ref"):
                return selected_row._host_ref
        return None

    def navigate_with_key(self, keyval, state):
        """Handle keyboard navigation in the host list."""
        if not self.filtered_hosts:
            return False

        current_index = self._get_current_selection_index()
        if current_index is None:
            current_index = 0

        new_index = current_index

        if keyval == Gdk.KEY_Up:
            new_index = max(0, current_index - 1)
        elif keyval == Gdk.KEY_Down:
            new_index = min(len(self.filtered_hosts) - 1, current_index + 1)
        elif keyval == Gdk.KEY_Home:
            new_index = 0
        elif keyval == Gdk.KEY_End:
            new_index = len(self.filtered_hosts) - 1
        elif keyval == Gdk.KEY_Page_Up:
            new_index = max(0, current_index - 10)
        elif keyval == Gdk.KEY_Page_Down:
            new_index = min(len(self.filtered_hosts) - 1, current_index + 10)
        else:
            return False

        if new_index != current_index and new_index < len(self.filtered_hosts):
            host = self.filtered_hosts[new_index]
            self.select_host(host)
            return True

        return False

    def _get_current_selection_index(self) -> int | None:
        """Get the index of the currently selected host in filtered_hosts."""
        selected_host = self.get_selected_host()
        if selected_host is None:
            return None

        try:
            return self.filtered_hosts.index(selected_host)
        except ValueError:
            return None

    def _rebuild_listbox_rows(self):
        if not hasattr(self, "list_box") or self.list_box is None:
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
            secondary = (
                f"{user}@{hostname}" if (hostname or user) else (hostname or patterns)
            )
            action_row.set_subtitle(secondary)

            action_row.set_selectable(True)
            action_row.set_activatable(True)
            action_row._host_ref = host

            button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

            duplicate_button = Gtk.Button()
            duplicate_button.set_icon_name("edit-copy-symbolic")
            duplicate_button.set_tooltip_text(_("Duplicate Host"))
            duplicate_button.add_css_class("flat")
            duplicate_button.set_visible(False)
            duplicate_button.connect("clicked", self._on_duplicate_host_clicked, host)

            delete_button = Gtk.Button()
            delete_button.set_icon_name("edit-delete-symbolic")
            delete_button.set_tooltip_text(_("Delete Host"))
            delete_button.add_css_class("flat")
            delete_button.add_css_class("destructive-action")
            delete_button.set_visible(False)
            delete_button.connect("clicked", self._on_delete_host_clicked, host)

            button_box.append(duplicate_button)
            button_box.append(delete_button)

            action_row._duplicate_button = duplicate_button
            action_row._delete_button = delete_button

            action_row.add_suffix(button_box)
            self.list_box.append(action_row)

    def _on_row_selected(self, listbox, row):
        self._hide_all_row_buttons()

        if row is None:
            self._update_bottom_toolbar_sensitivity()
            return
        host = getattr(row, "_host_ref", None)
        if host is not None:
            self._selected_host = host
            self.emit("host-selected", host)
            self._show_row_buttons(row)
        self._update_bottom_toolbar_sensitivity()

    def _hide_all_row_buttons(self):
        """Hide buttons on all ActionRows."""
        if not hasattr(self, "list_box") or self.list_box is None:
            return
        child = self.list_box.get_first_child()
        while child is not None:
            if hasattr(child, "_duplicate_button") and hasattr(child, "_delete_button"):
                child._duplicate_button.set_visible(False)
                child._delete_button.set_visible(False)
            child = child.get_next_sibling()

    def _show_row_buttons(self, row):
        """Show buttons on the specified ActionRow."""
        if hasattr(row, "_duplicate_button") and hasattr(row, "_delete_button"):
            row._duplicate_button.set_visible(True)
            row._delete_button.set_visible(True)

    def _get_selected_host(self):
        if hasattr(self, "list_box") and self.list_box is not None:
            try:
                row = self.list_box.get_selected_row()
            except Exception:
                row = None
            if row is not None:
                host = getattr(row, "_host_ref", None)
                if host is not None:
                    return host
        if hasattr(self, "tree_view") and self.tree_view is not None:
            selection = self.tree_view.get_selection()
            model, tree_iter = selection.get_selected()
            if tree_iter:
                return model.get_value(tree_iter, 5)
        return self._selected_host

    def _update_bottom_toolbar_sensitivity(self):
        pass

    def _on_search_button_clicked(self, button):
        """Toggle search bar visibility when search button is clicked."""
        if self.search_bar:
            is_visible = self.search_bar.get_visible()
            self.search_bar.set_visible(not is_visible)
            
            if not is_visible:
                if self.search_entry:
                    self.search_entry.grab_focus()
            else:
                if self.search_entry:
                    self.search_entry.set_text("")
                    self.filter_hosts("")

    def _on_search_changed(self, search_bar, query):
        """Handle search query changes."""
        self.filter_hosts(query)
