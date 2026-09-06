#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) @Lululla 2026
# foreca_map_api.py - Foreca One Maps API Management

import time
import hashlib
import subprocess
import tempfile
from json import load, dump
from os import remove, listdir, unlink
from os.path import exists, join, isfile, getmtime
from threading import Thread

import requests
from PIL import Image

from . import (
    DEBUG,
    CACHE_BASE,
    TOKEN_FILE,
    CONFIG_FILE,
    CACHE_EXPIRE
)


class ForecaMapAPI:
    """Manages the Foreca  1 Map API with cache and file-based configuration"""

    def __init__(self, region='eu'):
        self.user = ""
        self.password = ""
        self.token_expire_hours = 720
        # server_map = {
        # 'eu': 'map-eu.foreca.com',
        # 'europe': 'map-eu.foreca.com',
        # 'us': 'map-us.foreca.com',
        # 'usa': 'map-us.foreca.com',
        # }
        # self.map_server = server_map.get(region, 'map-eu.foreca.com')
        server_map = {
            'eu': 'map-eu.foreca.com',
            'europe': 'map-eu.foreca.com',
            # <-- Force use of European server for USA too
            'us': 'map-eu.foreca.com',
            # <-- Force use of European server for USA too
            'usa': 'map-eu.foreca.com',
        }
        self.map_server = server_map.get(region, 'map-eu.foreca.com')
        self.auth_server = 'pfa.foreca.com'

        self.token = None
        self.token_expire = 0

        self.load_config()
        self.load_token()
        if DEBUG:
            print(
                f"[Foreca1MapAPI] Initialized for user: {self.user}, region: {region}")
        self.clear_cache()

    def load_config(self):
        """Load configuration from file"""
        default_config = {
            "API_USER": "your_username_here",
            "API_PASSWORD": "your_password_here",
            "TOKEN_EXPIRE_HOURS": "720",
            "MAP_SERVER": "map-eu.foreca.com",
            "AUTH_SERVER": "pfa.foreca.com"
        }

        config_data = default_config.copy()
        if exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    lines = f.readlines()

                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip()
                            if '#' in value:
                                value = value.split('#')[0].strip()
                            config_data[key] = value
                if DEBUG:
                    print(
                        f"[Foreca1MapAPI] Configuration loaded from {CONFIG_FILE}")
            except Exception as e:
                print(f"[Foreca1MapAPI] Error loading config: {e}")
                # Create example config file
                self.create_example_config()
        else:
            if DEBUG:
                print("[Foreca1MapAPI] Config file not found, creating example")
            self.create_example_config()
            # Use hardcoded values as fallback
            config_data = default_config

        # Assign values
        self.user = config_data.get("API_USER", "ekekaz")
        self.password = config_data.get("API_PASSWORD", "im5issEYcMUG")
        self.token_expire_hours = int(
            config_data.get(
                "TOKEN_EXPIRE_HOURS", 720))
        self.map_server = config_data.get("MAP_SERVER", "map-eu.foreca.com")
        self.auth_server = config_data.get("AUTH_SERVER", "pfa.foreca.com")

        # Check if credentials are present
        if not self.user or not self.password:
            print("[Foreca1MapAPI] WARNING: API credentials missing in config file!")

    def _get_colorscheme_for_layer(self, layer_id, unit_system='metric'):
        """
        Returns the appropriate color scheme for the layer and unit system.
        Based on the actual capabilities.
        """
        # Complete mapping from the real data in capabilities.json
        colorschemes = {
            # Temperature (ID 2)
            2: {
                'metric': 'default',           # default is Celsius
                'imperial': 'temp-fahrenheit-noalpha'
            },
            # Wind symbol (ID 3) - uses only default
            3: {
                'metric': 'default',
                'imperial': 'default'          # symbols do not depend on units
            },
            # Wind speed (ID 8) - if present
            8: {
                'metric': 'winds-noalpha',
                'imperial': 'winds-mph-noalpha'
            },
            # Precipitation (ID 5) - if needed
            5: {
                'metric': 'default',
                'imperial': 'precip-in-noalpha'
            }
        }
        # Default to 'default' if the layer is not mapped
        return colorschemes.get(layer_id, {}).get(unit_system, 'default')

    def create_example_config(self):
        """Create example configuration file"""
        try:
            example_content = """# Foreca API Configuration
                # Rename this file to api_config.txt and fill with your credentials

                # Your Foreca API username
                API_USER=ekekaz

                # Your Foreca API password
                API_PASSWORD=im5issEYcMUG

                # Token expiration in hours (max 720 = 30 days)
                TOKEN_EXPIRE_HOURS=720

                # Map server (EU, US, etc.)
                MAP_SERVER=map-eu.foreca.com

                # Authentication server
                AUTH_SERVER=pfa.foreca.com

                # Save this file as api_config.txt (remove .example)
                """
            example_file = CONFIG_FILE + ".example"
            with open(example_file, 'w') as f:
                f.write(example_content)
            if DEBUG:
                print(f"[Foreca1MapAPI] Created example file: {example_file}")
        except Exception as e:
            print(f"[Foreca1MapAPI] Error creating example: {e}")

    def load_token(self):
        """Load token from cache"""
        if exists(TOKEN_FILE):
            try:
                with open(TOKEN_FILE, 'r') as f:
                    data = load(f)
                    if data['expire'] > time.time():
                        self.token = data['token']
                        self.token_expire = data['expire']
                        if DEBUG:
                            print("[Foreca1MapAPI] Token loaded from cache")
            except Exception as e:
                print(f"[Foreca1MapAPI] Error loading token: {e}")

    def get_token(self, force_new=False):
        """Get a valid authentication token"""
        if DEBUG:
            print(
                f"[DEBUG] get_token called. "
                f"force_new={force_new}, "
                f"token_exists={self.token is not None}, "
                f"expire={self.token_expire}, "
                f"current_time={time.time()}"
            )

        # Check if credentials exist
        if not self.user or not self.password:
            print("[Foreca1MapAPI] ERROR: Missing credentials!")
            return None

        # Use cached token if still valid (with 5 minutes safety margin)
        if not force_new and self.token and self.token_expire > time.time() + 300:
            if DEBUG:
                print("[DEBUG] Cached token is still valid")
            return self.token
        if DEBUG:
            print("[DEBUG] Requesting a NEW token...")
        try:
            url = f"https://{self.auth_server}/authorize/token?expire_hours={self.token_expire_hours}"
            data = {"user": self.user, "password": self.password}
            if DEBUG:
                print(f"[DEBUG] Auth URL: {url}")

            response = requests.post(url, json=data, timeout=10)
            if DEBUG:
                print(f"[DEBUG] Auth HTTP status: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                self.token = result['access_token']
                self.token_expire = time.time() + result['expires_in']
                if DEBUG:
                    print(
                        f"[DEBUG] New token received: {self.token[:30]}..., "
                        f"expires in {result['expires_in']} seconds"
                    )
                with open(TOKEN_FILE, 'w') as f:
                    dump({
                        'token': self.token,
                        'expire': self.token_expire
                    }, f)
                return self.token

            if response.status_code == 200:
                result = response.json()
                self.token = result['access_token']
                self.token_expire = time.time() + result['expires_in']

            else:
                if DEBUG:
                    print(
                        f"[DEBUG] Auth HTTP error {response.status_code}: "
                        f"{response.text[:100]}"
                    )
                return None

        except Exception as e:
            print(f"[DEBUG] get_token exception: {e}")
            import traceback
            traceback.print_exc()
            return None

    def get_capabilities(self):
        """Get available layers list"""
        token = self.get_token()
        if not token:
            if DEBUG:
                print("[Foreca1MapAPI] No token for capabilities")
            return []

        cache_file = join(CACHE_BASE, "capabilities.json")

        # Use cache if valid (30 minutes)
        if exists(cache_file):
            mtime = getmtime(cache_file)
            if time.time() - mtime < 1800:  # 30 minutes
                try:
                    with open(cache_file, 'r') as f:
                        data = load(f)
                        if DEBUG:
                            print(
                                f"[Foreca1MapAPI] Capabilities from cache: {len(data.get('images', []))} layers")
                        return data.get('images', [])
                except Exception as e:
                    print(f"[Foreca1MapAPI] Cache capabilities error: {e}")

        try:
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(
                f"https://{self.map_server}/api/v1/capabilities",
                headers=headers,
                timeout=15
            )

            if response.status_code == 200:
                data = response.json()
                # Save to cache
                with open(cache_file, 'w') as f:
                    dump(data, f)
                if DEBUG:
                    print(
                        f"[Foreca1MapAPI] Capabilities downloaded: {len(data.get('images', []))} layers")
                return data.get('images', [])
            else:
                if DEBUG:
                    print(
                        f"[Foreca1MapAPI] Capabilities HTTP error {response.status_code}")
                return []

        except Exception as e:
            print(f"[Foreca1MapAPI] Capabilities error: {e}")
            return []

    def _convert_svg_to_png(self, svg_data, output_png):
        """Converts SVG data to PNG using rsvg-convert."""
        try:
            # Check if rsvg-convert is available
            subprocess.run(['rsvg-convert', '--version'],
                           capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            if DEBUG:
                print(
                    "[Foreca1MapAPI] rsvg-convert not found, unable to convert SVG")
            return False

        try:
            with tempfile.NamedTemporaryFile(suffix='.svg', delete=False) as f:
                f.write(svg_data)
                svg_path = f.name

            subprocess.run(['rsvg-convert', '-o', output_png,
                           svg_path], check=True, timeout=10)
            unlink(svg_path)
            return True
        except Exception as e:
            print(f"[Foreca1MapAPI] SVG conversion failed: {e}")
            if exists(svg_path):
                unlink(svg_path)
            return False

    def get_tile(self, layer_id, timestamp, zoom, x, y, unit_system='metric'):
        token = self.get_token()
        if not token:
            return None

        colorscheme = self._get_colorscheme_for_layer(layer_id, unit_system)
        cache_key = f"{layer_id}_{timestamp}_{zoom}_{x}_{y}_{colorscheme}"
        cache_hash = hashlib.md5(cache_key.encode()).hexdigest()

        # We determine the extent based on the layer
        if layer_id == 3:  # windsvg
            cache_file = join(CACHE_BASE, f"{cache_hash}.svg")
        else:
            cache_file = join(CACHE_BASE, f"{cache_hash}.png")

        if exists(cache_file):
            mtime = getmtime(cache_file)
            if time.time() - mtime < CACHE_EXPIRE:
                return cache_file

        url = f"https://{self.map_server}/api/v1/image/tile/{zoom}/{x}/{y}/{timestamp}/{layer_id}"
        params = {"token": token, "colorscheme": colorscheme}

        try:
            response = requests.get(url, params=params, timeout=30)
            if response.status_code == 200:
                with open(cache_file, 'wb') as f:
                    f.write(response.content)
                return cache_file
            else:
                print(
                    f"[Foreca1MapAPI] Tile download error: {response.status_code}")
                return None
        except Exception as e:
            print(f"[Foreca1MapAPI] Tile download exception: {e}")
            return None

    def download_tile_grid_async(self, timestamp, callback):
        def download_thread():
            cx, cy = self.latlon_to_tile(
                self.center_lat, self.center_lon, self.zoom_level)
            offset_cols = self.grid_cols // 2
            offset_rows = self.grid_rows // 2

            tile_paths = []
            for dx in range(-offset_cols, offset_cols + 1):
                for dy in range(-offset_rows, offset_rows + 1):
                    tx = cx + dx
                    ty = cy + dy
                    path = self.api.get_tile(
                        self.layer_id,
                        timestamp,
                        self.zoom_level,
                        tx, ty,
                        self.unit_system
                    )

                    if path and exists(path):
                        try:
                            if DEBUG:
                                with Image.open(path) as img:
                                    # Debug only, if it fails skip
                                    print(
                                        f"[DEBUG] Tile zoom={self.zoom_level} ({tx},{ty}) size: {img.size}")
                            tile_paths.append(
                                (dx + offset_cols, dy + offset_rows, path))
                        except Exception as e:
                            print(
                                f"[Foreca1] Corrupted tile, skipped: {path} - {e}")
                            # Remove corrupted file to avoid future reuse
                            try:
                                remove(path)
                            except BaseException:
                                pass

            if len(tile_paths) > 0:
                merged = self.merge_tile_grid(tile_paths)
                if merged and callback:
                    callback(merged)
            else:
                if DEBUG:
                    print("[Foreca1] No valid tiles downloaded")
                from twisted.internet import reactor
                reactor.callFromThread(self._show_no_tiles_error)
                callback(None)

        Thread(target=download_thread).start()

    def check_credentials(self):
        """Check if credentials are configured"""
        return bool(self.user and self.password)

    def clear_cache(self, days_old=1):
        """Clear old cache files"""
        try:
            current_time = time.time()
            deleted_files = 0

            for filename in listdir(CACHE_BASE):
                filepath = join(CACHE_BASE, filename)

                # Skip token file and capabilities
                if filename in ["token.json", "capabilities.json"]:
                    continue

                if isfile(filepath):
                    # Check if file is older than X days
                    file_age = current_time - getmtime(filepath)
                    if file_age > (days_old * 86400):  # days to seconds
                        remove(filepath)
                        deleted_files += 1

            if deleted_files > 0:
                print(
                    f"[Foreca1MapAPI] Cleared {deleted_files} old cache files")

        except Exception as e:
            print(f"[Foreca1MapAPI] Error clearing cache: {e}")
