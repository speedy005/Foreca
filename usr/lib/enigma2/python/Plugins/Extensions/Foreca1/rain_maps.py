#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) @Lululla 2026
# wetter_maps.py - RainViewer radar viewer with geographic background
# (free, no API key)

import hashlib
import requests
from datetime import datetime
from threading import Thread
from os.path import exists, join
from os import makedirs, listdir, remove
from math import log, tan, pi, radians, cos
from PIL import Image
from twisted.internet import reactor
from enigma import getDesktop

from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Components.ActionMap import HelpableActionMap
from Components.Pixmap import Pixmap
from Components.Label import Label
from Components.Sources.StaticText import StaticText

from .map_legend import MapLegendOverlay  # MapLegend
from .google_translate import trans
from . import (
    _,
    DEBUG,
    # THUMB_PATH,
    load_skin_for_class,
    apply_global_theme,
    TEMP_DIR,
    HEADERS,
    OSM_HEADERS
)


RAIN_MAPS_DIR = join(TEMP_DIR, "rainviewer")
if not exists(RAIN_MAPS_DIR):
    makedirs(RAIN_MAPS_DIR)

TILE_SIZE = 256
API_URL = "https://api.rainviewer.com/public/weather-maps.json"
OSM_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"


BACKGROUND_EXTENTS = {
    # Europe (based on get_background_for_layer)
    'europa.png': {'minLat': 36, 'maxLat': 71, 'minLon': -9.57, 'maxLon': 66.17},
    # Africa
    'africa.png': {'minLat': -34.85, 'maxLat': 37.35, 'minLon': -17.56, 'maxLon': 51.46},
    # Asia (two ranges to cross 180°)
    'asia.png': {'minLat': -1.27, 'maxLat': 77.72, 'minLon': 26.07, 'maxLon': 180},
    # North America (two ranges)
    'nordamerika.png': {'minLat': 7.2, 'maxLat': 83.67, 'minLon': -180, 'maxLon': -12.13},
    # South America
    'suedamerika.png': {'minLat': -56.5, 'maxLat': 12.45, 'minLon': -81.33, 'maxLon': -34.78},
    # Oceania
    'oceania.png': {'minLat': -55.05, 'maxLat': 28.63, 'minLon': 110, 'maxLon': 180},
    # World (fallback)
    'world.png': {'minLat': -90, 'maxLat': 90, 'minLon': -180, 'maxLon': 180},
}


