# -*- coding: utf-8 -*-
from __future__ import absolute_import
import datetime
import math
import re

try:
    from Components.Converter.Converter import Converter
except Exception:
    class Converter(object):
        CHANGED_POLL = 2
        def __init__(self, type): pass

PLUGIN_PATH = "/usr/lib/enigma2/python/Plugins/Extensions/Foreca1"
WEATHER_ANIM_PATH = PLUGIN_PATH + "/animated_icons"
WIND_DIRECTION_ANIM_PATH = PLUGIN_PATH + "/animated_icons/windspeed"
WIND_SPEED_ANIM_PATH = PLUGIN_PATH + "/animated_icons/wind_speed2"
_MISSING = object()

ALIASES = {
    "temperature": ("temperature", "temp", "cur_temp", "max_temp", "tmax"),
    "temp": ("temperature", "temp", "cur_temp", "max_temp", "tmax"),
    "feels_like": ("feels_like", "feel_temp", "feelsLikeTemp", "fl_temp"),
    "min_temp": ("min_temp", "minTemp", "tmin"),
    "max_temp": ("max_temp", "maxTemp", "tmax"),
    "dewpoint": ("dewpoint", "dewp", "dew_point"),
    "humidity": ("humidity", "relHumidity", "maxRelHumidity", "rhum"),
    "wind_speed": ("wind_speed", "windSpeed", "winds"),
    "wind_gust": ("wind_gust", "maxwind", "maxWindSpeed", "maxWind"),
    "wind_direction": ("wind_direction", "windDir", "windd"),
    "pressure": ("pressure", "pres"),
    "precipitation": ("precipitation", "precipAccum", "rain"),
    "rain_probability": ("rain_probability", "rainp", "precipProb"),
    "snow_probability": ("snow_probability", "snowp", "snowProb"),
    "snowfall": ("snowfall", "snowff", "snow", "snowAccum"),
    "uv_index": ("uv_index", "uvIndex", "uvi"),
    "aqi": ("aqi", "airQualityIndex"),
    "description": ("description", "condition", "weatherDescription", "text"),
    "symbol": ("symbol", "condition", "symb"),
    "solar_radiation": ("solar_radiation", "solarRadiation", "solarRadiationSum"),
    "day_length": ("day_length", "daylength", "daylen"),
    "sunrise": ("sunrise",),
    "sunset": ("sunset",),
    "updated": ("updated",),
    "station": ("station", "station_name"),
    "visibility": ("visibility", "vis"),
    "date": ("date",),
    "time": ("time",),
}

MOON_ALIASES = {
    "rise_time": ("rise_time", "moonrise", "moonrise_time"),
    "set_time": ("set_time", "moonset", "moonset_time"),
    "phase": ("phase", "phase_name", "moon_phase"),
    "illumination": ("illumination", "illum", "moon_illumination"),
    "distance": ("distance", "moon_distance"),
    "azimuth": ("azimuth", "moon_azimuth"),
    "transit_time": ("transit_time",),
    "transit_altitude": ("transit_altitude", "transit_alt"),
    "magnitude": ("magnitude",),
    "angular_diameter": ("angular_diameter",),
    "age": ("age",),
    "trend": ("trend",),
    "icon_number": ("icon_number",),
    "icon_path": ("icon_path",),
}

_SYMBOL_TEXT = {
    "000": "Clear", "100": "Mostly clear", "200": "Partly cloudy",
    "210": "Partly cloudy and light rain", "211": "Partly cloudy and light wet snow",
    "212": "Partly cloudy and light snow", "220": "Partly cloudy and showers",
    "221": "Partly cloudy and wet snow showers", "222": "Partly cloudy and snow showers",
    "240": "Partly cloudy, possible thunderstorms with rain", "300": "Cloudy",
    "310": "Cloudy and light rain", "311": "Cloudy and light wet snow", "312": "Cloudy and light snow",
    "320": "Cloudy and showers", "321": "Cloudy and wet snow showers", "322": "Cloudy and snow showers",
    "340": "Cloudy, thunderstorms with rain", "400": "Overcast", "410": "Overcast and light rain",
    "411": "Overcast and light wet snow", "412": "Overcast and light snow", "420": "Overcast and showers",
    "421": "Overcast and wet snow showers", "422": "Overcast and snow", "430": "Overcast and rain",
    "431": "Overcast and wet snow", "432": "Overcast and snow showers", "440": "Overcast, thunderstorms with rain",
    "500": "Thin upper cloud", "600": "Fog", "na": "N/A",
}


def _get(obj, key, default=_MISSING):
    if obj is None: return default
    if isinstance(obj, dict): return obj.get(key, default)
    return getattr(obj, key, default)


def _first(obj, names, default=_MISSING):
    for name in names:
        v = _get(obj, name, _MISSING)
        if v is not _MISSING and v is not None: return v
    return default


