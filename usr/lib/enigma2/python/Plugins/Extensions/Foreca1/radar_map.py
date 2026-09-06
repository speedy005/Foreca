#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) @Lululla 2026
# radar_map.py - Simple radar map view

from Screens.Screen import Screen
from Components.ActionMap import HelpableActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.Sources.StaticText import StaticText
from enigma import gRGB
from skin import parseColor
from Screens.HelpMenu import HelpableScreen
from os.path import exists, join
from os import makedirs
import requests
from threading import Thread, Lock
from twisted.internet import reactor

from . import (
    _,
    load_skin_for_class,
    apply_global_theme,
    PLUGIN_PATH,
    TEMP_DIR,
    HEADERS
)

RADAR_MAPS_DIR = join(TEMP_DIR, "pngfold")
if not exists(RADAR_MAPS_DIR):
    makedirs(RADAR_MAPS_DIR)


class RadarMapView(Screen, HelpableScreen):
    def __init__(self, session, weather_api, foreca_preview):
        self.skin = load_skin_for_class(RadarMapView)
        Screen.__init__(self, session)
        HelpableScreen.__init__(self)
        self.weather_api = weather_api
        self.foreca_preview = foreca_preview
        self.town = foreca_preview.town
        self.lon = foreca_preview.lon
        self.lat = foreca_preview.lat
        self.setTitle(_('Weather Map'))
        try:
            lat_float = float(self.lat)
            # Formula: the closer to the equator, the higher zoom is needed
            self.zoom_level = max(4, min(5, int(10 - abs(lat_float) / 20)))
        except (ValueError, TypeError):
            # Default value if latitude is unavailable or not numeric
            self.zoom_level = 4
        self.min_zoom = 1
        self.max_zoom = 12

        self._download_lock = Lock()
        self._current_download = None

        self['title'] = Label(f"{_('Weather Radar')} {self.town}")
        self['radar_map'] = Pixmap()
        self['icon_longitude'] = Pixmap()
        self['icon_latitude'] = Pixmap()
        self['value_latitude'] = Label()
        self['value_longitude'] = Label()
        self["background_plate"] = Label("")
        self["selection_overlay"] = Label("")
        self['zoom_label'] = Label(_("Zoom: ") + str(self.zoom_level))

        self['key_red'] = StaticText(_("Exit"))
        self['key_green'] = StaticText("Zoom+")
        self['key_yellow'] = StaticText("Zoom-")
        self['key_blue'] = StaticText()
        self["actions"] = HelpableActionMap(
            self, "ForecaActions",
            {
                "cancel": (self.close, _("Exit")),
                "red": (self.close, _("Exit")),
                "green": (self.zoom_in, _("Zoom+")),
                "yellow": (self.zoom_out, _("Zoom-")),
                "nextBouquet": (self.zoom_in, _("Zoom+")),
                "prevBouquet": (self.zoom_out, _("Zoom-"))
            },
            -1
        )
        self.onLayoutFinish.append(self._load_static_content)
        self.onShow.append(self._update_dynamic_content)
        self.onLayoutFinish.append(self._update_map)
        self.onLayoutFinish.append(self._apply_theme)

    def _apply_theme(self):
        apply_global_theme(self)

    def _load_static_content(self):
        radar_path = join(RADAR_MAPS_DIR, '385.png')
        if exists(radar_path):
            self['radar_map'].instance.setPixmapFromFile(radar_path)

        base = join(PLUGIN_PATH, "images")
        lon_path = join(base, "longitude.png")
        lat_path = join(base, "latitude.png")
        if exists(lon_path):
            self['icon_longitude'].instance.setPixmapFromFile(lon_path)
        if exists(lat_path):
            self['icon_latitude'].instance.setPixmapFromFile(lat_path)

        self['value_latitude'].setText(self.foreca_preview.lat)
        self['value_longitude'].setText(self.foreca_preview.lon)

    def _update_dynamic_content(self):
        bg = gRGB(
            int(self.foreca_preview.rgbmyr),
            int(self.foreca_preview.rgbmyg),
            int(self.foreca_preview.rgbmyb)
        )
        self["background_plate"].instance.setBackgroundColor(bg)
        self["selection_overlay"].instance.setBackgroundColor(
            parseColor(self.foreca_preview.alpha)
        )

    def zoom_in(self):
        if self.zoom_level < self.max_zoom:
            self.zoom_level += 1
            self._update_map()

    def zoom_out(self):
        if self.zoom_level > self.min_zoom:
            self.zoom_level -= 1
            self._update_map()

    def _update_map(self):
        """Download and display the radar map with current zoom level."""
        if not self.lon or not self.lat or self.lon == 'N/A' or self.lat == 'N/A':
            return

        # Update zoom label
        self['zoom_label'].setText(_("Zoom: ") + str(self.zoom_level))

        # Build URL with current zoom level)
        with self._download_lock:
            if self._current_download and self._current_download.is_alive():
                return
            output_file = join(
                RADAR_MAPS_DIR,
                f'radar_map_{self.zoom_level}.png')
            url = f"https://map-cf.foreca.net/teaser/map/light/rain/{self.zoom_level}/{self.lon}/{self.lat}/380/598.png?names&units=mm"
            self._current_download = Thread(
                target=self._download_map, args=(
                    url, output_file))
            self._current_download.start()

    def _download_map(self, url, output_file):
        try:
            # Use requests for download (synchronous but threaded)
            response = requests.get(url, headers=HEADERS, timeout=10)
            if response.status_code == 200 and len(response.content) > 0:
                with open(output_file, 'wb') as f:
                    f.write(response.content)
                reactor.callFromThread(self._set_map_pixmap, output_file)
            else:
                print(
                    f"[RadarMap] Download failed for zoom {self.zoom_level}: status {response.status_code}")
        except Exception as e:
            print(f"[RadarMap] Download error: {e}")

    def _set_map_pixmap(self, filepath):
        if exists(filepath):
            self['radar_map'].instance.setPixmapFromFile(filepath)
