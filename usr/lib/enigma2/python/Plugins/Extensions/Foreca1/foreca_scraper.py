#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) @Lululla 2026
# foreca_scraper.py - Scraping functions for hourly forecast (regex based)

import datetime
from json import loads, JSONDecodeError
from typing import List

import requests

from . import HEADERS, DEBUG
from .foreca_weather_api import Place, HourForecast


def _fetch_html(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            return resp.text
    except Exception as e:
        print(f"[ForecaScraper] Error fetching {url}: {e}")
    return None


def scrape_hourly_forecast(place: Place, day: int = 0) -> List[HourForecast]:
    """
    Scrape hourly forecast for a given day from the Foreca website.
    Uses regex to extract the embedded JSON data.
    day: 0 = today, 1 = tomorrow, etc.
    Returns a list of HourForecast objects (empty on failure).
    """
    url = f"https://www.foreca.com/{place.id}/{place.address}/hourly?day={day}"
    html = _fetch_html(url)
    if not html:
        return []

    # Find the start of the data array
    data_start = html.find("data: [{")
    if data_start == -1:
        if DEBUG:
            print("[ForecaScraper] Could not find 'data: [' in page")
        return []

    # Extract from after "data: [" to the closing "}]"
    begin_data = html[data_start + 7:]  # after "data: ["
    # Find the end of the data array (the first occurrence of "}]" that closes the outer array)
    # We need to balance braces? Simpler: find the first "}]" that appears after some pattern.
    # In the plugin they used begin_data.find('}]') which works if the array content doesn't contain "}]".
    # We'll use that.
    hours_end = begin_data.find('}]')
    if hours_end == -1:
        if DEBUG:
            print("[ForecaScraper] Could not find end of data array")
        return []
    all_hours = begin_data[:hours_end + 1]  # include the closing "}]"

    # Now we have a string like: { ... }, { ... } ... ]
    # We need to turn it into valid JSON by giving each object a key.
    # The original plugin does: for each '{' replace with '"item{i}": {'
    # and then wrap with {"items": count, ...}
    formatted = ''
    item_count = 0
    # in_object = False
    for char in all_hours:
        if char == '{':
            # Start of a new object, replace with key
            formatted += f'"item{item_count}": {{'
            item_count += 1
        else:
            formatted += char

    # Wrap with outer object containing item count
    json_str = f'{{ "items": {item_count}, {formatted} }}'

    try:
        data = loads(json_str)
    except JSONDecodeError as e:
        print(f"[ForecaScraper] JSON decode error: {e}")
        return []

    result = []
    for i in range(item_count):
        item = data.get(f"item{i}")
        if not item:
            continue
        try:
            # Extract time (e.g., "2025-02-15T13:00")
            time_str = item.get("time", "")
            if not time_str:
                continue
            # We only need hour:minute
            time_part = time_str.split("T")[1] if "T" in time_str else time_str
            hour_min = time_part.split(":")[:2]
            hour = int(hour_min[0])
            minute = int(hour_min[1]) if len(hour_min) > 1 else 0
            time_obj = datetime.time(hour, minute)

            # uvi index
            uvi = int(item.get("uvi", 0))

            # Temperature (celsius)
            temp = int(item.get("temp", 0))

            # Feels like temperature (they might use "flike" or "feelsLike")
            feel_temp = int(item.get("flike", item.get("feelsLike", temp)))

            # Weather condition symbol
            condition = item.get("symb", "d000")

            # Humidity
            humidity = int(item.get("rhum", 0))

            # Wind speed (m/s) - key could be "winds" or "windSpeed"
            wind_speed = int(item.get("winds", item.get("windSpeed", 0)))

            # Wind direction (degrees)
            wind_direction = int(item.get("windd", 0))

            # Precipitation (mm) - key could be "rain" or "precip"
            precip = float(item.get("rain", item.get("precip", 0.0)))

            precip_prob = item.get("rainp")
            if precip_prob is not None:
                try:
                    precip_prob = int(precip_prob)
                except BaseException:
                    precip_prob = None

            hf = HourForecast(
                time=time_obj,
                temp=temp,
                feel_temp=feel_temp,
                condition=condition,
                humidity=humidity,
                wind_speed=wind_speed,
                wind_direction=wind_direction,
                uvi=uvi,
                precipitation=precip,
                precip_prob=precip_prob,
                solar_radiation=None
            )
            result.append(hf)
        except Exception as e:
            print(f"[ForecaScraper] Error parsing item {i}: {e}")
            continue

    return result
