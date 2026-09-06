#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) @Lululla 2026
# weather_detail.py - Detailed weather view (today/tomorrow) with animated
# symbols

import glob
from os.path import exists, join
from os import makedirs
import requests

from twisted.internet import reactor

from enigma import gRGB, eTimer
from skin import parseColor

from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen

from Components.ActionMap import HelpableActionMap
from Components.Pixmap import Pixmap
from Components.Label import Label
from Components.Sources.StaticText import StaticText

from . import (
    _,
    DEBUG,
    load_skin_for_class,
    apply_global_theme,
    PLUGIN_PATH,
    TEMP_DIR,
    HEADERS,
    get_icon_path
)
from .google_translate import trans
from .foreca_weather_api import _symbol_to_description


WEATHER_DETAIL_VIEW_DIR = join(TEMP_DIR, "weather_detail")
if not exists(WEATHER_DETAIL_VIEW_DIR):
    makedirs(WEATHER_DETAIL_VIEW_DIR)


class WeatherDetailView(Screen, HelpableScreen):
    def __init__(self, session, weather_api, foreca_preview, unit_manager):
        """
        Parameters:
            session: enigma session
            weather_api: instance of ForecaFreeAPI (or ForecaWeatherAPI)
            location_id: str
            town: str
            country: str
            lat: str
            lon: str
            rgbmyr, rgbmyg, rgbmyb: int (color components)
            alpha: str (transparency color)
        """
        self.skin = load_skin_for_class(WeatherDetailView)
        Screen.__init__(self, session)
        HelpableScreen.__init__(self)
        self.weather_api = weather_api
        self.foreca_preview = foreca_preview
        self.unit_manager = unit_manager
        self._downloading = False
        self.town = foreca_preview.town
        self.country = foreca_preview.country
        self.lat = foreca_preview.lat
        self.lon = foreca_preview.lon
        self.myloc = foreca_preview.myloc
        self.tz_offset = getattr(foreca_preview, 'tz_offset', None)
        self.paths = [
            foreca_preview.path_loc0,
            foreca_preview.path_loc1,
            foreca_preview.path_loc2]
        current_path = self.paths[self.myloc]
        self.location_id = current_path.split(
            '/')[0] if '/' in current_path else current_path
        self.rgbmyr = foreca_preview.rgbmyr
        self.rgbmyg = foreca_preview.rgbmyg
        self.rgbmyb = foreca_preview.rgbmyb
        self.alpha = foreca_preview.alpha

        # Calculate zoom level
        try:
            lat_float = float(self.lat)
            self.zoom_level = max(4, min(5, int(10 - abs(lat_float) / 20)))
        except (ValueError, TypeError):
            self.zoom_level = 4
        self.min_zoom = 1
        self.max_zoom = 12

        self.weather_data = self._fetch_data()
        # --- Animation support ---
        self.anim_timer = eTimer()
        self.anim_timer.callback.append(self._next_animation_frame)
        self._animations = {}  # {widget_name: {"frames": [], "current": 0, "running": False}}

        """
        print("[DEBUG] weather_data keys:", self.weather_data.keys())
        if self.weather_data.get('today'):
            print("[DEBUG] today keys:", self.weather_data['today'].keys())
            for period in ['morning', 'afternoon', 'evening', 'overnight']:
                print(f"[DEBUG] today[{period}]:", self.weather_data['today'].get(period, {}))
        if self.weather_data.get('tomorrow'):
            print("[DEBUG] tomorrow keys:", self.weather_data['tomorrow'].keys())
            for period in ['morning', 'afternoon', 'evening', 'overnight']:
                print(f"[DEBUG] tomorrow[{period}]:", self.weather_data['tomorrow'].get(period, {}))
        """

        self['title_main'] = Label(_('Weather Radar'))
        self['title_location'] = Label()
        self['title_today'] = Label(_('Weather today'))
        self['title_tomorrow'] = Label(_('Weather tomorrow'))
        self['title_wind_today'] = Label(_('Wind Direction today'))
        self['title_wind_tomorrow'] = Label(_('Wind Direction tomorrow'))

        self['summary_today'] = Label()
        self['summary_tomorrow'] = Label()

        # Period labels
        for suffix in ['1', '2']:
            self[f'label_morning_{suffix}'] = Label(_('Morning'))
            self[f'label_afternoon_{suffix}'] = Label(_('Afternoon'))
            self[f'label_evening_{suffix}'] = Label(_('Evening'))
            self[f'label_overnight_{suffix}'] = Label(_('Overnight'))

        # Temperature values
        for suffix in ['1', '2']:
            self[f'temp_morning_{suffix}'] = Label()
            self[f'temp_afternoon_{suffix}'] = Label()
            self[f'temp_evening_{suffix}'] = Label()
            self[f'temp_overnight_{suffix}'] = Label()

        # Temperature unit labels
        for suffix in ['1', '2']:
            self[f'temp_label_morning_{suffix}'] = Label("")
            self[f'temp_label_afternoon_{suffix}'] = Label("")
            self[f'temp_label_evening_{suffix}'] = Label("")
            self[f'temp_label_overnight_{suffix}'] = Label("")

        # Symbol pixmaps
        for suffix in ['1', '2']:
            self[f'symbol_morning_{suffix}'] = Pixmap()
            self[f'symbol_afternoon_{suffix}'] = Pixmap()
            self[f'symbol_evening_{suffix}'] = Pixmap()
            self[f'symbol_overnight_{suffix}'] = Pixmap()

        self['zoom_label'] = Label(_("Zoom: ") + str(self.zoom_level))
        self['radar_map'] = Pixmap()
        self['icon_longitude'] = Pixmap()
        self['icon_latitude'] = Pixmap()
        self['value_longitude'] = Label()
        self['value_latitude'] = Label()
        self['wind_icon_today'] = Pixmap()
        self['wind_icon_tomorrow'] = Pixmap()
        self["background_plate"] = Label("")
        self["selection_overlay"] = Label("")
        self["key_ok"] = StaticText(_("OK - Open Map"))
        self["key_red"] = StaticText(_("Exit"))
        self["key_green"] = StaticText(_("Zoom In"))
        self["key_yellow"] = StaticText(_("Zoom Out"))
        self["key_blue"] = StaticText()
        self["actions"] = HelpableActionMap(
            self, "ForecaActions",
            {
                "cancel": (self.close, _("Exit")),
                "red": (self.close, _("Exit")),
                "ok": (self._open_full_radar, _("Open Map")),
                "green": (self.zoom_in, _("Zoom In")),
                "yellow": (self.zoom_out, _("Zoom Out")),
                "nextBouquet": (self.zoom_in, _("Zoom+")),
                "prevBouquet": (self.zoom_out, _("Zoom-"))
            },
            -1
        )

        self.onLayoutFinish.append(self._on_layout_finished)
        self.onShow.append(self._on_screen_shown)
        self.onLayoutFinish.append(self._apply_theme)
        self.onClose.append(self._stop_all_animations)

    # ---------- Animation methods ----------
    def _start_animation(self, widget_name, frames):
        if DEBUG:
            print(
                f"[WeatherDetail] Starting animation for {widget_name}, {len(frames)} frames")
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
        """Look for frames in: PLUGIN_PATH/animated_icons/{folder_name}/*.png"""
        anim_dir = join(PLUGIN_PATH, "animated_icons", folder_name)
        if exists(anim_dir):
            frames = sorted(glob.glob(join(anim_dir, "*.png")))
            if DEBUG:
                print(
                    f"[WeatherDetail] Found {len(frames)} frames in {anim_dir}")
            return frames
        return []

    def _apply_theme(self):
        apply_global_theme(self)

    def _open_full_radar(self):
        from .radar_map import RadarMapView
        self.session.open(RadarMapView, self.weather_api, self.foreca_preview)

    def _fetch_data(self):
        if hasattr(self.weather_api, 'get_today_tomorrow_details'):
            return self.weather_api.get_today_tomorrow_details(
                self.location_id,
                tz_offset=self.tz_offset
            ) or {}
        return {}

    def _on_layout_finished(self):
        self._load_radar_map()
        self._load_coordinate_icons()
        self._load_weather_symbols()
        self._update_coordinate_values()
        self._setup_temperature_labels()
        self._update_titles()

    def _on_screen_shown(self):
        self._update_titles()
        self._update_summaries()
        self._update_temperature_values()
        self._update_background_colors()
        self._start_translation_thread()
        self._update_wind_icons()

    def _load_radar_map(self):
        """Starts downloading the radar map with the current zoom level."""
        if self._downloading:
            return
        from threading import Thread
        self._downloading = True
        self['zoom_label'].setText(
            _("Zoom: ") + str(self.zoom_level) + " (loading...)")
        Thread(target=self._download_map_thread).start()

    def _download_map_thread(self):
        """Performs the download in a separate thread."""
        try:
            url = "https://map-cf.foreca.net/teaser/map/light/rain/{}/{}/{}/380/598.png?names&units=mm".format(
                self.zoom_level, self.lon, self.lat)
            response = requests.get(url, headers=HEADERS, timeout=10)
            if response.status_code == 200 and len(response.content) > 0:
                output_file = join(
                    WEATHER_DETAIL_VIEW_DIR,
                    'radar_{}.png'.format(self.zoom_level)
                )
                with open(output_file, 'wb') as f:
                    f.write(response.content)

                # Update the Pixmap in the main thread
                reactor.callFromThread(self._update_map_pixmap, output_file)
            else:
                print(
                    "[WeatherDetail] Download failed for zoom {}".format(
                        self.zoom_level))
        except Exception as e:
            print("[WeatherDetail] Download error: {}".format(e))
        finally:
            self._downloading = False
            reactor.callFromThread(self._reset_zoom_label)

    def zoom_in(self):
        if self.zoom_level < self.max_zoom:
            self.zoom_level += 1
            self._load_radar_map()

    def zoom_out(self):
        if self.zoom_level > self.min_zoom:
            self.zoom_level -= 1
            self._load_radar_map()

    def _reset_zoom_label(self):
        """Resets the zoom label."""
        self['zoom_label'].setText(_("Zoom: ") + str(self.zoom_level))

    def _load_coordinate_icons(self):
        base = join(PLUGIN_PATH, "images")
        lon_path = join(base, "longitude.png")
        lat_path = join(base, "latitude.png")
        if exists(lon_path):
            self['icon_longitude'].instance.setPixmapFromFile(lon_path)
        if exists(lat_path):
            self['icon_latitude'].instance.setPixmapFromFile(lat_path)

    def _load_weather_symbols(self):
        today = self.weather_data.get('today', {})
        tomorrow = self.weather_data.get('tomorrow', {})
        self._set_symbols_for_day('1', today)
        self._set_symbols_for_day('2', tomorrow)

    def _set_symbols_for_day(self, suffix, day_data):
        periods = ['morning', 'afternoon', 'evening', 'overnight']
        for period in periods:
            period_data = day_data.get(period, {})
            temp = period_data.get('temp')
            symbol = period_data.get('symbol', 'd000')
            widget_name = f'symbol_{period}_{suffix}'

            # Conditions for using NA
            use_na = False
            if temp is None or temp == 'N/A':
                use_na = True
            elif symbol == 'd000' and period in ['evening', 'overnight']:
                use_na = True

            if use_na:
                # Try loading animation from "NA" folder
                frames = self._load_animated_frames("NA")
                if frames:
                    self._start_animation(widget_name, frames)
                else:
                    # Static Fallback
                    path = get_icon_path('na.png')
                    if path:
                        self[widget_name].instance.setPixmapFromFile(path)
                        self[widget_name].show()
                    else:
                        self[widget_name].hide()
                    self._stop_animation(widget_name)
                continue

            # Valid data: standard animation or static icon
            frames = self._load_animated_frames(symbol)
            if frames:
                self._start_animation(widget_name, frames)
            else:
                path = get_icon_path(f"{symbol}.png")
                if path:
                    self[widget_name].instance.setPixmapFromFile(path)
                    self[widget_name].show()
                else:
                    self[widget_name].hide()
                self._stop_animation(widget_name)

    # def _set_symbols_for_day(self, suffix, day_data):
        # periods = ['morning', 'afternoon', 'evening', 'overnight']
        # for period in periods:
            # period_data = day_data.get(period, {})
            # temp = period_data.get('temp')
            # symbol = period_data.get('symbol', 'd000')
            # widget_name = f'symbol_{period}_{suffix}'

            # if temp is None or temp == 'N/A':
                # # No data – hide widget
                # self[widget_name].hide()
                # self._stop_animation(widget_name)
                # continue

            # # Try to load animated frames
            # frames = self._load_animated_frames(symbol)
            # if frames:
                # self._start_animation(widget_name, frames)
            # else:
                # # Fallback static icon
                # path = get_icon_path(f"{symbol}.png")
                # if path:
                # self[widget_name].instance.setPixmapFromFile(path)
                # self[widget_name].show()
                # else:
                # self[widget_name].hide()
                # self._stop_animation(widget_name)

    def _setup_temperature_labels(self):
        temp_unit = self.unit_manager.get_temp_label()
        for suffix in ['1', '2']:
            for period in ['morning', 'afternoon', 'evening', 'overnight']:
                self[f'temp_label_{period}_{suffix}'].setText(temp_unit)

    def _format_summary(self, day):
        if not day:
            return _("No data")
        symbol = day.get('text', 'd000')
        text = _symbol_to_description(symbol)
        max_t = day.get('max_temp', 'N/A')
        min_t = day.get('min_temp', 'N/A')
        rain = day.get('rain_mm', 0)

        if max_t != 'N/A' and min_t != 'N/A':
            max_converted, unused = self.unit_manager.convert_temperature(
                max_t)
            min_converted, unused = self.unit_manager.convert_temperature(
                min_t)
            temp_str = f"{int(min_converted)}° - {int(max_converted)}°{self.unit_manager.get_temp_label()[-1]}"
        else:
            temp_str = f"{min_t}° - {max_t}°C"

        rain_converted, rain_unit = self.unit_manager.convert_precipitation(
            rain)
        rain_str = f"{rain_converted:.1f}{rain_unit}"

        return f"{trans(text)} {temp_str}. {rain_str}."

    def _convert_temp_value(self, temp_val):
        """Helper: Converts a temperature (number or 'N/A') to a rounded string."""
        if temp_val is None or temp_val == 'N/A':
            return '-'
        try:
            converted, _ = self.unit_manager.convert_temperature(
                float(temp_val))
            return str(int(converted))
        except BaseException:
            return '-'

    def _update_titles(self):
        self['title_today'].setText(_('Weather today'))
        self['title_tomorrow'].setText(_('Weather tomorrow'))
        self['title_location'].setText(trans(self.town))

    def _update_summaries(self):
        today = self.weather_data.get('today', {})
        tomorrow = self.weather_data.get('tomorrow', {})
        self['summary_today'].setText(self._format_summary(today))
        self['summary_tomorrow'].setText(self._format_summary(tomorrow))

    def _update_coordinate_values(self):
        self['value_latitude'].setText(str(self.lat))
        self['value_longitude'].setText(str(self.lon))

    def _update_map_pixmap(self, filepath):
        """Sets the pixmap with the downloaded file."""
        if exists(filepath):
            self['radar_map'].instance.setPixmapFromFile(filepath)
            self['radar_map'].instance.show()

    def _update_wind_icons(self):
        today = self.weather_data.get('today', {})
        tomorrow = self.weather_data.get('tomorrow', {})

        for suffix, day in [('today', today), ('tomorrow', tomorrow)]:
            wind_dir = day.get('wind_dir')
            if wind_dir is not None and wind_dir != 'N/A':
                try:
                    deg = float(wind_dir)
                    icon_name = self._degrees_to_wind_icon(deg)
                except BaseException:
                    icon_name = "wN"

                path = get_icon_path(f"{icon_name}.png")
                if path:
                    self[f'wind_icon_{suffix}'].instance.setPixmapFromFile(
                        path)
                    self[f'wind_icon_{suffix}'].show()
                else:
                    self[f'wind_icon_{suffix}'].hide()

            else:
                self[f'wind_icon_{suffix}'].hide()

    def _update_temperature_values(self):
        today = self.weather_data.get('today', {})
        tomorrow = self.weather_data.get('tomorrow', {})
        for suffix, data in [('1', today), ('2', tomorrow)]:
            # Morning
            val = data.get('morning', {}).get('temp')
            self[f'temp_morning_{suffix}'].setText(
                self._convert_temp_value(val))
            val = data.get('afternoon', {}).get('temp')
            self[f'temp_afternoon_{suffix}'].setText(
                self._convert_temp_value(val))
            # Evening
            val = data.get('evening', {}).get('temp')
            self[f'temp_evening_{suffix}'].setText(
                self._convert_temp_value(val))
            # Night
            val = data.get('overnight', {}).get('temp')
            self[f'temp_overnight_{suffix}'].setText(
                self._convert_temp_value(val))

    def _update_background_colors(self):
        bg = gRGB(
            int(self.rgbmyr),
            int(self.rgbmyg),
            int(self.rgbmyb)
        )
        self["background_plate"].instance.setBackgroundColor(bg)
        self["selection_overlay"].instance.setBackgroundColor(
            parseColor(self.alpha)
        )

    def _start_translation_thread(self):
        from threading import Thread
        Thread(target=self._translate_content).start()

    def _translate_content(self):
        self['title_today'].setText(_('Weather today'))
        self['title_tomorrow'].setText(_('Weather tomorrow'))
        self['title_location'].setText(trans(self.town))
        # Also update summaries if needed
        self._update_summaries()

    def _degrees_to_wind_icon(self, degrees):
        try:
            deg = int(degrees) % 360
            directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
            index = round(deg / 45) % 8
            return "w" + directions[index]
        except BaseException:
            return "wN"

    def close(self):
        self._stop_all_animations()
        super(WeatherDetailView, self).close()
