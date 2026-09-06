#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) @Lululla 2026
# info_dialog.py - Info about the plugin

from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen

from Components.ActionMap import HelpableActionMap
from Components.Label import Label

from enigma import gRGB
from skin import parseColor

from . import (
    _,
    VERSION,
    _AUTHOR_,
    THANKS,
    IDEAS,
    load_skin_for_class,
    apply_global_theme,
)


class InfoDialog(Screen, HelpableScreen):
    def __init__(self, session, foreca_preview):
        self.skin = load_skin_for_class(InfoDialog)
        Screen.__init__(self, session)
        HelpableScreen.__init__(self)
        self.setTitle(_("Info"))
        self.foreca_preview = foreca_preview
        self['version_label'] = Label(
            _('Foreca One Weather and Forecast ver. %s') % VERSION)
        self['mod_label'] = Label(
            _('Thanks {thanks} and other friends for suggestions').format(
                thanks=THANKS))
        IA = '%s\n%s' % (IDEAS, _AUTHOR_)
        self['author_label'] = Label(
            _('Original design and idea by %s') % IA
        )
        self['website_label'] = Label(
            'http://linuxsat-support.com\nhttp://www.corvoboys.org')
        self["background_plate"] = Label("")
        self["selection_overlay"] = Label("")
        self["actions"] = HelpableActionMap(
            self, "ForecaActions",
            {
                "cancel": (self.close, _("Exit")),
                "red": (self.close, _("Exit")),
                "ok": (self.close, _("Exit"))
            },
            -1
        )
        self.onShow.append(self.initialize_colors)
        self.onLayoutFinish.append(self._apply_theme)

    def _apply_theme(self):
        apply_global_theme(self)

    def initialize_colors(self):
        current_color = gRGB(
            int(self.foreca_preview.rgbmyr),
            int(self.foreca_preview.rgbmyg),
            int(self.foreca_preview.rgbmyb)
        )
        self["background_plate"].instance.setBackgroundColor(current_color)
        self["selection_overlay"].instance.setBackgroundColor(
            parseColor(self.foreca_preview.alpha)
        )
