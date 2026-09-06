#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) @Lululla 2026
# unit_manager.py - Base Foreca One map viewer
# unit_settings_simple - Simplified unit settings screen
# unit_settings_advanced.py - Advanced unit of measurement settings

from os.path import join, exists
from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Components.ActionMap import HelpableActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.Sources.StaticText import StaticText
from Components.MenuList import MenuList

from . import (
    _,
    DEBUG,
    load_skin_for_class,
    apply_global_theme,
    PLUGIN_PATH,
    SYSTEM_DIR
)

global rgbmyr, rgbmyg, rgbmyb, alpha

rgbmyr = 0
rgbmyg = 80
rgbmyb = 239
alpha = '#40000000'
PRECIP_MM = 'mm'
PRECIP_IN = 'in'


def read_alpha():
    global alpha
    alpha = '#40000000'
    if exists(join(SYSTEM_DIR, "set_alpha.conf")) is True:
        try:
            with open(join(SYSTEM_DIR, "set_alpha.conf"), "r") as file:
                contents = file.readlines()
                a = str(contents[0])
                alpha = a.rstrip()
                file.close()
        except BaseException:
            alpha = '#40000000'


read_alpha()


class UnitManager:

    # Define constants for unit systems
    SYSTEM_METRIC = 'metric'
    SYSTEM_IMPERIAL = 'imperial'
    MODE_SIMPLE = 'simple'
    MODE_ADVANCED = 'advanced'

    # Define constants for specific units
    WIND_KMH = 'KMH'
    WIND_MS = 'MS'
    WIND_KTS = 'KTS'
    WIND_MPH = 'MPH'

    PRESSURE_HPA = 'HPA'
    PRESSURE_MMHG = 'MMHG'
    PRESSURE_INHG = 'INHG'

    PRECIP_MM = 'mm'
    PRECIP_IN = 'in'

    TEMP_C = 'C'
    TEMP_F = 'F'

    def __init__(self, config_path):
        self.config_path = config_path
        self.system = self.SYSTEM_METRIC
        self.mode = self.MODE_SIMPLE
        self.wind_unit = self.WIND_KMH
        self.pressure_unit = self.PRESSURE_HPA
        self.temp_unit = self.TEMP_C
        self.precip_unit = self.PRECIP_MM
        self.readsetcolor()
        self.load_config()

    def load_config(self):
        """Load unit configuration from file"""
        CONFIG_FILE = join(self.config_path, 'units.conf')
        if exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    for line in f:
                        if '=' in line:
                            key, value = line.strip().split('=', 1)
                            if key == 'system':
                                self.system = value
                            elif key == 'mode':
                                self.mode = value
                            elif key == 'wind_unit':
                                self.wind_unit = value
                            elif key == 'pressure_unit':
                                self.pressure_unit = value
                            elif key == 'temp_unit':
                                self.temp_unit = value
                            elif key == 'precip_unit':
                                self.precip_unit = value
            except Exception as e:
                print(f"[UnitManager] Error loading config: {e}")

    def save_config(self):
        """Save unit configuration to file"""
        try:
            CONFIG_FILE = join(self.config_path, 'units.conf')
            with open(CONFIG_FILE, 'w') as f:
                f.write(f"system={self.system}\n")
                f.write(f"mode={self.mode}\n")
                f.write(f"wind_unit={self.wind_unit}\n")
                f.write(f"pressure_unit={self.pressure_unit}\n")
                f.write(f"temp_unit={self.temp_unit}\n")
                f.write(f"precip_unit={self.precip_unit}\n")
        except Exception as e:
            print(f"[UnitManager] Error saving config: {e}")

    def set_wind_unit(self, unit):
        """Set the wind unit (KMH, MS, MPH, KTS) and switch to advanced mode"""
        self.wind_unit = unit
        self.mode = self.MODE_ADVANCED
        if unit in [self.WIND_KMH, self.WIND_MS]:
            self.system = self.SYSTEM_METRIC
        elif unit == self.WIND_MPH:
            self.system = self.SYSTEM_IMPERIAL
        self.save_config()

    def set_pressure_unit(self, unit):
        self.pressure_unit = unit
        self.mode = self.MODE_ADVANCED
        self.save_config()

    def set_temp_unit(self, unit):
        self.temp_unit = unit
        self.mode = self.MODE_ADVANCED
        self.save_config()

    def set_precip_unit(self, unit):
        self.precip_unit = unit
        self.mode = self.MODE_ADVANCED
        self.save_config()

    def readsetcolor(self):
        global rgbmyr, rgbmyg, rgbmyb
        rgbmyr = 0
        rgbmyg = 80
        rgbmyb = 239
        if exists(
                join(SYSTEM_DIR, "set_color.conf")) is True:
            try:
                with open(join(SYSTEM_DIR, "set_color.conf"), "r") as file:
                    contents = file.readlines()
                    a = str(contents[0])
                    trspz = a.rstrip()
                    rgbmyr = trspz.split(' ')[0]
                    rgbmyg = trspz.split(' ')[1]
                    rgbmyb = trspz.split(' ')[2]
                    file.close()
            except BaseException:
                rgbmyr = 0
                rgbmyg = 80
                rgbmyb = 239

    def set_simple_unit_system(self, system):
        """
        Set a simplified unit system (metric or imperial)
        system: 'metric' or 'imperial'
        """
        self.mode = self.MODE_SIMPLE
        self.system = system
        if system == self.SYSTEM_METRIC:
            self.wind_unit = self.WIND_KMH
            self.pressure_unit = self.PRESSURE_HPA
            self.temp_unit = self.TEMP_C
            self.precip_unit = self.PRECIP_MM
        elif system == self.SYSTEM_IMPERIAL:

            self.wind_unit = self.WIND_MPH
            self.pressure_unit = self.PRESSURE_INHG
            self.temp_unit = self.TEMP_F
            self.precip_unit = self.PRECIP_IN

        self.save_config()

    def get_simple_system(self):
        """Return the current simplified system"""
        return self.system

    def convert_temperature(self, temp_c):
        """
        Convert temperature from Celsius to configured unit.
        Returns (value, unit_label)
        """
        try:
            temp = float(temp_c)
        except (ValueError, TypeError):
            return ('N/A', self.get_temp_label())
        if self.temp_unit == self.TEMP_F:
            return (temp * 9.0 / 5.0 + 32, self.get_temp_label())
        return (temp, self.get_temp_label())

    def convert_wind(self, speed_ms):
        """
        Convert wind speed from m/s to configured unit.
        Returns (value, unit_label)
        """
        try:
            speed = float(speed_ms)
        except (ValueError, TypeError):
            return (0.0, self.get_wind_label())
        if self.wind_unit == self.WIND_KMH:
            return (speed * 3.6, self.get_wind_label())
        elif self.wind_unit == self.WIND_KTS:
            return (speed * 1.94384, self.get_wind_label())
        elif self.wind_unit == self.WIND_MPH:
            return (speed * 2.23694, self.get_wind_label())
        else:  # m/s
            return (speed, self.get_wind_label())

    def convert_pressure(self, pressure_hpa):
        """
        Convert pressure from hPa to configured unit.
        Returns (value, unit_label)
        """
        try:
            press = float(pressure_hpa)
        except (ValueError, TypeError):
            return (0.0, self.get_pressure_label())
        if self.pressure_unit == self.PRESSURE_MMHG:
            return (press * 0.750062, self.get_pressure_label())
        elif self.pressure_unit == self.PRESSURE_INHG:
            return (press * 0.02953, self.get_pressure_label())
        else:  # hPa
            return (press, self.get_pressure_label())

    def convert_precipitation(self, precip_mm):
        """
        Convert precipitation from mm to configured unit.
        Returns (value, unit_label)
        """
        try:
            val = float(precip_mm)
        except (ValueError, TypeError):
            return (0.0, self.get_precip_unit())
        if self.precip_unit == self.PRECIP_IN:
            return (val * 0.0393701, self.get_precip_unit())
        return (val, self.get_precip_unit())

    def get_wind_label(self):
        """Get display label for wind unit"""
        labels = {
            self.WIND_KMH: 'km/h',
            self.WIND_MS: 'm/s',
            self.WIND_KTS: 'kts',
            self.WIND_MPH: 'mph'
        }
        return labels.get(self.wind_unit, 'km/h')

    def get_pressure_label(self):
        """Get display label for pressure unit"""
        labels = {
            self.PRESSURE_HPA: 'hPa',
            self.PRESSURE_MMHG: 'mmHg',
            self.PRESSURE_INHG: 'inHg'
        }
        return labels.get(self.pressure_unit, 'hPa')

    def get_temp_label(self):
        """Get display label for temperature unit"""
        return '°C' if self.temp_unit == self.TEMP_C else '°F'

    def get_precip_unit(self):
        """Get display label for precipitation unit (mm or in)"""
        return self.precip_unit

    def get_api_params(self):
        """
        Get parameters for Foreca One API calls based on configuration[citation:2][citation:5].
        Returns dict with windunit and tempunit parameters.
        """
        # Map our internal units to Foreca One API parameter values
        windunit_map = {
            self.WIND_MS: 'MS',
            self.WIND_KMH: 'KMH',
            self.WIND_KTS: 'KTS',
            self.WIND_MPH: 'MPH'
        }

        tempunit_map = {
            self.TEMP_C: 'C',
            self.TEMP_F: 'F'
        }

        return {
            'windunit': windunit_map.get(self.wind_unit, 'MS'),
            'tempunit': tempunit_map.get(self.temp_unit, 'C')
        }


