#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) @Lululla 2026
# meteogram.py - Custom meteogram for Foreca One


import datetime
from json import loads, JSONDecodeError
from os.path import exists, join
from os import makedirs, listdir, remove
import requests

from enigma import getDesktop, ePoint

from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen

from Components.ActionMap import HelpableActionMap
from Components.Pixmap import Pixmap
from Components.Label import Label


from . import (
    _,
    DEBUG,
    load_skin_for_class,
    # get_resolution_type,
    apply_global_theme,
    PLUGIN_PATH,
    TEMP_DIR,
    DBG_DIR,
    HEADERS,
    get_icon_path
)
from .google_translate import _get_system_language


METEOGRAM_DIR = join(TEMP_DIR, "meteogram")
if not exists(METEOGRAM_DIR):
    makedirs(METEOGRAM_DIR)


# =============================================================================
# SCREEN RESOLUTION DEPENDENT CONSTANTS
# =============================================================================
# GRAPH_WIDTH  – total width of the chart area (pixels)
# GRAPH_HEIGHT – total height of the chart area (pixels)
# HOUR_STEP    – horizontal distance between two consecutive 3‑hour points (pixels)
# GRAPH_TOP    – Y‑coordinate of the top of the chart (where maximum temperature is drawn)
# =============================================================================

desk = getDesktop(0)
res = (desk.size().width(), desk.size().height())

if res == (1920, 1080):     # Full HD
    GRAPH_WIDTH = 1665
    GRAPH_HEIGHT = 522
    HOUR_STEP = 48
    GRAPH_TOP = 198
elif res == (1280, 720):    # HD ready
    GRAPH_WIDTH = 1105
    GRAPH_HEIGHT = 348
    HOUR_STEP = 32
    GRAPH_TOP = 132
elif res == (2560, 1440):   # WQHD
    GRAPH_WIDTH = 2215
    GRAPH_HEIGHT = 696
    HOUR_STEP = 64
    GRAPH_TOP = 264
else:                       # fallback (should match skin defaults)
    GRAPH_WIDTH = 1665
    GRAPH_HEIGHT = 522
    HOUR_STEP = 48
    GRAPH_TOP = 198

# Number of 3-hour periods to display (covers ~4.5 days, but typically we
# have 7 days)
PERIODS = 35


TEMP_PALETTE = [
    '#3b62ff', '#408cff', '#40b3ff', '#40d9ff', '#40ffff',
    '#53c905', '#77f424', '#ffff40', '#ffb340', '#ff6640', '#ff4040'
]


def write_meteogram_debug(text):
    try:
        dbg_path = join(DBG_DIR, "meteogram_debug.txt")
        with open(dbg_path, "a") as dbg:
            dbg.write(text + "\n")
    except Exception as e:
        print(f"[Meteogram] Debug write error: {e}")


def smooth_curve_path(nodes, k=3):
    if len(nodes) < 2:
        return ''

    def _lim(n):
        return max(0, min(len(nodes) - 1, n))

    mul = k / 20.0
    out = [f'M{nodes[0][0]},{nodes[0][1]}']

    for n in range(len(nodes) - 1):
        pA = nodes[_lim(n - 1)]
        pB = nodes[n]
        pC = nodes[n + 1]
        pD = nodes[_lim(n + 2)]

        bx1 = pB[0] + (pC[0] - pA[0]) * mul
        by1 = pB[1] + (pC[1] - pA[1]) * mul
        bx2 = pC[0] - (pD[0] - pB[0]) * mul
        by2 = pC[1] - (pD[1] - pB[1]) * mul

        out.append(f'C{bx1},{by1} {bx2},{by2} {pC[0]},{pC[1]}')

    return ' '.join(out)


def wind_arrow(degrees):
    """Convert wind direction in degrees to a cardinal letter (N, NE, …)."""
    try:
        deg = int(degrees) % 360
        directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
        return directions[round(deg / 45) % 8]
    except BaseException:
        return 'N'


