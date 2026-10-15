import gi
import subprocess
import json
import sys

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gtk, Gdk, GLib

class PassClientWindow(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_title("Proton Pass CLI")
        
        # 360x600 is a great default for the Librem 5's portrait screen
        self.set_default_size(360, 600) 

        # Main Layout
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        vbox.set_margin_top(24)
        vbox.set_margin_bottom(24)
        vbox.set_margin_start(24)
        vbox.set_margin_end(24)
        self.set_child(vbox)

        # Title
        title = Gtk.Label(label="<b>Get Credentials</b>", use_markup=True, xalign=0)
        vbox.append(title)

        # Vault Input
        vbox.append(Gtk.Label(label="Vault Name", xalign=0))
        self.vault_entry = Gtk.Entry(text="Personal")
        vbox.append(self.vault_entry)

        # Item Input
        vbox.append(Gtk.Label(label="Item Title", xalign=0))
        self.item_entry = Gtk.Entry(placeholder_text="e.g., Netflix")
        # Pressing 'Enter' on the keyboard triggers the fetch
        self.item_entry.connect("activate", self.on_fetch_clicked) 
        vbox.append(self.item_entry)

        # Fetch Button
        self.fetch_btn = Gtk.Button(label="Retrieve Info")
        self.fetch_btn.connect("clicked", self.on_fetch_clicked)
        vbox.append(self.fetch_btn)

        # Status / Error Label
        self.status_label = Gtk.Label(label="")
        self.status_label.set_wrap(True)
        vbox.append(self.status_label)

        # --- Results Section ---
        
        # Username Row
        self.user_val = Gtk.Entry(editable=False)
        copy_user_btn = Gtk.Button(icon_name="edit-copy-symbolic", tooltip_text="Copy Username")
        copy_user_btn.connect("clicked", lambda x: self.copy_to_clipboard(self.user_val.get_text()))
        
        user_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.user_val.set_hexpand(True)
        user_box.append(self.user_val)
        user_box.append(copy_user_btn)
        
        vbox.append(Gtk.Label(label="Username", xalign=0))
        vbox.append(user_box)

        # Password Row
        # PasswordEntry obfuscates the text and adds a native "reveal" eye icon
        self.pass_val = Gtk.PasswordEntry() 
        self.pass_val.set_editable(False)
        copy_pass_btn = Gtk.Button(icon_name="edit-copy-symbolic", tooltip_text="Copy Password")
        copy_pass_btn.connect("clicked", lambda x: self.copy_to_clipboard(self.pass_val.get_text()))
        
        pass_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.pass_val.set_hexpand(True)
        pass_box.append(self.pass_val)
        pass_box.append(copy_pass_btn)

        vbox.append(Gtk.Label(label="Password", xalign=0))
        vbox.append(pass_box)

    def on_fetch_clicked(self, button):
        vault = self.vault_entry.get_text().strip()
        item = self.item_entry.get_text().strip()

        if not item:
            self.status_label.set_text("Please enter an item title.")
            return

        self.status_label.set_text("Fetching...")
        
        # Run the pass-cli command synchronously 
        try:
            result = subprocess.run(
                ["pass-cli", "item", "view", "--vault-name", vault, "--item-title", item, "--output", "json"],
                capture_output=True,
                text=True,
                check=True
            )
            
            data = json.loads(result.stdout)
            
            # Note: adjust these dictionary keys if pass-cli JSON structure differs slightly
            login_data = data.get("login", {})
            username = login_data.get("username", "")
            password = login_data.get("password", "")
            
            self.user_val.set_text(username)
            self.pass_val.set_text(password)
            self.status_label.set_text("Credentials retrieved.")
            
        except subprocess.CalledProcessError as e:
            self.status_label.set_text("Error: Item not found or CLI not logged in.")
        except json.JSONDecodeError:
            self.status_label.set_text("Error parsing CLI output.")
        except Exception as e:
            self.status_label.set_text(f"Unexpected error: {str(e)}")

    def copy_to_clipboard(self, text):
        if text:
            clipboard = Gdk.Display.get_default().get_clipboard()
            clipboard.set(text) # Native GTK4 Wayland-compatible clipboard set
            self.status_label.set_text("Copied to clipboard!")

class PassClientApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.example.PassClient")
        self.connect("activate", self.on_activate)

    def on_activate(self, app):
        win = PassClientWindow(application=app)
        win.present()

if __name__ == "__main__":
    app = PassClientApp()
    app.run(sys.argv)
