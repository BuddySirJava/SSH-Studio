#!/usr/bin/env python3
"""SSH-Studio: Main Application Entry Point."""

import sys
import gi
import logging
from gettext import gettext as _
import gettext

import os

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gio, GLib, Gdk, Adw

try:
    from ssh_studio.ssh_config_parser import SSHConfigParser
except ImportError:
    from ssh_config_parser import SSHConfigParser

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
if os.getenv("FLATPAK_ID"):
    logging.getLogger().setLevel(logging.INFO)


class SSHConfigStudioApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="io.github.BuddySirJava.SSH-Studio", flags=Gio.ApplicationFlags.FLAGS_NONE
        )

        self.parser = None
        self.main_window = None

    def do_activate(self):
        try:
            from ssh_studio.ui.main_window import MainWindow
        except ImportError:
            from ui.main_window import MainWindow

        if not self.main_window:
            self.main_window = MainWindow(self)
            self.main_window.present()
        else:
            self.main_window.present()

    def do_startup(self):
        Adw.Application.do_startup(self)

        try:
            # Prefer system install locale dir, fallback to user data dir
            system_locale_dir = (
                os.path.join(get_option := getattr(GLib, "get_user_data_dir"), "locale")
                if False
                else "/app/share/locale"
            )
            gettext.bindtextdomain("ssh-studio", system_locale_dir)
            gettext.textdomain("ssh-studio")
        except Exception:
            try:
                locale_dir = os.path.join(GLib.get_user_data_dir(), "locale")
                gettext.bindtextdomain("ssh-studio", locale_dir)
                gettext.textdomain("ssh-studio")
            except Exception:
                pass

        if os.getenv("FLATPAK_ID"):
            try:
                resource = Gio.Resource.load(
                    "/app/share/io.github.BuddySirJava.SSH-Studio/ssh-studio-resources.gresource"
                )
                Gio.resources_register(resource)
                logging.info("Registered GResource from Flatpak install directory")
            except Exception:
                pass
        else:
            resource_candidates = [
                os.path.join(
                    GLib.get_user_data_dir(),
                    "io.github.BuddySirJava.SSH-Studio",
                    "ssh-studio-resources.gresource",
                ),
                os.path.join(
                    GLib.get_user_data_dir(), "ssh-studio-resources.gresource"
                ),
                "/app/share/io.github.BuddySirJava.SSH-Studio/ssh-studio-resources.gresource",
                "/app/share/ssh-studio-resources.gresource",
                os.path.join(
                    GLib.get_home_dir(),
                    ".local",
                    "share",
                    "io.github.BuddySirJava.SSH-Studio",
                    "ssh-studio-resources.gresource",
                ),
                "data/ssh-studio-resources.gresource",
            ]
            for candidate in resource_candidates:
                try:
                    if os.path.exists(candidate):
                        resource = Gio.Resource.load(candidate)
                        Gio.resources_register(resource)
                        logging.info(f"Registered GResource from: {candidate}")
                        break
                except Exception:
                    continue

        self._load_css_styles()
        try:
            Gtk.IconTheme.get_for_display(Gtk.Display.get_default()).add_resource_path(
                "/io/github/BuddySirJava/SSH-Studio/icons"
            )
        except Exception:
            pass
        self._add_actions()

        self.parser = SSHConfigParser()
        GLib.idle_add(self._parse_config_async)

    def _parse_config_async(self):
        try:
            if self.parser is not None:
                self.parser.parse()
        except Exception as e:
            logging.error(f"Failed to initialize SSH config parser: {e}")
            self._show_error_dialog(_("Failed to load SSH config"), str(e))
        return False

    def _add_actions(self):
        search_action = Gio.SimpleAction.new("search", None)
        search_action.connect("activate", self._on_search_action)
        self.add_action(search_action)

        add_host_action = Gio.SimpleAction.new("add-host", None)
        add_host_action.connect("activate", self._on_add_host_action)
        self.add_action(add_host_action)

        reload_action = Gio.SimpleAction.new("reload", None)
        reload_action.connect("activate", self._on_reload_action)
        self.add_action(reload_action)

    def _on_search_action(self, action, param):
        if self.main_window:
            self.main_window._toggle_search()

    def _on_add_host_action(self, action, param):
        if self.main_window and self.main_window.host_list:
            self.main_window.host_list.add_host()

    def _on_reload_action(self, action, param):
        if self.main_window:
            self.main_window.reload_config()

    def _load_css_styles(self):
        try:
            if os.getenv("FLATPAK_ID"):  # Flatpak fast path for CSS
                css_provider = Gtk.CssProvider()
                css_provider.load_from_resource("/io/github/BuddySirJava/SSH-Studio/ssh-studio.css")
                Gtk.StyleContext.add_provider_for_display(
                    Gdk.Display.get_default(),
                    css_provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                )
                logging.info("Loaded CSS styles from GResource bundle (Flatpak)")
                return
            else:  # Existing fallback logic for non-Flatpak
                try:
                    css_provider = Gtk.CssProvider()
                    css_provider.load_from_resource("/io/github/BuddySirJava/SSH-Studio/ssh-studio.css")
                    Gtk.StyleContext.add_provider_for_display(
                        Gdk.Display.get_default(),
                        css_provider,
                        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                    )
                    logging.info("Loaded CSS styles from GResource bundle")
                    return
                except Exception as e:
                    logging.warning(f"Failed to load CSS from GResource: {e}")

                css_candidates = [
                    os.path.join(
                        GLib.get_user_data_dir(), "io.github.BuddySirJava.SSH-Studio", "ssh-studio.css"
                    ),
                    os.path.join(GLib.get_user_data_dir(), "ssh-studio.css"),
                    "/app/share/io.github.BuddySirJava.SSH-Studio/ssh-studio.css",
                    "/app/share/ssh-studio.css",
                    os.path.join(
                        GLib.get_home_dir(),
                        ".local",
                        "share",
                        "io.github.BuddySirJava.SSH-Studio",
                        "ssh-studio.css",
                    ),
                    "data/ssh-studio.css",
                ]

                for candidate in css_candidates:
                    if os.path.exists(candidate):
                        try:
                            css_provider = Gtk.CssProvider()
                            css_provider.load_from_path(candidate)
                            Gtk.StyleContext.add_provider_for_display(
                                Gdk.Display.get_default(),
                                css_provider,
                                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                            )
                            logging.info(f"Loaded CSS styles from: {candidate}")
                            break
                        except Exception as e:
                            logging.warning(f"Failed to load CSS from {candidate}: {e}")
                            continue
        except Exception as e:
            logging.warning(f"Failed to load CSS styles: {e}")

    def _show_error_dialog(self, title: str, message: str):
        dialog = Gtk.MessageDialog(
            transient_for=self.main_window,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=title,
            secondary_text=message,
        )
        dialog.connect("response", lambda d, r: d.destroy())
        dialog.present()

    def _show_error(self, message: str):
        """Displays an error message to the user, typically from HostEditor or other components."""
        logging.error(f"Application Error: {message}")
        self._show_error_dialog(_("Error"), message)

    def _show_toast(self, message: str):
        """Displays a transient toast message to the user."""
        logging.info(f"Toast: {message}")
        if self.main_window and hasattr(self.main_window, "show_toast"):
            try:
                self.main_window.show_toast(message)
                return
            except Exception:
                pass
        self._show_error_dialog(_("Info"), message)


def main():
    app = SSHConfigStudioApp()
    try:
        app.set_default_icon_name("io.github.BuddySirJava.SSH-Studio")
    except Exception:
        pass
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
