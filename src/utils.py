import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib
import subprocess


def copy_text_to_clipboard(text: str) -> bool:
    """
    Copies the provided text to the clipboard using multiple backends.
    Tries GDK clipboard first, then falls back to command line tools.
    """
    try:
        display = Gdk.Display.get_default()
        if not display:
            raise RuntimeError("no display")
        clipboard = display.get_clipboard()
        bytes_utf8 = GLib.Bytes.new(text.encode("utf-8"))
        providers = [
            Gdk.ContentProvider.new_for_bytes("text/plain;charset=utf-8", bytes_utf8),
            Gdk.ContentProvider.new_for_bytes("text/plain", bytes_utf8),
        ]
        provider = (
            Gdk.ContentProvider.new_union(providers)
            if hasattr(Gdk.ContentProvider, "new_union")
            else providers[0]
        )

        if hasattr(clipboard, "set_content"):
            clipboard.set_content(provider)
        elif hasattr(clipboard, "set"):
            clipboard.set(provider)
        elif hasattr(clipboard, "set_text"):
            clipboard.set_text(text)
        else:
            raise RuntimeError("unsupported clipboard api")

        try:
            primary = display.get_primary_clipboard()
            if primary:
                if hasattr(primary, "set_content"):
                    primary.set_content(provider)
                elif hasattr(primary, "set"):
                    primary.set(provider)
                elif hasattr(primary, "set_text"):
                    primary.set_text(text)
        except Exception:
            pass
        return True
    except Exception:
        pass

    # Fallback to command line tools
    try:
        for cmd in [
            ["wl-copy"],
            ["xclip", "-selection", "clipboard"],
            ["xsel", "--clipboard", "--input"],
        ]:
            try:
                res = subprocess.run(cmd, input=text, text=True, capture_output=True)
                if res.returncode == 0:
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False