def _number(v):
    if v is None or v is _MISSING: return None
    if isinstance(v, bool): return float(v)
    try:
        s = str(v).strip().replace(",", ".")
        m = re.search(r"[-+]?\d+(?:\.\d+)?", s)
        return float(m.group(0)) if m else None
    except Exception: return None


def _date(v):
    if v is None or v is _MISSING: return None
    if isinstance(v, datetime.datetime): return v
    if isinstance(v, datetime.date): return datetime.datetime.combine(v, datetime.time())
    if isinstance(v, datetime.time): return datetime.datetime.combine(datetime.date.today(), v)
    s = str(v).strip()
    for x in (s.replace("Z", "+00:00"), s):
        try: return datetime.datetime.fromisoformat(x)
        except Exception: pass
    for f in ("%Y-%m-%d", "%d.%m.%Y", "%H:%M", "%H:%M:%S"):
        try: return datetime.datetime.strptime(s, f)
        except Exception: pass
    return None


def compass(v):
    n = _number(v)
    if n is None:
        s = str(v or "").strip()
        if s.startswith("w"): s = s[1:]
        return s.upper()
    dirs = ("N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW")
    return dirs[int(((n % 360.0) + 11.25) / 22.5) % 16]


def DtoJD(dt):
    if dt.tzinfo is None: dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.timestamp() / 86400.0 + 2440587.5


def _phase_fraction(jd): return ((jd - 2451550.25972) / 29.530588853) % 1.0

def JDLunarPhase(jd):
    f = _phase_fraction(jd)
    if f < .0625 or f >= .9375: return "New Moon"
    if f < .1875: return "Waxing Crescent"
    if f < .3125: return "First Quarter"
    if f < .4375: return "Waxing Gibbous"
    if f < .5625: return "Full Moon"
    if f < .6875: return "Waning Gibbous"
    if f < .8125: return "Last Quarter"
    return "Waning Crescent"

def LunarIllum(jd): return (1.0 - math.cos(2.0 * math.pi * _phase_fraction(jd))) * 50.0

def phase_icon_number(jd): return int(round(_phase_fraction(jd) * 100.0)) % 101


