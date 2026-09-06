#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) @Lululla 2026
# color_selector.py - Color selection screen

from Screens.Screen import Screen
from Components.ActionMap import HelpableActionMap
from Components.Label import Label
from Components.MenuList import MenuList
from Components.Pixmap import Pixmap
from Screens.HelpMenu import HelpableScreen
from enigma import gRGB
from skin import parseColor
from os.path import exists

from . import (
    _,
    load_skin_for_class,
    DATA_FILE
)


class ColorSelector(Screen, HelpableScreen):
    def __init__(self, session, foreca_preview):
        self.skin = load_skin_for_class(ColorSelector)
        Screen.__init__(self, session)
        HelpableScreen.__init__(self)
        self.setTitle(_('Color Selector'))
        self.foreca_preview = foreca_preview

        self.rgbmyr = foreca_preview.rgbmyr
        self.rgbmyg = foreca_preview.rgbmyg
        self.rgbmyb = foreca_preview.rgbmyb
        self.alpha = foreca_preview.alpha

        self.color_list = []
        self.source_names = []
        self.translated_names = []
        self.color_data = []

        self["menu"] = MenuList([])
        self["color_selection"] = Label(_('Color Selector'))
        self["color_name_label"] = Label()
        self["color_name_label"].setText(_('Color name'))
        self["color_info_label"] = Label()
        self["color_info_label"].setText(_('Color data'))
        self["color_preview"] = Pixmap()
        self["background_plate"] = Label("")
        self["selection_overlay"] = Label("")
        self["actions"] = HelpableActionMap(
            self, "ForecaActions",
            {
                "cancel": (self.close, _("Exit")),
                "red": (self.close, _("Exit")),
                "ok": (self.confirm_selection, _("Select")),
                "left": (self.page_up, _("Previous page")),
                "right": (self.page_down, _("Next page")),
                "up": (self.move_up, _("Previous")),
                "down": (self.move_down, _("Next")),

            },
            -1
        )
        self.onShown.append(self.initialize_data)

    def initialize_data(self):
        current_color = gRGB(int(self.rgbmyr), int(
            self.rgbmyg), int(self.rgbmyb))
        self["background_plate"].instance.setBackgroundColor(current_color)
        self["selection_overlay"].instance.setBackgroundColor(
            parseColor(self.alpha))

        if exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    if " #" in line:
                        name, values = line.split(" #", 1)
                        name = name.strip()
                        values = values.strip()
                    else:
                        name = line
                        values = ""
                    self.source_names.append(name)
                    self.translated_names.append(name)
                    self.color_data.append(values)
                    self.color_list.append(name)
            except Exception as e:
                print("[ColorSelector] Error reading file:", e)

        self["menu"].setList(self.color_list)
        self["menu"].selectionEnabled(1)
        if self.color_list:
            self.update_current_selection(0)

    def update_current_selection(self, index):
        if 0 <= index < len(self.translated_names):
            display_name = self.translated_names[index]
            self["color_name_label"].setText(display_name)

            if index < len(self.color_data) and self.color_data[index]:
                parts = self.color_data[index].split()
                if len(parts) >= 4:
                    html = '#' + parts[0]
                    r, g, b = int(parts[1]), int(parts[2]), int(parts[3])
                    color_obj = gRGB(r, g, b)
                    brightness = (r * 299 + g * 587 + b * 114) / 1000
                    text_color = parseColor(
                        "#000000" if brightness > 128 else "#FFFFFF")

                    self["color_name_label"].instance.setForegroundColor(
                        color_obj)
                    self["color_info_label"].instance.setBackgroundColor(
                        color_obj)
                    self["color_info_label"].instance.setTransparent(False)
                    self["color_info_label"].instance.setForegroundColor(
                        text_color)
                    self["color_preview"].instance.setBackgroundColor(
                        color_obj)

                    info = f"{_('HTML')} ({html})   {_('Red')} ({r})   {_('Green')} ({g})   {_('Blue')} ({b})"
                    self["color_info_label"].setText(info)

    def move_up(self):
        self["menu"].up()
        self.update_current_selection(self["menu"].getSelectedIndex())

    def move_down(self):
        self["menu"].down()
        self.update_current_selection(self["menu"].getSelectedIndex())

    def page_up(self):
        self["menu"].pageUp()
        self.update_current_selection(self["menu"].getSelectedIndex())

    def page_down(self):
        self["menu"].pageDown()
        self.update_current_selection(self["menu"].getSelectedIndex())

    def confirm_selection(self):
        idx = self["menu"].getSelectedIndex()
        if 0 <= idx < len(self.color_data) and self.color_data[idx]:
            parts = self.color_data[idx].split()
            if len(parts) >= 4:
                self.foreca_preview.rgbmyr = parts[1]
                self.foreca_preview.rgbmyg = parts[2]
                self.foreca_preview.rgbmyb = parts[3]
                self.foreca_preview._save_color()
                self.foreca_preview._update_button()
                self.foreca_preview.instance.invalidate()
        self.close()

    def exit_screen(self):
        self.close()