class UnitSettingsSimple(Screen, HelpableScreen):
    """Screen for changing units (metric/imperial) with advanced option"""

    def __init__(self, session, unit_manager):
        self.skin = load_skin_for_class(UnitSettingsSimple)
        Screen.__init__(self, session)
        HelpableScreen.__init__(self)
        self.unit_manager = unit_manager
        self.setTitle(_("Unit Settings"))

        self.current_temp = unit_manager.temp_unit
        self.current_wind = unit_manager.wind_unit
        self.current_pressure = unit_manager.pressure_unit
        self.current_precip = unit_manager.precip_unit

        self["background_plate"] = Label("")
        self["selection_overlay"] = Label("")
        self["key_red"] = StaticText(_("Cancel"))
        self["key_green"] = StaticText(_("Save"))
        self["key_yellow"] = StaticText()
        self["key_blue"] = StaticText(_("Advanced"))
        self["title"] = Label(_("Select unit system"))
        self["info"] = Label(_("Changes apply immediately"))
        self["option_metric"] = Label(_("Metric System"))
        self["metric_details"] = Label(_("Celsius, km/h, hPa"))
        self["option_imperial"] = Label(_("Imperial System"))
        self["imperial_details"] = Label(_("Fahrenheit, mph, inHg"))
        self["check_metric"] = Pixmap()
        self["check_imperial"] = Pixmap()
        self["actions"] = HelpableActionMap(
            self, "ForecaActions",
            {
                "cancel": (self.exit, _("Exit")),
                "red": (self.exit, _("Exit")),
                "green": (self.save, _("Save")),
                "blue": (self.open_advanced, _("Advanced")),
                "left": (self.down, _("Prev")),
                "right": (self.down, _("Next")),
                "up": (self.up, _("Prev")),
                "down": (self.down, _("Next"))
            },
            -2
        )

        self.onLayoutFinish.append(self.update_display)
        self.onLayoutFinish.append(self._apply_theme)

    def _apply_theme(self):
        apply_global_theme(self)

    def update_display(self):
        """Update checkboxes based on current units"""
        # Check if current units match presets
        self["check_metric"].hide()
        self["check_imperial"].hide()
        is_metric = (
            self.current_temp == self.unit_manager.TEMP_C and
            self.current_wind == self.unit_manager.WIND_KMH and
            self.current_pressure == self.unit_manager.PRESSURE_HPA and
            self.current_precip == self.unit_manager.PRECIP_MM
        )
        is_imperial = (
            self.current_temp == self.unit_manager.TEMP_F and
            self.current_wind == self.unit_manager.WIND_MPH and
            self.current_pressure == self.unit_manager.PRESSURE_INHG and
            self.current_precip == self.unit_manager.PRECIP_IN
        )

        check_path = join(PLUGIN_PATH, "images", "check.png")
        empty_path = join(PLUGIN_PATH, "images", "empty.png")

        # Update metric check
        if is_metric:
            if exists(check_path):
                self["check_metric"].instance.setPixmapFromFile(check_path)
        else:
            if exists(empty_path):
                self["check_metric"].instance.setPixmapFromFile(empty_path)

        # Update imperial check
        if is_imperial:
            if exists(check_path):
                self["check_imperial"].instance.setPixmapFromFile(check_path)
        else:
            if exists(empty_path):
                self["check_imperial"].instance.setPixmapFromFile(empty_path)

        self["check_metric"].show()
        self["check_imperial"].show()

    def up(self):
        """Select metric"""
        self.current_temp = self.unit_manager.TEMP_C
        self.current_wind = self.unit_manager.WIND_KMH
        self.current_pressure = self.unit_manager.PRESSURE_HPA
        self.current_precip = self.unit_manager.PRECIP_MM
        self.update_display()

    def down(self):
        """Select imperial"""
        self.current_temp = self.unit_manager.TEMP_F
        self.current_wind = self.unit_manager.WIND_MPH
        self.current_pressure = self.unit_manager.PRESSURE_INHG
        self.current_precip = self.unit_manager.PRECIP_IN
        self.update_display()

    def open_advanced(self):
        """Open advanced unit settings"""
        self.session.openWithCallback(
            self.advanced_closed,
            UnitSettingsAdvanced,
            self.unit_manager)

    def advanced_closed(self, result=None):
        """Callback after advanced settings closed"""
        if result:  # if user saved
            # Reload current units from manager
            self.current_temp = self.unit_manager.temp_unit
            self.current_wind = self.unit_manager.wind_unit
            self.current_pressure = self.unit_manager.pressure_unit
            self.current_precip = self.unit_manager.precip_unit
            self.update_display()

    def save(self):
        """Save preferences"""
        try:
            # Apply current units (can be presets or custom)
            self.unit_manager.set_temp_unit(self.current_temp)
            self.unit_manager.set_wind_unit(self.current_wind)
            self.unit_manager.set_pressure_unit(self.current_pressure)
            self.unit_manager.set_precip_unit(self.current_precip)
            self.close(True)
        except Exception as e:
            print(f"[UnitSettings] Error saving: {e}")
            self.close(False)

    def exit(self):
        self.close(False)


