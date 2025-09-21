import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw
from gettext import gettext as _


@Gtk.Template(resource_path="/io/github/BuddySirJava/SSH-Studio/ui/welcome_view.ui")
class WelcomeView(Gtk.Box):

    __gtype_name__ = "WelcomeView"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
