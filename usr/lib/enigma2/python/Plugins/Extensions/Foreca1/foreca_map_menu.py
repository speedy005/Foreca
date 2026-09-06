#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) @Lululla 2026
# foreca_map_menu.py - Foreca One map selection menu

from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen

from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label

from . import (
    _,
    DEBUG,
    load_skin_for_class,
    apply_global_theme,
)
from .google_translate import trans


class ForecaMapMenu(Screen, HelpableScreen):
    """Menu to select Foreca One map layers"""

    def __init__(self, session, api, unit_system='metric', region='eu'):
        self.skin = load_skin_for_class(ForecaMapMenu)
        self.session = session
        self.api = api
        self.unit_system = unit_system
        self.region = region

        Screen.__init__(self, session)
        HelpableScreen.__init__(self)
        self.setTitle(
            trans("Foreca One") +
            " | " + trans("Region") + ": " + region +
            " | " + trans("Unit System:") + " " + unit_system
        )
        self.layers = []
        self["list"] = MenuList([])
        self["info"] = Label(_("Select a map with OK"))
        self["selection_overlay"] = Label("")
        self["background_plate"] = Label("")
        self["title"] = Label("")
        self["actions"] = ActionMap(
            ["OkCancelActions", "DirectionActions"],
            {
                "cancel": self.exit,
                "ok": self.select_layer,
                "up": self.up,
                "down": self.down,
            },
            -1
        )
        self.onLayoutFinish.append(self.load_layers)
        self.onLayoutFinish.append(self._apply_theme)

    def _apply_theme(self):
        apply_global_theme(self)

    def load_layers(self):
        """Load available layers"""
        self.layers = self.api.get_capabilities()
        if DEBUG:
            print(f"[DEBUG] Layers ricevuti ({len(self.layers)}):")
        for layer in self.layers:
            layer_id = layer['id']
            title = layer.get('title', 'N/A')
            layer_type = layer.get('type', 'N/A')
            colorschemes = layer.get('colorschemes', [])
            if DEBUG:
                print(
                    f"  ID: {layer_id}, Title: {title}, Type: {layer_type}, Schemes: {colorschemes}")

        if not self.layers:
            self["info"].setText(_("Error loading maps. Check connection."))
            return

        items = []
        for layer in self.layers:
            title = layer.get('title', f"Layer {layer['id']}")
            if 'wind symbol' in title.lower():
                continue
            if layer_id == 3:
                continue
            items.append((trans(title), layer))

        self["list"].setList(items)
        self.setTitle(trans("Foreca One Maps") + " - " + self.region.upper())
        self["title"].setText(
            trans("Foreca One | Region {} | Unit System: {}").format(
                self.region.upper(), self.unit_system))

    def up(self):
        self["list"].up()

    def down(self):
        self["list"].down()

    def select_layer(self):
        selection = self["list"].getCurrent()
        if selection:
            layer = selection[1]
            layer_type = layer.get('type', 'png')

            if layer_type == 'windsvg':
                from .foreca_svg_map_viewer import ForecaSVGMapViewer
                self.session.open(
                    ForecaSVGMapViewer,
                    self.api,
                    layer,
                    self.unit_system,
                    self.region
                )
            else:
                from .foreca_map_viewer import ForecaMapViewer
                self.session.open(
                    ForecaMapViewer,
                    self.api,
                    layer,
                    self.unit_system,
                    self.region
                )

    def exit(self):
        self.close()