class RainViewerMaps(Screen, HelpableScreen):
    def __init__(self, session, foreca_preview):
        self.skin = load_skin_for_class(RainViewerMaps)
        Screen.__init__(self, session)
        HelpableScreen.__init__(self)

        self.foreca_preview = foreca_preview
        self.host = None
        self.frames = []
        self.current_frame = 0
        self.setTitle(_("RainViewer Radar"))

        try:
            self.center_lat = float(
                foreca_preview.lat) if foreca_preview.lat != 'N/A' else 50.0
            self.center_lon = float(
                foreca_preview.lon) if foreca_preview.lon != 'N/A' else 10.0
        except BaseException:
            self.center_lat = 50.0
            self.center_lon = 10.0

        self.min_zoom = 2
        self.max_zoom = 7
        if DEBUG:
            print("[RainViewerMaps] No extent, using default center (50,10)")

        # Grid based on screen resolution
        desktop = getDesktop(0)
        self.screen_w = desktop.size().width()
        self.screen_h = desktop.size().height()
        if self.screen_h <= 720:
            self.grid_cols = 5
            self.grid_rows = 3
        elif self.screen_h <= 1080:
            self.grid_cols = 5
            self.grid_rows = 5
        else:
            self.grid_cols = 7
            self.grid_rows = 7

        self.map_w = self.grid_cols * TILE_SIZE
        self.map_h = self.grid_rows * TILE_SIZE

        # Initial Zoom
        self.zoom_level = 4

        self._downloading = False
        self["map"] = Pixmap()
        self["title"] = Label(_("RainViewer Radar"))
        self["time_label"] = Label("")
        self["info"] = Label(_("Loading..."))
        self["osm_attribution"] = Label(
            "© OpenStreetMap contributors, Style: OpenRailwayMap CC-BY-SA 2.0"
        )
        self['key_red'] = StaticText(_("Exit"))
        self['key_green'] = StaticText(_("Zoom+"))
        self['key_yellow'] = StaticText(_("Zoom-"))
        self['key_blue'] = StaticText()
        self['key_left'] = StaticText(_("← Frame"))
        self['key_right'] = StaticText(_("Frame →"))
        self['zoom_label'] = Label(_("Zoom: ") + str(self.zoom_level))
        self["background_plate"] = Label("")
        self["selection_overlay"] = Label("")
        self.legend = self.session.instantiateDialog(
            MapLegendOverlay, 'precip')
        self.legend_active = False
        self["actions"] = HelpableActionMap(
            self, "ForecaActions",
            {
                "cancel": (self.handle_cancel, _("Exit / Close legend")),
                "red": (self.handle_red, _("Exit / Close legend")),
                "ok": (self.handle_ok, _("Close legend")),
                "left": (self.pan_left, _("Pan left")),
                "right": (self.pan_right, _("Pan right")),
                "up": (self.pan_up, _("Pan up")),
                "down": (self.pan_down, _("Pan down")),
                "pageUp": (self.prev_frame, _("Previous frame")),
                "pageDown": (self.next_frame, _("Next frame")),
                "green": (self.zoom_in, _("Zoom+")),
                "yellow": (self.zoom_out, _("Zoom-")),
                "nextBouquet": (self.zoom_in, _("Zoom+")),
                "prevBouquet": (self.zoom_out, _("Zoom-")),
                "showEventInfo": (self.toggle_legend, _("Toggle legend")),
            },
            -1
        )
        self.clear_cache()
        self.widget_width = 1819
        self.widget_height = 853
        self.onLayoutFinish.append(self.get_widget_size)
        self.onLayoutFinish.append(self._apply_theme)
        self.onLayoutFinish.append(self.load_frame_list)
        self.onClose.append(self.clear_cache)

    def _apply_theme(self):
        apply_global_theme(self)

    def toggle_legend(self):
        if self.legend_active:
            self.legend.hide()
        else:
            self.legend.show()
        self.legend_active = not self.legend_active

    def handle_cancel(self):
        if self.legend_active:
            self.legend.hide()
            self.legend_active = False
        else:
            self.exit()

    def handle_red(self):
        self.handle_cancel()

    def handle_ok(self):
        if self.legend_active:
            self.legend.hide()
            self.legend_active = False

    def exit(self):
        if self.legend:
            self.session.deleteDialog(self.legend)
            self.legend = None
        self.close()

    def get_widget_size(self):
        if "map" in self and self["map"].instance:
            size = self["map"].instance.size()
            self.widget_width = size.width()
            self.widget_height = size.height()
            if DEBUG:
                print(
                    f"[RainViewer] Widget size: {self.widget_width}x{self.widget_height}")

    def clear_cache(self):
        try:
            if exists(RAIN_MAPS_DIR):
                for f in listdir(RAIN_MAPS_DIR):
                    if f.endswith('.png') or f.endswith('.jpg'):
                        remove(join(RAIN_MAPS_DIR, f))
                if DEBUG:
                    print("[RainViewerMaps] Cache cleaned")
        except Exception as e:
            print(f"[RainViewerMaps] Error cleaning cache: {e}")

    def latlon_to_tile(self, lat, lon, zoom):
        lat_rad = radians(lat)
        n = 2.0 ** zoom
        x = int((lon + 180.0) / 360.0 * n)
        y = int((1.0 - log(tan(lat_rad) + 1.0 / cos(lat_rad)) / pi) / 2.0 * n)
        return x, y

    def download_tile(self, url, prefix=''):
        key = (prefix + url).encode()
        cache_file = join(RAIN_MAPS_DIR, hashlib.md5(key).hexdigest() + '.png')
        if exists(cache_file):
            return cache_file
        try:
            if 'openstreetmap.org' in url or 'openrailwaymap.org' in url:
                headers = OSM_HEADERS  # Use specific headers for OSM/ORM
            else:
                headers = HEADERS  # Use generic headers for other services
            r = requests.get(url, headers=headers, timeout=5)
            if r.status_code == 200:
                with open(cache_file, 'wb') as f:
                    f.write(r.content)
                return cache_file
            else:
                if DEBUG:
                    print(
                        f"[RainViewer] Tile download error {r.status_code}: {url}")
        except Exception as e:
            print(f"[RainViewer] download exception: {e}")
        return None

    def build_tile_url(self, frame_path, x, y, z):
        # Fixed parameters: size=256, color=2 (green-red), options=1_1 (blur +
        # snow)
        return f"{self.host}{frame_path}/256/{z}/{x}/{y}/2/1_1.png"

    def load_frame_list(self):
        """Download the JSON and get the list of available frames"""
        self["info"].setText(trans("Fetching radar data..."))
        Thread(target=self._fetch_frames).start()

    def _fetch_frames(self):
        try:
            if 'openstreetmap.org' in API_URL or 'openrailwaymap.org' in API_URL:
                headers = OSM_HEADERS  # Use specific headers for OSM/ORM
            else:
                headers = HEADERS  # Use generic headers for other services
            resp = requests.get(API_URL, headers=headers, timeout=10)
            if resp.status_code != 200:
                print(f"[RainViewer] API error: {resp.status_code}")
                reactor.callFromThread(
                    lambda: self["info"].setText(
                        _("API error")))
                return
            data = resp.json()
            self.host = data['host']
            self.frames = [frame['path'] for frame in data['radar']['past']]
            self.frames.reverse()  # oldest to newest
            self.current_frame = len(self.frames) - 1  # last frame
            print(
                f"[RainViewer] {len(self.frames)} frames available, host: {self.host}")
            reactor.callFromThread(self.update_frame_display)
        except Exception as e:
            print(f"[RainViewer] Error: {e}")
            reactor.callFromThread(
                lambda: self["info"].setText(
                    _("Error loading data")))

    def update_frame_display(self):
        if self._downloading:
            print("[RainViewer] Already downloading, skipping")
            return
        self._downloading = True

        if not self.frames:
            return
        frame_path = self.frames[self.current_frame]
        timestamp = frame_path.split('/')[-1]
        try:
            dt = datetime.utcfromtimestamp(int(timestamp))
            time_str = dt.strftime("%d.%m.%Y %H:%M UTC")
        except BaseException:
            time_str = timestamp
        self["time_label"].setText(_("Frame: {}").format(time_str))
        self["info"].setText(_("Loading tiles..."))
        print(f"[RainViewer] Loading frame: {frame_path}")
        self.download_tiles(frame_path)

    def download_tiles(self, frame_path):
        """Download and compose tiles for the selected frame"""
        Thread(target=self._download_thread, args=(frame_path,)).start()

    def _download_thread(self, frame_path):
        print("[RainViewer] _download_thread started")

        def reset():
            reactor.callFromThread(self._reset_download_flag)

        try:
            cx, cy = self.latlon_to_tile(
                self.center_lat, self.center_lon, self.zoom_level)
            offset_cols = self.grid_cols // 2
            offset_rows = self.grid_rows // 2

            osm_tiles = []
            radar_tiles = []
            for dx in range(-offset_cols, offset_cols + 1):
                for dy in range(-offset_rows, offset_rows + 1):
                    x = cx + dx
                    y = cy + dy

                    # Tile OSM
                    osm_url = OSM_URL.format(z=self.zoom_level, x=x, y=y)
                    osm_path = self.download_tile(osm_url, prefix='osm')
                    if osm_path:
                        osm_tiles.append(
                            (dx + offset_cols, dy + offset_rows, osm_path))
                    else:
                        print(f"[RainViewer] OSM tile missing: ({x},{y})")

                    # Tile Radar
                    radar_url = self.build_tile_url(
                        frame_path, x, y, self.zoom_level)
                    radar_path = self.download_tile(radar_url, prefix='radar')
                    if radar_path:
                        radar_tiles.append(
                            (dx + offset_cols, dy + offset_rows, radar_path))
                    else:
                        print(f"[RainViewer] Radar tile missing: ({x},{y})")
            if osm_tiles and radar_tiles:
                print(
                    f"[RainViewer] {len(osm_tiles)} OSM tiles, {len(radar_tiles)} Radar tiles")
                merged = self.merge_tiles(osm_tiles, radar_tiles)
                if merged:
                    print("[RainViewer] download_thread running")
                    reactor.callFromThread(self.show_map, merged)
                else:
                    reactor.callFromThread(
                        lambda: self["info"].setText(
                            _("Merge failed")))
            else:
                reactor.callFromThread(
                    lambda: self["info"].setText(
                        _("No tiles downloaded")))
        except Exception as e:
            print(f"[RainViewer] Exception in _download_thread: {e}")
            reactor.callFromThread(
                lambda: self["info"].setText(
                    _("Download error")))
        finally:
            reset()

    def _reset_download_flag(self):
        self._downloading = False

    def merge_tiles(self, osm_tiles, radar_tiles):
        try:
            # Create background with OSM tiles
            bg = Image.new('RGBA', (self.map_w, self.map_h), (0, 0, 0, 255))
            for col, row, path in osm_tiles:
                tile = Image.open(path).convert('RGBA')
                x = col * TILE_SIZE
                y = row * TILE_SIZE
                bg.paste(tile, (x, y), tile)

            # Overlay radar tiles
            for col, row, path in radar_tiles:
                tile = Image.open(path).convert('RGBA')
                x = col * TILE_SIZE
                y = row * TILE_SIZE
                bg.paste(tile, (x, y), tile)

            bg_rgb = bg.convert('RGB')
            out_path = join(RAIN_MAPS_DIR, 'merged.jpg')
            bg_rgb.save(out_path, 'JPEG', quality=90)
            return out_path
        except Exception as e:
            print(f"[RainViewer] merge error: {e}")
            return None

    def show_map(self, path):
        try:
            if not self.widget_width or not self.widget_height:
                self.get_widget_size()

            from PIL import Image
            img = Image.open(path)
            if hasattr(self, 'widget_width') and self.widget_width > 0:
                img = img.resize(
                    (self.widget_width,
                     self.widget_height),
                    Image.Resampling.LANCZOS)
                resized_path = path.replace('.jpg', '_widget.jpg')
                img.save(resized_path)
                self["map"].instance.setPixmapFromFile(resized_path)
            else:
                self["map"].instance.setPixmapFromFile(path)
            self["map"].instance.show()
            self["map"].instance.invalidate()
            self["info"].setText(_("Map loaded"))
        except Exception as e:
            print(f"[RainViewer] Error showing map: {e}")
            self["info"].setText(_("Error loading map"))

    def zoom_in(self):
        if self.zoom_level < self.max_zoom:
            self.zoom_level += 1
            self['zoom_label'].setText(_("Zoom: ") + str(self.zoom_level))
            self.update_frame_display()

    def zoom_out(self):
        if self.zoom_level > self.min_zoom:
            self.zoom_level -= 1
            self['zoom_label'].setText(_("Zoom: ") + str(self.zoom_level))
            self.update_frame_display()

    def prev_frame(self):
        if self.current_frame > 0:
            self.current_frame -= 1
            self.update_frame_display()

    def next_frame(self):
        if self.current_frame < len(self.frames) - 1:
            self.current_frame += 1
            self.update_frame_display()

    """
    Adjust the base step
    The 0.5 value in the formula is empirical.
    You can adjust it to achieve the desired sensitivity.
    If you want the movement to be faster, increase the value;
    if you want it to be slower, decrease it.
    """

    def _get_pan_step(self):
        tile_size_lon = 360.0 / (2 ** self.zoom_level)
        step = tile_size_lon * 0.8
        if DEBUG:
            print(
                f"[RainViewer] _get_pan_step: zoom={self.zoom_level}, step={step:.4f}°")
        return step

    def pan_left(self):
        step = self._get_pan_step()
        new_lon = self.center_lon - step
        old_lon = self.center_lon
        self.center_lon = max(-180, min(180, new_lon))
        if DEBUG:
            print(
                f"[RainViewer] pan_left: old={old_lon:.4f}, new={self.center_lon:.4f}, step={step:.4f}")
        self.update_frame_display()

    def pan_right(self):
        step = self._get_pan_step()
        new_lon = self.center_lon + step
        old_lon = self.center_lon
        self.center_lon = max(-180, min(180, new_lon))
        if DEBUG:
            print(
                f"[RainViewer] pan_right: old={old_lon:.4f}, new={self.center_lon:.4f}, step={step:.4f}")
        self.update_frame_display()

    def pan_up(self):
        step = self._get_pan_step() * 2
        new_lat = self.center_lat + step
        old_lat = self.center_lat
        self.center_lat = min(90, new_lat)
        if DEBUG:
            print(
                f"[RainViewer] pan_up: old={old_lat:.4f}, new={self.center_lat:.4f}, step={step:.4f}")
        self.update_frame_display()

    def pan_down(self):
        step = self._get_pan_step() * 2
        new_lat = self.center_lat - step
        old_lat = self.center_lat
        self.center_lat = max(-90, new_lat)
        if DEBUG:
            print(
                f"[RainViewer] pan_down: old={old_lat:.4f}, new={self.center_lat:.4f}, step={step:.4f}")
        self.update_frame_display()
