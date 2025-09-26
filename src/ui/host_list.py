import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, GObject, Adw, Gdk, GLib
from gettext import gettext as _

try:
    from ssh_studio.ssh_config_parser import SSHHost, SSHOption
except ImportError:
    from ssh_config_parser import SSHHost, SSHOption


@Gtk.Template(resource_path="/io/github/BuddySirJava/SSH-Studio/ui/host_list.ui")
class HostList(Gtk.Box):

    __gtype_name__ = "HostList"

    list_box = Gtk.Template.Child()
    host_stack = Gtk.Template.Child()
    empty_page = Gtk.Template.Child()
    count_label = Gtk.Template.Child()
    add_bottom_button = Gtk.Template.Child()
    search_button = Gtk.Template.Child()
    undo_button = Gtk.Template.Child()
    search_bar = Gtk.Template.Child()
    search_entry = Gtk.Template.Child()

    __gsignals__ = {
        "host-selected": (GObject.SignalFlags.RUN_LAST, None, (object,)),
        "host-added": (GObject.SignalFlags.RUN_LAST, None, (object,)),
        "host-deleted": (GObject.SignalFlags.RUN_LAST, None, (object,)),
        "hosts-reordered": (GObject.SignalFlags.RUN_LAST, None, (object,)),
        "undo-clicked": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self):
        super().__init__()

        self.hosts = []
        self.filtered_hosts = []
        self.current_filter = ""
        self._selected_host = None
        self._dragging_host = None
        self._order_before_drag = None
        self._dnd_hover_row = None

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
                drop_target = Gtk.DropTarget.new(
                    GObject.TYPE_STRING, Gdk.DragAction.MOVE
                )
                drop_target.connect("drop", self._on_listbox_drop)
                try:
                    drop_target.connect("motion", self._on_listbox_motion)
                except Exception:
                    pass
                try:
                    drop_target.connect("accept", lambda *args: True)
                except Exception:
                    pass
                self.list_box.add_controller(drop_target)
            except Exception:
                pass

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
            if self.undo_button:
                self.undo_button.connect(
                    "clicked", lambda *_: self.emit("undo-clicked")
                )
                self.undo_button.set_sensitive(False)
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
        self._update_empty_state()

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
        self._update_empty_state()

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
        self._update_empty_state()

    def _update_empty_state(self):
        try:
            has_hosts = bool(self.hosts)
            if self.empty_page:
                self.empty_page.set_visible(not has_hosts)
            if self.list_box:
                self.list_box.set_visible(has_hosts)
        except Exception:
            pass

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

            try:
                button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            except Exception:
                button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

            grip_button = Gtk.Button()
            try:
                grip_button.set_icon_name("list-drag-handle-symbolic")
            except Exception:
                grip_button.set_icon_name("open-menu-symbolic")
            grip_button.set_tooltip_text(_("Drag to reorder"))
            grip_button.add_css_class("flat")
            try:
                grip_button.set_visible(False)
            except Exception:
                pass

            try:
                drag_source = Gtk.DragSource()
                drag_source.set_actions(Gdk.DragAction.MOVE)

                def _on_drag_begin(
                    src,
                    drag,
                    host_ref=host,
                    patterns_text=patterns,
                    secondary_text=secondary,
                ):
                    self._dragging_host = host_ref
                    self._order_before_drag = list(self.hosts)
                    try:
                        icon = Gtk.DragIcon.get_for_drag(drag)
                        preview = Gtk.Box(
                            orientation=Gtk.Orientation.VERTICAL, spacing=2
                        )
                        lbl_title = Gtk.Label(label=patterns_text)
                        lbl_title.set_xalign(0)
                        try:
                            lbl_title.add_css_class("title-4")
                        except Exception:
                            pass
                        lbl_sub = Gtk.Label(label=secondary_text)
                        lbl_sub.set_xalign(0)
                        try:
                            lbl_sub.add_css_class("dim-label")
                        except Exception:
                            pass
                        preview.append(lbl_title)
                        preview.append(lbl_sub)
                        preview.set_margin_start(8)
                        preview.set_margin_end(8)
                        preview.set_margin_top(6)
                        preview.set_margin_bottom(6)
                        try:
                            preview.add_css_class("card")
                        except Exception:
                            pass
                        icon.set_child(preview)
                        try:
                            icon.set_hotspot(8, 8)
                        except Exception:
                            pass
                    except Exception:
                        pass

                def _on_drag_end(src, drag, delete_data):
                    self._dragging_host = None

                def _on_prepare(src, x, y, host_ref=host):
                    try:
                        alias = ", ".join(host_ref.patterns) or "host"
                        return Gdk.ContentProvider.new_for_value(alias)
                    except Exception:
                        try:
                            bytes_utf8 = GLib.Bytes.new(
                                (", ".join(host_ref.patterns) or "host").encode("utf-8")
                            )
                            return Gdk.ContentProvider.new_for_bytes(
                                "text/plain;charset=utf-8", bytes_utf8
                            )
                        except Exception:
                            return None

                drag_source.connect("drag-begin", _on_drag_begin)
                drag_source.connect("drag-end", _on_drag_end)
                drag_source.connect("prepare", _on_prepare)
                grip_button.add_controller(drag_source)
            except Exception:
                pass

            try:
                action_row.add_prefix(grip_button)
            except Exception:
                pass
            action_row._grip_button = grip_button

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

    def _on_listbox_drop(self, drop_target, value, x, y):
        source_host = self._dragging_host
        if source_host is None:
            return False

        try:
            y_int = int(y)
            target_row = None
            try:
                target_row = self.list_box.get_row_at_y(y_int)
            except Exception:
                target_row = None

            if target_row is not None:
                row_idx = self._get_row_index_from_widget(target_row)
                alloc = target_row.get_allocation()
                row_top = getattr(alloc, "y", 0)
                row_height = getattr(alloc, "height", 0)
                after = (y_int - row_top) >= int(row_height * 0.55)
                dest_index_filtered = row_idx + (1 if after else 0)
            else:
                dest_index_filtered = self._get_insert_index_from_y(y_int)

            if dest_index_filtered >= len(self.filtered_hosts):
                dest_index_base = len(self.hosts)
            else:
                dest_host_at_pos = self.filtered_hosts[dest_index_filtered]
                dest_index_base = self.hosts.index(dest_host_at_pos)

            if source_host not in self.hosts:
                return False
            source_index_base = self.hosts.index(source_host)

            if (
                dest_index_base == source_index_base
                or dest_index_base == source_index_base + 1
            ):
                return True

            host_obj = self.hosts.pop(source_index_base)
            if dest_index_base > source_index_base:
                dest_index_base -= 1
            self.hosts.insert(dest_index_base, host_obj)

            self.filter_hosts(self.current_filter)
            try:
                self.select_host(source_host)
            except Exception:
                pass
            self._update_count()
            prev = self._order_before_drag or []
            self._order_before_drag = None
            self.emit("hosts-reordered", prev)
            return True
        except Exception:
            return False

    def _get_row_index_from_widget(self, row_widget) -> int:
        try:
            idx = 0
            child = self.list_box.get_first_child()
            while child is not None:
                if child is row_widget:
                    return idx
                idx += 1
                child = child.get_next_sibling()
            return idx
        except Exception:
            return 0

    def _on_listbox_motion(self, drop_target, x, y):
        try:
            scroller = self._find_scroller()
            if not scroller:
                return Gdk.DragAction.MOVE
            vadj = scroller.get_vadjustment()
            if not vadj:
                return Gdk.DragAction.MOVE
            height = scroller.get_allocated_height()
            edge = 28
            step = max(
                12,
                (
                    int(vadj.get_page_increment() * 0.15)
                    if hasattr(vadj, "get_page_increment")
                    else 20
                ),
            )
            y_int = int(y)
            new_val = vadj.get_value()
            if y_int < edge:
                new_val = max(vadj.get_lower(), vadj.get_value() - step)
            elif y_int > height - edge:
                upper = vadj.get_upper() - vadj.get_page_size()
                new_val = min(upper, vadj.get_value() + step)
            if new_val != vadj.get_value():
                vadj.set_value(new_val)
        except Exception:
            pass
        return Gdk.DragAction.MOVE

    def _find_scroller(self):
        try:
            w = self.list_box
            while w is not None and not isinstance(w, Gtk.ScrolledWindow):
                w = w.get_parent()
            return w
        except Exception:
            return None

    def _get_insert_index_from_y(self, y: int) -> int:
        """Return the filtered index at which to insert based on y position.
        Inserts before the row whose midpoint is below y; append at end otherwise.
        """
        try:
            index = 0
            child = self.list_box.get_first_child()
            while child is not None:
                alloc = child.get_allocation()
                row_top = getattr(alloc, "y", 0)
                row_height = getattr(alloc, "height", 0)
                row_mid = row_top + (row_height // 2)
                if y < row_mid:
                    return index
                index += 1
                child = child.get_next_sibling()
            return index
        except Exception:
            return len(self.filtered_hosts)

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
            if hasattr(child, "_grip_button"):
                try:
                    child._grip_button.set_visible(False)
                except Exception:
                    pass
            child = child.get_next_sibling()

    def _show_row_buttons(self, row):
        """Show buttons on the specified ActionRow."""
        if hasattr(row, "_duplicate_button") and hasattr(row, "_delete_button"):
            row._duplicate_button.set_visible(True)
            row._delete_button.set_visible(True)
        if hasattr(row, "_grip_button"):
            try:
                row._grip_button.set_visible(True)
            except Exception:
                pass

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

    def set_undo_enabled(self, enabled: bool):
        """Enable or disable the header undo button."""
        try:
            if self.undo_button:
                self.undo_button.set_sensitive(bool(enabled))
        except Exception:
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

    def _on_search_changed(self, entry):
        """Handle search query changes."""
        try:
            text = entry.get_text()
        except Exception:
            text = ""
        self.filter_hosts(text)
