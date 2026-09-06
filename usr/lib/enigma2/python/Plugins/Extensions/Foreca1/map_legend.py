#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# map_legend.py - Color legend screen for weather maps

from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Components.ActionMap import HelpableActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from enigma import gRGB
from os.path import exists, join
from os import close, makedirs, remove, listdir
from PIL import Image
import tempfile

from . import (
    _,
    load_skin_for_class,
    apply_global_theme,
    TEMP_DIR,
    DEBUG
)

MAPLEGEND_DIR = join(TEMP_DIR, "maplegend")
if not exists(MAPLEGEND_DIR):
    makedirs(MAPLEGEND_DIR)


class MapLegend(Screen, HelpableScreen):
    def __init__(
            self,
            session,
            layer_type="precip",
            overlay=False,
            image_path=None):
        self.overlay = overlay
        self.image_path = image_path

        Screen.__init__(self, session)
        HelpableScreen.__init__(self)
        self.setTitle(_("Color Legend"))
        self.layer_type = layer_type.lower()
        self["background_plate"] = Label("")
        self["selection_overlay"] = Label("")
        for i in range(1, 8):
            self[f"color{i}"] = Label("")
            self[f"desc{i}"] = Label("")

        self["legend_image"] = Pixmap()

        self["actions"] = HelpableActionMap(
            self, "ForecaActions",
            {
                "cancel": (self.close, _("Exit")),
                "ok": (self.close, _("Close")),
                "red": (self.close, _("Exit")),
            },
            -1
        )
        self.onLayoutFinish.append(self._apply_theme)
        self.onLayoutFinish.append(self.populate_legend)
        self.onClose.append(self.clear_cache)

    def _apply_theme(self):
        apply_global_theme(self)

    def populate_legend(self):
        if self.image_path and exists(self.image_path):
            print(f"[MapLegend] Showing image legend: {self.image_path}")
            for i in range(1, 8):
                if f"color{i}" in self:
                    self[f"color{i}"].hide()
                if f"desc{i}" in self:
                    self[f"desc{i}"].hide()

            if "legend_image" in self and self["legend_image"].instance:
                widget_size = self["legend_image"].instance.size()
                target_w = widget_size.width()
                target_h = widget_size.height()
                if target_w <= 0 or target_h <= 0:
                    target_w = 290
                    target_h = 1000
            else:
                print("[MapLegend] legend_image widget not found, cannot resize")
                return

            try:
                img = Image.open(self.image_path).convert("RGBA")
                ratio = min(target_w / img.width, target_h / img.height)
                new_w = int(img.width * ratio)
                new_h = int(img.height * ratio)
                img_resized = img.resize(
                    (new_w, new_h), Image.Resampling.LANCZOS)

                canvas = Image.new('RGBA', (target_w, target_h), (0, 0, 0, 0))
                paste_x = (target_w - new_w) // 2
                paste_y = (target_h - new_h) // 2
                canvas.paste(img_resized, (paste_x, paste_y), img_resized)

                fd, temp_path = tempfile.mkstemp(
                    suffix='.png', dir=MAPLEGEND_DIR)
                close(fd)
                canvas.save(temp_path)

                self["legend_image"].instance.setPixmapFromFile(temp_path)
                self["legend_image"].show()
                self["legend_image"].instance.invalidate()
            except Exception as e:
                print(f"[MapLegend] Error processing image: {e}")
                self["legend_image"].instance.setPixmapFromFile(
                    self.image_path)
                self["legend_image"].show()
            return
        else:
            print("[MapLegend] populate_legend called (text mode)")
            for i in range(1, 8):
                self[f"color{i}"].hide()
                self[f"desc{i}"].hide()

            if self.layer_type in ("precip", "rain", "radar"):
                legend = [
                    (0x0000ff, _("Light rain / drizzle")),
                    (0x00aaff, _("Light to moderate")),
                    (0x00ff00, _("Moderate rain")),
                    (0xffff00, _("Heavy rain")),
                    (0xffaa00, _("Very heavy rain")),
                    (0xff0000, _("Extreme / thunderstorms")),
                    (0xcccccc, _("Snow / ice")),
                ]
            elif self.layer_type in ("temp", "temperature"):
                legend = [
                    (0x0000ff, _("Cold (< 0°C)")),
                    (0x00aaff, _("Cool (0-10°C)")),
                    (0x00ff00, _("Mild (10-20°C)")),
                    (0xffff00, _("Warm (20-30°C)")),
                    (0xffaa00, _("Hot (30-40°C)")),
                    (0xff0000, _("Very hot (>40°C)")),
                    (0xcccccc, _("Ice / frost")),
                ]
            elif self.layer_type == "wind":
                legend = [
                    (0x00ff00, _("Light (0-20 km/h)")),
                    (0xffff00, _("Moderate (20-40 km/h)")),
                    (0xffaa00, _("Strong (40-60 km/h)")),
                    (0xff0000, _("Gale force (>60 km/h)")),
                ]
            else:
                legend = [
                    (0xffffff, _("No specific legend available.")),
                ]

            for i, (color, desc) in enumerate(legend, start=1):
                if i > 7:
                    break
                self[f"desc{i}"].setText(desc)
                if self[f"color{i}"].instance:
                    r = (color >> 16) & 0xFF
                    g = (color >> 8) & 0xFF
                    b = color & 0xFF
                    print(f"[MapLegend] Setting color{i} to RGB({r},{g},{b})")
                    self[f"color{i}"].instance.setBackgroundColor(
                        gRGB(r, g, b))
                    self[f"color{i}"].instance.setTransparent(False)
                    self[f"color{i}"].instance.invalidate()
                else:
                    print(f"[MapLegend] WARNING: color{i}.instance is None")
                self[f"color{i}"].show()
                self[f"desc{i}"].show()

            for i in range(len(legend) + 1, 8):
                self[f"color{i}"].hide()
                self[f"desc{i}"].hide()

    def clear_cache(self):
        try:
            if exists(MAPLEGEND_DIR):
                for f in listdir(MAPLEGEND_DIR):
                    if f.endswith('.png') or f.endswith('.jpg'):
                        remove(join(MAPLEGEND_DIR, f))
                if DEBUG:
                    print("[RainViewerMaps] Cache cleaned")
        except Exception as e:
            print(f"[RainViewerMaps] Error cleaning cache: {e}")


class MapLegendOverlayText(MapLegend):
    """Textual legend overlay (small skin)."""

    def __init__(self, session, layer_type="precip", **kwargs):
        self.skin = load_skin_for_class(MapLegendOverlayText)
        super().__init__(session, layer_type, overlay=True, image_path=None)


class MapLegendOverlayImage(MapLegend):
    """Image legend overlay (large skin)."""

    def __init__(
            self,
            session,
            layer_type="precip",
            image_path=None,
            **kwargs):
        self.skin = load_skin_for_class(MapLegendOverlayImage)
        super().__init__(session, layer_type, overlay=True, image_path=image_path)


MapLegendOverlay = MapLegendOverlayText
