#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) @Lululla 2026
# city_panel.py - City selection panel with offline file and online search
# fallback

import requests
from os.path import exists, join
from enigma import eListboxPythonMultiContent, gFont, RT_VALIGN_CENTER, eTimer, eListbox

from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Screens.MessageBox import MessageBox
from Screens.VirtualKeyBoard import VirtualKeyBoard

from Components.ActionMap import HelpableActionMap
from Components.GUIComponent import GUIComponent
from Components.Label import Label
from Components.MultiContent import MultiContentEntryText
from Components.Sources.StaticText import StaticText

from . import (
    _,
    DEBUG,
    load_skin_for_class,
    apply_global_theme,
    HEADERS,
    SYSTEM_DIR
)
from .google_translate import _get_system_language


BASE_URL = "https://api.foreca.net"


class CityPanel4List(GUIComponent):

    def __init__(self, entries):
        GUIComponent.__init__(self)
        self.lst = eListboxPythonMultiContent()
        self.lst.setFont(0, gFont("Regular", 30))
        self.foregroundColor = 0xffffff
        self.foregroundColorSelected = 0x00a0ff
        self.backgroundColor = 0x000000
        self.backgroundColorSelected = 0x2c2c2c
        self.itemHeight = 45
        self.column = 70
        self.setList(entries)

    GUI_WIDGET = eListbox

    def postWidgetCreate(self, instance):
        instance.setContent(self.lst)
        instance.setItemHeight(self.itemHeight)

    def preWidgetRemove(self, instance):
        instance.setContent(None)

    def setList(self, entries):
        self.lst.setList(entries)

    def getCurrentIndex(self):
        if self.instance:
            if hasattr(self.instance, 'getCurrentIndex'):
                return self.instance.getCurrentIndex()
            elif hasattr(self.instance, 'getSelectedIndex'):
                return self.instance.getSelectedIndex()
            else:
                return 0
        return 0

    def moveToIndex(self, index):
        if self.instance:
            self.instance.moveSelectionTo(index)

    def getSelectedIndex(self):
        return self.getCurrentIndex()

    def getCurrentSelection(self):
        if self.instance:
            return self.lst.getCurrentSelection()
        return None

    def getItemsPerPage(self):
        if self.instance:
            return self.instance.size().height() // self.itemHeight
        return 10

    def selectionEnabled(self, enabled):
        if self.instance:
            self.instance.setSelectionEnable(enabled)

    def moveSelectionTo(self, index):
        if self.instance:
            self.instance.moveSelectionTo(index)


