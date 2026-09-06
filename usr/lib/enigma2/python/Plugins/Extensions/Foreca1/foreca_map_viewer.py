#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) @Lululla 2026
# foreca_map_viewer.py - Foreca map viewer with OSM background and Foreca
# tiles overlay

import hashlib
import requests
from datetime import datetime
from threading import Thread
from os.path import exists, join
from os import makedirs, listdir, remove
from math import log, tan, pi, radians, cos

from enigma import getDesktop
from twisted.internet import reactor

from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Components.ActionMap import HelpableActionMap
from Components.Pixmap import Pixmap
from Components.Label import Label
from Components.Sources.StaticText import StaticText
from PIL import Image

from .map_legend import MapLegendOverlay, MapLegendOverlayImage
from . import (
    _,
    DEBUG,
    CACHE_BASE,
    load_skin_for_class,
    apply_global_theme,
    HEADERS,
    OSM_HEADERS
)

TILE_SIZE = 256
OSM_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"

# OSM Tile Cache Directory
OSM_CACHE_DIR = join(CACHE_BASE, "osm")
if not exists(OSM_CACHE_DIR):
    makedirs(OSM_CACHE_DIR)


class ForecaMapViewer(Screen, HelpableScreen):
    def __init__(self, session, api, layer, unit_system='metric', region='eu'):
        self.skin = load_skin_for_class(ForecaMapViewer)
        Screen.__init__(self, session)
        HelpableScreen.__init__(self)

        self.api = api
        self.layer = layer
        self.layer_id = layer['id']
        self.layer_title = layer.get('title', 'Map')
        self.unit_system = unit_system
        self.region = region.lower()

        self.setTitle(f"Foreca: {self.layer_title}")

        # Get layer extent if available
        extent = layer.get('extent', {})
        if extent and 'minLat' in extent and 'maxLat' in extent and 'minLon' in extent and 'maxLon' in extent:
            self.center_lat = (
                extent['minLat'] + extent['maxLat']) / 2.0
            self.center_lon = (
                extent['minLon'] + extent['maxLon']) / 2.0
            self.min_zoom = extent.get('minZoom', 2)
            self.max_zoom = extent.get('maxZoom', 21)
            if DEBUG:
                print(f"[ForecaMapViewer] Layer extent: {extent}")
        else:
            # Fallback to known coordinates (Europe)
            self.center_lat = 50.0
            self.center_lon = 10.0
            self.min_zoom = 2
            self.max_zoom = 21
            if DEBUG:
                print("[ForecaMapViewer] No extent, using default center (50,10)")

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
        self.zoom_level = max(
            self.min_zoom, min(
                self.max_zoom, self.zoom_level))

        # Timestamps layer
        self.timestamps = layer.get('times', {}).get('available', [])
        self.current_time_index = layer.get('times', {}).get('current', 0)

        self._downloading = False

        self["map"] = Pixmap()
        self["title"] = Label(self.layer_title)
        self["layerinfo"] = Label("")
        self["time"] = Label(_("Loading..."))
        self["info"] = Label(_("Use ←/→/↑/↓ to move | OK to exit"))
        self["osm_attribution"] = Label(
            "© OpenStreetMap contributors, Style: OpenRailwayMap CC-BY-SA 2.0"
        )
        self['key_red'] = StaticText(_("Exit"))
        self['key_green'] = StaticText(_("Zoom+"))
        self['key_yellow'] = StaticText(_("Zoom-"))
        self['key_blue'] = StaticText()
        self['zoom_label'] = Label(_("Zoom: ") + str(self.zoom_level))
        self["background_plate"] = Label("")
        self["selection_overlay"] = Label("")
        # self.legend = self.session.instantiateDialog(
        # MapLegendOverlay, 'precip')
        # self.legend_active = False
        self.legend = None
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
                "pageUp": (self.prev_time, _("Previous time")),
                "pageDown": (self.next_time, _("Next time")),
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
        self.onLayoutFinish.append(self.load_current_tile)
        self.onClose.append(self.clear_cache)

        self.onLayoutFinish.append(self._create_legend)

    def _create_legend(self):
        if self.legend is None:
            self.legend = self.session.instantiateDialog(
                MapLegendOverlay, 'precip')

    def _apply_theme(self):
        apply_global_theme(self)

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
                    f"[ForecaMapViewer] Widget size: {self.widget_width}x{self.widget_height}")

    def clear_cache(self):
        try:
            if exists(OSM_CACHE_DIR):
                for f in listdir(OSM_CACHE_DIR):
                    if f.endswith('.png') or f.endswith('.jpg'):
                        remove(join(OSM_CACHE_DIR, f))
                if DEBUG:
                    print("[ForecaMapViewer] OSM Cache cleaned")
        except Exception as e:
            print(f"[ForecaMapViewer] Error cleaning cache: {e}")

    def latlon_to_tile(self, lat, lon, zoom):
        lat_rad = radians(lat)
        n = 2.0 ** zoom
        x = int((lon + 180.0) / 360.0 * n)
        y = int((1.0 - log(tan(lat_rad) + 1.0 / cos(lat_rad)) / pi) / 2.0 * n)
        return x, y

    def download_tile(self, url, prefix=''):
        """Download a tile with appropriate headers"""
        key = (prefix + url).encode()
        cache_file = join(OSM_CACHE_DIR, hashlib.md5(key).hexdigest() + '.png')

        # Return if already cached
        if exists(cache_file):
            return cache_file

        # Choose headers based on tile type
        if 'openstreetmap.org' in url or 'openrailwaymap.org' in url:
            headers = OSM_HEADERS  # Use specific headers for OSM/ORM
        else:
            headers = HEADERS  # Use generic headers for other services

        try:
            if DEBUG:
                print(f"[ForecaMapViewer] Downloading tile: {url}")
                print(f"[ForecaMapViewer] Using headers: {headers}")

            r = requests.get(url, headers=headers, timeout=5)

            if r.status_code == 200:
                with open(cache_file, 'wb') as f:
                    f.write(r.content)
                if DEBUG:
                    print(f"[ForecaMapViewer] Tile downloaded: {cache_file}")
                return cache_file
            elif r.status_code == 429:
                # Too many requests - log and wait
                print(f"[ForecaMapViewer] Rate limited (429) for {url}")
                return None
            else:
                if DEBUG:
                    print(
                        f"[ForecaMapViewer] Tile download error {r.status_code}: {url}")
                    if r.status_code == 403:
                        print("[ForecaMapViewer] 403 Forbidden - Check headers")
        except Exception as e:
            print(f"[ForecaMapViewer] download exception: {e}")
        return None

    def get_foreca_tile(self, x, y, z, timestamp):
        return self.api.get_tile(
            self.layer_id,
            timestamp,
            z,
            x, y,
            self.unit_system
        )

    def load_current_tile(self):
        if self._downloading:
            print("[ForecaMapViewer] Already downloading, skipping")
            return
        self._downloading = True

        if not self.timestamps:
            now = datetime.utcnow().strftime("%d.%m.%YT%H:%M:%SZ")
            self.timestamps = [now]
            self.current_time_index = 0
            self["time"].setText(_("Using current time"))

        if self.current_time_index >= len(self.timestamps):
            self.current_time_index = 0

        timestamp = self.timestamps[self.current_time_index]
        try:
            dt = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
            display_time = dt.strftime("%d.%m.%Y %H:%M UTC")
        except BaseException:
            display_time = timestamp

        self["time"].setText(f"{display_time}")
        self["zoom_label"].setText(f"Zoom: {self.zoom_level}")
        self["info"].setText(_("Downloading tiles..."))
        self.download_tile_grid_async(timestamp)

    def download_legend(self):
        """
        Download the legend image for the current layer.
        Returns path to the downloaded image, or None if failed.
        """
        token = self.api.get_token()
        if not token:
            return None

        # Determine color scheme based on unit system
        if hasattr(self, 'unit_system'):
            if self.unit_system == 'metric':
                colorscheme = 'default'
            else:
                # For temperature layer (id=2), use fahrenheit scheme
                if self.layer_id == 2:
                    colorscheme = 'temp-fahrenheit-noalpha'
                else:
                    colorscheme = 'default'
        else:
            colorscheme = 'default'

        # Build URL
        url = f"https://{self.api.map_server}/api/v1/legend/{colorscheme}/{self.layer_id}"
        params = {"token": token}

        # Cache file
        cache_key = f"legend_{self.layer_id}_{colorscheme}.png"
        cache_file = join(CACHE_BASE, cache_key)

        if exists(cache_file):
            return cache_file

        try:
            response = requests.get(
                url, params=params, headers=OSM_HEADERS, timeout=10)
            if response.status_code == 200:
                with open(cache_file, 'wb') as f:
                    f.write(response.content)
                return cache_file
            else:
                if DEBUG:
                    print(
                        f"[ForecaMapViewer] Legend download error: {response.status_code}")
        except Exception as e:
            print(f"[ForecaMapViewer] Legend exception: {e}")
        return None

    def toggle_legend(self):
        if self.legend_active:
            self.legend.hide()
        else:
            legend_path = self.download_legend()
            if legend_path:
                self.legend = self.session.instantiateDialog(
                    MapLegendOverlayImage,
                    layer_type='temp',
                    image_path=legend_path
                )
            else:
                self.legend = self.session.instantiateDialog(
                    MapLegendOverlay,
                    layer_type='temp'
                )
            self.legend.show()
        self.legend_active = not self.legend_active

    def download_tile_grid_async(self, timestamp):
        print("[ForecaMapViewer] download_tile_grid_async started")

        def download_thread():
            print("[ForecaMapViewer] download_thread running")
            cx, cy = self.latlon_to_tile(
                self.center_lat, self.center_lon, self.zoom_level)
            offset_cols = self.grid_cols // 2
            offset_rows = self.grid_rows // 2

            osm_tiles = []
            foreca_tiles = []
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
                        print(f"[ForecaMapViewer] OSM tile missing: ({x},{y})")

                    # Tile Foreca
                    foreca_path = self.get_foreca_tile(
                        x, y, self.zoom_level, timestamp)
                    if foreca_path and exists(foreca_path):
                        foreca_tiles.append(
                            (dx + offset_cols, dy + offset_rows, foreca_path))
                    else:
                        print(
                            f"[ForecaMapViewer] Foreca tile missing: ({x},{y})")
            if osm_tiles:
                print(
                    f"[ForecaMapViewer] {len(osm_tiles)} OSM tiles, {len(foreca_tiles)} Foreca tiles")
                merged = self.merge_tile_grid(osm_tiles, foreca_tiles)
                if merged:
                    reactor.callFromThread(self.show_map, merged)
                else:
                    reactor.callFromThread(
                        lambda: self["info"].setText(
                            _("Merge failed")))
            else:
                print("[ForecaMapViewer] No OSM tiles")
                reactor.callFromThread(
                    lambda: self["info"].setText(
                        _("No OSM tiles")))

            # Reset flag quando il thread termina
            reactor.callFromThread(self._reset_download_flag)

        Thread(target=download_thread).start()

    def _reset_download_flag(self):
        self._downloading = False

    def merge_tile_grid(self, osm_tiles, foreca_tiles):
        try:
            # Create background with OSM tiles
            bg = Image.new('RGBA', (self.map_w, self.map_h), (0, 0, 0, 255))
            for col, row, path in osm_tiles:
                tile = Image.open(path).convert('RGBA')
                x = col * TILE_SIZE
                y = row * TILE_SIZE
                bg.paste(tile, (x, y), tile)

            # Overlay radar tiles
            for col, row, path in foreca_tiles:
                tile = Image.open(path).convert('RGBA')
                x = col * TILE_SIZE
                y = row * TILE_SIZE
                bg.paste(tile, (x, y), tile)

            bg_rgb = bg.convert('RGB')
            out_path = join(
                OSM_CACHE_DIR,
                f"merged_{self.layer_id}_{self.zoom_level}.jpg")
            bg_rgb.save(out_path, 'JPEG', quality=90)
            return out_path
        except Exception as e:
            print(f"[ForecaMapViewer] merge error: {e}")
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
            print(f"[ForecaMapViewer] Error showing map: {e}")
            self["info"].setText(_("Error loading map"))

    def zoom_in(self):
        if self.zoom_level < self.max_zoom:
            self.zoom_level += 1
            self['zoom_label'].setText(_("Zoom: ") + str(self.zoom_level))
            self.load_current_tile()

    def zoom_out(self):
        if self.zoom_level > self.min_zoom:
            self.zoom_level -= 1
            self['zoom_label'].setText(_("Zoom: ") + str(self.zoom_level))
            self.load_current_tile()

    def prev_time(self):
        if len(self.timestamps) > 1:
            self.current_time_index = (
                self.current_time_index - 1) % len(self.timestamps)
            self.load_current_tile()

    def next_time(self):
        if len(self.timestamps) > 1:
            self.current_time_index = (
                self.current_time_index + 1) % len(self.timestamps)
            self.load_current_tile()

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
                f"[ForecaMapViewer] _get_pan_step: zoom={self.zoom_level}, step={step:.4f}°")
        return step

    def pan_left(self):
        step = self._get_pan_step()
        new_lon = self.center_lon - step
        old_lon = self.center_lon

        if hasattr(self, 'layer_extent') and self.layer_extent:
            min_lon = self.layer_extent.get('minLon', -180)
            self.center_lon = max(min_lon, new_lon)
        else:
            self.center_lon = max(-180, min(180, new_lon))

        if DEBUG:
            print(
                f"[ForecaMapViewer] pan_left: old={old_lon:.4f}, new={self.center_lon:.4f}, step={step:.4f}")
        self.load_current_tile()

    def pan_right(self):
        step = self._get_pan_step()
        new_lon = self.center_lon + step
        old_lon = self.center_lon

        if hasattr(self, 'layer_extent') and self.layer_extent:
            max_lon = self.layer_extent.get('maxLon', 180)
            self.center_lon = min(max_lon, new_lon)
        else:
            self.center_lon = max(-180, min(180, new_lon))

        if DEBUG:
            print(
                f"[ForecaMapViewer] pan_right: old={old_lon:.4f}, new={self.center_lon:.4f}, step={step:.4f}")
        self.load_current_tile()

    def pan_up(self):
        step = self._get_pan_step() * 2
        new_lat = self.center_lat + step
        old_lat = self.center_lat
        self.center_lat = min(90, new_lat)
        if DEBUG:
            print(
                f"[ForecaMapViewer] pan_up: old={old_lat:.4f}, new={self.center_lat:.4f}, step={step:.4f}")
        self.load_current_tile()

    def pan_down(self):
        step = self._get_pan_step() * 2
        new_lat = self.center_lat - step
        old_lat = self.center_lat
        self.center_lat = max(-90, new_lat)
        if DEBUG:
            print(
                f"[ForecaMapViewer] pan_down: old={old_lat:.4f}, new={self.center_lat:.4f}, step={step:.4f}")
        self.load_current_tile()
