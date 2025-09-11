import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gio, GLib, GObject, Adw
from gettext import gettext as _
from pathlib import Path
import subprocess


@Gtk.Template(resource_path="/com/sshstudio/app/ui/ssh_key_manager_dialog.ui")
class SSHKeyManagerDialog(Adw.Dialog):
    __gtype_name__ = "SSHKeyManagerDialog"

    toast_overlay = Gtk.Template.Child()
    private_list = Gtk.Template.Child()
    public_list = Gtk.Template.Child()
    generate_button = Gtk.Template.Child()
    import_button = Gtk.Template.Child()
    copy_pub_button = Gtk.Template.Child()
    reveal_button = Gtk.Template.Child()
    delete_button = Gtk.Template.Child()

    def __init__(self, parent):
        super().__init__()
        self._home_ssh = Path.home() / ".ssh"
        self._connect_signals()
        self._load_keys()

    def _connect_signals(self):
        self.generate_button.connect("clicked", self._on_generate_clicked)
        self.import_button.connect("clicked", self._on_import_clicked)
        self.copy_pub_button.connect("clicked", self._on_copy_public_clicked)
        self.reveal_button.connect("clicked", self._on_reveal_clicked)
        self.delete_button.connect("clicked", self._on_delete_clicked)
        self.private_list.connect("row-selected", self._on_row_selected)
        self.public_list.connect("row-selected", self._on_row_selected)

    def _load_keys(self):
        for lst in (self.private_list, self.public_list):
            row = lst.get_first_child()
            while row is not None:
                next_row = row.get_next_sibling()
                lst.remove(row)
                row = next_row

        priv_keys, pub_keys = self._discover_keys_split()
        for key in priv_keys:
            row = self._create_row_for_key(key)
            self.private_list.append(row)
        for key in pub_keys:
            row = self._create_row_for_key(key)
            self.public_list.append(row)
        self._update_buttons_sensitivity()

    def _discover_keys_split(self):
        private_keys = []
        public_keys = []
        try:
            if self._home_ssh.exists():
                for path in sorted(self._home_ssh.iterdir()):
                    if not path.is_file():
                        continue
                    name = path.name
                    if name in {"known_hosts", "config", "authorized_keys"}:
                        continue
                    if name.endswith(".pub"):
                        public_keys.append(
                            {
                                "name": name,
                                "path": str(path),
                                "pub": None,
                            }
                        )
                    else:
                        if path.suffix == "":
                            pub_path = path.with_name(name + ".pub")
                            private_keys.append(
                                {
                                    "name": name,
                                    "path": str(path),
                                    "pub": str(pub_path) if pub_path.exists() else None,
                                }
                            )
        except Exception:
            pass
        return private_keys, public_keys

    def _create_row_for_key(self, key_info):
        box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            margin_start=12,
            margin_end=12,
            margin_top=8,
            margin_bottom=8,
        )
        label = Gtk.Label(label=key_info["name"], halign=Gtk.Align.START, hexpand=True)
        sub = Gtk.Label(label=key_info["path"], halign=Gtk.Align.END)
        sub.get_style_context().add_class("dim-label")
        box.append(label)
        box.append(sub)
        row = Gtk.ListBoxRow()
        row.set_child(box)
        row.key_info = key_info
        return row

    def _get_selected_key(self):
        row = (
            self.private_list.get_selected_row() or self.public_list.get_selected_row()
        )
        return getattr(row, "key_info", None) if row else None

    def _on_row_selected(self, listbox, row):
        self._update_buttons_sensitivity()

    def _update_buttons_sensitivity(self):
        has_sel = self._get_selected_key() is not None
        for btn in (self.copy_pub_button, self.reveal_button, self.delete_button):
            try:
                btn.set_sensitive(has_sel)
            except Exception:
                pass

    def _on_generate_clicked(self, button):
        from .generate_key_dialog import GenerateKeyDialog

        dlg = GenerateKeyDialog(self)

        def on_generate(*_):
            opts = dlg.get_options()
            dlg.close()
            self._generate_key_with_options(opts)

        dlg.generate_btn.connect("clicked", on_generate)
        dlg.present(self)

    def _on_import_clicked(self, button):
        dialog = Gtk.FileChooserNative.new(
            title=_("Import Private Key"),
            parent=self.get_root(),
            action=Gtk.FileChooserAction.OPEN,
            accept_label=_("Import"),
            cancel_label=_("Cancel"),
        )

        def on_response(dlg, response_id):
            if response_id == Gtk.ResponseType.ACCEPT:
                file = dlg.get_file()
                if file:
                    src = Path(file.get_path())
                    try:
                        dst = self._home_ssh / src.name
                        self._home_ssh.mkdir(parents=True, exist_ok=True)
                        data = src.read_bytes()
                        dst.write_bytes(data)
                        try:
                            dst.chmod(0o600)
                        except Exception:
                            pass
                        self._show_toast(_("Key imported"))
                        self._load_keys()
                    except Exception as e:
                        self._show_toast(_(f"Failed to import key: {e}"))
            dlg.destroy()

        dialog.connect("response", on_response)
        dialog.show()

    def _on_copy_public_clicked(self, button):
        key = self._get_selected_key()
        if not key:
            return
        pub_path = Path(key.get("pub") or "")
        if not pub_path.exists():
            self._show_toast(_("No public key found; generate with ssh-keygen -y"))
            return
        try:
            text = pub_path.read_text()
            display = Gtk.Display.get_default()
            clipboard = display.get_clipboard()
            clipboard.set(text)
            self._show_toast(_("Public key copied"))
        except Exception as e:
            self._show_toast(_(f"Failed to copy: {e}"))

    def _on_reveal_clicked(self, button):
        key = self._get_selected_key()
        if not key:
            return
        try:
            Gio.AppInfo.launch_default_for_uri(f"file://{key['path']}")
        except Exception as e:
            self._show_toast(_(f"Failed to reveal: {e}"))

    def _on_delete_clicked(self, button):
        key = self._get_selected_key()
        if not key:
            return
        dialog = Gtk.MessageDialog(
            transient_for=self.get_root(),
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=_("Delete key?"),
            secondary_text=_(
                "This will permanently delete the selected private key (and public key if present)."
            ),
        )

        def on_resp(dlg, resp):
            if resp == Gtk.ResponseType.OK:
                try:
                    Path(key["path"]).unlink(missing_ok=True)
                    if key.get("pub"):
                        Path(key["pub"]).unlink(missing_ok=True)
                    self._show_toast(_("Key deleted"))
                    self._load_keys()
                except Exception as e:
                    self._show_toast(_(f"Failed to delete: {e}"))
            dlg.destroy()

        dialog.connect("response", on_resp)
        dialog.present()

    def _generate_key_with_options(self, opts: dict):
        try:
            self._home_ssh.mkdir(parents=True, exist_ok=True)
            name = opts.get("name") or "id_ed25519"
            base_name = name
            j = 0
            while (self._home_ssh / name).exists():
                j += 1
                name = f"{base_name}_{j}"
            key_path = self._home_ssh / name
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
            self._show_toast(_("Key generated"))
            self._load_keys()
        except FileNotFoundError:
            self._show_toast(_("ssh-keygen not found"))
        except subprocess.CalledProcessError as e:
            self._show_toast(_(f"Keygen failed: {e}"))
        except Exception as e:
            self._show_toast(_(f"Failed to generate key: {e}"))

    def _show_toast(self, message: str):
        try:
            toast = Adw.Toast.new(message)
            self.toast_overlay.add_toast(toast)
        except Exception:
            pass
