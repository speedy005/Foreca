#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) @Lululla 2026
# moon_calendar.py - Annual lunar phase calendar

from datetime import datetime, timedelta
from os.path import exists, join
from collections import defaultdict
from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Screens.MessageBox import MessageBox
from Components.ActionMap import HelpableActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.ProgressBar import ProgressBar
from Components.Sources.List import List
from Tools.LoadPixmap import LoadPixmap

from . import _, PLUGIN_PATH, DEBUG, load_skin_for_class, apply_global_theme
from .MoonPhase import MoonPhase
from .moon_calc import JDtoD, DtoJD  # CheckState, JDLunarPhase
from .google_translate import trans


class MoonCalendar(Screen, HelpableScreen):
    def __init__(self, session, moon_obj=None, tz_offset=None):
        self.skin = load_skin_for_class(MoonCalendar)
        Screen.__init__(self, session)
        HelpableScreen.__init__(self)
        self.setTitle(_("Lunar Calendar"))
        self.moon = moon_obj or MoonPhase(
            icon_path=join(PLUGIN_PATH, "moon"),
            total_icons=101
        )
        self.tz_offset = tz_offset   # save offset (float, time)
        self.phases = []
        self.list = []
        self["menu"] = List(self.list)
        self["background_plate"] = Label("")
        self["selection_overlay"] = Label("")
        self["info"] = Label(_("Loading lunar phases..."))
        self["Phase"] = Label(_("Phase"))
        self["Day"] = Label(_("Day"))
        self["Month"] = Label(_("Month"))
        self["Time"] = Label(_("Time"))

        self["current_phase_icon"] = Pixmap()
        self["current_phase_name"] = Label()
        self["current_illum"] = Label()
        self["current_distance"] = Label()
        self["illum_bar"] = ProgressBar()

        self["title"] = Label(_("Lunar phases from next month"))
        self["actions"] = HelpableActionMap(
            self, "ForecaActions",
            {
                "cancel": (self.close, _("Exit")),
                "ok": (self.show_details, _("Details")),
                "up": (self["menu"].up, _("Move up")),
                "down": (self["menu"].down, _("Move down")),
                "pageUp": (self["menu"].pageUp, _("Page up")),
                "pageDown": (self["menu"].pageDown, _("Page down")),
            },
            -1
        )

        self.onLayoutFinish.append(self._apply_theme)
        self.onLayoutFinish.append(self.load_calendar)

    def _apply_theme(self):
        apply_global_theme(self)

    def _is_supermoon(self, full_moon):
        """Return True if the full moon is a supermoon (distance = 360000 km)."""
        return full_moon.get('distance', 999999) <= 360000

    def _get_blue_moons(self, full_moons):
        """Return list of blue moons (second full moon in a calendar month)."""
        by_month = defaultdict(list)
        for fm in full_moons:
            key = (fm['date'].year, fm['date'].month)
            by_month[key].append(fm)

        blue = []

        for month, fms in by_month.items():
            if len(fms) == 2:
                blue.append(fms[1])  # second is the blue moon

        return blue

    def _get_black_moons(self, new_moons):
        """Return list of black moons (second new moon in a calendar month)."""
        by_month = defaultdict(list)
        for nm in new_moons:
            key = (nm['date'].year, nm['date'].month)
            by_month[key].append(nm)

        black = []
        for month, nms in by_month.items():
            if len(nms) == 2:
                black.append(nms[1])

        return black

    def _get_perigee_for_month(self, year, month):
        """Find the perigee (minimum lunar distance) within the given month.

        Returns:
            dict | None: A dictionary containing date, distance, icon_path,
            and phase_name, or None if no perigee was found.
        """
        from datetime import datetime, timedelta

        start = datetime(year, month, 1)

        if month == 12:
            end = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            end = datetime(year, month + 1, 1) - timedelta(days=1)
        best_dist = float('inf')
        best_jd = None
        current = start
        while current <= end:
            jd = self._date_to_jd(current)
            data = self.moon.get_phase_info_for_jd(jd)
            dist = data['distance']
            if dist < best_dist:
                best_dist = dist
                best_jd = jd
            current += timedelta(days=1)
        if best_jd:
            dt = self._jd_to_datetime(best_jd)
            info = self.moon.get_phase_info_for_jd(
                best_jd)
            return {
                'date': dt,
                'distance': best_dist,
                'icon_path': info['icon_path'],
                'phase_name': info['name'],
                'illumination': info['illumination'],
                'event_type': 'Perigee'
            }
        return None

    def _date_to_jd(self, dt):
        return DtoJD(dt.day, dt.month, dt.year, dt.hour, dt.minute, dt.second)

    def _jd_to_datetime(self, jd):
        d, m, y, h, mn, s, _ = JDtoD(jd)
        return datetime(y, m, d, h, mn, s)

    # ------------------------------------------------------------------
    # Calendar generation
    # ------------------------------------------------------------------
    def load_calendar(self):
        """Generate the list of lunar phases and special events for the next 12 months."""
        self["info"].setText(_("Calculating..."))
        self.phases = []
        today = datetime.now()
        # Start from the first day of next month
        if today.month == 12:
            start_month = 1
            start_year = today.year + 1
        else:
            start_month = today.month
            start_year = today.year

        current = datetime(start_year, start_month, 1)

        # Calculate for 12 months
        for x in range(12):
            month_phases = self._get_month_phases(current.year, current.month)
            self.phases.extend(month_phases)
            # Move to next month
            if current.month == 12:
                current = datetime(current.year + 1, 1, 1)
            else:
                current = datetime(current.year, current.month + 1, 1)

        # --- Collect full moons and new moons from self.phases ---
        full_moons = [p for p in self.phases if p["phase_name"] == "Full Moon"]
        new_moons = [p for p in self.phases if p["phase_name"] == "New Moon"]

        # 1) Supermoons
        supermoons = [fm for fm in full_moons if self._is_supermoon(fm)]

        # 2) Blue moons
        blue_moons = self._get_blue_moons(full_moons)

        # 3) Black moons
        black_moons = self._get_black_moons(new_moons)

        # 4) Perigees for each month
        perigees = []
        for year, month in {(p["date"].year, p["date"].month)
                            for p in self.phases}:
            perigee_data = self._get_perigee_for_month(year, month)
            if perigee_data:
                perigees.append(perigee_data)

        # Add special events as new entries (copy to avoid altering original
        # phases)
        special_events = []

        for sm in supermoons:
            # Add a modified copy so the original entry is not altered
            ev = sm.copy()
            ev["event_type"] = "Supermoon"
            ev["phase_name"] = "Supermoon"
            special_events.append(ev)

        for bm in blue_moons:
            ev = bm.copy()
            ev["event_type"] = "Blue Moon"
            ev["phase_name"] = "Blue Moon"
            special_events.append(ev)

        for bkm in black_moons:
            ev = bkm.copy()
            ev["event_type"] = "Black Moon"
            ev["phase_name"] = "Black Moon"
            special_events.append(ev)

        for pg in perigees:
            special_events.append(pg)

        # Merge all events and sort by date
        self.phases.extend(special_events)
        self.phases.sort(key=lambda x: x["date"])

        # Build the list for the Listbox
        self.list = []

        # self.list.append((
        # _("Month"),        # 0
        # None,              # 1: no icon
        # _("Phase"),        # 2
        # _("Day"),          # 3
        # _("Time")          # 4
        # ))

        for idx, p in enumerate(self.phases, start=1):
            self.list.append(self._create_entry(p))
            if DEBUG:
                print(
                    f"[MoonCalendar] #{idx:02d} | "
                    f"Date: {p.get('date', 'N/A')} | "
                    f"Phase: {p.get('phase_name', 'N/A')} | "
                    f"Illum: {p.get('illumination', 'N/A')}% | "
                    f"Icon: {p.get('icon_path', 'N/A')}"
                )
        # Update current moon info
        info = self.moon.get_phase_info()

        if info["icon_path"] and exists(info["icon_path"]):
            self["current_phase_icon"].instance.setPixmapFromFile(
                info["icon_path"])
        self["current_phase_name"].setText(_(info["name"]))
        self["current_illum"].setText(
            _("Illumination: {:.1f}%").format(
                info["illumination"]))
        self["current_distance"].setText(
            _("Distance: {} km").format(
                info["distance"]))
        self["illum_bar"].setValue(int(info["illumination"]))

        self["menu"].setList(self.list)
        self["info"].setText(
            trans("Found {} lunar phases").format(len(self.phases))
        )
        self.instance.invalidate()

    def _create_entry(self, phase):
        """Create a UI entry tuple for a lunar phase or special event."""
        from os.path import join, exists

        icon_path = phase.get("icon_path")
        event_type = phase.get("event_type")

        # For perigees, use a dedicated icon if available,
        # otherwise keep the phase icon.
        if event_type == "Perigee":
            custom_icon = join(self.moon.icon_path, "perigee.png")
            if exists(custom_icon):
                icon_path = custom_icon

        if icon_path and exists(icon_path):
            icon = LoadPixmap(cached=True, path=icon_path)
        else:
            icon = None

        date = phase["date"]
        month = date.strftime("%B %Y")
        day = date.strftime("%d")
        hour = date.strftime("%H:%M")

        if event_type == "Supermoon":
            phase_text = _("Super Full Moon") + " ★"
        elif event_type == "Blue Moon":
            phase_text = _("Blue Moon") + " ☆"
        elif event_type == "Black Moon":
            phase_text = _("Black Moon") + " ◇"
        elif event_type == 'Perigee':
            # phase_text = _("Perigee") + f" ({phase['distance']:.0f} km)"
            dist_km = int(round(phase['distance']))
            phase_text = _("Perigee") + f" ({dist_km} km)"
        else:
            phase_text = _(phase["phase_name"])
        if DEBUG:
            print(
                f"[MoonCalendar] Entry | "
                f"Month: {month} | "
                f"Day: {day} | "
                f"Hour: {hour} | "
                f"Phase: {phase_text} | "
                f"Icon: {icon}"
            )
        return (month, icon, phase_text, day, hour)

    def _utc_to_local(self, dt_utc):
        """Converts a UTC datetime to a local datetime using the stored offset."""
        if self.tz_offset is None:
            return dt_utc
        return dt_utc + timedelta(hours=self.tz_offset)

    def _get_month_phases(self, year, month):
        target_phases = [0.0, 0.25, 0.5, 0.75]
        names = {
            0.0: "New Moon",
            0.25: "First Quarter",
            0.5: "Full Moon",
            0.75: "Last Quarter"
        }
        start_of_month = datetime(year, month, 1)
        if month == 12:
            end_of_month = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_of_month = datetime(year, month + 1, 1) - timedelta(days=1)

        jd_start = self._date_to_jd(start_of_month)
        jd_end = self._date_to_jd(end_of_month)
        jd_ref = self._date_to_jd(datetime(2000, 1, 6, 0, 0, 0))
        month_phases = []
        for target in target_phases:
            jd_phase = self._find_next_phase_after(jd_start, target, jd_ref)
            while jd_phase <= jd_end:
                dt_phase_utc = self.moon._jd_to_datetime(jd_phase)   # UTC
                dt_phase_local = self._utc_to_local(
                    dt_phase_utc)    # converti in ora locale
                if dt_phase_local.year == year and dt_phase_local.month == month:
                    info = self.moon.get_phase_info_for_jd(jd_phase)
                    month_phases.append({
                        'date': dt_phase_local,
                        'phase_name': names[target],
                        'icon_path': info['icon_path'],
                        'jd': jd_phase,
                        'illumination': info['illumination'],
                        'distance': info['distance']
                    })
                jd_phase += 29.530588853
        month_phases.sort(key=lambda x: x['date'])
        return month_phases

    def _find_next_phase_after(self, jd_start, target_phase, jd_ref):
        """Find the Julian Day of the next target phase after jd_start."""
        days_since_ref = jd_start - jd_ref
        phase_at_start = (days_since_ref / 29.530588853) % 1.0
        delta = (target_phase - phase_at_start) % 1.0
        if delta < 0.0001:
            delta = 1.0
        return jd_start + delta * 29.530588853

    def show_details(self):
        idx = self["menu"].getSelectedIndex()
        if idx < 0 or idx >= len(self.phases):
            return
        phase = self.phases[idx]
        phase_name = _(phase['phase_name'])
        date_obj = phase['date']
        illum = phase['illumination']
        distance_km = int(round(phase['distance']))
        age = self.moon._calculate_age(date_obj)
        mag = self.moon._calculate_magnitude(phase['distance'], illum)
        diam = self.moon._calculate_angular_diameter(phase['distance'])

        details = trans("Phase: {}").format(phase_name) + "\n"
        details += trans("Date: {}").format(date_obj.strftime("%d.%m.%Y")) + "\n"
        details += trans("Time: {}").format(date_obj.strftime("%H:%M")) + "\n"
        details += trans("Illumination: {:.1f}%").format(illum) + "\n"
        details += trans("Distance: {} km").format(distance_km) + "\n"
        details += trans("Age: {:.1f} days").format(age) + "\n"
        details += trans("Magnitude: {:.2f}").format(mag) + "\n"
        details += trans("Angular diameter: {:.0f} arcsec").format(diam)

        self.session.open(MessageBox, details, MessageBox.TYPE_INFO)

    def exit(self):
        self.close()
