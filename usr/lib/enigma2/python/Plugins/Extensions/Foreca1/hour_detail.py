#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) @Lululla 2026
# hour_detail.py - Detailed view for a single hour with animated icons

import glob
from os.path import exists, join
from enigma import eTimer
from Screens.Screen import Screen
from Components.ActionMap import HelpableActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.Sources.StaticText import StaticText
from enigma import gRGB
from skin import parseColor
from Screens.HelpMenu import HelpableScreen

from . import (
    _,
    PLUGIN_PATH,
    load_skin_for_class,
    apply_global_theme,
    get_icon_path,
    DEBUG
)
from .google_translate import trans
from .foreca_weather_api import _symbol_to_description


class HourDetailView(Screen, HelpableScreen):
    def __init__(
            self,
            session,
            weather_api,
            foreca_preview,
            unit_manager,
            hour_data):
        """
        hour_data: dict containing all available data for the selected hour.
        """
        self.skin = load_skin_for_class(HourDetailView)
        Screen.__init__(self, session)
        HelpableScreen.__init__(self)
        self.weather_api = weather_api
        self.foreca_preview = foreca_preview
        self.unit_manager = unit_manager
        self.hour_data = hour_data

        # Inherit colors and transparency from main screen
        self.rgbmyr = foreca_preview.rgbmyr
        self.rgbmyg = foreca_preview.rgbmyg
        self.rgbmyb = foreca_preview.rgbmyb
        self.alpha = foreca_preview.alpha

        self.setTitle(_("Hour Details"))

        self["title_location"] = Label()
        self["title_datetime"] = Label()
        self["condition_icon"] = Pixmap()
        self["condition_text"] = Label()

        self["summary"] = Label()

        self["temp_label"] = Label(_("Temperature"))
        self["temp_value"] = Label()
        self["temp_icon"] = Pixmap()                 # Folder: "temp"

        self["feels_label"] = Label(_("Feels like"))
        self["feels_value"] = Label()
        self["feels_icon"] = Pixmap()                # Folder: "feels"

        self["wind_dir_label"] = Label(_("Wind direction"))
        self["wind_dir_icon"] = Pixmap()             # (static, no animation)

        self["wind_speed_label"] = Label(_("Wind speed"))
        self["wind_speed_value"] = Label()
        self["wind_speed_icon"] = Pixmap()           # Folder: "windspeed"

        self["precip_label"] = Label(_("Rain Prob."))
        self["precip_value"] = Label()
        self["precip_icon"] = Pixmap()               # Folder: "precip"

        self["humidity_label"] = Label(_("Humidity"))
        self["humidity_value"] = Label()
        self["humidity_icon"] = Pixmap()             # Folder: "humidity"

        self["uvi_label"] = Label(_("UV Index"))
        self["uvi_value"] = Label()
        self["uvi_icon"] = Pixmap()                  # Folder: "uvi"

        self["background_plate"] = Label("")
        self["selection_overlay"] = Label("")
        self["key_red"] = StaticText(_("Exit"))
        self["key_green"] = StaticText(_("Refresh"))
        self["key_yellow"] = StaticText()
        self["key_blue"] = StaticText()

        self["actions"] = HelpableActionMap(
            self, "ForecaActions",
            {
                "cancel": (self.close, _("Exit")),
                "red": (self.close, _("Exit")),
                "green": (self.refresh, _("Refresh")),
            },
            -1
        )

        # ---- Animation support for all icons ----
        self.anim_timer = eTimer()
        self.anim_timer.callback.append(self._next_animation_frame)
        self._animations = {}  # {widget_name: {"frames": [], "current": 0, "running": False}}

        self.onLayoutFinish.append(self.update_display)
        self.onLayoutFinish.append(self._apply_theme)
        self.onClose.append(self._stop_all_animations)

    def _apply_theme(self):
        apply_global_theme(self)

    def refresh(self):
        self.update_display()

    # ---------- Animation methods ----------
    def _start_animation(self, widget_name, frames):
        if DEBUG:
            print(
                f"[HourDetail] Starting animation for {widget_name}, {len(frames)} frames")
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
                print(f"[HourDetail] Found {len(frames)} frames in {anim_dir}")
            return frames
        return []

    # ---------- UI Update ----------
    def update_display(self):
        # Stop all running animations before reloading
        self._stop_all_animations()

        # Location and date/time
        location = f"{self.hour_data['town']}, {trans(self.hour_data['country'])}"
        dt = f"{self.hour_data['date']} {self.hour_data['day']} - {self.hour_data['time']}"
        self["title_location"].setText(location)
        self["title_datetime"].setText(dt)

        # ---- 1. Weather condition (animated) ----
        # Folder: codes like "d000", "n000", etc. (already present)
        condition = self.hour_data['condition']
        frames_cond = self._load_animated_frames(condition)
        if frames_cond:
            self._start_animation("condition_icon", frames_cond)
        else:
            icon_path = get_icon_path(f"{condition}.png")
            if icon_path:
                self["condition_icon"].instance.setPixmapFromFile(icon_path)
                self["condition_icon"].show()
            else:
                self["condition_icon"].hide()
            self._stop_animation("condition_icon")

        desc = _symbol_to_description(condition)
        self["condition_text"].setText(trans(desc))

        # ---- 2. Temperature (value + animated icon) ----
        # Folder: "temp"
        try:
            temp_val = float(self.hour_data['temp'])
            converted, unit = self.unit_manager.convert_temperature(temp_val)
            self["temp_value"].setText(f"{converted:.0f}{unit}")
        except BaseException:
            self["temp_value"].setText("N/A")
        frames_temp = self._load_animated_frames("temp")
        if frames_temp:
            self._start_animation("temp_icon", frames_temp)
        else:
            temp_icon = join(PLUGIN_PATH, "images", "temp.png")
            if exists(temp_icon):
                self["temp_icon"].instance.setPixmapFromFile(temp_icon)
                self["temp_icon"].show()
            else:
                self["temp_icon"].hide()
            self._stop_animation("temp_icon")

        # ---- 3. Feels like (value + animated icon) ----
        # Folder: "feels"
        try:
            feels_val = float(self.hour_data['feels_like'])
            converted, unit = self.unit_manager.convert_temperature(feels_val)
            self["feels_value"].setText(f"{converted:.0f}{unit}")
        except BaseException:
            self["feels_value"].setText("N/A")
        frames_feels = self._load_animated_frames("feels")
        if frames_feels:
            self._start_animation("feels_icon", frames_feels)
        else:
            feels_icon = join(PLUGIN_PATH, "images", "temp_perc_detail.png")
            if exists(feels_icon):
                self["feels_icon"].instance.setPixmapFromFile(feels_icon)
                self["feels_icon"].show()
            else:
                self["feels_icon"].hide()
            self._stop_animation("feels_icon")

        # ---- 4. Wind direction (static icon only, no animation) ----
        wind_dir = self.hour_data['wind_dir']
        wind_icon_path = join(PLUGIN_PATH, "thumb", f"{wind_dir}.png")
        if exists(wind_icon_path):
            self["wind_dir_icon"].instance.setPixmapFromFile(wind_icon_path)
        else:
            fallback = join(PLUGIN_PATH, "thumb", "wN.png")
            if exists(fallback):
                self["wind_dir_icon"].instance.setPixmapFromFile(fallback)
        self["wind_dir_icon"].show()

        # ---- 5. Wind speed (value + animated icon) ----
        # Folder: "windspeed"
        try:
            speed = float(self.hour_data['wind_speed'])
            converted, unit = self.unit_manager.convert_wind(speed)
            self["wind_speed_value"].setText(f"{converted:.1f} {unit}")
        except BaseException:
            self["wind_speed_value"].setText("N/A")
        frames_wind = self._load_animated_frames("windspeed")
        if frames_wind:
            self._start_animation("wind_speed_icon", frames_wind)
        else:
            wind_speed_icon = join(
                PLUGIN_PATH, "images", "wind_speed_detail.png")
            if exists(wind_speed_icon):
                self["wind_speed_icon"].instance.setPixmapFromFile(
                    wind_speed_icon)
                self["wind_speed_icon"].show()
            else:
                self["wind_speed_icon"].hide()
            self._stop_animation("wind_speed_icon")

        # ---- 6. Precipitation (value + animated icon) ----
        # Folder: "precip"
        precip = self.hour_data['precipitation']
        self["precip_value"].setText(f"{precip}%")
        frames_precip = self._load_animated_frames("precip")
        if frames_precip:
            self._start_animation("precip_icon", frames_precip)
        else:
            precip_icon = join(PLUGIN_PATH, "images", "precipitation.png")
            if exists(precip_icon):
                self["precip_icon"].instance.setPixmapFromFile(precip_icon)
                self["precip_icon"].show()
            else:
                self["precip_icon"].hide()
            self._stop_animation("precip_icon")

        # ---- 7. Humidity (value + animated icon) ----
        # Folder: "humidity"
        hum = self.hour_data['humidity']
        self["humidity_value"].setText(f"{hum}%")
        frames_hum = self._load_animated_frames("humidity")
        if frames_hum:
            self._start_animation("humidity_icon", frames_hum)
        else:
            hum_icon = join(PLUGIN_PATH, "images", "humidity.png")
            if exists(hum_icon):
                self["humidity_icon"].instance.setPixmapFromFile(hum_icon)
                self["humidity_icon"].show()
            else:
                self["humidity_icon"].hide()
            self._stop_animation("humidity_icon")

        # ---- 8. UV Index (value + animated icon) ----
        # Folder: "uvi"
        uvi = self.hour_data['uvi']
        self["uvi_value"].setText(str(uvi))
        frames_uvi = self._load_animated_frames("uvi")
        if frames_uvi:
            self._start_animation("uvi_icon", frames_uvi)
        else:
            uvi_icon = join(PLUGIN_PATH, "images", "uva_detail.png")
            if exists(uvi_icon):
                self["uvi_icon"].instance.setPixmapFromFile(uvi_icon)
                self["uvi_icon"].show()
            else:
                self["uvi_icon"].hide()
            self._stop_animation("uvi_icon")

        summary = self._format_summary()
        self["summary"].setText(summary)

        bg = gRGB(int(self.rgbmyr), int(self.rgbmyg), int(self.rgbmyb))
        self["background_plate"].instance.setBackgroundColor(bg)
        self["selection_overlay"].instance.setBackgroundColor(
            parseColor(self.alpha))

    def _format_summary(self):
        data = self.hour_data
        desc = _symbol_to_description(data['condition'])
        desc_trans = trans(desc)
        try:
            temp_val, temp_unit = self.unit_manager.convert_temperature(
                float(data['temp']))
            feels_val, _dummy = self.unit_manager.convert_temperature(
                float(data['feels_like']))
            wind_val, wind_unit = self.unit_manager.convert_wind(
                float(data['wind_speed']))
        except Exception as e:
            print(f"[HourDetail] Conversion error: {e}")
            temp_val = feels_val = wind_val = 0
            temp_unit = wind_unit = ""

        summary = f"{desc_trans}. {_('Temp')}: {temp_val:.0f}{temp_unit}, {_('Feels like')}: {feels_val:.0f}{temp_unit}. "
        summary += f"{_('Wind')}: {wind_val:.1f} {wind_unit} {data['wind_dir']}. "
        summary += f"{_('Rain Prob.')}: {data['precipitation']}%, {_('Humidity')}: {data['humidity']}%, {_('UV')}: {data['uvi']}."
        return summary
