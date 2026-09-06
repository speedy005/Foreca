# -*- coding: UTF-8 -*-
# moon_details_screen.py - Moon details view

from os.path import exists
from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Components.ActionMap import HelpableActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.Sources.StaticText import StaticText
from enigma import gRGB
from skin import parseColor

from . import (
    _,
    load_skin_for_class,
    apply_global_theme,
)
from .google_translate import trans

# Foreca One Weather Forecast for Enigma2
# Copyright (C) 2026 @Lululla
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#
# -------------------------------------------------------
#
#          Foreca One Weather Forecast E2
#
#   This Plugin retrieves the actual weather forecast
#   for the next 10 days from the Foreca website.
#        We wish all users wonderful weather!
#
#     Source of information: https://www.foreca.com
#     Original design and idea by @Bauernbub
#     Enigma2 all code rewrite by @Lululla, 2026
#     Thank's @Orlandox and other friends for suggestions and test
# -------------------------------------------------------

# ---------- Utility functions ----------


class MoonDetailsScreen(Screen, HelpableScreen):
    def __init__(self, session, icon_path, data):

        self.skin = load_skin_for_class(MoonDetailsScreen)

        Screen.__init__(self, session)
        HelpableScreen.__init__(self)

        self.icon_path = icon_path
        self.data = data

        # Inherit colors and transparency from main screen (if available)
        self.rgbmyr = getattr(session, 'rgbmyr', '0')
        self.rgbmyg = getattr(session, 'rgbmyg', '80')
        self.rgbmyb = getattr(session, 'rgbmyb', '239')
        self.alpha = getattr(session, 'alpha', '#40000000')

        self.setTitle(_("Moon Details"))

        # Widgets
        self["title"] = Label()
        self["moon_icon"] = Pixmap()
        self["phase_label"] = Label()
        self["illum_label"] = Label()
        self["distance_label"] = Label()
        self["moonrise_label"] = Label()
        self["moonset_label"] = Label()
        self["rise_azimuth_label"] = Label()
        self["set_azimuth_label"] = Label()
        self["transit_label"] = Label()
        self["transit_alt_label"] = Label()
        self["magnitude_label"] = Label()
        self["angular_diam_label"] = Label()
        self["age_label"] = Label()

        # Background and overlay (for skin theming)
        self["background_plate"] = Label("")
        self["selection_overlay"] = Label("")

        # Buttons (standard colors)
        self["key_red"] = StaticText(_("Exit"))
        self["key_green"] = StaticText("")
        self["key_yellow"] = StaticText("")
        self["key_blue"] = StaticText("")
        self["title"].setText(_("Moon Details"))
        self["actions"] = HelpableActionMap(
            self, "ForecaActions",
            {
                "cancel": (self.close, _("Exit")),
                "red": (self.close, _("Exit")),
            },
            -1
        )

        self.onLayoutFinish.append(self.update_display)
        self.onLayoutFinish.append(self._apply_theme)

    def _apply_theme(self):
        apply_global_theme(self)

    def update_display(self):
        # Load moon icon
        if self.icon_path and exists(self.icon_path):
            self["moon_icon"].instance.setPixmapFromFile(self.icon_path)
            self["moon_icon"].show()
        else:
            self["moon_icon"].hide()

        data = self.data

        # Phase name translated
        phase = data.get('phase_name', 'N/A')
        self["phase_label"].setText(_("Phase: {}").format(trans(phase)))

        self["illum_label"].setText(
            _("Illumination: {:.1f}%").format(
                data.get(
                    'illumination', 0)))
        self["distance_label"].setText(
            _("Distance: {} km").format(
                data.get(
                    'distance', 0)))
        self["moonrise_label"].setText(
            _("Moonrise: {}").format(
                data.get(
                    'moonrise', 'N/A')))
        self["moonset_label"].setText(
            _("Moonset: {}").format(
                data.get(
                    'moonset', 'N/A')))

        extra = data.get('extra', {})
        self["rise_azimuth_label"].setText(
            _("Rise azimuth: {:.0f}°").format(
                extra.get(
                    'rise_azimuth',
                    0)) if extra.get('rise_azimuth') is not None else _("Rise azimuth: N/A"))
        self["set_azimuth_label"].setText(
            _("Set azimuth: {:.0f}°").format(
                extra.get(
                    'set_azimuth',
                    0)) if extra.get('set_azimuth') is not None else _("Set azimuth: N/A"))
        self["transit_label"].setText(
            _("Transit (culmination): {}").format(
                extra.get(
                    'transit_time', 'N/A')))
        self["transit_alt_label"].setText(
            _("Transit altitude: {:.0f}°").format(
                extra.get(
                    'transit_altitude',
                    0)) if extra.get('transit_altitude') is not None else _("Transit altitude: N/A"))
        self["magnitude_label"].setText(
            _("Apparent magnitude: {:.2f}").format(
                extra.get(
                    'magnitude',
                    0)) if extra.get('magnitude') is not None else _("Magnitude: N/A"))
        self["angular_diam_label"].setText(
            _("Angular diameter: {:.0f}″").format(
                extra.get(
                    'angular_diameter',
                    0)) if extra.get('angular_diameter') is not None else _("Angular diameter: N/A"))
        self["age_label"].setText(_("Age since New Moon: {:.1f} days").format(
            extra.get('age', 0)) if extra.get('age') is not None else _("Age: N/A"))

        # Apply background colors
        bg = gRGB(int(self.rgbmyr), int(self.rgbmyg), int(self.rgbmyb))
        self["background_plate"].instance.setBackgroundColor(bg)
        self["selection_overlay"].instance.setBackgroundColor(
            parseColor(self.alpha))
