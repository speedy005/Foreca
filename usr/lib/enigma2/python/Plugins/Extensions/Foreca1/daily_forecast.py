#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# daily_forecast.py - Weekly detailed forecast screen

from os.path import join, exists
from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Screens.MessageBox import MessageBox

from Components.ActionMap import HelpableActionMap
from Components.Label import Label
from Components.Sources.List import List

from Tools.LoadPixmap import LoadPixmap

from . import (
    _,
    load_skin_for_class,
    apply_global_theme,
    PLUGIN_PATH,
    get_icon_path
)
from .google_translate import trans
from .foreca_weather_api import _symbol_to_description


def _celsius_to_fahrenheit(c):
    return (c * 9.0 / 5.0) + 32


def _degrees_to_cardinal(deg):
    try:
        deg = int(deg) % 360
        directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
        return directions[round(deg / 45) % 8]
    except BaseException:
        return 'N'


class DailyForecast(Screen, HelpableScreen):
    def __init__(self, session, api, location_id, location_name):
        self.skin = load_skin_for_class(DailyForecast)
        Screen.__init__(self, session)
        HelpableScreen.__init__(self)
        self.api = api
        self.location_id = location_id
        self.location_name = location_name
        self.forecast_days = []
        self.list = []
        self.setTitle(_("Weekly Forecast") + " - " + location_name)
        self["title"] = Label("")
        self["info"] = Label(_("Loading weekly forecast..."))
        self["menu"] = List(self.list)
        self["background_plate"] = Label("")
        self["selection_overlay"] = Label("")
        self["actions"] = HelpableActionMap(
            self, "ForecaActions",
            {
                "cancel": (self.exit, _("Exit")),
                "ok": (self.show_day_details, _("Details")),
                "up": (self["menu"].up, _("Move up")),
                "down": (self["menu"].down, _("Move down")),
                "pageUp": (self["menu"].pageUp, _("Page up")),
                "pageDown": (self["menu"].pageDown, _("Page down")),
            },
            -1
        )

        self.onLayoutFinish.append(self.load_forecast)
        self.onLayoutFinish.append(self._apply_theme)

    def _apply_theme(self):
        apply_global_theme(self)

    def load_forecast(self):
        self["info"].setText(_("Loading weekly forecast..."))
        try:
            self.forecast_days = self.api.get_daily_forecast(
                self.location_id, days=7)
        except Exception as e:
            print(f"[DailyForecast] API error: {e}")
            self.forecast_days = []

        if not self.forecast_days:
            self["info"].setText(_("Could not load forecast data"))
            return

        self["title"].setText(f"{self.location_name} - {_('7 Day Forecast')}")
        self["info"].setText(_("Use arrow keys to scroll"))

        self.list = []
        self.list.append(self._create_header_entry())
        # Days
        for day in self.forecast_days:
            self.list.append(self._create_day_entry(day))
        self.list.append(self._create_footer_entry())

        self["menu"].setList(self.list)

    def _create_header_entry(self):
        return (
            None,                   # 0: icon (none)
            _("Day"),               # 1: day
            _("Temp"),              # 2: temperature
            _("Weather"),           # 3: description
            _("Precipitation"),     # 4: precipitation
            None,                   # 5: (no icon)
            _("Wind"),              # 6: wind
        )

    def _create_day_entry(self, day):
        # Date and day
        date_str = day.date.strftime("%d.%m") if day.date else "??.??"
        day_name = _(day.date.strftime("%A")[:3]) if day.date else "???"
        day_display = f"{day_name} {date_str}"

        # Temperature with unit
        if hasattr(self.api, 'unit_manager') and self.api.unit_manager:
            min_val, temp_unit = self.api.unit_manager.convert_temperature(
                day.min_temp)
            max_val, _unused = self.api.unit_manager.convert_temperature(
                day.max_temp)
            temp_str = f"{int(min_val)} - {int(max_val)}{temp_unit[-1]}"
        else:
            temp_str = f"{day.min_temp} - {day.max_temp}C"

        # Weather description
        desc = _symbol_to_description(day.condition)
        weather = trans(desc)
        if len(weather) > 60:
            weather = weather[:60] + "."

        # Weather icon
        icon_path = get_icon_path(f"{day.condition}.png")
        if icon_path:
            icon = LoadPixmap(cached=True, path=icon_path)
        else:
            icon = None

        # Precipitation
        if hasattr(self.api, 'unit_manager') and self.api.unit_manager:
            precip_val, precip_unit = self.api.unit_manager.convert_precipitation(
                day.precipitation)
            precip = f"{precip_val:.1f}{precip_unit}"
        else:
            precip = f"{day.precipitation} mm"

        # Icona vento
        wind_icon_name = "w" + _degrees_to_cardinal(day.wind_direction)
        wind_icon_path = join(PLUGIN_PATH, "thumb", f"{wind_icon_name}.png")
        if not exists(wind_icon_path):
            wind_icon_path = join(PLUGIN_PATH, "thumb", "wN.png")
        wind_icon = LoadPixmap(cached=True, path=wind_icon_path)

        # Wind
        wind_dir = _degrees_to_cardinal(day.wind_direction)
        if hasattr(self.api, 'unit_manager') and self.api.unit_manager:
            wind_val, wind_unit = self.api.unit_manager.convert_wind(
                day.wind_speed)
            wind_val = int(wind_val)
            wind_str = f"{wind_val} {wind_unit} {wind_dir}"
        else:
            wind_val = int(day.wind_speed * 3.6)
            wind_str = f"{wind_val} km/h {wind_dir}"

        return (
            icon,          # 0
            day_display,   # 1
            temp_str,      # 2
            weather,       # 3
            precip,        # 4
            wind_icon,     # 5
            wind_str,      # 6
        )

    def _create_footer_entry(self):
        return (
            None,
            "",
            "",
            _("Data provided by Foreca"),
            "",
            None,
            ""
        )

    def show_day_details(self):
        idx = self["menu"].getIndex()
        if idx <= 0 or idx >= len(self.forecast_days) + 1:
            return
        day = self.forecast_days[idx - 1]

        lines = []
        lines.append(_("Date: {}").format(day.date))

        # --- Temperature with conversion ---
        if hasattr(self.api, 'unit_manager') and self.api.unit_manager:
            min_val, temp_unit = self.api.unit_manager.convert_temperature(
                day.min_temp)
            max_val, unused = self.api.unit_manager.convert_temperature(
                day.max_temp)
            temp_str = f"{int(min_val)}-{int(max_val)}{temp_unit}"
        else:
            temp_str = f"{day.min_temp}-{day.max_temp}°C"
        lines.append(_("Temperature: {}").format(temp_str))

        # --- Wind with conversion ---
        if hasattr(self.api, 'unit_manager') and self.api.unit_manager:
            wind_val, wind_unit = self.api.unit_manager.convert_wind(
                day.wind_speed)
            wind_val = round(wind_val, 1)
            wind_dir = _degrees_to_cardinal(day.wind_direction)
            wind_str = f"{wind_val} {wind_unit} {wind_dir}"
        else:
            wind_str = f"{day.wind_speed} km/h {_degrees_to_cardinal(day.wind_direction)}"
        lines.append(_("Wind: {}").format(wind_str))

        # --- Precipitation (already converted) ---
        if hasattr(self.api, 'unit_manager') and self.api.unit_manager:
            precip_val, precip_unit = self.api.unit_manager.convert_precipitation(
                day.precipitation)
            precip_str = f"{precip_val:.1f}{precip_unit}"
        else:
            precip_str = f"{day.precipitation} mm"
        lines.append(_("Precipitation: {}").format(precip_str))

        lines.append(_("Humidity: {}%").format(day.humidity))
        lines.append(
            _("Condition: {}").format(
                trans(
                    _symbol_to_description(
                        day.condition))))

        details = "\n".join(lines)
        self.session.open(MessageBox, details, MessageBox.TYPE_INFO)

    def exit(self):
        self.close()
