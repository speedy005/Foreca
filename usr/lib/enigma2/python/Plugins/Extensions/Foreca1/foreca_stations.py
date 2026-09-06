#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) @Lululla 2026
# foreca_stations.py - Display nearby station observations

from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Screens.MessageBox import MessageBox

from Components.ActionMap import HelpableActionMap
from Components.MenuList import MenuList
from Components.Label import Label

from skin import parseColor

from . import (
    _,
    DEBUG,
    load_skin_for_class,
    apply_global_theme,
)


class ForecaStations(Screen, HelpableScreen):
    """Screen for nearby weather station observations"""

    def __init__(
            self,
            session,
            api_free,
            api_auth,
            location_id,
            location_name,
            unit_manager=None,
            tz=None,
            tz_offset=None):
        self.skin = load_skin_for_class(ForecaStations)
        self.session = session
        self.api_free = api_free
        self.api_auth = api_auth
        self.location_id = location_id
        self.location_name = location_name
        self.unit_manager = unit_manager
        self.tz = tz
        self.tz_offset = tz_offset
        self.observations = []

        Screen.__init__(self, session)
        HelpableScreen.__init__(self)
        self.setTitle(_("Station Observations") + " - " + location_name)
        self["list"] = MenuList([])
        self["background_plate"] = Label("")
        self["selection_overlay"] = Label("")
        self["info"] = Label(_("Loading nearby stations..."))
        self["distance"] = Label()
        self["station_name"] = Label()
        self["temperature"] = Label()
        self["dewpoint"] = Label()
        self["visibility"] = Label()
        self["feels_like"] = Label()
        self["humidity"] = Label()
        self["pressure"] = Label()
        self["wind"] = Label()
        self["actions"] = HelpableActionMap(
            self, "ForecaActions",
            {
                "cancel": (self.close, _("Exit")),
                "red": (self.close, _("Exit")),
                "ok": (self.show_station_popup, _("Details")),
                "up": (self.list_up, _("Move Up")),
                "down": (self.list_down, _("Move Down")),
                "left": (self.key_left, _("Move Up")),
                "right": (self.key_right, _("Move Down"))
            },
            -1
        )
        self.onLayoutFinish.append(self.load_stations)
        self.onLayoutFinish.append(self._apply_theme)

    def _apply_theme(self):
        apply_global_theme(self)

    def load_stations(self):
        self["info"].setText(_("Loading..."))
        observations = []
        self.source = None  # Track the source used

        # 1. Try authenticated API (if available)
        if self.api_auth and hasattr(
                self.api_auth,
                'get_station_observations'):
            try:
                observations = self.api_auth.get_station_observations(
                    self.location_id, station_limit=15)
                if observations:
                    self.source = "API"
                    print("[ForecaStations] Authenticated API used")
            except Exception as e:
                print(f"[ForecaStations] Auth API error: {e}")
                observations = []

        # 2. Fallback to scraping
        if not observations and self.api_free and hasattr(
                self.api_free, 'get_nearby_stations_scraped'):
            try:
                observations = self.api_free.get_nearby_stations_scraped(
                    self.location_id)
                if observations:
                    self.source = _("Scraped")
                    if DEBUG:
                        print("[ForecaStations] Scraping used")
            except Exception as e:
                print(f"[ForecaStations] Scraping error: {e}")

        if not observations:
            self["info"].setText(_("No station data available"))
            self["list"].setList([(_("No stations found"), None)])
            return

        # Build the list (adapted to the data structure)
        items = []
        for obs in observations:
            station_name = obs.get('station', 'Unknown')
            temp = obs.get('temperature', 'N/A')
            if isinstance(temp, (int, float)):
                temp_str = f"+{temp}°" if temp >= 0 else f"{temp}°"
            else:
                temp_str = str(temp)

            if self.source == "API":
                # For API, we have more fields
                distance = obs.get('distance', '?')
                item_text = f"{station_name} ({distance}) - {temp_str}C"
            else:
                # For scraping, we have time_ago
                time_ago = obs.get('time_ago', '')
                item_text = f"{station_name} - {temp_str}C ({time_ago})" if time_ago else f"{station_name} - {temp_str}C"

            items.append((item_text, obs))

        if items:
            self["list"].setList(items)
            self["list"].moveToIndex(0)
            self.show_station_details()
            self["info"].setText(
                _("Foreca One Stations: {} stations nearby ({})").format(
                    len(items), self.source or '?'))
        else:
            self["list"].setList([(_("Foreca One No stations found"), None)])

    def _format_station_details(self, station):
        """Format station details with correct units"""
        lines = []

        # Name and distance
        station_name = station.get('station', 'Unknown')
        lines.append(station_name.upper())
        lines.append("─" * 40)
        lines.append(f"{_('Distance')}: {station.get('distance', 'N/A')}")
        lines.append("")

        # Temperatures (already in correct units)
        temp = station.get('temperature', 'N/A')
        feels = station.get('feelsLikeTemp', 'N/A')

        # Add + sign for positive temperatures
        if isinstance(temp, (int, float)):
            temp_str = f"+{temp}" if temp >= 0 else f"{temp}"
            lines.append(f"{_('Temperature')}: {temp_str}°")
        else:
            lines.append(f"{_('Temperature')}: {temp}")

        if isinstance(feels, (int, float)) and feels != 'N/A':
            feels_str = f"+{feels}" if feels >= 0 else f"{feels}"
            lines.append(f"{_('Feels like')}: {feels_str}°")

        # Other data
        lines.append(f"{_('Humidity')}: {station.get('relHumidity', 'N/A')}%")

        # Pressure (if available)
        pressure = station.get('pressure')
        if pressure:
            lines.append(f"{_('Pressure')}: {pressure} hPa")

        # Wind (already in correct units)
        wind_speed = station.get('windSpeed', 'N/A')
        wind_dir = station.get('windDirString', 'N/A')

        if wind_speed and wind_speed != 'N/A':
            wind_unit = "km/h"  # Or "mph" if imperial
            lines.append(f"{_('Wind')}: {wind_speed} {wind_unit} {wind_dir}")

        # Timestamp
        time_str = station.get('time', '')
        if time_str:
            time_str = self._convert_time(time_str)
            lines.append("")
            lines.append(f"{_('Last update')}: {time_str}")

        return "\n".join(lines)

    def show_station_details(self):
        selection = self["list"].getCurrent()
        if not selection or not selection[1]:
            return

        station = selection[1]
        self["station_name"].setText(station.get('station', _('Unknown')))

        # Distance
        distance = station.get('distance', 'N/A')
        self["distance"].setText(_("Distance: %s") % distance)

        # Temperature
        temp = station.get('temperature')
        if temp is not None and self.unit_manager:
            converted, unit = self.unit_manager.convert_temperature(temp)
            self["temperature"].setText(
                _("Temperature: %d%s") %
                (int(converted), unit))
        else:
            if temp is not None:
                self["temperature"].setText(_("Temperature: %s°C") % temp)
            else:
                self["temperature"].setText(_("Temperature: N/A"))

        # Dew point
        dew = station.get('dewpoint')
        if dew is not None and self.unit_manager:
            converted, unit = self.unit_manager.convert_temperature(dew)
            self["dewpoint"].setText(
                _("Dewpoint: %d%s") %
                (int(converted), unit))
        else:
            if dew is not None:
                self["dewpoint"].setText(_("Dewpoint: %s°C") % dew)
            else:
                self["dewpoint"].setText(_("Dewpoint: N/A"))

        # Visibility
        vis = station.get('visibility', 'N/A')
        self["visibility"].setText(_("Visibility: %s m") % vis)

        # Feels like
        feels = station.get('feelsLikeTemp')
        if feels is not None and self.unit_manager:
            converted, unit = self.unit_manager.convert_temperature(feels)
            self["feels_like"].setText(
                _("Feels like: %d%s") %
                (int(converted), unit))
        else:
            if feels is not None:
                self["feels_like"].setText(_("Feels like: %s°C") % feels)
            else:
                self["feels_like"].setText(_("Feels like: N/A"))

        # Humidity
        hum = station.get('relHumidity', 'N/A')
        self["humidity"].setText(_("Humidity: %s%%") % hum)

        # Pressure
        press = station.get('pressure')
        if press is not None and self.unit_manager:
            converted, unit = self.unit_manager.convert_pressure(press)
            if unit == 'inHg':
                press_str = "%.2f %s" % (converted, unit)
            else:
                press_str = "%d %s" % (int(converted), unit)
            self["pressure"].setText(_("Pressure: %s") % press_str)
        else:
            if press is not None:
                self["pressure"].setText(_("Pressure: %s hPa") % press)
            else:
                self["pressure"].setText(_("Pressure: N/A"))

        # Wind
        wind_speed = station.get('windSpeed')
        wind_dir = station.get('windDirString', '')

        if wind_speed is not None and self.unit_manager:
            converted, unit = self.unit_manager.convert_wind(wind_speed)
            self["wind"].setText(
                _("Wind: %d %s %s") %
                (int(converted), unit, wind_dir))
        else:
            if wind_speed is not None:
                self["wind"].setText(
                    _("Wind: %s km/h %s") %
                    (wind_speed, wind_dir))
            else:
                self["wind"].setText(_("Wind: N/A"))

        self.apply_widget_colors(station)

    def show_station_popup(self):
        """Opens a MessageBox with the details of the selected station."""
        selection = self["list"].getCurrent()
        if not selection or not selection[1]:
            return
        station = selection[1]

        # Collect formatted data
        lines = []
        lines.append(
            _("Station: {}").format(
                station.get(
                    'station',
                    _('Unknown'))))
        lines.append(
            _("Distance: {}").format(
                station.get(
                    'distance',
                    'N/A')))

        # Temperature
        temp = station.get('temperature')
        if temp is not None:
            if self.unit_manager:
                converted, unit = self.unit_manager.convert_temperature(temp)
                lines.append(
                    _("Temperature: {}{}").format(
                        int(converted), unit))
            else:
                lines.append(_("Temperature: {}°C").format(temp))

        # Feels like temperature
        feels = station.get('feelsLikeTemp')
        if feels is not None:
            if self.unit_manager:
                converted, unit = self.unit_manager.convert_temperature(feels)
                lines.append(
                    _("Feels like: {}{}").format(
                        int(converted), unit))
            else:
                lines.append(_("Feels like: {}°C").format(feels))

        # Humidity
        hum = station.get('relHumidity')
        if hum is not None:
            lines.append(_("Humidity: {}%").format(hum))

        # Pressure
        press = station.get('pressure')
        if press is not None:
            if self.unit_manager:
                converted, unit = self.unit_manager.convert_pressure(press)
                if unit == 'inHg':
                    press_str = f"{converted:.2f} {unit}"
                else:
                    press_str = f"{int(converted)} {unit}"
                lines.append(_("Pressure: {}").format(press_str))
            else:
                lines.append(_("Pressure: {} hPa").format(press))

        # Wind
        wind_speed = station.get('windSpeed')
        wind_dir = station.get('windDirString', '')
        if wind_speed is not None:
            if self.unit_manager:
                converted, unit = self.unit_manager.convert_wind(wind_speed)
                lines.append(
                    _("Wind: {} {} {}").format(
                        int(converted), unit, wind_dir))
            else:
                lines.append(
                    _("Wind: {} km/h {}").format(wind_speed, wind_dir))

        # Visibility
        vis = station.get('visibility')
        if vis is not None:
            lines.append(_("Visibility: {} m").format(vis))

        # Update time (if available)
        time_str = station.get('time')
        if time_str:
            time_str = self._convert_time(time_str)
            lines.append(_("Updated: {}").format(time_str))

        details = "\n".join(lines)
        self.session.open(MessageBox, details, MessageBox.TYPE_INFO)

    def apply_widget_colors(self, station):
        station_name = station.get('station', 'Unknown')
        temp = station.get('temperature')
        dew = station.get('dewpoint')
        vis = station.get('visibility')
        feels = station.get('feelsLikeTemp')
        hum = station.get('relHumidity')
        press = station.get('pressure')
        wind_speed = station.get('windSpeed')

        color_station_name = parseColor(
            "#00FF00") if station_name != "Unknown" else parseColor("#AAAAAA")
        color_temperature = parseColor("#FF6347") if isinstance(
            temp, (int, float)) else parseColor("#AAAAAA")
        color_dewpoint = parseColor("#4682B4") if isinstance(
            dew, (int, float)) else parseColor("#AAAAAA")
        color_visibility = parseColor("#32CD32") if isinstance(
            vis, (int, float)) else parseColor("#AAAAAA")
        color_feels_like = parseColor("#FFD700") if isinstance(
            feels, (int, float)) else parseColor("#AAAAAA")
        color_humidity = parseColor("#00FFFF") if isinstance(
            hum, (int, float)) else parseColor("#AAAAAA")
        color_pressure = parseColor("#8A2BE2") if isinstance(
            press, (int, float)) else parseColor("#AAAAAA")
        if isinstance(wind_speed, (int, float)):
            if wind_speed >= 20:
                color_wind = parseColor("#FF0000")
            elif wind_speed >= 10:
                color_wind = parseColor("#FFA500")
            else:
                color_wind = parseColor("#32CD32")
        else:
            color_wind = parseColor("#AAAAAA")

        if self["station_name"].instance:
            self["station_name"].instance.setForegroundColor(
                color_station_name)
        if self["temperature"].instance:
            self["temperature"].instance.setForegroundColor(color_temperature)
        if self["dewpoint"].instance:
            self["dewpoint"].instance.setForegroundColor(color_dewpoint)
        if self["visibility"].instance:
            self["visibility"].instance.setForegroundColor(color_visibility)
        if self["feels_like"].instance:
            self["feels_like"].instance.setForegroundColor(color_feels_like)
        if self["humidity"].instance:
            self["humidity"].instance.setForegroundColor(color_humidity)
        if self["pressure"].instance:
            self["pressure"].instance.setForegroundColor(color_pressure)
        if self["wind"].instance:
            self["wind"].instance.setForegroundColor(color_wind)

    def _convert_time(self, time_str):
        """Converts a UTC ISO timestamp to local time (formatted string)."""
        if not time_str:
            return time_str
        try:
            from datetime import datetime
            utc_dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            if self.tz:
                local_dt = utc_dt.astimezone(self.tz)
            elif self.tz_offset is not None:
                local_dt = utc_dt + datetime.timedelta(hours=self.tz_offset)
            else:
                local_dt = utc_dt
            return local_dt.strftime("%d.%m.%Y %H:%M")
        except Exception as e:
            if DEBUG:
                print(f"[ForecaStations] Error converting time: {e}")
            return time_str

    def list_up(self):
        self["list"].up()
        self.show_station_details()

    def list_down(self):
        self["list"].down()
        self.show_station_details()

    def key_left(self):
        self["list"].up()
        self.show_station_details()

    def key_right(self):
        self["list"].down()
        self.show_station_details()

    def exit(self):
        self.close()
