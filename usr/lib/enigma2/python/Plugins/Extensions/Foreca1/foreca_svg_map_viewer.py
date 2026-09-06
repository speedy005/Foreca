#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) @Lululla 2026
# foreca_svg_map_viewer.py - SVG Map Viewer with pan and zoom

from os.path import exists, join
from os import makedirs, listdir, remove
from math import log, tan, pi, radians, cos
from datetime import datetime

from PIL import Image
from twisted.internet import reactor
from enigma import ePoint, eSize

from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen

from Components.ActionMap import HelpableActionMap
from Components.Pixmap import Pixmap
from Components.Label import Label
from Components.Sources.StaticText import StaticText

from .map_legend import MapLegendOverlay
from .google_translate import trans
from . import (
    _,
    DEBUG,
    THUMB_PATH,
    load_skin_for_class,
    apply_global_theme,
    TEMP_DIR
)
from .foreca_map_viewer import REGION_CENTERS, get_background_for_layer

SVG_MAPS_DIR = join(TEMP_DIR, "svgmapviewer")
if not exists(SVG_MAPS_DIR):
    makedirs(SVG_MAPS_DIR)

TILE_SIZE = 256


class ForecaSVGMapViewer(Screen, HelpableScreen):
    def __init__(self, session, api, layer, unit_system='metric', region='eu'):
        self.grid_cols = 5
        self.grid_rows = 5
        self.tile_widgets = []
        for row in range(self.grid_rows):
            for col in range(self.grid_cols):
                name = f"tile_{row}_{col}"
                self[name] = Pixmap()
                self.tile_widgets.append((row, col, name))

        self.skin = load_skin_for_class(ForecaSVGMapViewer)
        Screen.__init__(self, session)
        HelpableScreen.__init__(self)

        self.api = api
        self.layer = layer
        self.layer_id = layer['id']
        self.layer_title = layer.get('title', 'SVG Map')
        self.unit_system = unit_system
        self.region = region.lower()
        self.setTitle(f"Foreca One: {self.layer_title}")

        self.legend = self.session.instantiateDialog(
            MapLegendOverlay, 'precip')
        self.legend_active = False

        if self.region in REGION_CENTERS:
            self.center_lat, self.center_lon = REGION_CENTERS[self.region]
        else:
            self.center_lat, self.center_lon = 50.0, 10.0

        self.tile_size = TILE_SIZE
        # Compute initial zoom level based on latitude (if possible)
        self.zoom_level = 4
        try:
            lat_float = float(self.center_lat)
            self.zoom_level = max(4, min(6, int(8 - abs(lat_float) / 15)))
        except (ValueError, TypeError):
            self.zoom_level = 4

        self.min_zoom = 2
        self.max_zoom = 21

        self.timestamps = layer.get('times', {}).get('available', [])
        self.current_time_index = layer.get('times', {}).get('current', 0)

        self._downloading = False

        self["background"] = Pixmap()
        self["background"].hide()
        self["map"] = Pixmap()
        self["map"].hide()
        self["title"] = Label(self.layer_title)
        self["layerinfo"] = Label("")
        self["time"] = Label(_("Loading..."))
        self["info"] = Label(_("Use ← → to change time | OK to exit"))
        self['key_red'] = StaticText(_("Exit"))
        self['key_green'] = StaticText(_("Zoom+"))
        self['key_yellow'] = StaticText(_("Zoom-"))
        self['key_blue'] = StaticText()
        self['zoom_label'] = Label(_("Zoom: ") + str(self.zoom_level))
        self["background_plate"] = Label("")
        self["selection_overlay"] = Label("")
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
                "showEventInfo": (self.toggle_legend, _("Color legend")),
            },
            -1
        )
        self.on_first_layout = True
        self.clear_cache()
        self.onLayoutFinish.append(self._apply_theme)
        self.onLayoutFinish.append(self.on_first_layout_cb)
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
                    f"[ForecaSVGMapViewer] Widget size: {self.widget_width}x{self.widget_height}")

    def clear_cache(self):
        try:
            if exists(SVG_MAPS_DIR):
                for f in listdir(SVG_MAPS_DIR):
                    if f.endswith('.png') or f.endswith('.jpg'):
                        remove(join(SVG_MAPS_DIR, f))
                if DEBUG:
                    print("[ForecaSVGMapViewer] Cache cleaned")
        except Exception as e:
            print(f"[ForecaSVGMapViewer] Error cleaning cache: {e}")

    def on_first_layout_cb(self):
        if self.on_first_layout:
            self.on_first_layout = False
            reactor.callLater(0.1, self.do_layout)

    def do_layout(self):
        map_widget = self["map"]
        if map_widget and map_widget.instance:
            pos = map_widget.getPosition()
            size = map_widget.instance.size()
            x, y = pos
            if x >= 0 and y >= 0 and size.width() > 0 and size.height() > 0:
                self.bg_x = x
                self.bg_y = y
                self.bg_width = size.width()
                self.bg_height = size.height()
            else:
                self.bg_x, self.bg_y = 49, 127
                self.bg_width, self.bg_height = 1819, 853
        else:
            self.bg_x, self.bg_y = 49, 127
            self.bg_width, self.bg_height = 1819, 853

        self.scale_x = self.bg_width / float(self.grid_cols * 256)
        self.scale_y = self.bg_height / float(self.grid_rows * 256)

        if "background" in self and self["background"].instance:
            self["background"].instance.move(ePoint(self.bg_x, self.bg_y))
            self["background"].instance.resize(
                eSize(self.bg_width, self.bg_height))
            self["background"].instance.setZPosition(2)
            self["background"].show()

        for row, col, name in self.tile_widgets:
            self[name].hide()

        self.load_current_tile()

    def latlon_to_tile(self, lat, lon, zoom):
        lat_rad = radians(lat)
        n = 2.0 ** zoom
        x = int((lon + 180.0) / 360.0 * n)
        y = int((1.0 - log(tan(lat_rad) + 1.0 / cos(lat_rad)) / pi) / 2.0 * n)
        return x, y

    def load_current_tile(self):
        if self._downloading:
            print("[ForecaSVGMapViewer] Already downloading, skipping")
            return
        self._downloading = True

        if not self.timestamps:
            now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            self.timestamps = [now]
            self.current_time_index = 0
            self["time"].setText(trans("Using current time"))

        if self.current_time_index >= len(self.timestamps):
            self.current_time_index = 0

        timestamp = self.timestamps[self.current_time_index]
        try:
            dt = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
            display_time = dt.strftime("%d/%m %H:%M UTC")
        except BaseException:
            display_time = timestamp

        self["time"].setText(f"{display_time}")
        self["zoom_label"].setText(f"Zoom: {self.zoom_level}")
        self["info"].setText(_("Downloading tiles..."))

        from threading import Thread
        Thread(target=self.download_tiles, args=(timestamp,)).start()

    def download_tiles(self, timestamp):
        try:
            cx, cy = self.latlon_to_tile(
                self.center_lat, self.center_lon, self.zoom_level)
            offset_cols = self.grid_cols // 2
            offset_rows = self.grid_rows // 2
            tile_files = []
            for dx in range(-offset_cols, offset_cols + 1):
                for dy in range(-offset_rows, offset_rows + 1):
                    tx = cx + dx
                    ty = cy + dy
                    path = self.api.get_tile(
                        self.layer_id,
                        timestamp,
                        self.zoom_level,
                        tx, ty,
                        self.unit_system
                    )
                    if path and exists(path):
                        col = dx + offset_cols
                        row = dy + offset_rows
                        tile_files.append((col, row, path))
            if DEBUG:
                print(f"[DEBUG] Downloaded SVG tiles: {len(tile_files)}")
            if tile_files:
                self.tile_files = tile_files
                bg_path = self.create_background_image()
                if bg_path:
                    svg_path = self.create_composite_svg(tile_files)
                    reactor.callFromThread(self.display_svg, svg_path, bg_path)
                else:
                    reactor.callFromThread(self.show_error)
            else:
                reactor.callFromThread(self.show_error)
        except Exception as e:
            print(f"[ForecaSVGMapViewer] Exception in download_tiles: {e}")
            reactor.callFromThread(self.show_error)
        finally:
            reactor.callFromThread(self._reset_download_flag)

    def _reset_download_flag(self):
        self._downloading = False

    def get_foreca_tile(self, x, y, z, timestamp):
        return self.api.get_tile(
            self.layer_id,
            timestamp,
            z,
            x, y,
            self.unit_system
        )

    def display_background(self, bg_path):
        """Display the background PNG directly, without intermediate SVG."""
        if exists(bg_path):
            self["background"].instance.setPixmapFromFile(bg_path)
            self["background"].show()
            if DEBUG:
                print("[DEBUG] Background PNG displayed correctly")
        else:
            print(f"[DEBUG] Background PNG not found: {bg_path}")

    def extract_svg_content(self, svg_text):
        """Extract the content between <svg> and </svg> (removing the main tags)."""
        start = svg_text.find('<svg')
        if start == -1:
            return None
        end_of_open = svg_text.find('>', start)
        if end_of_open == -1:
            return None
        content_start = end_of_open + 1
        close_tag = svg_text.rfind('</svg>')
        if close_tag == -1:
            return None
        return svg_text[content_start:close_tag]

    def create_background_image(self):
        bg_file = get_background_for_layer(self.layer_title, self.region)
        bg_path = join(THUMB_PATH, bg_file)
        if exists(bg_path):
            try:
                bg_img = Image.open(bg_path).convert("RGB")
                bg_img = bg_img.resize(
                    (self.bg_width, self.bg_height), Image.Resampling.LANCZOS)
                temp_bg = join(
                    SVG_MAPS_DIR,
                    f"background_{self.region}_{self.zoom_level}.png")
                bg_img.save(temp_bg, 'PNG')
                if DEBUG:
                    print(
                        f"[DEBUG] Background generated: {temp_bg} size {self.bg_width}x{self.bg_height}")
                return temp_bg
            except Exception as e:
                print(f"[ForecaSVG] Error generating background: {e}")
                return None
        else:
            if DEBUG:
                print(f"[ForecaSVG] Background file not found: {bg_path}")
            return None

    def create_composite_svg(self, tile_files):
        cell_width = self.bg_width / float(self.grid_cols)
        cell_height = self.bg_height / float(self.grid_rows)
        svg_content = f'''<?xml version="1.0" encoding="utf-8"?>
    <svg xmlns="http://www.w3.org/2000/svg" width="{self.bg_width}" height="{self.bg_height}" viewBox="0 0 {self.bg_width} {self.bg_height}">
    '''
        for col, row, path in tile_files:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    tile_text = f.read()
                inner = self.extract_svg_content(tile_text)
                if inner:
                    x = col * cell_width
                    y = row * cell_height
                    transform = f"translate({x}, {y}) scale({cell_width / 256}, {cell_height / 256})"
                    svg_content += f'<g transform="{transform}">\n{inner}\n</g>\n'
            except Exception as e:
                print(f"[Foreca1SVG] Error processing {path}: {e}")
        svg_content += '</svg>'

        temp_svg = join(
            SVG_MAPS_DIR,
            f"composite_{self.layer_id}_{self.zoom_level}.svg")
        with open(temp_svg, 'w', encoding='utf-8') as f:
            f.write(svg_content)
        if DEBUG:
            print(
                f"[DEBUG] Composite SVG (original colors) generated: {temp_svg}")
        return temp_svg

    def display_svg(self, svg_path, bg_path):
        if bg_path and exists(bg_path):
            if DEBUG:
                print('bg_path:', str(bg_path))
            self["background"].instance.setPixmapFromFile(bg_path)
            self["background"].show()
            if DEBUG:
                print(f"[DEBUG] Background PNG displayed: {bg_path}")
        else:
            self["background"].hide()

        if svg_path and exists(svg_path):
            self["map"].instance.setPixmapFromFile(svg_path)
            self["map"].show()
            if DEBUG:
                print(f"[DEBUG] Composite SVG displayed: {svg_path}")
        else:
            self["map"].hide()

        current_time = self.timestamps[self.current_time_index]
        try:
            dt = datetime.strptime(current_time, "%Y-%m-%dT%H:%M:%SZ")
            display_time = dt.strftime("%d/%m %H:%M UTC")
        except BaseException:
            display_time = current_time
        self["time"].setText(
            f"{display_time} | Grid: {self.grid_cols}x{self.grid_rows}")
        self["info"].setText(_("Map & Tiles Loaded"))

    def update_layer_info(self):
        try:
            layer_name = self.layer_title
            data_type = self.get_data_type_from_layer(layer_name)
            region_name = self.region.upper()
            unit = "Metric" if self.unit_system == 'metric' else "Imperial"
            self["layerinfo"].setText(f"{data_type} - {region_name} ({unit})")
        except BaseException:
            self["layerinfo"].setText(self.layer_title)

    def show_error(self):
        self["time"].setText(trans("No tiles available"))
        self["info"].setText(trans("Try different zoom or region"))

    def _adjust_grid_to_widget(self):
        if "map" in self and self["map"].instance:
            w = self["map"].instance.size().width()
            h = self["map"].instance.size().height()
            self.grid_cols = (w + self.tile_size - 1) // self.tile_size
            self.grid_rows = (h + self.tile_size - 1) // self.tile_size
            self.map_w = self.grid_cols * self.tile_size
            self.map_h = self.grid_rows * self.tile_size

    def zoom_in(self):
        if self.zoom_level < self.max_zoom:
            self.zoom_level += 1
            self._adjust_grid_to_widget()
            self.load_current_tile()

    def zoom_out(self):
        if self.zoom_level > self.min_zoom:
            self.zoom_level -= 1
            self._adjust_grid_to_widget()
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

    def _get_pan_step(self):
        """Calcola il passo di spostamento in gradi in base allo zoom corrente."""
        tile_size_lon = 360.0 / (2 ** self.zoom_level)
        step = tile_size_lon * 0.8  # 80% of tile
        if DEBUG:
            print(
                f"[ForecaSVGMapViewer] _get_pan_step: zoom={self.zoom_level}, step={step:.4f}°")
        return step

    def pan_left(self):
        step = self._get_pan_step()
        new_lon = self.center_lon - step
        old_lon = self.center_lon
        self.center_lon = max(-180, min(180, new_lon))
        if DEBUG:
            print(
                f"[ForecaSVGMapViewer] pan_left: old={old_lon:.4f}, new={self.center_lon:.4f}, step={step:.4f}")
        self.load_current_tile()

    def pan_right(self):
        step = self._get_pan_step()
        new_lon = self.center_lon + step
        old_lon = self.center_lon
        self.center_lon = max(-180, min(180, new_lon))
        if DEBUG:
            print(
                f"[ForecaSVGMapViewer] pan_right: old={old_lon:.4f}, new={self.center_lon:.4f}, step={step:.4f}")
        self.load_current_tile()

    def pan_up(self):
        step = self._get_pan_step() * 2
        new_lat = self.center_lat + step
        old_lat = self.center_lat
        self.center_lat = min(90, new_lat)
        if DEBUG:
            print(
                f"[ForecaSVGMapViewer] pan_up: old={old_lat:.4f}, new={self.center_lat:.4f}, step={step:.4f}")
        self.load_current_tile()

    def pan_down(self):
        step = self._get_pan_step() * 2
        new_lat = self.center_lat - step
        old_lat = self.center_lat
        self.center_lat = max(-90, new_lat)
        if DEBUG:
            print(
                f"[ForecaSVGMapViewer] pan_down: old={old_lat:.4f}, new={self.center_lat:.4f}, step={step:.4f}")
        self.load_current_tile()