class ForecaWeatherConverter(Converter):
    CHANGED_POLL = 2

    def __init__(self, type):
        self.type = type.strip()
        try: super(ForecaWeatherConverter, self).__init__(type)
        except Exception: pass
        parts = self.type.split(":", 1)
        self.field = parts[0].strip()
        self.fmt = parts[1].strip() if len(parts) > 1 else "text"

    def _source(self):
        source = getattr(self, "source", None)
        if source is None: return None
        # A Foreca1 Screen exposes the full five-day API objects.
        days = getattr(source, "foreca_days", None)
        if days:
            current = {
                "temperature": getattr(source, "cur_temp", ""),
                "feels_like": getattr(source, "fl_temp", ""),
                "dewpoint": getattr(source, "dewpoint", ""),
                "humidity": getattr(source, "hum", ""),
                "wind_speed": getattr(source, "wind_speed", ""),
                "wind_gust": getattr(source, "wind_gust", ""),
                "wind_direction": getattr(source, "wind", ""),
                "precipitation": getattr(source, "rain_mm", ""),
                "rain_probability": getattr(source, "rainp", ""),
                "snow_probability": getattr(source, "snowp", ""),
                "pressure": getattr(source, "pressure", ""),
                "uv_index": getattr(source, "uvi", ""),
                "aqi": getattr(source, "aqi", ""),
                "symbol": getattr(source, "pic", ""),
                "description": getattr(source, "pic", ""),
                "sunrise": getattr(source, "sunrise", ""),
                "sunset": getattr(source, "sunset", ""),
                "day_length": getattr(source, "daylen", ""),
                "updated": getattr(source, "updated", ""),
                "station": getattr(source, "f_town", getattr(source, "town", "")),
            }
            return {"daily": days[:5], "current": current}
        for attr in ("raw", "raw_response", "api_response", "raw_data", "data", "weather", "value", "last_response", "current"):
            value = getattr(source, attr, _MISSING)
            if value is not _MISSING and value is not None: return value
        return source

    def _daily(self, data):
        for key in ("daily", "forecast", "days", "daily_forecast"):
            value = _get(data, key, _MISSING)
            if isinstance(value, (list, tuple)) and value: return value
        return []

    def _resolve_day(self, data, field):
        try:
            prefix, rest = field.split(".", 1)
            if prefix.startswith("day") and prefix[3:].isdigit():
                idx = int(prefix[3:]); days = self._daily(data)
                if idx >= len(days): return _MISSING
                obj = days[idx]
                # Friendly derived fields from the daily API object.
                if rest == "temperature": return _first(obj, ALIASES["max_temp"], "")
                if rest == "description":
                    sym = _first(obj, ALIASES["symbol"], "na")
                    code = re.sub(r"^[dn]", "", str(sym))
                    return _SYMBOL_TEXT.get(code, str(sym))
                if rest == "weekday": return _first(obj, ("date",), "")
                if rest == "wind_direction_compass": return compass(_first(obj, ALIASES["wind_direction"], ""))
                return _first(obj, ALIASES.get(rest, (rest,)), _MISSING)
        except Exception: pass
        return _MISSING

    def _moon_info(self):
        dt = datetime.datetime.now(datetime.timezone.utc); jd = DtoJD(dt); f = _phase_fraction(jd)
        return {"phase": JDLunarPhase(jd), "illumination": LunarIllum(jd), "distance": 384400.0,
                "trend": 1 if f < .5 else -1, "age": f * 29.530588853, "icon_number": phase_icon_number(jd)}

    def resolve(self, data):
        if data is None: return ""
        value = _get(data, self.field, _MISSING)
        if value is not _MISSING: return value
        value = self._resolve_day(data, self.field)
        if value is not _MISSING: return value
        if self.field.startswith("current."):
            key = self.field[8:]; value = _first(_get(data, "current", {}), ALIASES.get(key, (key,)), _MISSING)
            if value is not _MISSING: return value
        if self.field.startswith("moon."):
            key = self.field[5:]; moon = _first(data, ("moon", "moon_data", "moon_info"), _MISSING)
            if moon is not _MISSING:
                value = _first(moon, MOON_ALIASES.get(key, (key,)), _MISSING)
                if value is not _MISSING: return value
            info = self._moon_info()
            if key in info: return info[key]
        names = ALIASES.get(self.field, (self.field,)); value = _first(data, names, _MISSING)
        if value is not _MISSING: return value
        for container in ("current", "weather", "data"):
            obj = _get(data, container, _MISSING)
            if obj is not _MISSING:
                value = _first(obj, names, _MISSING)
                if value is not _MISSING: return value
        return ""

    def _format(self, value):
        if value is None or value is _MISSING: return ""
        fmt = self.fmt.lower()
        if fmt in ("raw", "text", "string", "description"): return str(value)
        n = _number(value)
        if fmt in ("number", "float"): return "" if n is None else ("%.2f" % n).rstrip("0").rstrip(".")
        if fmt in ("integer", "int"): return "" if n is None else str(int(round(n)))
        if fmt in ("c", "°c"): return "" if n is None else "%.1f °C" % n
        if fmt in ("f", "°f"): return "" if n is None else "%.1f °F" % (n * 9 / 5 + 32)
        if fmt == "k": return "" if n is None else "%.1f K" % (n + 273.15)
        if fmt in ("km/h", "kmh"): return "" if n is None else "%.1f km/h" % n
        if fmt in ("m/s", "ms"): return "" if n is None else "%.1f m/s" % (n / 3.6)
        if fmt == "mph": return "" if n is None else "%.1f mph" % (n / 1.609344)
        if fmt in ("knots", "kt"): return "" if n is None else "%.1f kn" % (n / 1.852)
        if fmt == "beaufort":
            if n is None: return ""
            return str(max(0, min(12, int(round(((n / 3.6) / 0.836) ** (2.0 / 3.0) / 2.0)))) )
        if fmt in ("hpa", "mb"): return "" if n is None else "%.0f hPa" % n
        if fmt == "inhg": return "" if n is None else "%.2f inHg" % (n * .0295299831)
        if fmt == "mmhg": return "" if n is None else "%.0f mmHg" % (n * .750061683)
        if fmt == "kpa": return "" if n is None else "%.1f kPa" % (n / 10.0)
        if fmt == "mm": return "" if n is None else "%.1f mm" % n
        if fmt == "in": return "" if n is None else "%.2f in" % (n / 25.4)
        if fmt in ("percent", "%"): return "" if n is None else "%.0f%%" % n
        if fmt == "compass": return compass(value)
        if fmt in ("time", "localtime"):
            d = _date(value); return d.strftime("%H:%M") if d else str(value)
        if fmt == "date":
            d = _date(value); return d.strftime("%d.%m.%Y") if d else str(value)
        if fmt in ("weekday", "dayname"):
            d = _date(value); return d.strftime("%A") if d else str(value)
        if fmt in ("weekday_short", "day_short"):
            d = _date(value); return d.strftime("%a") if d else str(value)
        if fmt in ("date_short", "shortdate"):
            d = _date(value); return d.strftime("%d.%m.") if d else str(value)
        if fmt in ("datetime", "date_time"):
            d = _date(value); return d.strftime("%d.%m.%Y %H:%M") if d else str(value)
        if fmt in ("minutes", "duration"):
            if n is None: return str(value)
            return "%d h %02d min" % (int(n)//60, int(n)%60)
        return str(value)

    @property
    def text(self): return self._format(self.resolve(self._source()))
    @property
    def value(self):
        v = self.resolve(self._source()); n = _number(v); return n if n is not None else 0.0
    @property
    def boolean(self): return bool(self.resolve(self._source()))

WeatherConverter = ForecaWeatherConverter
