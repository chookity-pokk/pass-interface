#!/usr/bin/env python3
import json
import shutil
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
from gi.repository import Adw, Gdk, GLib, Gtk

# --- Custom Styling: Proton Pass Android Dark Palette ---
CUSTOM_CSS = b"""
window {
    background-color: #120e24;
    color: #f1f0f7;
    font-family: system-ui, -apple-system, sans-serif;
}

.search-bar {
    background-color: #201a38;
    border-radius: 12px;
    border: 1px solid #322b52;
    color: #ffffff;
    padding: 6px 12px;
}

.vault-chip {
    background-color: #2a2247;
    color: #ded9f5;
    border-radius: 20px;
    padding: 4px 12px;
    font-size: 13px;
    font-weight: bold;
}

.proton-card {
    background-color: #1c1733;
    border-radius: 14px;
    border: 1px solid #282147;
    margin: 4px 8px;
    padding: 10px 14px;
}

.proton-card:active {
    background-color: #2b234f;
}

.item-avatar {
    background-color: #3b2d6a;
    color: #ffffff;
    font-weight: bold;
    border-radius: 10px;
    min-width: 38px;
    min-height: 38px;
}

.alias-subtext {
    color: #8c83b3;
    font-size: 13px;
}

.totp-pill {
    background-color: #0d2c2c;
    border: 1px solid #14b8a6;
    color: #2dd4bf;
    border-radius: 12px;
    padding: 8px 14px;
    font-family: monospace;
    font-size: 20px;
    font-weight: bold;
}

.detail-label {
    color: #928aa6;
    font-size: 12px;
    text-transform: uppercase;
    font-weight: 600;
}

.detail-value {
    color: #f5f4fb;
    font-size: 15px;
}

.action-btn {
    border-radius: 8px;
    background-color: #2b234f;
    color: #ded9f5;
    min-height: 36px;
    min-width: 36px;
}
"""


