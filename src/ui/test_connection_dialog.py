import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GObject, GLib, Adw
import subprocess
import threading
from gettext import gettext as _
import os

@Gtk.Template(resource_path="/com/sshstudio/app/ui/test_connection_dialog.ui")
class TestConnectionDialog(Adw.Window):
    __gtype_name__ = "TestConnectionDialog"

    stack = Gtk.Template.Child()
    loading_page = Gtk.Template.Child()
    status_title = Gtk.Template.Child()
    status_description = Gtk.Template.Child()
    output_text = Gtk.Template.Child()

    def __init__(self, parent=None, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(parent)

    def start_test(self, command, hostname):
        """Start the SSH connection test with the given command and hostname."""
        if not hostname:
            self._show_error(_("No hostname or pattern available to test."))
            return

        self.stack.set_visible_child_name("loading")
        self.loading_page.set_title(_("Testing Connection"))
        self.loading_page.set_description(_("Running SSH command..."))
        self.loading_page.set_icon_name("network-workgroup-symbolic")

        def run_test():
            try:
                result = subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=20
                )
                rc = result.returncode
                stdout_text = (result.stdout or "").strip()
                stderr_text = (result.stderr or "").strip()

                def update_ui():
                    self._show_results(rc, stdout_text, stderr_text, command)
                    return False

                GLib.idle_add(update_ui)

            except subprocess.TimeoutExpired:
                def update_timeout():
                    self._show_timeout(command)
                    return False
                GLib.idle_add(update_timeout)
            except Exception as e:
                def update_error():
                    self._show_exception(e)
                    return False
                GLib.idle_add(update_error)

        threading.Thread(target=run_test, daemon=True).start()

    def _show_error(self, message):
        """Show error state."""
        self.stack.set_visible_child_name("loading")
        self.loading_page.set_title(_("Error"))
        self.loading_page.set_description(message)
        self.loading_page.set_icon_name("dialog-error-symbolic")

    def _show_results(self, return_code, stdout_text, stderr_text, command):
        """Show test results."""
        self.stack.set_visible_child_name("results")
        
        if return_code == 0:
            self.status_title.set_text(_("Connection Successful"))
            self.status_description.set_text(_("SSH connection test completed successfully"))
        else:
            self.status_title.set_text(_("Connection Failed"))
            self.status_description.set_text(_(f"SSH connection failed with exit code {return_code}"))
        
        output_lines = []
        output_lines.append(f"Command: {' '.join(command)}")
        output_lines.append("")
        
        if stdout_text:
            output_lines.append("STDOUT:")
            output_lines.append(stdout_text)
            output_lines.append("")
        
        if stderr_text:
            output_lines.append("STDERR:")
            output_lines.append(stderr_text)
            output_lines.append("")
        
        output_lines.append(f"Exit code: {return_code}")
        
        self.output_text.get_buffer().set_text("\n".join(output_lines))

    def _show_timeout(self, command):
        """Show timeout state."""
        self.stack.set_visible_child_name("results")
        self.status_title.set_text(_("Connection Timed Out"))
        self.status_description.set_text(_("SSH connection test timed out after 20 seconds"))
        
        output_lines = []
        output_lines.append(f"Command: {' '.join(command)}")
        output_lines.append("")
        output_lines.append("Timed out after 20 seconds")
        
        self.output_text.get_buffer().set_text("\n".join(output_lines))

    def _show_exception(self, exception):
        """Show exception state."""
        self.stack.set_visible_child_name("results")
        self.status_title.set_text(_("Error"))
        self.status_description.set_text(_(f"An error occurred: {exception}"))
        
        output_lines = []
        output_lines.append("Error Details:")
        output_lines.append(str(exception))
        
        self.output_text.get_buffer().set_text("\n".join(output_lines))