class UnitSettingsAdvanced(Screen, HelpableScreen):
    """Screen for advanced selection of measurement units"""

    def __init__(self, session, unit_manager):
        self.skin = load_skin_for_class(UnitSettingsAdvanced)
        Screen.__init__(self, session)
        HelpableScreen.__init__(self)
        self.unit_manager = unit_manager
        self.setTitle(_("Advanced Unit Settings"))

        # Available options
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
        self["key_yellow"] = StaticText(_("Prev"))
        self["key_blue"] = StaticText(_("Next"))

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
                "blue": (self.next_category, _("Next")),
                "yellow": (self.prev_category, _("Prev")),
                "left": (self.prev_category, _("Prev")),
                "right": (self.next_category, _("Next")),
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
        if DEBUG:
            print(
                f"[UnitSettingsAdvanced] update_list called for category: {self.current_category[2]}")
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

        for idx, (label, unit) in enumerate(options):
            if unit == current_unit:
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
        if DEBUG:
            print(
                f"[UnitSettingsAdvanced] next_category called, current index: {self.category_index}")
        self.category_index = (self.category_index + 1) % len(self.categories)
        self.current_category = self.categories[self.category_index]
        if DEBUG:
            print(
                f"[UnitSettingsAdvanced] new index: {self.category_index}, category: {self.current_category[2]}")
        self.update_list()

    def prev_category(self):
        if DEBUG:
            print(
                f"[UnitSettingsAdvanced] prev_category called, current index: {self.category_index}")
        self.category_index = (self.category_index - 1) % len(self.categories)
        self.current_category = self.categories[self.category_index]
        if DEBUG:
            print(
                f"[UnitSettingsAdvanced] new index: {self.category_index}, category: {self.current_category[2]}")
        self.update_list()

    def select_current(self):
        idx = self["list"].getSelectedIndex()
        if idx is None:
            return
        cat_key, options, ds = self.current_category
        selected_label, selected_unit = options[idx]

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
