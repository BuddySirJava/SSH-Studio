#!/usr/bin/env python3
"""SSH-Studio: Main Application Entry Point."""

import sys
import gi
import logging
from gettext import gettext as _
import gettext

import os
import threading

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gio, GLib, Gdk, Adw


def _ensure_utf8_locale():
    import locale
    try:
        current = locale.setlocale(locale.LC_ALL, "")
        if current is None or ("UTF-8" not in current and "utf8" not in current):
            os.environ.setdefault("LC_ALL", "C.UTF-8")
            os.environ.setdefault("LANG", "C.UTF-8")
            try:
                locale.setlocale(locale.LC_ALL, "C.UTF-8")
            except Exception:
                pass
    except Exception:
        pass


def _configure_renderer_for_x11():
    if os.getenv("GSK_RENDERER") or os.getenv("SSH_STUDIO_FORCE_GPU") == "1":
        return

    is_x11 = os.getenv("DISPLAY") and not os.getenv("WAYLAND_DISPLAY")
    if not is_x11:
        return

    os.environ.setdefault("GDK_BACKEND", "x11")

    dri_path = "/dev/dri"
    try:
        has_dri = os.path.exists(dri_path) and os.access(dri_path, os.R_OK)
    except Exception:
        has_dri = False

    if not has_dri and not os.getenv("LIBGL_ALWAYS_SOFTWARE"):
        os.environ["GSK_RENDERER"] = "cairo"
        logging.info("GSK_RENDERER=cairo set for X11 without DRM; forcing software rendering")

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
            application_id="io.github.BuddySirJava.SSH-Studio",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
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
            try:
                icon_theme = Gtk.IconTheme.get_for_display(Gtk.Display.get_default())
                icon_theme.add_search_path("/app/share/icons")
                icon_theme.add_search_path("/usr/share/icons")
                icon_theme.set_theme_name("Adwaita")
            except Exception:
                pass
            try:
                settings = Gtk.Settings.get_default()
                if settings is not None:
                    settings.set_property("gtk-icon-theme-name", "Adwaita")
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
                "/opt/homebrew/share/io.github.BuddySirJava.SSH-Studio/ssh-studio-resources.gresource",
                "/usr/local/share/io.github.BuddySirJava.SSH-Studio/ssh-studio-resources.gresource",
                "/usr/share/io.github.BuddySirJava.SSH-Studio/ssh-studio-resources.gresource",
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
        def worker():
            try:
                if self.parser is not None:
                    self.parser.parse()
                def update_ui():
                    try:
                        if self.main_window and getattr(self.main_window, "host_list", None):
                            self.main_window.host_list.load_hosts(self.parser.config.hosts)
                            try:
                                self.main_window._update_status(_("Configuration loaded successfully"))
                            except Exception:
                                pass
                    except Exception:
                        pass
                    return False
                GLib.idle_add(update_ui)
            except Exception as e:
                logging.error(f"Failed to initialize SSH config parser: {e}")
                GLib.idle_add(lambda: (self._show_error_dialog(_("Failed to load SSH config"), str(e)), False)[1])

        t = threading.Thread(target=worker, daemon=True)
        t.start()
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
            if os.getenv("FLATPAK_ID"):
                css_provider = Gtk.CssProvider()
                css_provider.load_from_resource(
                    "/io/github/BuddySirJava/SSH-Studio/ssh-studio.css"
                )
                Gtk.StyleContext.add_provider_for_display(
                    Gdk.Display.get_default(),
                    css_provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                )
                logging.info("Loaded CSS styles from GResource bundle (Flatpak)")
                return
            else:
                try:
                    css_provider = Gtk.CssProvider()
                    css_provider.load_from_resource(
                        "/io/github/BuddySirJava/SSH-Studio/ssh-studio.css"
                    )
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
                        GLib.get_user_data_dir(),
                        "io.github.BuddySirJava.SSH-Studio",
                        "ssh-studio.css",
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
                    "/opt/homebrew/share/io.github.BuddySirJava.SSH-Studio/ssh-studio.css",
                    "/usr/local/share/io.github.BuddySirJava.SSH-Studio/ssh-studio.css",
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
        logging.error(f"Application Error: {message}")
        self._show_error_dialog(_("Error"), message)

    def _show_toast(self, message: str):
        logging.info(f"Toast: {message}")
        if self.main_window and hasattr(self.main_window, "show_toast"):
            try:
                self.main_window.show_toast(message)
                return
            except Exception:
                pass
        self._show_error_dialog(_("Info"), message)


def main():
    _ensure_utf8_locale()
    _configure_renderer_for_x11()
    app = SSHConfigStudioApp()
    try:
        app.set_default_icon_name("io.github.BuddySirJava.SSH-Studio")
    except Exception:
        pass
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