class CityPanel4(Screen, HelpableScreen):
    def __init__(self, session, menu_dialog=None, weather_api=None):
        self.skin = load_skin_for_class(CityPanel4)
        self.session = session

        Screen.__init__(self, session)
        HelpableScreen.__init__(self)
        self.menu_dialog = menu_dialog
        self.weather_api = weather_api
        self.setTitle(_("Select a city"))
        self.Mlist = []
        self.city_list = []
        self.filtered_list = []
        self.search_text = ""
        self.search_ok = False

        self["Mlist"] = CityPanel4List([])
        self["background_plate"] = Label("")
        self["selection_overlay"] = Label("")
        self["key_ok"] = StaticText(_("OK - Forecast"))
        self["key_green"] = StaticText(_("Favorite 1"))
        self["key_yellow"] = StaticText(_("Favorite 2"))
        self["key_blue"] = StaticText(_("Home"))
        self["key_red"] = StaticText(_("Keyboard"))
        self["description"] = Label()
        self["actions"] = HelpableActionMap(
            self, "ForecaActions",
            {
                "cancel": (self.exit, _("Exit")),
                "red": (self.open_keyboard, _("Open Keyboard")),
                "green": (self.save_favorite1, _("Assign to Favorite 1")),
                "yellow": (self.save_favorite2, _("Assign to Favorite 2")),
                "blue": (self.save_home, _("Assign to Home")),
                "left": (self.left, _("Previous page")),
                "right": (self.right, _("Next page")),
                "up": (self.up, _("Previous")),
                "down": (self.down, _("Next")),
                "ok": (self.ok, _("Select")),
                "text": (self.open_keyboard, _("Keyboard")),
                "nextBouquet": (self.jump_down, _("Jump 500 down")),
                "prevBouquet": (self.jump_up, _("Jump 500 up")),
                "volumeDown": (self.jump_100_down, _("Jump 100 down")),
                "volumeUp": (self.jump_100_up, _("Jump 100 up")),
                "showEventInfo": (self.show_info, _("Show info")),
            },
            -1
        )
        self.onFirstExecBegin.append(self.onFirstExec)
        self.onShown.append(self.prepare_city_list)
        self.onLayoutFinish.append(self._apply_theme)

    def _apply_theme(self):
        apply_global_theme(self)

    def onFirstExec(self):
        def init_selection():
            if self.filtered_list:
                self.select_first_item()
                self.update_description()
        self.init_timer = eTimer()
        self.init_timer.callback.append(init_selection)
        self.init_timer.start(500, True)

    def prepare_city_list(self):
        """Load list from new_city.cfg file (offline)"""
        self.maxidx = 0
        self.Mlist = []
        self.city_list = []

        def _close_panel(*args):
            self.close()

        city_cfg_path = join(SYSTEM_DIR, "new_city.cfg")
        if not exists(city_cfg_path):
            self.session.openWithCallback(
                _close_panel,
                MessageBox,
                _("City list file not found!"),
                MessageBox.TYPE_WARNING,
                timeout=5
            )

        try:
            with open(city_cfg_path, "r", encoding="utf-8") as f:
                line_number = 0
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("#"):
                        text = line
                        mlist_entry = self.create_city_entry(
                            text, is_header=True)
                        self.Mlist.append(mlist_entry)
                        continue
                    if "/" not in line:
                        if DEBUG:
                            print(
                                f"[CityPanel4] Line {line_number} not valid: {line}")
                        continue
                    city_id, city_name = line.split("/", 1)
                    city_name = city_name.replace("_", " ")
                    mlist_entry = self.create_city_entry(
                        city_name, city_id=city_id)
                    self.Mlist.append(mlist_entry)
                    self.city_list.append((city_name, city_id))
                    line_number += 1

            if DEBUG:
                print(
                    "[CityPanel4] Loaded", len(
                        self.Mlist), "entries from file")
            self.filtered_list = self.Mlist
            self["Mlist"].setList(self.filtered_list)
            self["Mlist"].selectionEnabled(True)

            def select_first():
                self.select_first_item()
            self.timer = eTimer()
            self.timer.callback.append(select_first)
            self.timer.start(100, True)

            self._update_fav_buttons()
        except Exception as e:
            print("[CityPanel4] Error loading cities:", e)
            import traceback
            traceback.print_exc()

    def create_city_entry(self, text, city_id=None, is_header=False):
        """Create a MultiContent element for the list."""
        widget = self["Mlist"]
        if is_header:
            text_color = 0x808080
            text_color_selected = 0x808080
            back_color_selected = widget.backgroundColor
        else:
            text_color = widget.foregroundColor
            text_color_selected = widget.foregroundColorSelected
            back_color_selected = widget.backgroundColorSelected

        itemHeight = widget.itemHeight
        col = widget.column

        # The structure must be a LIST!
        # The first element is a tuple with the data (text, city_id, is_header)
        # Then follow the MultiContentEntry elements
        entry = [
            (text, city_id, is_header),  # Data
            MultiContentEntryText(
                pos=(0, 0),
                size=(col, itemHeight),
                font=0,
                text="",
                color=text_color,
                color_sel=text_color_selected,
                backcolor_sel=back_color_selected,
                flags=RT_VALIGN_CENTER
            ),
            MultiContentEntryText(
                pos=(col, 0),
                size=(1000, itemHeight),
                font=0,
                text=text,
                color=text_color,
                color_sel=text_color_selected,
                backcolor_sel=back_color_selected,
                flags=RT_VALIGN_CENTER
            )
        ]

        return entry

    def open_keyboard(self):
        self.session.openWithCallback(
            self.filter_cities,
            VirtualKeyBoard,
            title=_("Search your City"),
            text=''
        )

    def filter_cities(self, search_term):
        """Search for cities: first online (if available), otherwise offline on file."""
        if not search_term:
            return

        self.search_text = search_term
        self["description"].setText(_("Searching for '%s'...") % search_term)

        # Attempt to search online
        online_success = self.search_online(search_term)

        # If online search fails (no results or errors), switch to local search
        if not online_success:
            self.search_offline(search_term)

        self.search_ok = True

    def search_online(self, search_term):
        """Cerca tramite API Foreca. Ritorna True se ha trovato risultati, False altrimenti."""
        current_lang = _get_system_language()
        try:
            url = "%s/locations/search/%s.json" % (BASE_URL, search_term)
            params = {
                "limit": 20,
                "lang": current_lang
            }
            response = requests.get(
                url, params=params, headers=HEADERS, timeout=8)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print("[CityPanel4] Online search error:", e)
            return False

        results = data.get("results", [])
        if not results:
            return False

        # Build new list with online results
        new_entries = []
        new_city_list = []
        for res in results:
            city_id = res.get("id")
            name = res.get("name", "")
            country = res.get("countryName", "")
            display_name = f"{name}, {country}" if country else name
            entry = self.create_city_entry(
                display_name, city_id=city_id, is_header=False)
            new_entries.append(entry)
            new_city_list.append((display_name, city_id))

        # Replace the filtered list with the online one
        self.filtered_list = new_entries
        self.city_list = new_city_list
        self["Mlist"].setList(self.filtered_list)
        self["Mlist"].selectionEnabled(True)
        self.select_first_item()
        count = len(self.filtered_list)
        self["description"].setText(
            _("Found %d cities online for '%s'") %
            (count, search_term))
        return True

    def search_offline(self, search_term):
        """Search the local file (already loaded into self.Mlist)."""
        search_term_lower = search_term.lower()
        new_entries = []
        new_city_list = []
        for item in self.Mlist:
            data = item[0]
            text = data[0].lower()
            is_header = data[2] if len(data) > 2 else False
            if is_header:
                if search_term_lower in text:
                    new_entries.append(item)
            else:
                if search_term_lower in text:
                    new_entries.append(item)
                    new_city_list.append((data[0], data[1]))

        if not new_entries:
            self.session.open(
                MessageBox, _("No cities found locally for '%s'") %
                search_term, MessageBox.TYPE_INFO, timeout=5)
            self["description"].setText(_("Press RED to search again"))
            return

        self.search_ok = True
        self.filtered_list = new_entries
        self.city_list = new_city_list
        self["Mlist"].setList(self.filtered_list)
        self["Mlist"].selectionEnabled(True)
        self.select_first_item()
        count = len(self.filtered_list)
        self["description"].setText(
            _("Found %d cities locally for '%s'") %
            (count, search_term))

    def _update_fav_buttons(self):
        home_name = self._get_favorite_name('home')
        fav1_name = self._get_favorite_name('fav1')
        fav2_name = self._get_favorite_name('fav2')
        print(
            f"[CityPanel] home={home_name}, fav1={fav1_name}, fav2={fav2_name}")

        if home_name:
            self["key_blue"].setText(_(home_name))
        else:
            self["key_blue"].setText(_("Home"))

        if fav1_name:
            self["key_green"].setText(_(fav1_name))
        else:
            self["key_green"].setText(_("Favorite 1"))

        if fav2_name:
            self["key_yellow"].setText(_(fav2_name))
        else:
            self["key_yellow"].setText(_("Favorite 2"))

    def update_description(self):
        idx = self["Mlist"].getCurrentIndex()
        if idx is not None and 0 <= idx < len(self.filtered_list):
            item = self.filtered_list[idx]
            data = item[0]
            if len(data) > 2 and data[2]:  # header
                self["description"].setText(_("Header - not selectable"))
            elif len(data) >= 2:
                name, cid = data[0], data[1]
                self["description"].setText(f"{name}  id: {cid}")
        else:
            self["description"].setText(_("No city selected"))

    def get_selected_city(self):
        idx = self["Mlist"].getCurrentIndex()
        if idx is not None and 0 <= idx < len(self.filtered_list):
            item = self.filtered_list[idx]
            data = item[0]
            if len(data) > 2 and not data[2]:  # non header
                return f"{data[1]}/{data[0].replace(' ', '_')}"
        return None

    def _get_favorite_name(self, fav_type):
        """Returns the saved city name, retrieving it from the API if the file contains only the ID."""
        path = join(SYSTEM_DIR, f"{fav_type}.cfg")
        if not exists(path):
            return None
        try:
            with open(path, "r", encoding='utf-8') as f:
                content = f.read().strip()
            if '/' in content:
                city_name = content.split('/', 1)[1].replace('_', ' ')
            else:
                # Only ID: try to retrieve the name from the API
                if self.weather_api:
                    place = self.weather_api.get_location_by_id(content)
                    if place and place.name:
                        city_name = place.name
                    else:
                        return None
                else:
                    return None
            # Truncate if too long
            if len(city_name) > 15:
                city_name = city_name[:12] + "..."
            return city_name
        except Exception as e:
            print("[CityPanel4] Error reading favorite:", e)
            return None

    def save_favorite1(self):
        selected = self.get_selected_city()
        if selected:
            self.save_favorite("fav1", selected)
            self._update_fav_buttons()
            self.close((selected, 'assign', 1))

    def save_favorite2(self):
        selected = self.get_selected_city()
        if selected:
            self.save_favorite("fav2", selected)
            self._update_fav_buttons()
            self.close((selected, 'assign', 1))

    def save_home(self):
        selected = self.get_selected_city()
        if selected:
            self.save_favorite("home", selected)
            self._update_fav_buttons()
            self.close((selected, 'assign', 1))

    def ok(self):
        selected = self.get_selected_city()
        if selected:
            if '/' in selected:
                city_id, display_name = selected.split('/', 1)
                display_name = display_name.replace('_', ' ')
            else:
                city_id = selected
                display_name = None
            if self.menu_dialog:
                self.menu_dialog.close()
            self.close((city_id, 'select', display_name))

    def save_favorite(self, fav_type, city):
        path = join(SYSTEM_DIR, f"{fav_type}.cfg")
        try:
            with open(path, "w", encoding='utf-8') as f:
                f.write(city)
            city_id = city.split('/')[0]
            # Determine the favorite's index
            if fav_type == 'home':
                fav_index = 0
            elif fav_type == 'fav1':
                fav_index = 1
            elif fav_type == 'fav2':
                fav_index = 2
            else:
                fav_index = None
            self.close((city_id, 'assign', fav_index))
        except Exception as e:
            print("[CityPanel] Error saving:", e)
            self.session.open(
                MessageBox,
                _("Error saving favorite!"),
                MessageBox.TYPE_ERROR,
                timeout=5)

    def show_info(self):
        info = (
            _("City Selection Help:\n\n")
            + _("• Use arrow keys to navigate\n")
            + _("• OK to select city\n")
            + _("• GREEN to save as Favorite 1\n")
            + _("• YELLOW to save as Favorite 2\n")
            + _("• BLUE to save as Home\n")
            + _("• RED to open search keyboard\n")
            + _("• CH+/CH- to jump 500 cities\n")
            + _("• VOL+/VOL- to jump 100 cities\n\n")
            + _("Search first tries online, if fails uses local list.")
        )
        self.session.open(MessageBox, info, MessageBox.TYPE_INFO)

    def select_first_item(self):
        for idx, item in enumerate(self.filtered_list):
            data = item[0]
            if len(data) <= 2 or not data[2]:
                self["Mlist"].moveToIndex(idx)
                self.update_description()
                break

    def get_current_selectable_index(self):
        idx = self["Mlist"].getCurrentIndex()
        if idx is not None and 0 <= idx < len(self.filtered_list):
            return idx
        return 0

    def move_next_selectable(self, direction):
        if not self.filtered_list:
            return
        current = self.get_current_selectable_index()
        total = len(self.filtered_list)
        for i in range(1, total + 1):
            nxt = (current + direction * i) % total
            data = self.filtered_list[nxt][0]
            if len(data) <= 2 or not data[2]:
                self["Mlist"].moveToIndex(nxt)
                self.update_description()
                break

    def left(self):
        per_page = self["Mlist"].getItemsPerPage()
        self.jump_selectable(-per_page)

    def right(self):
        per_page = self["Mlist"].getItemsPerPage()
        self.jump_selectable(per_page)

    def up(self):
        self.move_next_selectable(-1)

    def down(self):
        self.move_next_selectable(1)

    def jump_up(self):
        self.jump_selectable(-500)

    def jump_down(self):
        self.jump_selectable(500)

    def jump_100_up(self):
        self.jump_selectable(-100)

    def jump_100_down(self):
        self.jump_selectable(100)

    def jump_selectable(self, step):
        if not self.filtered_list:
            return
        current = self.get_current_selectable_index()
        total = len(self.filtered_list)
        direction = 1 if step > 0 else -1
        abs_step = abs(step)
        for xz in range(abs_step):
            nxt = (current + direction) % total
            while len(self.filtered_list[nxt][0]
                      ) > 2 and self.filtered_list[nxt][0][2]:
                nxt = (nxt + direction) % total
            current = nxt
        self["Mlist"].moveToIndex(current)
        self.update_description()

    def exit(self):
        """Exit the city selection panel"""
        if self.search_ok:
            self.search_ok = False
        if hasattr(self, 'init_timer'):
            self.init_timer.stop()
        if hasattr(self, 'timer'):
            self.timer.stop()
        self.close(None)
