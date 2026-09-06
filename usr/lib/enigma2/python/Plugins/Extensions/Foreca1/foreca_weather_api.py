#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) @Lululla 2026
# foreca_weather_api.py - Client for Foreca One free public API

import re
import time
import datetime
import logging
from os.path import exists
from json import load, dump
from typing import List, Optional
from urllib.parse import quote_plus

import requests

from . import (
    _,
    DEBUG,
    HEADERS,
    TOKEN_FILE,
    CONFIG_FILE
)


class Place:
    def __init__(self, id, address, name, country_name, timezone, lat, long):
        self.id = id
        self.address = address
        self.name = name
        self.country_name = country_name
        self.timezone = timezone
        self.lat = lat
        self.long = long


class CurrentWeather:
    def __init__(
            self,
            datetime,
            temp,
            condition,
            feel_temp,
            humidity,
            wind_speed,
            wind_direction,
            precipitation,
            pressure=None,
            wind_gust=None,
            dewpoint=None,
            uvi=None,
            aqi=None,
            rainp=None,
            snowp=None,
            snowff=None,
            flikeFCA=None,
            updated=None):
        self.datetime = datetime
        self.temp = temp
        self.condition = condition
        self.feel_temp = feel_temp
        self.humidity = humidity
        self.wind_speed = wind_speed
        self.wind_direction = wind_direction
        self.precipitation = precipitation
        self.pressure = pressure
        self.wind_gust = wind_gust
        self.dewpoint = dewpoint
        self.uvi = uvi
        self.aqi = aqi
        self.rainp = rainp
        self.snowp = snowp
        self.snowff = snowff
        self.flikeFCA = flikeFCA
        self.updated = updated


class DayForecast:
    def __init__(
            self,
            date,
            min_temp,
            max_temp,
            wind_speed,
            wind_direction,
            humidity,
            condition,
            precipitation,
            sunrise,
            sunset,
            daylength,
            maxwind=None,
            pres=None,
            uvi=None,
            rainp=None,
            snowp=None,
            updated=None,
            solar_radiation_sum=None):
        self.date = date
        self.min_temp = min_temp
        self.max_temp = max_temp
        self.wind_speed = wind_speed
        self.wind_direction = wind_direction
        self.humidity = humidity
        self.condition = condition
        self.precipitation = precipitation
        self.sunrise = sunrise
        self.sunset = sunset
        self.daylength = daylength
        self.maxwind = maxwind
        self.pres = pres
        self.uvi = uvi
        self.rainp = rainp
        self.snowp = snowp
        self.updated = updated
        self.solar_radiation_sum = solar_radiation_sum


class HourForecast:
    def __init__(
            self,
            time,
            temp,
            feel_temp,
            condition,
            humidity,
            wind_speed,
            wind_direction,
            uvi,
            precipitation,
            precip_prob=None,
            solar_radiation=None):
        self.time = time
        self.temp = temp
        self.feel_temp = feel_temp
        self.condition = condition
        self.humidity = humidity
        self.wind_speed = wind_speed
        self.wind_direction = wind_direction
        self.precipitation = precipitation
        self.precip_prob = precip_prob
        self.solar_radiation = solar_radiation


