#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) @Lululla 2026
# MoonPhase.py - Accurate lunar phase calculations (Meeus algorithms)

import glob
import time
import datetime
import math
from os.path import exists, join, isdir, basename
from threading import Thread
import requests

from . import _, DEBUG
from .moon_calc import DtoJD, LunarPos, LunarIllum, JDtoD, JDLunarPhase  # , CheckState


MOON_PHASES = {
    "New Moon": _("New Moon"),
    "Waxing Crescent": _("Waxing Crescent"),
    "First Quarter": _("First Quarter"),
    "Waxing Gibbous": _("Waxing Gibbous"),
    "Full Moon": _("Full Moon"),
    "Waning Gibbous": _("Waning Gibbous"),
    "Last Quarter": _("Last Quarter"),
    "Waning Crescent": _("Waning Crescent"),
}


class MoonPhase:
    def __init__(self, icon_path=None, total_icons=101):
        self.icon_path = icon_path
        self.total_icons = total_icons
        self.api_data = None  # data from USNO API (moonrise/moonset)

    # ------------------------------------------------------------------
    # Maps phase + illumination to icon index (0-100)
    # ------------------------------------------------------------------
    def _phase_to_icon(self, phase_name, illum_percent):
        name = phase_name.lower()
        if name == "new moon":
            return 0   # moon0000.png)
        if name == "first quarter":
            return 25
        if name == "full moon":
            return 50
        if name in ("last quarter", "third quarter"):
            return 75

        if "waxing crescent" in name:
            return int(round(illum_percent * 25 / 50))
        if "waxing gibbous" in name:
            return int(round(25 + (illum_percent - 50) * 25 / 50))
        if "waning gibbous" in name:
            return int(round(50 + (100 - illum_percent) * 25 / 50))
        if "waning crescent" in name:
            return int(round(75 + (50 - illum_percent) * 25 / 50))
        return 50

    # ------------------------------------------------------------------
    # Determines the lunar phase from a date (datetime)
    # ------------------------------------------------------------------
    def _get_phase_name_from_date(self, dt):
        """
        Calculate accurate moon phase name for given datetime.
        Uses the nearest main phase (New/First/Full/Last) and then
        determines the intermediate phase based on illumination and trend.
        """
        # Calculate Julian Day
        jd = DtoJD(dt.day, dt.month, dt.year, dt.hour, dt.minute, dt.second)

        # Calculate illumination and trend (waxing/waning)
        illum = LunarIllum(jd) * 100
        jd_next = jd + 0.25
        illum_next = LunarIllum(jd_next) * 100
        waxing = illum_next > illum   # True = waxing, False = waning

        # Calculate k value (number of lunations since 2000)
        year = dt.year
        month = dt.month
        day = dt.day + (dt.hour + dt.minute / 60.0 + dt.second / 3600.0) / 24.0
        YearFrac = year + (month - 1 + (day - 1) / 30.5) / 12
        k = (YearFrac - 2000) * 12.3685

        # Round to the nearest quarter (0, 0.25, 0.5, 0.75)
        k0 = round(k * 4) / 4.0
        jd_phase = JDLunarPhase(k0)

        # Determine the main phase name based on fractional part of k0
        frac = abs(k0 - int(k0))
        if frac < 0.01:
            main_phase = "New Moon"
        elif abs(frac - 0.25) < 0.01:
            main_phase = "First Quarter"
        elif abs(frac - 0.5) < 0.01:
            main_phase = "Full Moon"
        else:
            main_phase = "Last Quarter"

        # If we are extremely close to the main phase (within ~0.02 days ≈ 30
        # minutes)
        if abs(jd - jd_phase) < 0.02:
            return main_phase

        # Determine intermediate phase
        if main_phase == "New Moon":
            return "Waxing Crescent" if waxing else "Waning Crescent"
        elif main_phase == "First Quarter":
            # After First Quarter -> Waxing Gibbous; before -> Waxing Crescent
            if waxing:
                return "Waxing Gibbous"
            else:
                return "Waxing Crescent"
        elif main_phase == "Full Moon":
            # After Full Moon -> Waning Gibbous; before -> Waxing Gibbous
            if waxing:
                return "Waxing Gibbous"
            else:
                return "Waning Gibbous"
        else:  # Last Quarter
            # After Last Quarter -> Waning Crescent; before -> Waning Gibbous
            if waxing:
                return "Waning Gibbous"
            else:
                return "Waning Crescent"

    # ------------------------------------------------------------------
    # Get complete information for a date (default now)
    # ------------------------------------------------------------------
    def get_phase_info(self, target_date=None):
        if target_date is None:
            target_date = datetime.datetime.utcnow()
        elif isinstance(target_date, datetime.date) and not isinstance(
                target_date, datetime.datetime):
            # If it's a date without a time, set the time to 00:00:00 UTC
            target_date = datetime.datetime(
                target_date.year, target_date.month, target_date.day, 0, 0, 0)

        jd = DtoJD(target_date.day, target_date.month, target_date.year,
                   target_date.hour, target_date.minute, target_date.second)
        illum = LunarIllum(jd) * 100
        phase_name = self._get_phase_name_from_date(target_date)
        distance = LunarPos(jd)[0]  # _Delta
        icon_number = self._phase_to_icon(phase_name, illum)

        # Calculate trend (waxing/waning) by comparing with +6 hours
        jd_next = jd + 0.25
        illum_next = LunarIllum(jd_next) * 100
        trend = 1 if illum_next > illum else -1

        icon_file = None
        if self.icon_path:
            icon_file = join(self.icon_path, f"moon{icon_number:04d}.png")
            if not exists(icon_file):
                icon_file = self._find_nearest_icon(icon_number)
        if DEBUG:
            print("[MoonPhase] DEBUG - target_date:", target_date)
            print("[MoonPhase] DEBUG - jd:", jd)
            print("[MoonPhase] DEBUG - illum calcolate:", illum)
            print("[MoonPhase] DEBUG - phase_name calcolate:", phase_name)
            print("[MoonPhase] DEBUG - distance:", distance)
        return {
            "illumination": illum,
            "name": phase_name,
            "icon_number": icon_number,
            "icon_path": icon_file,
            "distance": round(distance),   # or int(round(distance))
            "jd": jd,
            "trend": trend
        }

    # ------------------------------------------------------------------
    # For compatibility: get_phase_info_for_jd
    # ------------------------------------------------------------------
    def get_phase_info_for_jd(self, jd):
        """
        Returns lunar information for a given Julian Day.
        Includes jd and trend for compatibility.
        """
        dt = self._jd_to_datetime(jd)
        info = self.get_phase_info(dt)
        illum_now = info['illumination']
        jd_next = jd + 0.25
        illum_next = LunarIllum(jd_next) * 100
        trend = 1 if illum_next > illum_now else -1
        info['jd'] = jd
        info['trend'] = trend
        return info

    def _jd_to_datetime(self, jd):
        d, m, y, h, mn, s, _ = JDtoD(jd)
        return datetime.datetime(y, m, d, h, mn, s)

    # ------------------------------------------------------------------
    # API for moonrise/moonset (USNO) – asynchronous
    # ------------------------------------------------------------------
    def get_moon_data_async(
            self,
            lat,
            lon,
            callback,
            max_days=2,
            offset_hours=None,
            date=None):
        def worker():
            result = self.get_moon_data_from_api(
                lat, lon, max_days, offset_hours, date)
            if callback:
                callback(result)
        Thread(target=worker).start()

    def get_moon_data_from_api(
            self,
            lat,
            lon,
            max_days=2,
            offset_hours=None,
            date=None):
        if offset_hours is None:
            offset_hours = self._get_offset_hours()
        try:
            base_date = date if date is not None else datetime.date.today()
            moonrise = "N/A"
            moonset = "N/A"
            phase_name = "N/A"
            illumination = None
            for days_offset in range(max_days + 1):
                check_date = base_date + datetime.timedelta(days=days_offset)
                date_str = check_date.strftime("%Y-%m-%d")
                url = "https://aa.usno.navy.mil/api/rstt/oneday"
                params = {
                    "date": date_str,
                    "coords": f"{lat}, {lon}",
                    "tz": str(offset_hours),
                    "dst": "false"
                }
                try:
                    response = requests.get(url, params=params, timeout=10)
                    if response.status_code != 200:
                        continue
                    data = response.json()
                    props = data.get("properties", {}).get("data", {})
                    if not props:
                        continue
                    if days_offset == 0:
                        phase_name = props.get("curphase", "N/A")
                        illum_str = props.get(
                            "fracillum", "0%").replace(
                            "%", "").strip()
                        illumination = float(
                            illum_str) / 100.0 if illum_str != "N/A" else None
                    for item in props.get("moondata", []):
                        phen = item.get("phen", "")
                        time_val = item.get("time", "N/A")
                        if phen == "Rise" and moonrise == "N/A":
                            moonrise = time_val
                        elif phen == "Set" and moonset == "N/A":
                            moonset = time_val
                    if moonrise != "N/A" and moonset != "N/A":
                        break
                except Exception as e:
                    print(f"[Moon] API error: {e}")
            result = {
                "rise": moonrise,
                "set": moonset,
                "phase": phase_name,
                "illumination": illumination
            }
            if illumination is not None:
                self.api_data = result
            return result
        except Exception as e:
            print(f"[Moon] Exception in API: {e}")
            return None

    def _get_offset_hours(self):
        lt = time.localtime()
        if lt.tm_isdst:
            offset_sec = -time.altzone
        else:
            offset_sec = -time.timezone
        return round(offset_sec / 3600.0, 1)

    # def get_moon_distance(self):
        # return self.get_phase_info()["distance"]

    def get_moon_distance(self, target_date=None):
        info = self.get_phase_info(target_date)
        return info["distance"]

    def _find_nearest_icon(self, target_num):
        if not self.icon_path or not isdir(self.icon_path):
            return None
        pattern = join(self.icon_path, "moon*.png")
        files = glob.glob(pattern)
        numbers = []
        for f in files:
            base = basename(f)
            num_str = base.replace('moon', '').replace('.png', '')
            if num_str.isdigit():
                numbers.append((int(num_str), f))
        if not numbers:
            return None
        nearest = min(numbers, key=lambda x: abs(x[0] - target_num))
        return nearest[1]

    def get_moon_extra_details(self, lat, lon, dt=None):
        """
        Calculates additional Moon data for a specific date and position.

        Parameters:
            lat: observer latitude (degrees, negative for South)
            lon: observer longitude (degrees, negative for West)
            dt: datetime object (UTC). If None, uses current UTC time.

        Returns a dictionary with:
            - rise_time: moonrise time (HH:MM string, local time)
            - set_time: moonset time (HH:MM string, local time)
            - rise_azimuth: azimuth at moonrise (degrees, from North)
            - set_azimuth: azimuth at moonset (degrees, from North)
            - transit_time: transit (culmination) time (HH:MM string, local time)
            - transit_altitude: maximum altitude (degrees)
            - magnitude: apparent visual magnitude
            - angular_diameter: angular diameter (arcseconds)
            - age: age in days since last New Moon
        """

        if dt is None:
            dt = datetime.datetime.now(datetime.timezone.utc)
        jd = DtoJD(dt.day, dt.month, dt.year, dt.hour, dt.minute, dt.second)
        _, ra, dec, _, _ = LunarPos(jd)
        distance = LunarPos(jd)[0]
        # phase_name = self._get_phase_name_from_date(dt)   <-- ELIMINA QUESTA
        illumination = LunarIllum(jd) * 100

        # 2. Calculate rise/set time and azimuth (interpolation)
        rise_time, set_time, rise_az, set_az = self._calculate_rise_set(
            lat, lon, dt, ra, dec)

        # 3. Calculate transit time and altitude
        transit_time, transit_alt = self._calculate_transit(
            lat, lon, dt, ra, dec)

        # 4. Calculate apparent magnitude
        magnitude = self._calculate_magnitude(distance, illumination)

        # 5. Calculate angular diameter
        angular_diameter = self._calculate_angular_diameter(distance)

        # 6. Calculate Moon age
        age = self._calculate_age(dt)

        return {
            "rise_time": rise_time,
            "set_time": set_time,
            "rise_azimuth": rise_az,
            "set_azimuth": set_az,
            "transit_time": transit_time,
            "transit_altitude": transit_alt,
            "magnitude": magnitude,
            "angular_diameter": angular_diameter,
            "age": age
        }

    def _calculate_rise_set(self, lat, lon, dt, ra, dec):
        # Search around midnight of the specified day
        start_dt = datetime.datetime(
            dt.year,
            dt.month,
            dt.day,
            0,
            0,
            0,
            tzinfo=datetime.timezone.utc)
        rise_time = None
        set_time = None
        rise_az = None
        set_az = None
        prev_alt_val = None

        # Search interval: 24 hours
        for minute_offset in range(0, 24 * 60):
            check_dt = start_dt + datetime.timedelta(minutes=minute_offset)
            jd_check = DtoJD(
                check_dt.day,
                check_dt.month,
                check_dt.year,
                check_dt.hour,
                check_dt.minute,
                check_dt.second)
            _, ra_check, dec_check, _, _ = LunarPos(jd_check)
            alt, az = self._equatorial_to_horizontal(
                lat, lon, check_dt, ra_check, dec_check)

            if minute_offset > 0 and prev_alt_val is not None:
                if prev_alt_val < 0 and alt >= 0:
                    rise_time = check_dt
                    rise_az = az
                elif prev_alt_val > 0 and alt <= 0:
                    set_time = check_dt
                    set_az = az
            prev_alt_val = alt

            if rise_time and set_time:
                break

        # Format times as HH:MM strings (local time)
        tz_offset = self._get_offset_hours()
        if rise_time:
            local_rise = rise_time + datetime.timedelta(hours=tz_offset)
            rise_time_str = local_rise.strftime("%H:%M")
        else:
            rise_time_str = "N/A"

        if set_time:
            local_set = set_time + datetime.timedelta(hours=tz_offset)
            set_time_str = local_set.strftime("%H:%M")
        else:
            set_time_str = "N/A"

        return rise_time_str, set_time_str, rise_az, set_az

    def _calculate_transit(self, lat, lon, dt, ra, dec):
        start_dt = datetime.datetime(
            dt.year,
            dt.month,
            dt.day,
            0,
            0,
            0,
            tzinfo=datetime.timezone.utc)
        max_alt = -90
        transit_dt = None

        # Search full 24 hours
        for minute_offset in range(0, 24 * 60):
            check_dt = start_dt + datetime.timedelta(minutes=minute_offset)
            jd_check = DtoJD(
                check_dt.day,
                check_dt.month,
                check_dt.year,
                check_dt.hour,
                check_dt.minute,
                check_dt.second)
            _, ra_check, dec_check, _, _ = LunarPos(jd_check)
            alt, az = self._equatorial_to_horizontal(
                lat, lon, check_dt, ra_check, dec_check)

            # Track maximum altitude (transit point)
            if alt > max_alt:
                max_alt = alt
                transit_dt = check_dt

        tz_offset = self._get_offset_hours()
        if transit_dt:
            local_transit = transit_dt + datetime.timedelta(hours=tz_offset)
            transit_time_str = local_transit.strftime("%H:%M")
        else:
            transit_time_str = "N/A"

        return transit_time_str, max_alt

    def _equatorial_to_horizontal(self, lat, lon, dt, ra, dec):
        """
        Converts equatorial coordinates (RA, Dec) to horizontal coordinates (alt, az).

        Parameters:
            lat: observer latitude (degrees)
            lon: observer longitude (degrees)
            dt: UTC datetime
            ra: right ascension (degrees)
            dec: declination (degrees)

        Returns:
            alt: altitude (degrees, 0=horizon, 90=zenith)
            az: azimuth (degrees, from North, clockwise)
        """
        # Compute local sidereal time (LST)
        # JD at start of day (UTC midnight)
        jd_midnight = DtoJD(dt.day, dt.month, dt.year, 0, 0, 0)
        # UTC hours in the day
        utc_hours = dt.hour + dt.minute / 60.0 + dt.second / 3600.0
        # Mean sidereal time at Greenwich (GMST) in hours
        # T = (jd_midnight - 2451545.0) / 36525.0
        gmst_hours = 18.697374558 + 24.06570982441908 * \
            (jd_midnight - 2451545.0) / 36525.0
        gmst_hours = (gmst_hours + 24.0) % 24.0
        # Add UTC hour
        lst_hours = (gmst_hours + utc_hours + lon / 15.0) % 24.0
        # Hour angle (H) in degrees
        h = (lst_hours - ra / 15.0) * 15.0
        # Ensure H is in [-180, 180]
        if h > 180:
            h -= 360
        elif h < -180:
            h += 360

        # Convert lat, dec, h to radians
        lat_rad = math.radians(lat)
        dec_rad = math.radians(dec)
        h_rad = math.radians(h)

        # Compute altitude (alt)
        sin_alt = math.sin(lat_rad) * math.sin(dec_rad) + \
            math.cos(lat_rad) * math.cos(dec_rad) * math.cos(h_rad)
        alt = math.degrees(math.asin(sin_alt))

        # Compute azimuth (az)
        sin_az = -math.cos(dec_rad) * math.sin(h_rad)
        cos_az = math.sin(dec_rad) - math.sin(lat_rad) * sin_alt
        az = math.degrees(math.atan2(sin_az, cos_az))

        # Normalize azimuth to [0, 360)
        az = (az + 360.0) % 360.0

        return alt, az

    def _calculate_magnitude(self, distance, illumination):
        # Magnitudine a distanza media e fase piena
        mag_full = -12.74
        # Correzione per distanza (legge inversa del quadrato)
        dist_factor = 5.0 * math.log10(distance / 384400.0)
        # Correzione per fase (modello lineare in log, approssimato)
        if illumination > 0:
            phase_factor = 2.5 * math.log10(illumination / 100.0)
        else:
            phase_factor = 0
        magnitude = mag_full + dist_factor + phase_factor
        return round(magnitude, 2)

    def _calculate_angular_diameter(self, distance):
        # Mean radius of the Moon in km
        moon_radius = 1737.4
        # Angular diameter in radians
        angular_rad = 2.0 * math.asin(moon_radius / distance)
        # Convert to arcseconds
        angular_arcsec = math.degrees(angular_rad) * 3600.0
        return round(angular_arcsec, 1)

    def _calculate_age(self, dt):
        jd = DtoJD(dt.day, dt.month, dt.year, dt.hour, dt.minute, dt.second)
        # Calculate k value for the current date (number of lunations since
        # 2000)
        year = dt.year
        month = dt.month
        day = dt.day + (dt.hour + dt.minute / 60.0 + dt.second / 3600.0) / 24.0
        YearFrac = year + (month - 1 + (day - 1) / 30.5) / 12
        k = (YearFrac - 2000) * 12.3685
        # Find the last New Moon (nearest integer k rounded down)
        k_new = int(k)
        jd_new = JDLunarPhase(k_new)
        age_days = jd - jd_new
        return round(age_days, 2)


# extra = self.moon.get_moon_extra_details(float(self.lat), float(self.lon))
# self["moonrise_azimuth"].setText(f"{extra['rise_azimuth']:.0f}°")
# self["moonset_azimuth"].setText(f"{extra['set_azimuth']:.0f}°")
# self["moon_transit_time"].setText(extra['transit_time'])
# self["moon_transit_alt"].setText(f"{extra['transit_altitude']:.0f}°")
# self["moon_magnitude"].setText(f"{extra['magnitude']:.2f}")
# self["moon_angular_diameter"].setText(f"{extra['angular_diameter']:.0f}\"")
# self["moon_age"].setText(f"{extra['age']:.1f} d")
