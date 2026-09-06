#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) @Lululla 2026
# transparency_selector.py - Transparency selection screen

from Screens.Screen import Screen
from Components.ActionMap import HelpableActionMap
from Components.Label import Label
from Components.MenuList import MenuList
from skin import parseColor
from Screens.HelpMenu import HelpableScreen

from . import (
    _,
    load_skin_for_class,
    apply_global_theme
)


class TransparencySelector(Screen, HelpableScreen):
    def __init__(self, session, foreca_preview):
        self.skin = load_skin_for_class(TransparencySelector)
        Screen.__init__(self, session)
        HelpableScreen.__init__(self)
        self.setTitle(_('Window transparency'))
        self.foreca_preview = foreca_preview
        self.transparency_levels = [
            {"name": "56%", "value": "#90000000"},
            {"name": "50%", "value": "#80000000"},
            {"name": "44%", "value": "#70000000"},
            {"name": "38%", "value": "#60000000"},
            {"name": "31%", "value": "#50000000"},
            {"name": "25%", "value": "#40000000"},
            {"name": "19%", "value": "#30000000"},
            {"name": "13%", "value": "#20000000"},
            {"name": "6%", "value": "#10000000"},
            {"name": "0%", "value": "#00000000"}
        ]
        self["menu"] = MenuList([])
        self['title_label'] = Label(_('Window transparency'))
        self["background_plate"] = Label("")
        self["selection_overlay"] = Label("")
        self["actions"] = HelpableActionMap(
            self, "ForecaActions",
            {
                "cancel": (self.exit_screen, _("Exit")),
                "red": (self.exit_screen, _("Exit")),
                "left": (self.page_up, _("Previous page")),
                "right": (self.page_down, _("Next page")),
                "up": (self.move_up, _("Previous")),
                "down": (self.move_down, _("Next")),
                "ok": (self.confirm_selection, _("Select")),
            },
            -1
        )
        self.onShow.append(self.initialize_display)
        self.onLayoutFinish.append(self._apply_theme)

    def _apply_theme(self):
        apply_global_theme(self)

    def initialize_display(self):
        self._update_background_with_alpha(self.foreca_preview.alpha)
        items = []
        for level in self.transparency_levels:
            items.append(
                _("Transparency level") +
                f" {level['name']} ({level['value']})")
        self["menu"].setList(items)
        current_alpha = self.foreca_preview.alpha
        for idx, level in enumerate(self.transparency_levels):
            if level["value"] == current_alpha:
                if self["menu"].instance and 0 <= idx < len(
                        self.transparency_levels):
                    self["menu"].moveToIndex(idx)
                break

        self.update_preview()

    def _update_background_with_alpha(self, alpha_str):
        """Apply the specified alpha to the background, keeping current RGB colors."""
        # Extract RGB values from preview
        r = int(self.foreca_preview.rgbmyr)
        g = int(self.foreca_preview.rgbmyg)
        b = int(self.foreca_preview.rgbmyb)
        # Extract the two alpha characters from the string (e.g., '#90000000'
        # -> '90')
        alpha_hex = alpha_str[1:3]
        # Build the full ARGB color
        color_str = f"#{alpha_hex}{r:02x}{g:02x}{b:02x}"
        # Apply to background_plate
        self["background_plate"].instance.setBackgroundColor(
            parseColor(color_str))
        self["background_plate"].instance.invalidate()

    def update_preview(self):
        idx = self["menu"].getSelectedIndex()
        if 0 <= idx < len(self.transparency_levels):
            level = self.transparency_levels[idx]
            # Update background with selected alpha
            self._update_background_with_alpha(level["value"])
            # Update selection overlay (if desired, you can leave it unchanged
            # or also apply alpha)
            if "selection_overlay" in self and self["selection_overlay"].instance:
                self["selection_overlay"].instance.setBackgroundColor(
                    parseColor(level["value"]))
                self["selection_overlay"].instance.invalidate()

            self['title_label'].setText(
                _('Window transparency') +
                f" - {level['name']}")
        self.instance.invalidate()

    def move_up(self):
        self["menu"].up()
        self.update_preview()

    def move_down(self):
        self["menu"].down()
        self.update_preview()

    def page_up(self):
        self["menu"].pageUp()
        self.update_preview()

    def page_down(self):
        self["menu"].pageDown()
        self.update_preview()

    def confirm_selection(self):
        idx = self["menu"].getSelectedIndex()
        if 0 <= idx < len(self.transparency_levels):
            self.foreca_preview.alpha = self.transparency_levels[idx]["value"]
            self.foreca_preview._update_button()
        self.close()

    def exit_screen(self):
        self.close()
