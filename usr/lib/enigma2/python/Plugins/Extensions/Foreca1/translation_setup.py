#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) @Lululla 2026
# translation_setup.py - Translation settings screen

from Screens.Screen import Screen
from Components.ActionMap import HelpableActionMap
from Components.Label import Label
from Components.ConfigList import ConfigListScreen
from Components.Sources.StaticText import StaticText
from Components.config import getConfigListEntry, config
from Screens.HelpMenu import HelpableScreen
from enigma import gRGB
from skin import parseColor
from os.path import exists, join

from . import (
    _,
    load_skin_for_class,
    SYSTEM_DIR
)


class TranslationSetup(Screen, ConfigListScreen, HelpableScreen):
    """
    Translation settings screen.
    Loads the appropriate skin for the resolution (HD/FHD/WQHD).
    Uses ConfigListScreen for a clean UI.
    """

    def __init__(self, session):
        self.skin = load_skin_for_class(TranslationSetup)
        Screen.__init__(self, session)
        HelpableScreen.__init__(self)

        self.setTitle(_('Translation Settings'))

        self["background_plate"] = Label("")
        self["selection_overlay"] = Label("")

        self.translation_engine = config.plugins.foreca.translation_engine
        self.target_language = config.plugins.foreca.target_language

        self.list = [
            getConfigListEntry(
                _("Use Google Translate"),
                self.translation_engine),
            getConfigListEntry(
                _("Target Language"),
                self.target_language),
        ]

        ConfigListScreen.__init__(self, self.list, session=session)
        self["key_red"] = StaticText(_("Cancel"))
        self["key_green"] = StaticText(_("Save"))
        self["status"] = StaticText("")
        self["actions"] = HelpableActionMap(
            self,
            ["SetupActions", "ColorActions"],
            {
                "cancel": (self.close, _("Close setup without saving")),
                "save": (self.save, _("Save translation settings")),
                "green": (self.save, _("Save translation settings")),
                "red": (self.close, _("Close setup without saving")),
            },
            -2,
        )

        # Apply theme after layout is complete (widgets are fully rendered)
        self.onLayoutFinish.append(self.apply_theme)

    def apply_theme(self):
        """Apply colors and transparency like other hybrid screens."""
        color_file = join(SYSTEM_DIR, "set_color.conf")
        alpha_file = join(SYSTEM_DIR, "set_alpha.conf")

        if exists(color_file):
            try:
                with open(color_file, "r") as f:
                    parts = f.read().strip().split()
                    if len(parts) >= 3:
                        r, g, b = parts[0], parts[1], parts[2]
                        bg_color = gRGB(int(r), int(g), int(b))
                        if "background_plate" in self and self["background_plate"].instance is not None:
                            self["background_plate"].instance.setBackgroundColor(
                                bg_color)
            except Exception as e:
                print("[TranslationSetup] Error loading color:", e)

        if exists(alpha_file):
            try:
                with open(alpha_file, "r") as f:
                    alpha = f.read().strip()
                    if "selection_overlay" in self and self["selection_overlay"].instance is not None:
                        self["selection_overlay"].instance.setBackgroundColor(
                            parseColor(alpha))
            except Exception as e:
                print("[TranslationSetup] Error loading alpha:", e)

    def save(self):
        """Save settings and close."""
        config.plugins.foreca.translation_engine.save()
        config.plugins.foreca.target_language.save()
        self.close(True)

    def cancel(self):
        """Close without saving."""
        self.close(False)