class MeteogramView(Screen, HelpableScreen):
    """
    Screen that displays a 7‑day meteogram with temperature curve,
    precipitation bars, weather icons, wind information and date markers.
    All widget names are unique to this plugin.
    """

    def __init__(
            self,
            session,
            weather_api,
            location_id,
            location_name,
            unit_manager=None,
            tz=None,
            tz_offset=None):
        self.skin = load_skin_for_class(MeteogramView)
        Screen.__init__(self, session)
        HelpableScreen.__init__(self)
        self.setTitle(_("Meteogram"))

        self.api = weather_api
        self.loc_id = location_id
        self.loc_name = location_name
        self.units = unit_manager
        self.tz = tz
        self.tz_offset = tz_offset

        if not exists(METEOGRAM_DIR):
            makedirs(METEOGRAM_DIR)

        self["background_plate"] = Label("")
        self["selection_overlay"] = Label("")

        # --- Main widgets (custom names) ---
        self["temp_curve"] = Pixmap()               # SVG temperature line
        self["update_label"] = Label()              # last update time
        # wind speed unit (km/h or mph)
        self["wind_unit_label"] = Label()
        self["city_label"] = Label()                # city name
        self["zero_line"] = Pixmap()                # 0°C indicator (PNG)

        self["precip_text"] = Label(_("Precipitations"))
        self["showers_text"] = Label(_("Showers"))

        # --- 35 periods (3‑hour steps) ---
        for i in range(PERIODS):
            self[f"time_{i}"] = Label(" ")          # hour (e.g. "12")
            self[f"weather_{i}"] = Pixmap()         # weather icon
            self[f"winddir_{i}"] = Pixmap()         # wind direction icon
            self[f"rainbar_{i}"] = Pixmap()         # precipitation bar (SVG)
            self[f"windspeed_{i}"] = Label(" ")     # wind speed value

        # --- Temperature and rain scales (8 levels) ---
        for i in range(8):
            self[f"temp_scale_{i}"] = Label("  ")
            self[f"rain_scale_{i}"] = Label("")

        # --- Date separators (up to 10 days) ---
        for i in range(9):
            self[f"date_{i}"] = Label(" ")
            self[f"vline_{i}"] = Pixmap()           # vertical separator line

        self["vline_9"] = Pixmap()
        self["actions"] = HelpableActionMap(
            self, "ForecaActions",
            {
                "cancel": (self.close, _("Close")),
                "red": (self.close, _("Close")),
                "ok": (self.close, _("Close")),
            },
            -1
        )
        self.onLayoutFinish.append(self.fetch_data)
        self.onClose.append(self.cleanup_temp_files)
        self.onLayoutFinish.append(self._apply_theme)

    def _apply_theme(self):
        apply_global_theme(self)

    def cleanup_temp_files(self):
        if exists(METEOGRAM_DIR):
            try:
                for f in listdir(METEOGRAM_DIR):
                    if f.startswith(
                            'foreca_temp_curve.svg') or f.startswith('rainbar_'):
                        file_path = join(METEOGRAM_DIR, f)
                        remove(file_path)
                if DEBUG:
                    print(
                        f"[Meteogram] Cleaned temporary SVG files from {METEOGRAM_DIR}")
            except Exception as e:
                print(f"[Meteogram] Error cleaning temp files: {e}")

    def fetch_data(self):
        """Download the detailed forecast page and extract JSON data."""
        lang = _get_system_language()
        place = self.api.get_location_by_id(self.loc_id)
        if not place:
            self.close()
            return

        url = f"https://www.foreca.com/{lang}/{self.loc_id}/{place.address}/detailed-forecast"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return
            html = resp.text
        except Exception as e:
            print(f"[Meteogram] Network error: {e}")
            return

        # Extract JSON block from the HTML
        start = html.find('ranges: {')
        if start == -1:
            return
        json_str = html[start:].replace('ranges', '{ "ranges"')
        json_str = json_str.replace('data3h', '"3h"').replace('data', '"data"')
        end = json_str.find('showDetails:')
        if end == -1:
            return
        json_str = json_str[:end - 10] + '}'

        try:
            data = loads(json_str)
        except JSONDecodeError as e:
            print(f"[Meteogram] JSON error: {e}")
            return

        forecast = data.get('data', [])
        ranges = data.get('ranges', {})

        if not forecast or not ranges:
            return

        # DEBUG METEOGRAMM
        write_meteogram_debug("=== FETCH DATA ===")
        write_meteogram_debug(f"Forecast length: {len(forecast)}")
        write_meteogram_debug(f"Ranges: {ranges}")
        if forecast:
            write_meteogram_debug(
                f"First element keys: {list(forecast[0].keys())}")

        # Update time (first element's 'updated' field)
        if forecast and len(forecast) > 1:
            updated_utc = forecast[1].get('updated', '').replace('Z', '+00:00')
            try:
                dt_utc = datetime.datetime.fromisoformat(updated_utc)
                if self.tz:
                    dt_local = dt_utc.astimezone(self.tz)
                elif self.tz_offset is not None:
                    dt_local = dt_utc + \
                        datetime.timedelta(hours=self.tz_offset)
                else:
                    dt_local = dt_utc  # fallback a UTC
                self["update_label"].setText(
                    _("Updated: {}").format(
                        dt_local.strftime('%d.%m.%y %H:%M')))
            except BaseException:
                pass

        self["city_label"].setText(self.loc_name)

        # Set wind unit label
        if self.units:
            self["wind_unit_label"].setText(self.units.get_wind_label())
        else:
            self["wind_unit_label"].setText("km/h")

        # Draw all components
        self._draw_temperature_color(forecast, ranges)
        # self._draw_temperature_simple(forecast, ranges)
        self._draw_rain(forecast, ranges)
        self._draw_hourly(forecast)
        self._draw_dates(forecast)

    def _draw_temperature_color(self, forecast, ranges):
        """
        Draws the temperature curve as coloured segments.
        Each segment's colour is based on the average temperature of its endpoints.
        Also draws the 0°C (or 32°F) line if the temperature range crosses zero.
        """
        # Determine which temperature unit is currently used
        unit_flag = 'c'
        if self.units:
            unit_flag = 'c' if self.units.get_simple_system() == 'metric' else 'f'

        # Retrieve the temperature scale from the JSON data
        temp_block = ranges.get('temp', {})
        if unit_flag == 'c':
            conf = temp_block.get(
                'metric', {
                    'start': -20, 'end': 40, 'step': 5})
        else:
            conf = temp_block.get('us', {'start': -4, 'end': 104, 'step': 9})

        tmin = conf['start']
        tmax = conf['end']
        tstep = conf['step']

        # Build a list of points: (x, y, temperature)
        points = []
        x = 0
        for idx, item in enumerate(forecast):
            if idx >= PERIODS:
                break
            # Get the temperature value (Celsius or Fahrenheit)
            temp_val = item.get(
                'temp') if unit_flag == 'c' else item.get('tempf')
            if temp_val is None:
                temp_val = 0
            # Y coordinate: 0 = tmax (top of graph), GRAPH_HEIGHT = tmin
            # (bottom)
            ratio = 1 - (temp_val - tmin) / (tmax - tmin)
            y = int(GRAPH_HEIGHT * ratio)
            points.append((x, y, temp_val))
            x += HOUR_STEP

        # Generate an SVG with coloured line segments
        palette = TEMP_PALETTE
        n_colors = len(palette)

        def temp_to_color(t):
            frac = (t - tmin) / (tmax - tmin)
            idx = int(frac * (n_colors - 1))
            idx = max(0, min(n_colors - 1, idx))
            return palette[idx]

        segments = []
        for i in range(len(points) - 1):
            x1, y1, t1 = points[i]
            x2, y2, t2 = points[i + 1]
            avg_temp = (t1 + t2) / 2
            color = temp_to_color(avg_temp)
            segments.append(
                f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="3" />'
            )

        svg = f'''<?xml version="1.0" encoding="utf-8"?>
    <svg version="1.1" xmlns="http://www.w3.org/2000/svg"
         width="{GRAPH_WIDTH}" height="{GRAPH_HEIGHT}"
         viewBox="0 0 {GRAPH_WIDTH} {GRAPH_HEIGHT}">
        {''.join(segments)}
    </svg>'''

        # Save and load the SVG into the temp_curve pixmap
        svg_file = join(METEOGRAM_DIR, 'foreca_temp_curve.svg')
        try:
            with open(svg_file, 'w') as f:
                f.write(svg)
            self["temp_curve"].instance.setPixmapFromFile(svg_file)
        except Exception as e:
            print(f"[Meteogram] Failed to write temperature SVG: {e}")

        # Left‑hand temperature scale (8 labels)
        temps = []
        v = tmin
        while v <= tmax:
            temps.append(str(int(v)))
            v += tstep
        for i, txt in enumerate(temps[:8]):
            self[f"temp_scale_{i}"].setText(txt)
        self["temp_scale_0"].setText(("°C" if unit_flag == 'c' else "°F"))

        # -------------------------------------------------------------------------
        # Zero line (0°C / 32°F)
        # -------------------------------------------------------------------------
        zero_target = 0 if unit_flag == 'c' else 32
        if tmin < zero_target < tmax:
            # fraction from the top (where tmax is at y = GRAPH_TOP)
            fraction = (tmax - zero_target) / (tmax - tmin)
            zero_y = int(GRAPH_TOP + GRAPH_HEIGHT * fraction)

            zero_img = join(PLUGIN_PATH, "images", "zeroh.png")
            if exists(zero_img):
                self["zero_line"].instance.setPixmapFromFile(zero_img)
                # Keep the horizontal position defined in the skin
                current_pos = self["zero_line"].instance.position()
                self["zero_line"].move(ePoint(current_pos.x(), zero_y))
                self["zero_line"].show()
            else:
                self["zero_line"].hide()
        else:
            self["zero_line"].hide()

    def _draw_rain(self, forecast, ranges):
        rain_unit = 'mm'
        if self.units:
            rain_unit = self.units.get_precip_unit()

        rain_cfg = ranges.get('rain', {})
        if rain_unit == 'mm':
            rr = rain_cfg.get('metric', {'start': 0, 'end': 50, 'step': 5})
        else:
            rr = rain_cfg.get('us', {'start': 0, 'end': 2, 'step': 0.2})

        r0 = rr['start']
        r1 = rr['end']
        step = rr['step']
        span = r1 - r0
        if span <= 0:
            span = 1

        h = GRAPH_HEIGHT

        for n in range(PERIODS):
            if n >= len(forecast):
                break
            row = forecast[n]
            lx_mm = row.get('rainl', 0)
            s_mm = row.get('rains', 0)
            if rain_unit == 'mm':
                lx = lx_mm
                s = s_mm
            else:
                lx = lx_mm * 0.0393701
                s = s_mm * 0.0393701

            # Calculate heights (making sure they are not negative)
            lh = int(h * lx / span)
            if lh < 0:
                lh = 0
            ly = h - lh
            sh = int(h * s / span)
            if sh < 0:
                sh = 0
            sy = ly - sh
            if sy < 0:
                sy = 0

            if DEBUG:
                print(
                    f"[Meteogram] Period {n}: lx={lx:.2f}, s={s:.2f}, lh={lh}, sh={sh}, ly={ly}, sy={sy}")

            # Build SVG with solid colors
            if sh > 0:
                # Showers: gray color
                svg_chunk = f'''<?xml version="1.0" encoding="utf-8"?>
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="{h}">
      <rect x="0" y="{ly}" width="20" height="{lh}" fill="#1E90FF"/>
      <rect x="0" y="{sy}" width="20" height="{sh}" fill="#666666"/>
    </svg>'''
            else:
                # Precipitation only
                svg_chunk = f'''<?xml version="1.0" encoding="utf-8"?>
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="{h}">
      <rect x="0" y="{ly}" width="20" height="{lh}" fill="#1E90FF"/>
    </svg>'''

            ftmp = join(METEOGRAM_DIR, f'rainbar_{n}.svg')
            try:
                with open(ftmp, 'w', encoding='utf-8') as f:
                    f.write(svg_chunk)
                self[f"rainbar_{n}"].instance.setPixmapFromFile(ftmp)
            except Exception as e:
                print(f"[Meteogram] Error rainbar {n}: {e}")

        # Value scale (unchanged)
        values = []
        v = r0
        while v <= r1 + 0.001:
            values.append(v)
            v += step

        for i in range(min(8, len(values))):
            if rain_unit == 'mm':
                txt = str(int(values[i]))
            else:
                txt = f"{values[i]:.1f}"
            self[f"rain_scale_{i}"].setText(txt)

        self["rain_scale_0"].setText("mm" if rain_unit == 'mm' else "in")

    def _draw_hourly(self, forecast):
        """Fill hours, weather icons, wind directions and speeds."""
        for n in range(PERIODS):
            if n >= len(forecast):
                break
            row = forecast[n]

            # Time
            tval = row.get('time', '').split('T')[1][:5]
            self[f"time_{n}"].setText(tval)

            # Wind speed (original in m/s)
            ws_ms = row.get('winds', 0)
            if self.units:
                wind_val, _ = self.units.convert_wind(ws_ms)
                # we round up to the whole number
                self[f"windspeed_{n}"].setText(str(int(wind_val)))
            else:
                # fallback: km/h
                self[f"windspeed_{n}"].setText(str(int(ws_ms * 3.6)))

            # Weather icon
            symb = row.get('symb', 'd000')
            fpath = get_icon_path(f"{symb}.png")
            if fpath:
                self[f"weather_{n}"].instance.setPixmapFromFile(fpath)
            else:
                # Fallback na.png
                fallback = get_icon_path("na.png")
                if fallback:
                    self[f"weather_{n}"].instance.setPixmapFromFile(fallback)
                else:
                    self[f"weather_{n}"].hide()

            # Wind direction icon
            deg = row.get('windd', 0)
            card = wind_arrow(deg)
            wfile = get_icon_path(f"w{card}.png")
            if wfile:
                self[f"winddir_{n}"].instance.setPixmapFromFile(wfile)
            else:
                fallback = get_icon_path("wN.png")  # o na.png
                if fallback:
                    self[f"winddir_{n}"].instance.setPixmapFromFile(fallback)

    def _draw_dates(self, forecast):
        """Add date labels and vertical lines (up to 10 days)."""
        cur_day = None
        start_idx = 0
        blocks = []

        for i, r in enumerate(forecast[:PERIODS]):
            dstr = r.get('time', '').split('T')[0]
            if dstr != cur_day:
                if cur_day is not None:
                    blocks.append((cur_day, start_idx))
                cur_day = dstr
                start_idx = i
        if cur_day:
            blocks.append((cur_day, start_idx))

        sep_img = join(PLUGIN_PATH, "images", "sep.png")
        for idx, (ds, pos) in enumerate(blocks):
            if idx >= 9:
                break
            try:
                dt = datetime.datetime.strptime(ds, "%Y-%m-%d")
                self[f"date_{idx}"].setText(dt.strftime("%a, %d.%m"))
            except BaseException:
                self[f"date_{idx}"].setText(ds)

            if exists(sep_img):
                self[f"vline_{idx}"].instance.setPixmapFromFile(sep_img)