def _symbol_to_description(symbol_code):
    """Convert symbol code to weather description"""
    # Reuse or adapt your existing symbolToCondition method
    descriptions = {
        'd000': _('Clear'),
        'n000': _('Clear'),
        'd100': _('Mostly clear'),
        'n100': _('Mostly clear'),
        'd200': _('Partly cloudy'),
        'n200': _('Partly cloudy'),
        'd210': _('Partly cloudy and light rain'),
        'n210': _('Partly cloudy and light rain'),
        'd211': _('Partly cloudy and light wet snow'),
        'n211': _('Partly cloudy and light wet snow'),
        'd212': _('Partly cloudy and light snow'),
        'n212': _('Partly cloudy and light snow'),
        'd220': _('Partly cloudy and showers'),
        'n220': _('Partly cloudy and showers'),
        'd221': _('Partly cloudy and wet snow showers'),
        'n221': _('Partly cloudy and wet snow showers'),
        'd222': _('Partly cloudy and snow showers'),
        'n222': _('Partly cloudy and snow showers'),
        'd240': _('Partly cloudy, possible thunderstorms with rain'),
        'n240': _('Partly cloudy, possible thunderstorms with rain'),
        'd300': _('Cloudy'),
        'n300': _('Cloudy'),
        'd310': _('Cloudy and light rain'),
        'n310': _('Cloudy and light rain'),
        'd311': _('Cloudy and light wet snow'),
        'n311': _('Cloudy and light wet snow'),
        'd312': _('Cloudy and light snow'),
        'n312': _('Cloudy and light snow'),
        'd320': _('Cloudy and showers'),
        'n320': _('Cloudy and showers'),
        'd321': _('Cloudy and wet snow showers'),
        'n321': _('Cloudy and wet snow showers'),
        'd322': _('Cloudy and snow showers'),
        'n322': _('Cloudy and snow showers'),
        'd340': _('Cloudy, thunderstorms with rain'),
        'n340': _('Cloudy, thunderstorms with rain'),
        'd400': _('Overcast'),
        'n400': _('Overcast'),
        'd410': _('Overcast and light rain'),
        'n410': _('Overcast and light rain'),
        'd411': _('Overcast and light wet snow'),
        'n411': _('Overcast and light wet snow'),
        'd412': _('Overcast and light snow'),
        'n412': _('Overcast and light snow'),
        'd430': _('Overcast and rain'),
        'n430': _('Overcast and rain'),
        'd421': _('Overcast and wet snow showers'),
        'n421': _('Overcast and wet snow showers'),
        'd432': _('Overcast and snow showers'),
        'n432': _('Overcast and snow showers'),
        'd420': _('Overcast and showers'),
        'n420': _('Overcast and showers'),
        'd431': _('Overcast and wet snow'),
        'n431': _('Overcast and wet snow'),
        'd422': _('Overcast and snow'),
        'n422': _('Overcast and snow'),
        'd440': _('Overcast, thunderstorms with rain'),
        'n440': _('Overcast, thunderstorms with rain'),
        'd500': _('Thin upper cloud'),
        'n500': _('Thin upper cloud'),
        'd600': _('Fog'),
        'n600': _('Fog'),
        'na': _('N/A')
    }
    return descriptions.get(symbol_code, 'na')


