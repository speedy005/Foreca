#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) @Lululla 2026
# unit_settings_advanced.py - Advanced unit of measurement settings

from Screens.Screen import Screen
from Components.ActionMap import HelpableActionMap
from Components.Label import Label
from Components.Sources.StaticText import StaticText
from Components.MenuList import MenuList
from Screens.HelpMenu import HelpableScreen

from . import (
    _,
    load_skin_for_class,
    apply_global_theme
)


class UnitSettingsAdvanced(Screen, HelpableScreen):
    """Screen for advanced selection of measurement units"""

    def __init__(self, session, unit_manager):
        self.skin = load_skin_for_class(UnitSettingsAdvanced)
        Screen.__init__(self, session)
        HelpableScreen.__init__(self)
        self.unit_manager = unit_manager
        self.setTitle(_("Advanced Unit Settings"))

        self.wind_options = [
            ("km/h", unit_manager.WIND_KMH),
            ("m/s", unit_manager.WIND_MS),
            ("mph", unit_manager.WIND_MPH),
            ("kts", unit_manager.WIND_KTS),
        ]
        self.pressure_options = [
            ("hPa", unit_manager.PRESSURE_HPA),
            ("mmHg", unit_manager.PRESSURE_MMHG),
            ("inHg", unit_manager.PRESSURE_INHG),
        ]
        self.temp_options = [
            ("°C", unit_manager.TEMP_C),
            ("°F", unit_manager.TEMP_F),
        ]
        self.precip_options = [
            ("mm", unit_manager.PRECIP_MM),
            ("in", unit_manager.PRECIP_IN),
        ]

        self["background_plate"] = Label("")
        self["selection_overlay"] = Label("")
        self["key_red"] = StaticText(_("Cancel"))
        self["key_green"] = StaticText(_("Save"))
        self["key_yellow"] = StaticText(_("Next"))
        self["key_blue"] = StaticText(_("Prev"))
        self["title"] = Label(_("Select wind unit"))
        self["info"] = Label(_("Use ▲/▼ to change, OK to select"))
        self["current"] = Label("")
        self["list"] = MenuList([])

        self["actions"] = HelpableActionMap(
            self, "ForecaActions",
            {
                "cancel": (self.close, _("Exit")),
                "red": (self.close, _("Exit")),
                "green": (self.save_and_exit, _("Save")),
                "yellow": (self.next_category, _("Next")),
                "blue": (self.prev_category, _("Prev")),
                "up": (self.up, _("Up")),
                "down": (self.down, _("Down")),
                "ok": (self.select_current, _("Select")),
            },
            -1
        )

        self.category_index = 0
        self.categories = [
            ("wind", self.wind_options, _("Wind")),
            ("pressure", self.pressure_options, _("Pressure")),
            ("temperature", self.temp_options, _("Temperature")),
            ("precipitation", self.precip_options, _("Precipitation")),
        ]
        self.current_category = self.categories[self.category_index]

        self.onLayoutFinish.append(self._apply_theme)
        self.onLayoutFinish.append(self.update_list)

    def _apply_theme(self):
        apply_global_theme(self)

    def update_list(self):
        """Update the list with the options of the current category"""
        cat_key, options, cat_name = self.current_category
        self["title"].setText(_("Select {} unit").format(cat_name))

        attr_map = {
            "wind": "wind_unit",
            "pressure": "pressure_unit",
            "temperature": "temp_unit",
            "precipitation": "precip_unit"
        }
        attr_name = attr_map[cat_key]
        current_unit = getattr(self.unit_manager, attr_name)

        items = []
        for label, unit in options:
            marker = "✓ " if unit == current_unit else "  "
            items.append(f"{marker}{label}")

        self["list"].setList(items)
        self["info"].setText(
            _("Current: {}").format(
                self._get_current_label()))

        # Posiziona il cursore sull'opzione corrente (usa moveToIndex)
        for idx, (label, unit) in enumerate(options):
            if unit == current_unit:
                if self["list"].instance and 0 <= idx < len(items):
                    self["list"].moveToIndex(idx)
                break

    def _get_current_label(self):
        cat_key, options, ds = self.current_category
        attr_map = {
            "wind": "wind_unit",
            "pressure": "pressure_unit",
            "temperature": "temp_unit",
            "precipitation": "precip_unit"
        }
        attr_name = attr_map[cat_key]
        current_unit = getattr(self.unit_manager, attr_name)
        for label, unit in options:
            if unit == current_unit:
                return label
        return "?"

    def up(self):
        self["list"].up()

    def down(self):
        self["list"].down()

    def next_category(self):
        self.category_index = (self.category_index + 1) % len(self.categories)
        self.current_category = self.categories[self.category_index]
        self.update_list()

    def prev_category(self):
        self.category_index = (self.category_index - 1) % len(self.categories)
        self.current_category = self.categories[self.category_index]
        self.update_list()

    def select_current(self):
        """Select the highlighted unit for the current category"""
        idx = self["list"].getSelectedIndex()
        if idx is None:
            return
        cat_key, options, _ = self.current_category
        selected_label, selected_unit = options[idx]

        # Set the unit using the appropriate method
        if cat_key == "wind":
            self.unit_manager.set_wind_unit(selected_unit)
        elif cat_key == "pressure":
            self.unit_manager.set_pressure_unit(selected_unit)
        elif cat_key == "temperature":
            self.unit_manager.set_temp_unit(selected_unit)
        elif cat_key == "precipitation":
            self.unit_manager.set_precip_unit(selected_unit)

        self.update_list()

    def save_and_exit(self):
        self.unit_manager.save_config()
        self.close(True)