class PassCliClient:
    """Wrapper around pass-cli subcommands with fallback mock data."""

    def __init__(self):
        self.has_cli = shutil.which("pass-cli") is not None

    def _run_json(self, args: List[str]) -> Optional[Any]:
        if not self.has_cli:
            return None
        try:
            res = subprocess.run(
                ["pass-cli"] + args + ["--output", "json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            return json.loads(res.stdout)
        except Exception:
            return None

    def get_vaults(self) -> List[Dict[str, Any]]:
        data = self._run_json(["vault", "list"])
        if data and isinstance(data, list):
            return data
        # Fallback to match Android UI screenshot if CLI is not yet logged in
        return [
            {"vaultId": "all", "name": "All vaults", "itemCount": 154},
            {"vaultId": "v1", "name": "Personal", "itemCount": 57},
            {"vaultId": "v2", "name": "Work", "itemCount": 14},
            {"vaultId": "v3", "name": "Family", "itemCount": 65},
            {"vaultId": "v4", "name": "Gaming", "itemCount": 18},
        ]

    def get_items(self, vault_id: Optional[str] = None) -> List[Dict[str, Any]]:
        args = ["item", "list"]
        if vault_id and vault_id != "all":
            args += ["--share-id", vault_id]
        data = self._run_json(args)
        if data and isinstance(data, list):
            return data
        # Fallback items matching screenshot 1 & 2
        return [
            {
                "itemId": "1",
                "title": "Netflix",
                "username": "netflix.qcv42@passmail.com",
                "url": "https://netflix.com",
                "alias": True,
            },
            {
                "itemId": "2",
                "title": "The New York Times",
                "username": "eric.norbert@proton.me",
                "url": "https://www.nytimes.com/",
                "alias": False,
            },
            {
                "itemId": "3",
                "title": "BBC iPlayer",
                "username": "bbciplayer.ajf55@passmail.com",
                "url": "https://bbc.co.uk/iplayer",
                "alias": True,
            },
            {
                "itemId": "4",
                "title": "Fox One",
                "username": "foxone.fhd79@passmail.com",
                "url": "https://fox.com",
                "alias": True,
            },
            {
                "itemId": "5",
                "title": "Peacock",
                "username": "peacock.hds44@passmail.com",
                "url": "https://peacocktv.com",
                "alias": True,
            },
            {
                "itemId": "6",
                "title": "Tubi",
                "username": "tubi.saw14@passmail.com",
                "url": "https://tubitv.com",
                "alias": True,
            },
        ]

    def get_item_secret(self, item_id: str) -> Dict[str, str]:
        data = self._run_json(["item", "view", "--item-id", item_id])
        if data and isinstance(data, dict):
            # Extract key/password/totp from pass-cli json response
            key_data = (
                data.get("item", {})
                .get("content", {})
                .get("content", {})
                .get("key", {})
            )
            return {
                "password": key_data.get("password", "••••••••••••"),
                "totp": key_data.get("totp", ""),
            }
        # Fallback mock for UI demonstration
        return {
            "password": "%u$cLF!v)2M6mPQV#F",
            "totp": "820 996" if item_id == "2" else "",
        }


class ProtonPassLibremApp(Adw.Application):

    def __init__(self):
        super().__init__(application_id="me.proton.pass.librem5")
        self.cli = PassCliClient()
        self.current_items: List[Dict[str, Any]] = []
        self.active_vault = "all"

    def do_startup(self):
        super().do_startup()
        style_provider = Gtk.CssProvider()
        style_provider.load_from_data(CUSTOM_CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def do_activate(self):
        # Optimized for Librem 5 720x1440 portrait screen (360x720 scaled)
        self.win = Adw.ApplicationWindow(application=self, title="Proton Pass")
        self.win.set_default_size(360, 720)

        # Main Page Stack (List View <-> Detail View)
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)

        self.list_view = self.create_list_view()
        self.detail_view = self.create_detail_view()

        self.stack.add_named(self.list_view, "list")
        self.stack.add_named(self.detail_view, "detail")

        # Root layout with Toast Overlay for clipboard notifications
        self.toast_overlay = Adw.ToastOverlay()
        self.toast_overlay.set_child(self.stack)

        self.win.set_content(self.toast_overlay)
        self.win.present()

        # Load initial data
        self.refresh_items()

    def show_toast(self, text: str):
        toast = Adw.Toast.new(text)
        toast.set_timeout(2)
        self.toast_overlay.add_toast(toast)

    def copy_to_clipboard(self, text: str, label_type: str = "Item"):
        clipboard = self.win.get_clipboard()
        clipboard.set(text)
        self.show_toast(f"{label_type} copied to clipboard")

    # ==================== MAIN LIST VIEW ====================
    def create_list_view(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(10)
        box.set_margin_end(10)

        # Top Header Bar: Vault Dropdown Button
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.vault_btn = Gtk.Button(label="All vaults ▾")
        self.vault_btn.add_css_class("vault-chip")
        self.vault_btn.connect("clicked", self.open_vault_selector)
        header.append(self.vault_btn)

        # Search Box
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search in all vaults...")
        self.search_entry.add_css_class("search-bar")
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("search-changed", self.on_search_changed)
        header.append(self.search_entry)
        box.append(header)

        # Subheader info row
        sub_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.item_count_lbl = Gtk.Label(label="All")
        self.item_count_lbl.add_css_class("alias-subtext")
        sub_box.append(self.item_count_lbl)

        sort_lbl = Gtk.Label(label="↓↑ Most recent")
        sort_lbl.add_css_class("alias-subtext")
        sort_lbl.set_hexpand(True)
        sort_lbl.set_halign(Gtk.Align.END)
        sub_box.append(sort_lbl)
        box.append(sub_box)

        # Scrollable Item List
        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.list_box.connect("row-activated", self.on_item_activated)

        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_child(self.list_box)
        box.append(scroller)

        return box

    def refresh_items(self):
        def worker():
            items = self.cli.get_items(self.active_vault)
            GLib.idle_add(self.render_items, items)

        threading.Thread(target=worker, daemon=True).start()

    def render_items(self, items: List[Dict[str, Any]]):
        self.current_items = items
        self.item_count_lbl.set_text(f"All ({len(items)})")

        # Clear existing rows
        while child := self.list_box.get_first_child():
            self.list_box.remove(child)

        query = self.search_entry.get_text().strip().lower()

        for item in items:
            title = item.get("title", "")
            username = item.get("username", "")

            if query and query not in title.lower() and query not in username.lower():
                continue

            row = Gtk.ListBoxRow()
            card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            card.add_css_class("proton-card")

            # Initials badge
            avatar = Gtk.Label(label=title[0].upper() if title else "?")
            avatar.add_css_class("item-avatar")
            card.append(avatar)

            # Details
            info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            title_lbl = Gtk.Label(label=title)
            title_lbl.set_halign(Gtk.Align.START)
            title_lbl.set_css_classes(["heading"])

            sub_lbl = Gtk.Label(label=username)
            sub_lbl.set_halign(Gtk.Align.START)
            sub_lbl.add_css_class("alias-subtext")

            info_box.append(title_lbl)
            info_box.append(sub_lbl)
            card.append(info_box)

            row.set_child(card)
            row.item_data = item
            self.list_box.append(row)

    def on_search_changed(self, entry):
        self.render_items(self.current_items)

    def on_item_activated(self, list_box, row):
        item = getattr(row, "item_data", None)
        if item:
            self.show_item_detail(item)

    # ==================== DETAIL VIEW ====================
    def create_detail_view(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.set_margin_top(12)
        box.set_margin_bottom(16)
        box.set_margin_start(14)
        box.set_margin_end(14)

        # Header with back button & edit
        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        back_btn = Gtk.Button(label="←")
        back_btn.add_css_class("action-btn")
        back_btn.connect("clicked", lambda b: self.stack.set_visible_child_name("list"))
        hdr.append(back_btn)

        self.detail_title = Gtk.Label(label="Item Details")
        self.detail_title.set_hexpand(True)
        self.detail_title.set_halign(Gtk.Align.START)
        self.detail_title.set_css_classes(["title-2"])
        hdr.append(self.detail_title)

        edit_btn = Gtk.Button(label="Edit")
        edit_btn.add_css_class("action-btn")
        hdr.append(edit_btn)
        box.append(hdr)

        # Details Content Container
        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        detail_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)

        # Username Field
        self.user_box = self._create_field_box(
            "Username or email",
            on_copy=lambda: self.copy_to_clipboard(self.user_val.get_text(), "Username"),
        )
        self.user_val = self.user_box.val_lbl
        detail_content.append(self.user_box)

        # Password Field
        self.pass_box = self._create_field_box(
            "Password",
            on_copy=lambda: self.copy_to_clipboard(self.raw_password, "Password"),
            has_reveal=True,
        )
        self.pass_val = self.pass_box.val_lbl
        detail_content.append(self.pass_box)

        # 2FA / TOTP Field
        self.totp_group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        lbl = Gtk.Label(label="2FA token (TOTP)")
        lbl.add_css_class("detail-label")
        lbl.set_halign(Gtk.Align.START)
        self.totp_group.append(lbl)

        totp_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.totp_code_lbl = Gtk.Label(label="--- ---")
        self.totp_code_lbl.add_css_class("totp-pill")
        totp_row.append(self.totp_code_lbl)

        copy_totp_btn = Gtk.Button(label="Copy")
        copy_totp_btn.add_css_class("action-btn")
        copy_totp_btn.connect(
            "clicked",
            lambda b: self.copy_to_clipboard(
                self.totp_code_lbl.get_text().replace(" ", ""), "2FA Code"
            ),
        )
        totp_row.append(copy_totp_btn)

        self.totp_group.append(totp_row)
        detail_content.append(self.totp_group)

        # Website Field
        self.url_box = self._create_field_box(
            "Website",
            on_copy=lambda: self.copy_to_clipboard(self.url_val.get_text(), "Website"),
        )
        self.url_val = self.url_box.val_lbl
        detail_content.append(self.url_box)

        scroller.set_child(detail_content)
        box.append(scroller)
        return box

    def _create_field_box(self, label_text: str, on_copy=None, has_reveal: bool = False) -> Gtk.Box:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        card.add_css_class("proton-card")

        lbl = Gtk.Label(label=label_text)
        lbl.add_css_class("detail-label")
        lbl.set_halign(Gtk.Align.START)
        card.append(lbl)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        val = Gtk.Label(label="")
        val.add_css_class("detail-value")
        val.set_halign(Gtk.Align.START)
        val.set_hexpand(True)
        val.set_ellipsize(3)
        row.append(val)

        if has_reveal:
            self.pass_revealed = False
            reveal_btn = Gtk.Button(label="👁")
            reveal_btn.add_css_class("action-btn")

            def toggle_reveal(btn):
                self.pass_revealed = not self.pass_revealed
                val.set_text(self.raw_password if self.pass_revealed else "••••••••••••")
                btn.set_label("🔒" if self.pass_revealed else "👁")

            reveal_btn.connect("clicked", toggle_reveal)
            row.append(reveal_btn)

        if on_copy:
            copy_btn = Gtk.Button(label="Copy")
            copy_btn.add_css_class("action-btn")
            copy_btn.connect("clicked", lambda b: on_copy())
            row.append(copy_btn)

        card.append(row)
        card.val_lbl = val
        return card

    def show_item_detail(self, item: Dict[str, Any]):
        self.detail_title.set_text(item.get("title", "Details"))
        self.user_val.set_text(item.get("username", ""))
        self.url_val.set_text(item.get("url", ""))

        # Mask password initially
        self.raw_password = "••••••••••••"
        self.pass_val.set_text("••••••••••••")

        # Fetch passwords/TOTP in background
        def fetch_secret():
            secret = self.cli.get_item_secret(item.get("itemId", ""))
            self.raw_password = secret.get("password", "")

            def update_ui():
                totp = secret.get("totp", "")
                if totp:
                    self.totp_group.set_visible(True)
                    self.totp_code_lbl.set_text(totp)
                else:
                    self.totp_group.set_visible(False)

            GLib.idle_add(update_ui)

        threading.Thread(target=fetch_secret, daemon=True).start()
        self.stack.set_visible_child_name("detail")

    # ==================== VAULT SELECTOR ====================
    def open_vault_selector(self, button):
        dialog = Adw.PreferencesWindow()
        dialog.set_title("Select Vault")
        dialog.set_transient_for(self.win)
        dialog.set_modal(True)
        dialog.set_default_size(320, 400)

        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup(title="Vaults")
        page.add(group)

        vaults = self.cli.get_vaults()
        for v in vaults:
            row = Adw.ActionRow()
            row.set_title(v.get("name", "Vault"))
            row.set_subtitle(f"{v.get('itemCount', 0)} items")

            select_btn = Gtk.Button(label="Open")
            select_btn.add_css_class("suggested-action")
            vid = v.get("vaultId", "all")
            vname = v.get("name", "All vaults")

            def on_select(btn, chosen_id=vid, chosen_name=vname):
                self.active_vault = chosen_id
                self.vault_btn.set_label(f"{chosen_name} ▾")
                dialog.close()
                self.refresh_items()

            select_btn.connect("clicked", on_select)
            row.add_suffix(select_btn)
            group.add(row)

        dialog.add(page)
        dialog.present()


if __name__ == "__main__":
    app = ProtonPassLibremApp()
    app.run(None)