class ForecaFreeAPI:
    """
    Client for the public Foreca One API (no authentication required).
    Documentation: https://api.foreca.net
    """
    BASE_URL = "https://api.foreca.net"

    def __init__(self, unit_manager=None):
        self.unit_manager = unit_manager
        self._session = requests.Session()
        self._session.headers.update(HEADERS)
        # Lazy import of scraper to avoid circular imports
        self._scraper = None

    @property
    def scraper(self):
        if self._scraper is None:
            from .foreca_scraper import scrape_hourly_forecast
            self._scraper = scrape_hourly_forecast
        return self._scraper

    def _fetch_json(self, url, params=None):
        try:
            resp = self._session.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            else:
                logging.getLogger(__name__).error(
                    f"HTTP {resp.status_code} for {url}")
                return None
        except Exception as e:
            logging.getLogger(__name__).error(f"Error fetching {url}: {e}")
            return None

    def _fetch_html(self, url):
        """Fetch HTML content from a URL (used by scraping methods)."""
        try:
            resp = self._session.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.text
        except Exception as e:
            logging.getLogger(__name__).error(f"Error fetching {url}: {e}")
        return None

    # ---------- Location search ----------
    def search_locations(self, query: str, lang: str = "en") -> List[Place]:
        url = f"{self.BASE_URL}/locations/search/{quote_plus(query)}.json"
        params = {"limit": 30, "lang": lang}
        data = self._fetch_json(url, params)
        if not data or "results" not in data:
            return []
        places = []
        for item in data["results"]:
            address = "-".join(filter(None, [
                item.get("defaultName", "").replace(" ", "-"),
                item.get("defaultAdmName", "").replace(" ", "-"),
                item.get("defaultCountryName", "").replace(" ", "-")
            ]))
            places.append(Place(
                id=item["id"],
                address=address,
                name=item["name"],
                country_name=item["countryName"],
                timezone=item["timezone"],
                lat=item["lat"],
                long=item["lon"]
            ))
        return places

    def get_location_by_coords(
            self,
            lat: float,
            lon: float,
            accuracy=1000) -> Optional[Place]:
        url = f"{self.BASE_URL}/locations/{lon},{lat}.json"
        params = {"accuracy": accuracy}
        data = self._fetch_json(url, params)
        if not data:
            return None
        address = "-".join(filter(None, [
            data.get("defaultName", "").replace(" ", "-"),
            data.get("admName", "").replace(" ", "-"),
            data.get("defaultCountryName", "").replace(" ", "-")
        ]))
        return Place(
            id=data["id"],
            address=address,
            name=data["name"],
            country_name=data["countryName"],
            timezone=data["timezone"],
            lat=data["lat"],
            long=data["lon"]
        )

    def get_location_by_id(self, location_id: str) -> Optional[Place]:
        url = f"{self.BASE_URL}/locations/{location_id}.json"
        data = self._fetch_json(url)
        if not data:
            return None
        address = "-".join(filter(None, [
            data.get("defaultName", "").replace(" ", "-"),
            data.get("admName", "").replace(" ", "-"),
            data.get("defaultCountryName", "").replace(" ", "-")
        ]))
        return Place(
            id=data["id"],
            address=address,
            name=data["name"],
            country_name=data["countryName"],
            timezone=data["timezone"],
            lat=data["lat"],
            long=data["lon"]
        )

    # ---------- Daily forecast (10 days) ----------
    def get_daily_forecast(
            self,
            location_id: str,
            days: int = 10) -> List[DayForecast]:
        url = f"{self.BASE_URL}/data/favorites/{location_id}.json"
        data = self._fetch_json(url)
        if not data or location_id not in data:
            return []
        forecast_list = data[location_id][:days]
        days_forecast = []
        for item in forecast_list:
            try:
                date = datetime.datetime.strptime(
                    item["date"], "%Y-%m-%d").date()
                sunrise = None
                if item.get("sunrise") is not None:
                    try:
                        sunrise = datetime.datetime.strptime(
                            item["sunrise"], "%H:%M:%S").time()
                    except (ValueError, TypeError):
                        sunrise = None

                sunset = None
                if item.get("sunset") is not None:
                    try:
                        sunset = datetime.datetime.strptime(
                            item["sunset"], "%H:%M:%S").time()
                    except (ValueError, TypeError):
                        sunset = None
            except (KeyError, ValueError):
                continue
            day = DayForecast(
                date=date,
                min_temp=item["tmin"],
                max_temp=item["tmax"],
                wind_speed=item["winds"],
                wind_direction=item["windd"],
                humidity=item["rhum"],
                condition=item["symb"],
                precipitation=item.get("rain", 0),
                sunrise=sunrise,
                sunset=sunset,
                # daylength=item["daylen"],
                daylength=item.get("daylen"),
                maxwind=item.get("maxwind"),
                pres=item.get("pres"),
                uvi=item.get("uvi"),
                rainp=item.get("rainp"),
                snowp=item.get("snowp"),
                updated=item.get("updated"),
                solar_radiation_sum=None
            )
            days_forecast.append(day)
        return days_forecast

    # ---------- Current weather (using /recent endpoint) ----------
    def get_current_weather(
            self,
            location_id: str) -> Optional[CurrentWeather]:
        url = f"{self.BASE_URL}/data/recent/{location_id}.json"
        data = self._fetch_json(url)
        if not data or location_id not in data:
            return None
        item = data[location_id]
        if DEBUG:
            print(f"[ForecaFreeAPI] /recent response: {item}")  # DEBUG
        try:
            dt = datetime.datetime.now(datetime.timezone.utc)
            return CurrentWeather(
                datetime=dt,
                temp=item.get("temp", 0),
                condition=item.get("symb", "d000"),
                feel_temp=item.get("flike", item.get("temp", 0)),
                humidity=item.get("rhum", 0),
                pressure=item.get("pres"),
                wind_speed=item.get("winds", 0),
                wind_gust=item.get("maxwind"),
                wind_direction=item.get("windd", 0),
                precipitation=item.get("rain", 0.0),
                dewpoint=item.get("dewp"),
                uvi=item.get("uvi"),
                aqi=item.get("aqi"),
                rainp=item.get("rainp"),
                snowp=item.get("snowp"),
                snowff=item.get("snowff"),
                flikeFCA=item.get("flikeFCA"),
                updated=item.get("updated")
            )
        except Exception as e:
            logging.getLogger(__name__).error(
                f"Error parsing current weather: {e}")
            return None

    # ---------- Hourly forecast (scraping) ----------
    def get_hourly_forecast(
            self,
            location_id: str,
            day: int = 0) -> List[HourForecast]:
        place = self.get_location_by_id(location_id)
        if not place:
            return []
        try:
            hourly_list = self.scraper(place, day)
            # Ensure each object has solar_radiation = None (scraper doesn't
            # provide it)
            for h in hourly_list:
                h.solar_radiation = None
            return hourly_list
        except Exception as e:
            logging.getLogger(__name__).error(f"Error in hourly forecast: {e}")
            return []

    def get_today_tomorrow_details(
            self,
            location_id: str,
            tz_offset: float = None) -> dict:
        """
        Returns hourly details for today and tomorrow, divided into local time slots.
        If tz_offset is provided (e.g. +2, -5), converts UTC hours to local hours.
        """
        result = {'today': {}, 'tomorrow': {}}

        daily_all = self.get_daily_forecast(location_id, days=2)
        if len(daily_all) < 2:
            return result

        today_daily = daily_all[0]
        tomorrow_daily = daily_all[1]

        def _process_day(day_index):
            hourly = self.get_hourly_forecast(location_id, day=day_index)
            if not hourly:
                return None

            periods = {
                'overnight': [],   # 00:00 - 05:59 local time
                'morning': [],     # 06:00 - 11:59 local time
                'afternoon': [],   # 12:00 - 17:59 local time
                'evening': []      # 18:00 - 23:59 local time
            }

            for h in hourly:
                hour_utc = h.time.hour
                if tz_offset is not None:
                    # Simple conversion with integer offset (handles modulo 24)
                    hour_local = int((hour_utc + tz_offset) % 24)
                else:
                    hour_local = hour_utc

                if 0 <= hour_local < 6:
                    periods['overnight'].append(h)
                elif 6 <= hour_local < 12:
                    periods['morning'].append(h)
                elif 12 <= hour_local < 18:
                    periods['afternoon'].append(h)
                elif 18 <= hour_local < 24:
                    periods['evening'].append(h)

            day_data = {}
            for period, hours_list in periods.items():
                if not hours_list:
                    day_data[period] = {'temp': 'N/A', 'symbol': 'na'}
                else:
                    avg_temp = sum(
                        h.temp for h in hours_list) / len(hours_list)
                    symbols = [h.condition for h in hours_list]
                    # Median symbol for the time slot
                    symbol = symbols[len(symbols) // 2] if symbols else 'na'
                    day_data[period] = {
                        'temp': round(avg_temp), 'symbol': symbol}
            return day_data

        # Process tomorrow (index 1) and today (index 0)
        tomorrow_periods = _process_day(1)
        today_periods = _process_day(0)

        if not today_periods:
            today_periods = {}
        if not tomorrow_periods:
            tomorrow_periods = {}

        # If today's 'overnight' slot is empty, use tomorrow's (useful for
        # positive timezones)
        if today_periods.get('overnight', {}).get(
                'temp') == 'N/A' and tomorrow_periods.get('overnight'):
            today_periods['overnight'] = tomorrow_periods['overnight']

        result['today'].update(today_periods)
        result['tomorrow'].update(tomorrow_periods)

        # Daily summary data
        result['today']['text'] = today_daily.condition
        result['today']['max_temp'] = today_daily.max_temp
        result['today']['min_temp'] = today_daily.min_temp
        result['today']['rain_mm'] = today_daily.precipitation
        result['today']['wind_dir'] = today_daily.wind_direction
        result['today']['wind_speed'] = today_daily.wind_speed

        result['tomorrow']['text'] = tomorrow_daily.condition
        result['tomorrow']['max_temp'] = tomorrow_daily.max_temp
        result['tomorrow']['min_temp'] = tomorrow_daily.min_temp
        result['tomorrow']['rain_mm'] = tomorrow_daily.precipitation
        result['tomorrow']['wind_dir'] = tomorrow_daily.wind_direction
        result['tomorrow']['wind_speed'] = tomorrow_daily.wind_speed

        return result

    def get_station_observations(self, location_id, station_limit=3):
        """Stub: not available in free API"""
        return []

    def scrape_nearby_stations(self, place) -> List[dict]:
        """
        Scrape nearby weather stations from the Foreca page of a location.
        Returns a list of dicts with all available data.
        """
        url = f"https://www.foreca.com/{place.id}/{place.address}"
        html = self._fetch_html(url)
        if not html:
            return []

        # Look for the observations section
        obs_section = re.search(
            r'<section class="item observations front">(.*?)</section>',
            html,
            re.DOTALL | re.IGNORECASE)
        if not obs_section:
            return []
        obs_html = obs_section.group(1)

        stations = []
        # Each station is an <a class="obsLink"...>...</a>
        for match in re.finditer(
            r'<a class="obsLink"[^>]*>(.*?)</a>',
            obs_html,
                re.DOTALL | re.IGNORECASE):
            inner = match.group(1)

            # Station name
            name_match = re.search(
                r'<div class="locationName"><p>(.*?)</p>', inner, re.DOTALL)
            station_name = name_match.group(
                1).strip() if name_match else "Unknown"

            # Current temperature
            temp_match = re.search(
                r'<span class="value temp temp_c[^"]*">([+-]?\d+)', inner)
            temp = int(temp_match.group(1)) if temp_match else None

            # Feels like temperature
            feels_match = re.search(
                r'<p[^>]*class="feelsLike".*?<span[^>]*class="value temp temp_c"[^>]*>([+-]?\d+)',
                inner,
                re.DOTALL | re.IGNORECASE)
            feels_like = int(feels_match.group(1)) if feels_match else None

            # Dewpoint
            dew_match = re.search(
                r'<p[^>]*class="dewpoint".*?<span[^>]*class="value temp temp_c"[^>]*>([+-]?\d+)',
                inner,
                re.DOTALL | re.IGNORECASE)
            dewpoint = int(dew_match.group(1)) if dew_match else None

            # Humidity
            hum_match = re.search(
                r'<p[^>]*class="humidity".*?<span[^>]*>(\d+)',
                inner,
                re.DOTALL | re.IGNORECASE)
            humidity = int(hum_match.group(1)) if hum_match else None

            # Pressure (hPa)
            press_match = re.search(
                r'pres_hpa"[^>]*>(\d+)',
                inner,
                re.DOTALL | re.IGNORECASE)
            pressure = int(press_match.group(1)) if press_match else None

            # Visibility (m)
            vis_match = re.search(
                r'vis_km"[^>]*>(\d+)',
                inner,
                re.DOTALL | re.IGNORECASE)
            visibility = int(vis_match.group(1)) if vis_match else None

            # Last update time
            time_match = re.search(
                r'<span class="value time time_24h">(\d{1,2}:\d{2})', inner)
            time_ago = time_match.group(1) if time_match else None

            # Station ID
            station_id_match = re.search(r'stationId=(\d+)', inner)
            station_id = station_id_match.group(
                1) if station_id_match else None

            stations.append({
                'station': station_name,
                'temperature': temp,
                'feelsLikeTemp': feels_like,
                'dewpoint': dewpoint,
                'relHumidity': humidity,
                'pressure': pressure,
                'visibility': visibility,
                'time_ago': time_ago,
                'station_id': station_id
            })

        return stations

    def get_nearby_stations_scraped(self, location_id: str) -> List[dict]:
        """Scrape nearby stations from the Foreca website (public fallback)."""
        place = self.get_location_by_id(location_id)
        if not place:
            return []
        try:
            return self.scrape_nearby_stations(place)
        except Exception as e:
            logging.getLogger(__name__).error(f"Error scraping stations: {e}")
            return []

    def _api_symbol_to_icon(self, api_symbol):
        """Map API symbols to your local icons"""
        # Complete mapping based on the available weather codes
        symbol_map = {
            'd000': 'd000', 'n000': 'n000',
            'd100': 'd100', 'n100': 'n100',
            'd200': 'd200', 'n200': 'n200',
            'd210': 'd210', 'n210': 'n210',
            'd211': 'd211', 'n211': 'n211',
            'd212': 'd212', 'n212': 'n212',
            'd220': 'd220', 'n220': 'n220',
            'd221': 'd221', 'n221': 'n221',
            'd222': 'd222', 'n222': 'n222',
            'd240': 'd240', 'n240': 'n240',
            'd300': 'd300', 'n300': 'n300',
            'd310': 'd310', 'n310': 'n310',
            'd311': 'd311', 'n311': 'n311',
            'd312': 'd312', 'n312': 'n312',
            'd320': 'd320', 'n320': 'n320',
            'd321': 'd321', 'n321': 'n321',
            'd322': 'd322', 'n322': 'n322',
            'd340': 'd340', 'n340': 'n340',
            'd400': 'd400', 'n400': 'n400',
            'd410': 'd410', 'n410': 'n410',
            'd411': 'd411', 'n411': 'n411',
            'd412': 'd412', 'n412': 'n412',
            'd420': 'd420', 'n420': 'n420',
            'd421': 'd421', 'n421': 'n421',
            'd422': 'd422', 'n422': 'n422',
            'd430': 'd430', 'n430': 'n430',
            'd431': 'd431', 'n431': 'n431',
            'd432': 'd432', 'n432': 'n432',
            'd440': 'd440', 'n440': 'n440',
            'd500': 'd500', 'n500': 'n500',
            'd600': 'd600', 'n600': 'n600',
            'na': 'N/A'
        }
        return symbol_map.get(api_symbol, 'na')


class ForecaWeatherAPI:
    """Foreca One text weather data client API (current, forecast)"""

    def __init__(self, unit_manager=None):
        self.unit_manager = unit_manager
        self.base_url = "https://pfa.foreca.com"
        self.token = None
        self.token_expire = 0
        self.load_credentials()
        self.load_token()

    def load_credentials(self):
        """Load credentials from existing configuration file"""
        self.user = ""
        self.password = ""

        if exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('API_USER='):
                            self.user = line.split('=', 1)[1].strip()
                        elif line.startswith('API_PASSWORD='):
                            self.password = line.split('=', 1)[1].strip()

                if DEBUG:
                    print(
                        f"[Foreca1WeatherAPI] Credentials loaded for: {self.user}")
            except Exception as e:
                print(f"[Foreca1WeatherAPI] Error loading credentials: {e}")

    def get_daily_forecast(
            self,
            location_id: str,
            days: int = 7) -> List[DayForecast]:
        """
        Fetch daily forecast using the authenticated API.
        Returns a list of DayForecast objects with solar_radiation_sum.
        """
        token = self.get_token()
        if not token:
            return []

        url = f"{self.base_url}/api/v1/forecast/daily/{location_id}"
        headers = {"Authorization": f"Bearer {token}"}
        params = {
            "periods": days,
            "tempunit": "C",
            "windunit": "MS",
            "dataset": "full"
        }

        try:
            resp = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=15)
            if resp.status_code != 200:
                return []

            data = resp.json()
            forecast_list = data.get('forecast', [])
            result = []

            for item in forecast_list:
                date_str = item.get('date')
                if not date_str:
                    continue

                date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()

                # Parse optional times
                sunrise = None
                sunset = None
                if item.get('sunrise'):
                    sunrise = datetime.datetime.strptime(
                        item['sunrise'], "%H:%M:%S").time()
                if item.get('sunset'):
                    sunset = datetime.datetime.strptime(
                        item['sunset'], "%H:%M:%S").time()

                df = DayForecast(
                    date=date,
                    min_temp=item.get('minTemp'),
                    max_temp=item.get('maxTemp'),
                    wind_speed=item.get('maxWindSpeed'),
                    wind_direction=item.get('windDir'),
                    humidity=item.get('maxRelHumidity'),
                    condition=item.get('symbol'),
                    precipitation=item.get('precipAccum'),
                    sunrise=sunrise,
                    sunset=sunset,
                    daylength=None,
                    maxwind=item.get('maxWindSpeed'),
                    pres=item.get('pressure'),
                    uvi=item.get('uvIndex'),
                    rainp=item.get('precipProb'),
                    snowp=None,
                    updated=item.get('updated'),
                    solar_radiation_sum=item.get('solarRadiationSum')
                )
                result.append(df)

            return result

        except Exception as e:
            print(f"[ForecaWeatherAPI] Error in daily forecast: {e}")
            return []

    def get_hourly_forecast(
            self,
            location_id: str,
            day: int = 0) -> List[HourForecast]:
        token = self.get_token()
        if not token:
            return []

        url = f"{self.base_url}/api/v1/forecast/hourly/{location_id}"
        headers = {"Authorization": f"Bearer {token}"}
        params = {
            "periods": 120,
            "tempunit": "C",
            "windunit": "MS",
            "dataset": "full"
        }

        try:
            resp = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=15)
            if resp.status_code != 200:
                print(
                    f"[ForecaWeatherAPI] Hourly forecast error: {resp.status_code}")
                return []

            data = resp.json()
            # --- DEBUG: stampa i campi del primo elemento ---
            forecast_list = data.get('forecast', [])
            if forecast_list:
                print(
                    "[DEBUG] First forecast item keys:", list(
                        forecast_list[0].keys()))
                if 'solarRadiation' in forecast_list[0]:
                    print("[DEBUG] solarRadiation IS present")
                else:
                    print("[DEBUG] solarRadiation NOT present")
            # -------------------------------------------------
            target_date = (
                datetime.date.today() +
                datetime.timedelta(
                    days=day)).isoformat()
            result = []

            for item in forecast_list:
                time_str = item.get('time')
                if not time_str:
                    continue

                dt = datetime.datetime.fromisoformat(
                    time_str.replace('Z', '+00:00'))
                if dt.date().isoformat() != target_date:
                    continue

                hf = HourForecast(
                    time=dt.time(),
                    temp=item.get('temperature'),
                    feel_temp=item.get('feelsLikeTemp'),
                    condition=item.get('symbol'),
                    humidity=item.get('relHumidity'),
                    wind_speed=item.get('windSpeed'),
                    wind_direction=item.get('windDir'),
                    uvi=item.get('uvIndex'),
                    precipitation=item.get('precipAccum'),
                    precip_prob=item.get('precipProb'),
                    solar_radiation=item.get('solarRadiation')
                )
                result.append(hf)
                print(f"[ForecaWeatherAPI] result forecast: {result}")

            return result

        except Exception as e:
            print(f"[ForecaWeatherAPI] Error in hourly forecast: {e}")
            return []

    def check_credentials(self):
        """Check whether credentials are configured"""
        return bool(self.user and self.password)

    def load_token(self):
        """Load token from cache (shared with maps)"""
        if exists(TOKEN_FILE):
            try:
                with open(TOKEN_FILE, 'r') as f:
                    data = load(f)
                    if data['expire'] > time.time():
                        self.token = data['token']
                        self.token_expire = data['expire']
                        if DEBUG:
                            print("[Foreca1WeatherAPI] Token loaded from cache")
            except Exception as e:
                print(f"[Foreca1WeatherAPI] Error loading token: {e}")

    def get_token(self, force_new=False):
        """Get authentication token"""
        if not self.user or not self.password:
            if DEBUG:
                print("[Foreca1WeatherAPI] ERROR: Missing credentials!")
            return None

        if not force_new and self.token and self.token_expire > time.time() + 300:
            if DEBUG:
                print("[Foreca1WeatherAPI] Using cached token")
            return self.token

        if DEBUG:
            print("[Foreca1WeatherAPI] Requesting NEW token...")
        try:
            url = f"{self.base_url}/authorize/token?expire_hours=720"
            data = {"user": self.user, "password": self.password}

            response = requests.post(url, json=data, timeout=10)

            if response.status_code == 200:
                result = response.json()
                self.token = result['access_token']
                self.token_expire = time.time() + result['expires_in']

                # Save to cache
                with open(TOKEN_FILE, 'w') as f:
                    dump({
                        'token': self.token,
                        'expire': self.token_expire
                    }, f)

                if DEBUG:
                    print("[Foreca1WeatherAPI] New token received")
                return self.token
            else:
                if DEBUG:
                    print(
                        f"[Foreca1WeatherAPI] Auth error: {response.status_code}")
                    print(f"Response: {response.text[:200]}")
                return None

        except Exception as e:
            print(f"[Foreca1WeatherAPI] Error getting token: {e}")
            return None

    def get_station_observations(self, location_id, station_limit=3):
        """
        Get nearby weather station observations via Foreca API

        Args:
            location_id: Foreca One location ID (e.g., "100659935")
            station_limit: maximum number of stations (default 3, max 6)

        Returns:
            List of station observations or None
        """
        token = self.get_token()
        if not token:
            if DEBUG:
                print("[Foreca1WeatherAPI] No token for station observations")
            return None

        try:
            headers = {"Authorization": f"Bearer {token}"}

            # Build parameters according to API spec
            params = {
                "stations": min(station_limit, 6),  # Max 6 stations
                "tempunit": "C",  # Default, overwritten by unit_manager if present
                "windunit": "MS"  # Default m/s, overwritten by unit_manager
            }

            # Override units if UnitManager exists
            if self.unit_manager:
                unit_params = self.unit_manager.get_api_params()
                params["tempunit"] = unit_params.get("tempunit", "C")
                params["windunit"] = unit_params.get("windunit", "MS")

            # Endpoint: latest station observations
            url = f"https://pfa.foreca.com/api/v1/observation/latest/{location_id}"
            if DEBUG:
                print(f"[Foreca1WeatherAPI] Requesting: {url}")
                print(f"[Foreca1WeatherAPI] Params: {params}")

            response = requests.get(
                url, headers=headers, params=params, timeout=15)
            if DEBUG:
                print(
                    f"[Foreca1WeatherAPI] HTTP Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                observations = data.get('observations', [])
                if DEBUG:
                    print(
                        f"[Foreca1WeatherAPI] Got {len(observations)} station observations")

                # Debug: print first station sample
                if observations:
                    first = observations[0]
                    if DEBUG:
                        print(
                            f"[Foreca1WeatherAPI] Sample: {first.get('station')} - {first.get('temperature')}°C")

                return observations
            else:
                if DEBUG:
                    print(
                        f"[Foreca1WeatherAPI] Error {response.status_code}: {response.text[:200]}")
                return None

        except requests.exceptions.ConnectionError as e:
            if DEBUG:
                print(f"[Foreca1WeatherAPI] Connection error: {e}")
                print(
                    "[Foreca1WeatherAPI] Check if pfa.foreca.com is reachable from your network")
            return None
        except Exception as e:
            print(f"[Foreca1WeatherAPI] Exception: {e}")
            return None
