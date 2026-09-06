#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) @Lululla 2026
# favorites_detail.py - Detailed view for all favorites with animated icons

import glob
from os.path import exists, join
from enigma import eTimer
from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Components.ActionMap import HelpableActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.Sources.StaticText import StaticText
from enigma import gRGB
from skin import parseColor

from . import (
    _,
    PLUGIN_PATH,
    load_skin_for_class,
    apply_global_theme,
    get_icon_path,
    DEBUG
)


class FavoritesDetailView(Screen, HelpableScreen):
    def __init__(self, session, weather_api, foreca_preview, unit_manager):
        self.skin = load_skin_for_class(FavoritesDetailView)
        Screen.__init__(self, session)
        HelpableScreen.__init__(self)
        self.api = weather_api
        self.fp = foreca_preview
        self.units = unit_manager

        self.favs = [
            (_("Home"), foreca_preview.path_loc0),
            (_("Favorite 1"), foreca_preview.path_loc1),
            (_("Favorite 2"), foreca_preview.path_loc2),
        ]

        self.setTitle(_("Favorites Details"))

        # Colors from main screen
        self.rgbmyr = foreca_preview.rgbmyr
        self.rgbmyg = foreca_preview.rgbmyg
        self.rgbmyb = foreca_preview.rgbmyb
        self.alpha = foreca_preview.alpha

        # Create widgets for each favorite (0,1,2)
        for i in range(3):
            # City name
            self[f"city_name_{i}"] = Label()
            # Weather icon
            self[f"weather_icon_{i}"] = Pixmap()
            # Current temperature
            self[f"temp_current_{i}"] = Label()
            # Min/Max temperature
            self[f"temp_minmax_{i}"] = Label()
            # Wind direction icon
            self[f"wind_dir_icon_{i}"] = Pixmap()
            # Wind speed
            self[f"wind_speed_{i}"] = Label()
            # Humidity
            # self["icon_humidity"] = Pixmap()
            self[f"humidity_{i}"] = Label()
            self[f"humidity_icon_{i}"] = Pixmap()

            # Pressure
            # self["icon_pressure"] = Pixmap()
            self[f"pressure_{i}"] = Label()
            self[f"pressure_icon_{i}"] = Pixmap()
            # Sunrise time

            self[f"sunrise_{i}"] = Label()
            # Sunset time
            self[f"sunset_{i}"] = Label()

        # Static labels for headers
        self["title"] = Label(_("Favorites Details"))
        self["header_temp"] = Label(_("Temp"))
        self["header_wind"] = Label(_("Wind"))
        self["header_hum"] = Label(_("Humidity"))
        self["header_press"] = Label(_("Pressure"))
        self["header_temp1"] = Label(_("Temp"))
        self["header_wind1"] = Label(_("Wind"))
        self["header_hum1"] = Label(_("Humidity"))
        self["header_press1"] = Label(_("Pressure"))
        self["header_temp2"] = Label(_("Temp"))
        self["header_wind2"] = Label(_("Wind"))
        self["header_hum2"] = Label(_("Humidity"))
        self["header_press2"] = Label(_("Pressure"))
        self["background_plate"] = Label("")
        self["selection_overlay"] = Label("")
        self["key_red"] = StaticText(_("Exit"))
        self["actions"] = HelpableActionMap(
            self, "ForecaActions",
            {
                "cancel": (self.close, _("Exit")),
                "red": (self.close, _("Exit")),
            },
            -1
        )

        # ---- Animation support ----
        self.anim_timer = eTimer()
        self.anim_timer.callback.append(self._next_animation_frame)
        self._animations = {}  # {widget_name: {"frames": [], "current": 0, "running": False}}

        self.onLayoutFinish.append(self.load_data)
        self.onLayoutFinish.append(self._apply_theme)
        self.onClose.append(self._stop_all_animations)

    def _apply_theme(self):
        apply_global_theme(self)

    # ---------- Animation methods ----------
    def _start_animation(self, widget_name, frames):
        if DEBUG:
            print(
                f"[FavoritesDetail] Starting animation for {widget_name}, {len(frames)} frames")
        if widget_name not in self._animations:
            self._animations[widget_name] = {
                "frames": [], "current": 0, "running": False}
        anim = self._animations[widget_name]
        if anim["running"]:
            anim["running"] = False
        anim["frames"] = frames
        anim["current"] = 0
        anim["running"] = True
        if not self.anim_timer.isActive():
            self.anim_timer.start(200)

    def _next_animation_frame(self):
        any_running = False
        for widget_name, anim in self._animations.items():
            if not anim["running"]:
                continue
            frames = anim["frames"]
            if not frames:
                anim["running"] = False
                continue
            any_running = True
            current = anim["current"]
            frame_path = frames[current]
            widget = self[widget_name]
            if widget and widget.instance:
                widget.instance.setPixmapFromFile(frame_path)
                widget.show()
            anim["current"] = (current + 1) % len(frames)
        if not any_running and self.anim_timer.isActive():
            self.anim_timer.stop()

    def _stop_animation(self, widget_name):
        if widget_name in self._animations:
            self._animations[widget_name]["running"] = False
            self._animations[widget_name]["frames"] = []

    def _stop_all_animations(self):
        if self.anim_timer.isActive():
            self.anim_timer.stop()
        self._animations.clear()

    def _load_animated_frames(self, folder_name):
        """
        Look for frames in: PLUGIN_PATH/animated_icons/{folder_name}/*.png
        Returns sorted list or empty list.
        """
        anim_dir = join(PLUGIN_PATH, "animated_icons", folder_name)
        if exists(anim_dir):
            frames = sorted(glob.glob(join(anim_dir, "*.png")))
            if DEBUG:
                print(
                    f"[FavoritesDetail] Found {len(frames)} frames in {anim_dir}")
            return frames
        return []

    # ---------- Load data with animations ----------
    def load_data(self):
        # Stop any previous animations
        self._stop_all_animations()

        for i, (label, path) in enumerate(self.favs):
            location_id = path.split('/')[0] if '/' in path else path
            # Get location name
            place = self.api.get_location_by_id(location_id)
            if place:
                city_display = f"{place.name}, {place.country_name}"
            else:
                city_display = label  # fallback

            self[f"city_name_{i}"].setText(city_display)

            # Get current weather
            current = self.api.get_current_weather(location_id)
            if current:
                # Temperature
                temp_val, temp_unit = self.units.convert_temperature(
                    current.temp)
                self[f"temp_current_{i}"].setText(f"{temp_val:.0f}{temp_unit}")

                # ---- Weather icon (animated) ----
                condition = current.condition
                frames_cond = self._load_animated_frames(condition)
                if frames_cond:
                    self._start_animation(f"weather_icon_{i}", frames_cond)
                else:
                    icon_path = get_icon_path(f"{condition}.png")
                    if icon_path:
                        self[f"weather_icon_{i}"].instance.setPixmapFromFile(
                            icon_path)
                        self[f"weather_icon_{i}"].show()
                    else:
                        self[f"weather_icon_{i}"].hide()
                    self._stop_animation(f"weather_icon_{i}")

                # ---- Wind direction icon (animated) ----
                wind_dir_code = self.fp.degreesToWindDirection(
                    current.wind_direction)
                frames_wind = self._load_animated_frames(wind_dir_code)
                if frames_wind:
                    self._start_animation(f"wind_dir_icon_{i}", frames_wind)
                else:
                    wind_icon_path = get_icon_path(f"{wind_dir_code}.png")
                    if wind_icon_path:
                        self[f"wind_dir_icon_{i}"].instance.setPixmapFromFile(
                            wind_icon_path)
                        self[f"wind_dir_icon_{i}"].show()
                    else:
                        self[f"wind_dir_icon_{i}"].hide()
                    self._stop_animation(f"wind_dir_icon_{i}")

                # Wind speed
                wind_val, wind_unit = self.units.convert_wind(
                    current.wind_speed)
                self[f"wind_speed_{i}"].setText(f"{wind_val:.1f} {wind_unit}")

                # ---- Humidity (value + icon animation) ----
                if current.humidity is not None:
                    self[f"humidity_{i}"].setText(f"{current.humidity}%")
                else:
                    self[f"humidity_{i}"].setText("N/A")

                frames_hum = self._load_animated_frames("humidity")
                if frames_hum:
                    self._start_animation(f"humidity_icon_{i}", frames_hum)
                else:
                    static_hum = join(PLUGIN_PATH, "images", "humidity.png")
                    if exists(static_hum):
                        self[f"humidity_icon_{i}"].instance.setPixmapFromFile(
                            static_hum)
                        self[f"humidity_icon_{i}"].show()
                    else:
                        self[f"humidity_icon_{i}"].hide()
                    self._stop_animation(f"humidity_icon_{i}")

                # ---- Pressure (value + icon animation) ----
                if current.pressure is not None:
                    press_val, press_unit = self.units.convert_pressure(
                        current.pressure)
                    if press_unit == 'inHg':
                        press_text = f"{press_val:.2f} {press_unit}"
                    else:
                        press_text = f"{press_val:.0f} {press_unit}"
                    self[f"pressure_{i}"].setText(press_text)
                else:
                    self[f"pressure_{i}"].setText("N/A")

                frames_press = self._load_animated_frames("pressure")
                if frames_press:
                    self._start_animation(f"pressure_icon_{i}", frames_press)
                else:
                    static_press = join(PLUGIN_PATH, "images", "barometer.png")
                    if exists(static_press):
                        self[f"pressure_icon_{i}"].instance.setPixmapFromFile(
                            static_press)
                        self[f"pressure_icon_{i}"].show()
                    else:
                        self[f"pressure_icon_{i}"].hide()
                    self._stop_animation(f"pressure_icon_{i}")

                # Sunrise / Sunset from daily forecast (day 0)
                daily = self.api.get_daily_forecast(location_id, days=1)
                if daily and len(daily) > 0:
                    day0 = daily[0]
                    if day0.sunrise:
                        self[f"sunrise_{i}"].setText(
                            day0.sunrise.strftime("%H:%M"))
                    else:
                        self[f"sunrise_{i}"].setText("--:--")
                    if day0.sunset:
                        self[f"sunset_{i}"].setText(
                            day0.sunset.strftime("%H:%M"))
                    else:
                        self[f"sunset_{i}"].setText("--:--")
                    # Min/Max temperature
                    min_val, _ = self.units.convert_temperature(day0.min_temp)
                    max_val, _ = self.units.convert_temperature(day0.max_temp)
                    self[f"temp_minmax_{i}"].setText(
                        f"{int(min_val)} - {int(max_val)}{temp_unit[-1]}")
                else:
                    self[f"sunrise_{i}"].setText("--:--")
                    self[f"sunset_{i}"].setText("--:--")
                    self[f"temp_minmax_{i}"].setText("N/A")
            else:
                # No data – clear everything
                self[f"temp_current_{i}"].setText("N/A")
                self[f"temp_minmax_{i}"].setText("N/A")
                self[f"wind_speed_{i}"].setText("N/A")
                self[f"humidity_{i}"].setText("N/A")
                self[f"pressure_{i}"].setText("N/A")
                self[f"sunrise_{i}"].setText("--:--")
                self[f"sunset_{i}"].setText("--:--")
                self[f"weather_icon_{i}"].hide()
                self[f"wind_dir_icon_{i}"].hide()
                self[f"humidity_icon_{i}"].hide()
                self[f"pressure_icon_{i}"].hide()
                self._stop_animation(f"weather_icon_{i}")
                self._stop_animation(f"wind_dir_icon_{i}")
                self._stop_animation(f"humidity_icon_{i}")
                self._stop_animation(f"pressure_icon_{i}")

        # Apply background colors
        bg = gRGB(int(self.rgbmyr), int(self.rgbmyg), int(self.rgbmyb))
        self["background_plate"].instance.setBackgroundColor(bg)
        self["selection_overlay"].instance.setBackgroundColor(
            parseColor(self.alpha))
